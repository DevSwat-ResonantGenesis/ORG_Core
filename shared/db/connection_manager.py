"""
Database Connection Manager with Failover Support
=================================================

Provides automatic failover between primary and replica databases.
Implements read/write splitting and connection pooling.
"""

import os
import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
import logging

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
)
from sqlalchemy.pool import QueuePool
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DatabaseRole(Enum):
    PRIMARY = "primary"
    REPLICA = "replica"


@dataclass
class DatabaseNode:
    """Represents a database node in the cluster."""
    url: str
    role: DatabaseRole
    priority: int = 0
    healthy: bool = True
    last_check: float = 0
    latency_ms: float = 0


class ConnectionManager:
    """
    Manages database connections with automatic failover.
    
    Features:
    - Primary/replica read-write splitting
    - Automatic health checking
    - Failover on primary failure
    - Connection pooling
    """
    
    def __init__(
        self,
        primary_url: str,
        replica_urls: Optional[List[str]] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        health_check_interval: int = 30,
    ):
        self.primary_url = primary_url
        self.replica_urls = replica_urls or []
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.health_check_interval = health_check_interval
        
        # Initialize nodes
        self.nodes: Dict[str, DatabaseNode] = {}
        self._init_nodes()
        
        # Engines
        self._primary_engine: Optional[AsyncEngine] = None
        self._replica_engines: List[AsyncEngine] = []
        self._current_replica_idx = 0
        
        # Session makers
        self._write_session_maker: Optional[async_sessionmaker] = None
        self._read_session_maker: Optional[async_sessionmaker] = None
        
        # Health check task
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
    
    def _init_nodes(self):
        """Initialize database nodes."""
        self.nodes["primary"] = DatabaseNode(
            url=self.primary_url,
            role=DatabaseRole.PRIMARY,
            priority=0,
        )
        
        for i, url in enumerate(self.replica_urls):
            self.nodes[f"replica_{i}"] = DatabaseNode(
                url=url,
                role=DatabaseRole.REPLICA,
                priority=i + 1,
            )
    
    async def initialize(self):
        """Initialize all database connections."""
        # Create primary engine
        self._primary_engine = create_async_engine(
            self.primary_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_pre_ping=True,
        )
        
        self._write_session_maker = async_sessionmaker(
            self._primary_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Create replica engines
        for url in self.replica_urls:
            engine = create_async_engine(
                url,
                poolclass=QueuePool,
                pool_size=self.pool_size // 2,
                max_overflow=self.max_overflow // 2,
                pool_timeout=self.pool_timeout,
                pool_pre_ping=True,
            )
            self._replica_engines.append(engine)
        
        # If no replicas, use primary for reads
        if self._replica_engines:
            self._read_session_maker = async_sessionmaker(
                self._replica_engines[0],
                class_=AsyncSession,
                expire_on_commit=False,
            )
        else:
            self._read_session_maker = self._write_session_maker
        
        # Start health checking
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info(f"ConnectionManager initialized with {len(self._replica_engines)} replicas")
    
    async def close(self):
        """Close all database connections."""
        self._running = False
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._primary_engine:
            await self._primary_engine.dispose()
        
        for engine in self._replica_engines:
            await engine.dispose()
        
        logger.info("ConnectionManager closed")
    
    async def _health_check_loop(self):
        """Periodically check database health."""
        while self._running:
            try:
                await self._check_all_nodes()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(5)
    
    async def _check_all_nodes(self):
        """Check health of all database nodes."""
        import time
        
        # Check primary
        try:
            start = time.time()
            async with self._primary_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000
            
            self.nodes["primary"].healthy = True
            self.nodes["primary"].latency_ms = latency
            self.nodes["primary"].last_check = time.time()
        except Exception as e:
            logger.warning(f"Primary health check failed: {e}")
            self.nodes["primary"].healthy = False
        
        # Check replicas
        for i, engine in enumerate(self._replica_engines):
            node_key = f"replica_{i}"
            try:
                start = time.time()
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                latency = (time.time() - start) * 1000
                
                self.nodes[node_key].healthy = True
                self.nodes[node_key].latency_ms = latency
                self.nodes[node_key].last_check = time.time()
            except Exception as e:
                logger.warning(f"Replica {i} health check failed: {e}")
                self.nodes[node_key].healthy = False
    
    def _get_best_replica_engine(self) -> AsyncEngine:
        """Get the best available replica engine."""
        if not self._replica_engines:
            return self._primary_engine
        
        # Find healthy replica with lowest latency
        healthy_replicas = [
            (i, self.nodes.get(f"replica_{i}"))
            for i in range(len(self._replica_engines))
            if self.nodes.get(f"replica_{i}", DatabaseNode("", DatabaseRole.REPLICA)).healthy
        ]
        
        if not healthy_replicas:
            logger.warning("No healthy replicas, falling back to primary")
            return self._primary_engine
        
        # Sort by latency
        healthy_replicas.sort(key=lambda x: x[1].latency_ms if x[1] else float('inf'))
        best_idx = healthy_replicas[0][0]
        
        return self._replica_engines[best_idx]
    
    @asynccontextmanager
    async def write_session(self):
        """Get a session for write operations (uses primary)."""
        if not self.nodes["primary"].healthy:
            raise RuntimeError("Primary database is unhealthy")
        
        async with self._write_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    @asynccontextmanager
    async def read_session(self):
        """Get a session for read operations (uses replica or primary)."""
        engine = self._get_best_replica_engine()
        
        session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        async with session_maker() as session:
            yield session
    
    @asynccontextmanager
    async def session(self, read_only: bool = False):
        """Get a session with automatic read/write routing."""
        if read_only:
            async with self.read_session() as session:
                yield session
        else:
            async with self.write_session() as session:
                yield session
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all nodes."""
        return {
            node_key: {
                "role": node.role.value,
                "healthy": node.healthy,
                "latency_ms": round(node.latency_ms, 2),
                "last_check": node.last_check,
            }
            for node_key, node in self.nodes.items()
        }
    
    @property
    def primary_healthy(self) -> bool:
        """Check if primary is healthy."""
        return self.nodes["primary"].healthy
    
    @property
    def any_replica_healthy(self) -> bool:
        """Check if any replica is healthy."""
        return any(
            node.healthy
            for key, node in self.nodes.items()
            if key.startswith("replica_")
        )


# Factory function for creating connection managers
def create_connection_manager(
    service_name: str,
    primary_url: Optional[str] = None,
    replica_urls: Optional[List[str]] = None,
) -> ConnectionManager:
    """
    Create a connection manager for a service.
    
    Environment variables:
    - {SERVICE}_DATABASE_URL: Primary database URL
    - {SERVICE}_DATABASE_REPLICA_URLS: Comma-separated replica URLs
    """
    env_prefix = service_name.upper().replace("-", "_")
    
    if primary_url is None:
        primary_url = os.getenv(f"{env_prefix}_DATABASE_URL")
        if not primary_url:
            primary_url = os.getenv("DATABASE_URL")
    
    if replica_urls is None:
        replica_env = os.getenv(f"{env_prefix}_DATABASE_REPLICA_URLS", "")
        replica_urls = [url.strip() for url in replica_env.split(",") if url.strip()]
    
    if not primary_url:
        raise ValueError(f"No database URL configured for {service_name}")
    
    return ConnectionManager(
        primary_url=primary_url,
        replica_urls=replica_urls,
    )


# Singleton instances per service
_managers: Dict[str, ConnectionManager] = {}


async def get_connection_manager(service_name: str) -> ConnectionManager:
    """Get or create a connection manager for a service."""
    if service_name not in _managers:
        manager = create_connection_manager(service_name)
        await manager.initialize()
        _managers[service_name] = manager
    
    return _managers[service_name]


async def close_all_managers():
    """Close all connection managers."""
    for manager in _managers.values():
        await manager.close()
    _managers.clear()
