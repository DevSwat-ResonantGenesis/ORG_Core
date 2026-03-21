"""
Secret Management Client
========================

Provides secure secret retrieval from HashiCorp Vault or AWS Secrets Manager.
Falls back to environment variables for development.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)


class SecretBackend(Enum):
    """Supported secret backends."""
    VAULT = "vault"
    AWS = "aws"
    ENV = "env"  # Fallback to environment variables


@dataclass
class Secret:
    """Represents a secret value."""
    key: str
    value: str
    version: Optional[str] = None
    expires_at: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class SecretProvider(ABC):
    """Abstract base class for secret providers."""
    
    @abstractmethod
    async def get_secret(self, key: str) -> Optional[Secret]:
        """Retrieve a secret by key."""
        pass
    
    @abstractmethod
    async def list_secrets(self, path: str) -> List[str]:
        """List secrets at a path."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy."""
        pass


class EnvSecretProvider(SecretProvider):
    """Environment variable based secret provider (development fallback)."""
    
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
    
    async def get_secret(self, key: str) -> Optional[Secret]:
        """Get secret from environment variable."""
        env_key = f"{self.prefix}{key}".upper().replace("-", "_").replace("/", "_")
        value = os.getenv(env_key)
        
        if value is None:
            # Try without prefix
            value = os.getenv(key.upper().replace("-", "_").replace("/", "_"))
        
        if value is None:
            return None
        
        return Secret(key=key, value=value)
    
    async def list_secrets(self, path: str) -> List[str]:
        """List environment variables matching prefix."""
        prefix = f"{self.prefix}{path}".upper().replace("-", "_").replace("/", "_")
        return [
            key for key in os.environ.keys()
            if key.startswith(prefix)
        ]
    
    async def health_check(self) -> bool:
        """Always healthy for env provider."""
        return True


