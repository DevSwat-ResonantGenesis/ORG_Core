"""
CASCADE Control Plane - Data Models
Defines all data structures for dependency tracking, change impact analysis, and protection zones.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field
import uuid


class RiskLevel(str, Enum):
    """Risk levels for protected zones"""
    CRITICAL = "critical"  # Auth, Payment - requires explicit approval
    HIGH = "high"          # Memory, Logging - requires validation
    MEDIUM = "medium"      # Agents, Chat - requires impact analysis
    LOW = "low"            # UI, Docs - standard changes allowed


class ChangeType(str, Enum):
    """Types of code changes"""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    RENAME = "rename"
    MOVE = "move"


class NodeType(str, Enum):
    """Types of nodes in the dependency graph"""
    SERVICE = "service"
    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"
    ENDPOINT = "endpoint"
    DATABASE = "database"
    EXTERNAL = "external"
    CONFIG = "config"


class ConnectionType(str, Enum):
    """Types of connections between nodes"""
    IMPORT = "import"
    CALL = "call"
    INHERIT = "inherit"
    HTTP = "http"
    DATABASE = "database"
    WEBSOCKET = "websocket"
    CONFIG = "config"
    AUTH = "auth"


class ValidationStatus(str, Enum):
    """Status of change validation"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"


# ============== PROTECTED ZONES ==============