class VaultSecretProvider(SecretProvider):
    """HashiCorp Vault secret provider."""
    
    def __init__(
        self,
        vault_addr: str,
        vault_token: Optional[str] = None,
        vault_role: Optional[str] = None,
        mount_point: str = "secret",
    ):
        self.vault_addr = vault_addr.rstrip("/")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
        self.vault_role = vault_role
        self.mount_point = mount_point
        self._client = None
        self._initialized = False
    
    async def _ensure_client(self):
        """Ensure Vault client is initialized."""
        if self._initialized:
            return
        
        try:
            import hvac
            self._client = hvac.Client(
                url=self.vault_addr,
                token=self.vault_token,
            )
            
            # If using Kubernetes auth
            if self.vault_role and not self.vault_token:
                jwt_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
                if os.path.exists(jwt_path):
                    with open(jwt_path) as f:
                        jwt = f.read()
                    self._client.auth.kubernetes.login(
                        role=self.vault_role,
                        jwt=jwt,
                    )
            
            self._initialized = True
            logger.info("Vault client initialized")
            
        except ImportError:
            logger.error("hvac package not installed. Install with: pip install hvac")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Vault client: {e}")
            raise
    
    async def get_secret(self, key: str) -> Optional[Secret]:
        """Get secret from Vault."""
        await self._ensure_client()
        
        try:
            # Try KV v2 first
            response = self._client.secrets.kv.v2.read_secret_version(
                path=key,
                mount_point=self.mount_point,
            )
            
            data = response.get("data", {}).get("data", {})
            metadata = response.get("data", {}).get("metadata", {})
            
            # If single value, return it directly
            if len(data) == 1:
                value = list(data.values())[0]
            else:
                value = json.dumps(data)
            
            return Secret(
                key=key,
                value=value,
                version=str(metadata.get("version", "")),
                metadata=metadata,
            )
            
        except Exception as e:
            logger.warning(f"Failed to get secret {key} from Vault: {e}")
            return None
    
    async def list_secrets(self, path: str) -> List[str]:
        """List secrets at path in Vault."""
        await self._ensure_client()
        
        try:
            response = self._client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=self.mount_point,
            )
            return response.get("data", {}).get("keys", [])
        except Exception as e:
            logger.warning(f"Failed to list secrets at {path}: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check Vault health."""
        await self._ensure_client()
        
        try:
            return self._client.sys.is_initialized() and not self._client.sys.is_sealed()
        except Exception:
            return False


class AWSSecretProvider(SecretProvider):
    """AWS Secrets Manager provider."""
    
    def __init__(
        self,
        region_name: Optional[str] = None,
        prefix: str = "",
    ):
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.prefix = prefix
        self._client = None
        self._initialized = False
    
    async def _ensure_client(self):
        """Ensure AWS client is initialized."""
        if self._initialized:
            return
        
        try:
            import boto3
            self._client = boto3.client(
                "secretsmanager",
                region_name=self.region_name,
            )
            self._initialized = True
            logger.info("AWS Secrets Manager client initialized")
            
        except ImportError:
            logger.error("boto3 package not installed. Install with: pip install boto3")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS client: {e}")
            raise
    
    async def get_secret(self, key: str) -> Optional[Secret]:
        """Get secret from AWS Secrets Manager."""
        await self._ensure_client()
        
        secret_name = f"{self.prefix}{key}" if self.prefix else key
        
        try:
            response = self._client.get_secret_value(SecretId=secret_name)
            
            # Handle both string and binary secrets
            if "SecretString" in response:
                value = response["SecretString"]
            else:
                import base64
                value = base64.b64decode(response["SecretBinary"]).decode()
            
            return Secret(
                key=key,
                value=value,
                version=response.get("VersionId"),
                metadata={
                    "arn": response.get("ARN"),
                    "name": response.get("Name"),
                },
            )
            
        except Exception as e:
            logger.warning(f"Failed to get secret {secret_name} from AWS: {e}")
            return None
    
    async def list_secrets(self, path: str) -> List[str]:
        """List secrets in AWS Secrets Manager."""
        await self._ensure_client()
        
        try:
            secrets = []
            paginator = self._client.get_paginator("list_secrets")
            
            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    name = secret.get("Name", "")
                    if name.startswith(f"{self.prefix}{path}"):
                        secrets.append(name.replace(self.prefix, "", 1))
            
            return secrets
            
        except Exception as e:
            logger.warning(f"Failed to list secrets: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check AWS connection."""
        await self._ensure_client()
        
        try:
            self._client.list_secrets(MaxResults=1)
            return True
        except Exception:
            return False


class SecretManager:
    """
    Unified secret manager with caching and fallback.
    
    Usage:
        secrets = SecretManager()
        await secrets.initialize()
        
        api_key = await secrets.get("openai/api-key")
        db_password = await secrets.get("database/password")
    """
    
    def __init__(
        self,
        backend: Optional[SecretBackend] = None,
        cache_ttl: int = 300,  # 5 minutes
        fallback_to_env: bool = True,
    ):
        self.backend = backend or self._detect_backend()
        self.cache_ttl = cache_ttl
        self.fallback_to_env = fallback_to_env
        
        self._provider: Optional[SecretProvider] = None
        self._env_provider = EnvSecretProvider()
        self._cache: Dict[str, tuple] = {}  # key -> (secret, timestamp)
        self._initialized = False
    
    def _detect_backend(self) -> SecretBackend:
        """Auto-detect the secret backend."""
        if os.getenv("VAULT_ADDR"):
            return SecretBackend.VAULT
        elif os.getenv("AWS_SECRET_ACCESS_KEY") or os.path.exists("/var/run/secrets/eks"):
            return SecretBackend.AWS
        else:
            return SecretBackend.ENV
    
    async def initialize(self):
        """Initialize the secret provider."""
        if self._initialized:
            return
        
        if self.backend == SecretBackend.VAULT:
            self._provider = VaultSecretProvider(
                vault_addr=os.getenv("VAULT_ADDR", "http://vault:8200"),
                vault_token=os.getenv("VAULT_TOKEN"),
                vault_role=os.getenv("VAULT_ROLE"),
            )
        elif self.backend == SecretBackend.AWS:
            self._provider = AWSSecretProvider(
                region_name=os.getenv("AWS_REGION"),
                prefix=os.getenv("SECRET_PREFIX", "resonantgenesis/"),
            )
        else:
            self._provider = self._env_provider
        
        self._initialized = True
        logger.info(f"SecretManager initialized with backend: {self.backend.value}")
    
    async def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value.
        
        Args:
            key: Secret key/path
            default: Default value if not found
        
        Returns:
            Secret value or default
        """
        if not self._initialized:
            await self.initialize()
        
        # Check cache
        import time
        if key in self._cache:
            secret, timestamp = self._cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return secret.value
        
        # Try primary provider
        secret = await self._provider.get_secret(key)
        
        # Fallback to env if configured
        if secret is None and self.fallback_to_env and self._provider != self._env_provider:
            secret = await self._env_provider.get_secret(key)
        
        if secret is None:
            return default
        
        # Cache the result
        self._cache[key] = (secret, time.time())
        
        return secret.value
    
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a JSON secret."""
        value = await self.get(key)
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"value": value}
    
    async def require(self, key: str) -> str:
        """Get a required secret (raises if not found)."""
        value = await self.get(key)
        if value is None:
            raise ValueError(f"Required secret not found: {key}")
        return value
    
    def clear_cache(self):
        """Clear the secret cache."""
        self._cache.clear()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check secret manager health."""
        if not self._initialized:
            await self.initialize()
        
        return {
            "backend": self.backend.value,
            "healthy": await self._provider.health_check(),
            "cache_size": len(self._cache),
        }


# Global instance
_secret_manager: Optional[SecretManager] = None


async def get_secret_manager() -> SecretManager:
    """Get the global secret manager instance."""
    global _secret_manager
    
    if _secret_manager is None:
        _secret_manager = SecretManager()
        await _secret_manager.initialize()
    
    return _secret_manager


async def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Convenience function to get a secret."""
    manager = await get_secret_manager()
    return await manager.get(key, default)


async def require_secret(key: str) -> str:
    """Convenience function to get a required secret."""
    manager = await get_secret_manager()
    return await manager.require(key)