class ProtectedZone(BaseModel):
    """Defines a protected zone in the codebase"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    risk_level: RiskLevel
    patterns: List[str]  # File/path patterns that belong to this zone
    keywords: List[str]  # Keywords that indicate this zone
    dependencies: List[str] = []  # Other zones this depends on
    requires_approval: bool = True
    
    class Config:
        use_enum_values = True


# Default protected zones
DEFAULT_PROTECTED_ZONES = [
    ProtectedZone(
        name="authentication",
        description="Authentication and authorization systems",
        risk_level=RiskLevel.CRITICAL,
        patterns=[
            "*/auth_service/*",
            "*/auth.py",
            "*/auth_middleware.py",
            "*/security.py",
            "*/jwt*.py",
            "*/oauth*.py",
            "*/permissions.py"
        ],
        keywords=["jwt", "token", "auth", "login", "session", "password", "credential"],
        requires_approval=True
    ),
    ProtectedZone(
        name="payment",
        description="Payment and billing systems",
        risk_level=RiskLevel.CRITICAL,
        patterns=[
            "*/billing_service/*",
            "*/stripe*.py",
            "*/payment*.py",
            "*/subscription*.py"
        ],
        keywords=["stripe", "payment", "billing", "subscription", "invoice", "charge"],
        requires_approval=True
    ),
    ProtectedZone(
        name="gateway",
        description="API Gateway and routing",
        risk_level=RiskLevel.CRITICAL,
        patterns=[
            "*/gateway/*",
            "*/reverse_proxy.py",
            "*/rate_limit*.py"
        ],
        keywords=["gateway", "proxy", "route", "middleware"],
        requires_approval=True
    ),
    ProtectedZone(
        name="memory",
        description="Memory and Hash Sphere systems",
        risk_level=RiskLevel.HIGH,
        patterns=[
            "*/memory_service/*",
            "*/hash_sphere*.py",
            "*/resonance*.py",
            "*/embedding*.py"
        ],
        keywords=["memory", "hash_sphere", "embedding", "resonance", "vector"],
        requires_approval=True
    ),
    ProtectedZone(
        name="agents",
        description="Agent engine and autonomous systems",
        risk_level=RiskLevel.MEDIUM,
        patterns=[
            "*/agent_engine_service/*",
            "*/autonomous*.py",
            "*/agent*.py"
        ],
        keywords=["agent", "autonomous", "daemon", "spawn"],
        requires_approval=False
    ),
    ProtectedZone(
        name="chat",
        description="Chat and messaging systems",
        risk_level=RiskLevel.MEDIUM,
        patterns=[
            "*/chat_service/*",
            "*/resonant_chat*.py"
        ],
        keywords=["chat", "message", "conversation"],
        requires_approval=False
    ),
    ProtectedZone(
        name="database",
        description="Database schemas and migrations",
        risk_level=RiskLevel.HIGH,
        patterns=[
            "*/models.py",
            "*/migrations/*",
            "*/alembic/*",
            "*/*.sql"
        ],
        keywords=["migration", "schema", "table", "column", "index"],
        requires_approval=True
    ),
    ProtectedZone(
        name="blockchain",
        description="Blockchain and crypto systems",
        risk_level=RiskLevel.CRITICAL,
        patterns=[
            "*/blockchain_service/*",
            "*/crypto_service/*",
            "*/contracts/*",
            "*/web3*.py"
        ],
        keywords=["blockchain", "crypto", "wallet", "transaction", "contract", "web3"],
        requires_approval=True
    ),
    ProtectedZone(
        name="llm",
        description="LLM and AI model systems",
        risk_level=RiskLevel.HIGH,
        patterns=[
            "*/llm_service/*",
            "*/ml_service/*",
            "*/cognitive_service/*"
        ],
        keywords=["llm", "model", "inference", "prompt", "embedding", "openai", "anthropic"],
        requires_approval=True
    ),
    ProtectedZone(
        name="rara",
        description="RARA autonomous reasoning system",
        risk_level=RiskLevel.HIGH,
        patterns=[
            "*/rg_internal_invarients_sim/*",
            "*/rara*.py"
        ],
        keywords=["rara", "reasoning", "autonomous", "reflection"],
        requires_approval=True
    ),
    ProtectedZone(
        name="storage",
        description="File storage and object storage",
        risk_level=RiskLevel.MEDIUM,
        patterns=[
            "*/storage_service/*",
            "*/minio*.py",
            "*/s3*.py"
        ],
        keywords=["storage", "upload", "download", "bucket", "file"],
        requires_approval=False
    ),
    ProtectedZone(
        name="notifications",
        description="Notification and messaging systems",
        risk_level=RiskLevel.MEDIUM,
        patterns=[
            "*/notification_service/*",
            "*/email*.py",
            "*/sms*.py",
            "*/push*.py"
        ],
        keywords=["notification", "email", "sms", "push", "alert"],
        requires_approval=False
    ),
    ProtectedZone(
        name="workflow",
        description="Workflow and orchestration systems",
        risk_level=RiskLevel.MEDIUM,
        patterns=[
            "*/workflow_service/*",
            "*/celery*.py",
            "*/task*.py"
        ],
        keywords=["workflow", "task", "celery", "queue", "job"],
        requires_approval=False
    ),
    ProtectedZone(
        name="marketplace",
        description="Marketplace and commerce systems",
        risk_level=RiskLevel.HIGH,
        patterns=[
            "*/marketplace_service/*"
        ],
        keywords=["marketplace", "listing", "purchase", "order"],
        requires_approval=True
    ),
    ProtectedZone(
        name="user",
        description="User management and profiles",
        risk_level=RiskLevel.HIGH,
        patterns=[
            "*/user_service/*",
            "*/user_memory_service/*",
            "*/profile*.py"
        ],
        keywords=["user", "profile", "account", "preferences"],
        requires_approval=True
    ),
    ProtectedZone(
        name="shared",
        description="Shared libraries and utilities",
        risk_level=RiskLevel.HIGH,
        patterns=[
            "*/shared/*",
            "*/sdks/*",
            "*/common/*"
        ],
        keywords=["shared", "common", "utils", "helpers"],
        requires_approval=True
    ),
    ProtectedZone(
        name="governance",
        description="Governance and compliance systems",
        risk_level=RiskLevel.CRITICAL,
        patterns=[
            "*/governance/*",
            "*/compliance/*",
            "*/audit*.py"
        ],
        keywords=["governance", "compliance", "audit", "policy", "rule"],
        requires_approval=True
    ),
    ProtectedZone(
        name="ide",
        description="IDE and code execution systems",
        risk_level=RiskLevel.HIGH,
        patterns=[
            "*/ide_platform_service/*",
            "*/code_execution_service/*",
            "*/build_service/*"
        ],
        keywords=["ide", "execute", "compile", "build", "sandbox"],
        requires_approval=True
    )
]


# ============== DEPENDENCY GRAPH ==============

class DependencyNode(BaseModel):
    """A node in the dependency graph"""
    id: str
    name: str
    type: NodeType
    file_path: str
    service: str
    line_start: int = 0
    line_end: int = 0
    protected_zone: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    metadata: Dict[str, Any] = {}
    
    class Config:
        use_enum_values = True


class DependencyConnection(BaseModel):
    """A connection between nodes"""
    source_id: str
    target_id: str
    type: ConnectionType
    weight: float = 1.0  # Impact weight
    bidirectional: bool = False
    metadata: Dict[str, Any] = {}
    
    class Config:
        use_enum_values = True


class DependencyGraph(BaseModel):
    """Full dependency graph of the codebase"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    nodes: Dict[str, DependencyNode] = {}
    connections: List[DependencyConnection] = []
    services: List[str] = []
    protected_zones: List[ProtectedZone] = []
    
    def get_node(self, node_id: str) -> Optional[DependencyNode]:
        return self.nodes.get(node_id)
    
    def get_connections_from(self, node_id: str) -> List[DependencyConnection]:
        return [c for c in self.connections if c.source_id == node_id]
    
    def get_connections_to(self, node_id: str) -> List[DependencyConnection]:
        return [c for c in self.connections if c.target_id == node_id]


# ============== CHANGE TRACKING ==============

class CodeChange(BaseModel):
    """Represents a proposed or applied code change"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    change_type: ChangeType
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    description: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class ChangeImpact(BaseModel):
    """Analysis of a change's impact on the codebase"""
    change_id: str
    affected_nodes: List[str] = []  # Node IDs that will be affected
    affected_services: List[str] = []
    protected_zones_affected: List[str] = []
    risk_level: RiskLevel = RiskLevel.LOW
    impact_score: float = 0.0  # 0-100, higher = more impact
    cascade_depth: int = 0  # How many levels of dependencies affected
    warnings: List[str] = []
    blockers: List[str] = []  # Issues that prevent the change
    requires_approval: bool = False
    suggested_tests: List[str] = []
    rollback_complexity: str = "simple"  # simple, moderate, complex
    
    class Config:
        use_enum_values = True


class GhostChange(BaseModel):
    """A preview/simulation of a change before applying"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    changes: List[CodeChange] = []
    impact: Optional[ChangeImpact] = None
    validation_status: ValidationStatus = ValidationStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    applied_at: Optional[datetime] = None
    rollback_point: Optional[str] = None
    
    class Config:
        use_enum_values = True


class ChangeHistoryEntry(BaseModel):
    """Entry in the change history log"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ghost_id: str
    changes: List[CodeChange]
    impact: ChangeImpact
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    applied_by: str = "cascade"
    rollback_available: bool = True
    git_commit: Optional[str] = None
    
    class Config:
        use_enum_values = True


# ============== ISOLATION STRATEGY ==============

class IsolationLayer(BaseModel):
    """Defines an isolation layer in the fix hierarchy"""
    level: int
    name: str
    description: str
    services: List[str]
    can_modify_lower: bool = False  # Can this layer modify lower layers?
    requires_lower_stable: bool = True  # Does this require lower layers to be stable?


DEFAULT_ISOLATION_LAYERS = [
    IsolationLayer(
        level=0,
        name="Infrastructure",
        description="Docker, databases, networking, environment",
        services=["docker-compose", "nginx", "postgres", "redis", "minio"],
        can_modify_lower=False,
        requires_lower_stable=False
    ),
    IsolationLayer(
        level=1,
        name="Authentication",
        description="JWT, sessions, permissions, security",
        services=["auth_service", "gateway"],
        can_modify_lower=False,
        requires_lower_stable=True
    ),
    IsolationLayer(
        level=2,
        name="Core Services",
        description="Gateway routing, service discovery",
        services=["gateway", "reverse_proxy"],
        can_modify_lower=False,
        requires_lower_stable=True
    ),
    IsolationLayer(
        level=3,
        name="Data Layer",
        description="Memory, storage, embeddings, databases",
        services=["memory_service", "cognitive_service"],
        can_modify_lower=False,
        requires_lower_stable=True
    ),
    IsolationLayer(
        level=4,
        name="Business Logic",
        description="Agents, chat, billing, RARA",
        services=["agent_engine_service", "chat_service", "billing_service", "rg_internal_invarients_sim"],
        can_modify_lower=False,
        requires_lower_stable=True
    ),
    IsolationLayer(
        level=5,
        name="UI/Frontend",
        description="Components, pages, styles",
        services=["frontend"],
        can_modify_lower=False,
        requires_lower_stable=True
    )
]


# ============== AI MONITORING AGENTS ==============

class MonitoringAgentStatus(str, Enum):
    """Status of monitoring agents"""
    ACTIVE = "active"
    PAUSED = "paused"
    ALERT = "alert"
    ERROR = "error"


class MonitoringAgent(BaseModel):
    """An AI agent that monitors for dangerous changes"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    protected_zones: List[str]  # Zones this agent monitors
    status: MonitoringAgentStatus = MonitoringAgentStatus.ACTIVE
    last_check: Optional[datetime] = None
    alerts: List[str] = []
    
    class Config:
        use_enum_values = True


DEFAULT_MONITORING_AGENTS = [
    MonitoringAgent(
        name="AuthGuard",
        description="Monitors authentication and authorization changes",
        protected_zones=["authentication", "gateway"]
    ),
    MonitoringAgent(
        name="PaymentGuard",
        description="Monitors payment and billing system changes",
        protected_zones=["payment", "marketplace"]
    ),
    MonitoringAgent(
        name="MemoryGuard",
        description="Monitors memory and Hash Sphere system changes",
        protected_zones=["memory", "llm"]
    ),
    MonitoringAgent(
        name="SchemaGuard",
        description="Monitors database schema and migration changes",
        protected_zones=["database"]
    ),
    MonitoringAgent(
        name="BlockchainGuard",
        description="Monitors blockchain and crypto system changes",
        protected_zones=["blockchain"]
    ),
    MonitoringAgent(
        name="RARAGuard",
        description="Monitors RARA autonomous reasoning system changes",
        protected_zones=["rara", "agents"]
    ),
    MonitoringAgent(
        name="SharedGuard",
        description="Monitors shared libraries that affect all services",
        protected_zones=["shared", "governance"]
    ),
    MonitoringAgent(
        name="UserGuard",
        description="Monitors user data and profile changes",
        protected_zones=["user"]
    ),
    MonitoringAgent(
        name="IDEGuard",
        description="Monitors IDE and code execution sandbox changes",
        protected_zones=["ide"]
    )
]


# ============== API REQUEST/RESPONSE MODELS ==============

class AnalyzeImpactRequest(BaseModel):
    """Request to analyze change impact"""
    file_path: str
    change_type: ChangeType
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    description: str = ""


class CreateGhostRequest(BaseModel):
    """Request to create a ghost change"""
    changes: List[CodeChange]
    description: str = ""


class ValidateChangeRequest(BaseModel):
    """Request to validate a change"""
    ghost_id: str


class ApproveChangeRequest(BaseModel):
    """Request to approve a protected zone change"""
    ghost_id: str
    approver: str = "user"
    reason: str = ""


class RollbackRequest(BaseModel):
    """Request to rollback to a checkpoint"""
    history_id: str
    reason: str = ""
