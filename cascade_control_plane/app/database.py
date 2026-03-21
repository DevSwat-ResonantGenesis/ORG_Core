"""
CASCADE Control Plane - Database Layer
Persistent storage for analysis results, change history, and rollback points
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import QueuePool
import enum

# Database URL from environment or default
DATABASE_URL = os.getenv(
    "CASCADE_DATABASE_URL",
    "postgresql://cascade:cascade_secret@localhost:5433/cascade_db"
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============== ENUMS ==============

class RiskLevelEnum(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeTypeEnum(str, enum.Enum):
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"
    REFACTOR = "refactor"


class ValidationStatusEnum(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


# ============== DATABASE MODELS ==============

class AnalysisResult(Base):
    """Stores unified analysis results"""
    __tablename__ = "analysis_results"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    root_path = Column(String, nullable=False)
    
    # Stats
    total_services = Column(Integer, default=0)
    total_nodes = Column(Integer, default=0)
    total_connections = Column(Integer, default=0)
    total_endpoints = Column(Integer, default=0)
    total_functions = Column(Integer, default=0)
    total_classes = Column(Integer, default=0)
    total_files = Column(Integer, default=0)
    broken_connections = Column(Integer, default=0)
    dead_code_count = Column(Integer, default=0)
    circular_dependencies = Column(Integer, default=0)
    health_score = Column(Integer, default=100)
    
    # JSON data
    services = Column(JSON, default=list)
    protected_zones = Column(JSON, default=list)
    pipelines = Column(JSON, default=dict)
    recommendations = Column(JSON, default=list)
    
    # Full analysis data (large JSON)
    nodes_data = Column(JSON, default=dict)
    connections_data = Column(JSON, default=list)
    broken_data = Column(JSON, default=list)
    dead_code_data = Column(JSON, default=list)
    circular_data = Column(JSON, default=list)


class ServiceInfo(Base):
    """Stores information about each service"""
    __tablename__ = "services"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    analysis_id = Column(String, ForeignKey("analysis_results.id"))
    
    # Stats
    total_nodes = Column(Integer, default=0)
    total_connections = Column(Integer, default=0)
    total_endpoints = Column(Integer, default=0)
    total_functions = Column(Integer, default=0)
    total_classes = Column(Integer, default=0)
    total_files = Column(Integer, default=0)
    
    # Protection
    protected_zones = Column(JSON, default=list)
    risk_level = Column(String, default="low")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProtectedZoneDB(Base):
    """Stores protected zone configurations"""
    __tablename__ = "protected_zones"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text)
    risk_level = Column(String, default="medium")
    patterns = Column(JSON, default=list)
    keywords = Column(JSON, default=list)
    requires_approval = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MonitoringAgentDB(Base):
    """Stores AI monitoring agent configurations"""
    __tablename__ = "monitoring_agents"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text)
    protected_zones = Column(JSON, default=list)
    status = Column(String, default="active")
    last_check = Column(DateTime)
    alerts_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChangeHistory(Base):
    """Stores history of all changes analyzed"""
    __tablename__ = "change_history"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Change details
    file_path = Column(String, nullable=False, index=True)
    change_type = Column(String, nullable=False)
    description = Column(Text)
    old_content = Column(Text)
    new_content = Column(Text)
    line_start = Column(Integer, default=0)
    line_end = Column(Integer, default=0)
    
    # Impact analysis
    risk_level = Column(String, default="low")
    impact_score = Column(Float, default=0.0)
    cascade_depth = Column(Integer, default=0)
    affected_services = Column(JSON, default=list)
    affected_files = Column(JSON, default=list)
    warnings = Column(JSON, default=list)
    blockers = Column(JSON, default=list)
    suggested_tests = Column(JSON, default=list)
    
    # Status
    validation_status = Column(String, default="pending")
    applied = Column(Boolean, default=False)
    applied_at = Column(DateTime)
    applied_by = Column(String)
    rollback_available = Column(Boolean, default=True)
    
    # Relationships
    snapshot_id = Column(String, ForeignKey("snapshots.id"))


class GhostChangeDB(Base):
    """Stores ghost (simulated) changes"""
    __tablename__ = "ghost_changes"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    description = Column(Text)
    changes = Column(JSON, default=list)  # List of changes
    impact = Column(JSON, default=dict)   # Combined impact
    
    # Status
    status = Column(String, default="pending")  # pending, applied, rejected, expired
    applied_at = Column(DateTime)
    expires_at = Column(DateTime)


class Snapshot(Base):
    """Stores state snapshots for rollback"""
    __tablename__ = "snapshots"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    description = Column(Text)
    trigger = Column(String)  # manual, auto, pre-change
    
    # Snapshot data
    files_snapshot = Column(JSON, default=dict)  # file_path -> content hash
    analysis_id = Column(String, ForeignKey("analysis_results.id"))
    
    # Status
    is_valid = Column(Boolean, default=True)
    restored_at = Column(DateTime)
    restored_by = Column(String)


class Alert(Base):
    """Stores alerts from monitoring agents"""
    __tablename__ = "alerts"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    agent_name = Column(String, nullable=False, index=True)
    level = Column(String, nullable=False)  # info, warning, emergency
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    
    # Related change
    change_id = Column(String, ForeignKey("change_history.id"))
    
    # Status
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)


class AuditLog(Base):
    """Stores audit trail of all CASCADE operations"""
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    action = Column(String, nullable=False, index=True)  # analyze, impact_check, apply, rollback, etc.
    actor = Column(String, default="system")  # user or system
    target = Column(String)  # file path or resource
    details = Column(JSON, default=dict)
    result = Column(String)  # success, failure, blocked
    error_message = Column(Text)


# ============== DATABASE FUNCTIONS ==============

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all database tables (use with caution)"""
    Base.metadata.drop_all(bind=engine)


# ============== REPOSITORY CLASSES ==============

class AnalysisRepository:
    """Repository for analysis results"""
    
    def __init__(self, db):
        self.db = db
    
    def save(self, result: Dict[str, Any]) -> AnalysisResult:
        """Save analysis result"""
        analysis = AnalysisResult(
            id=result.get("id"),
            root_path=result.get("root_path", ""),
            total_services=len(result.get("services", [])),
            total_nodes=result.get("total_nodes", 0),
            total_connections=result.get("total_connections", 0),
            total_endpoints=result.get("total_endpoints", 0),
            total_functions=result.get("total_functions", 0),
            total_classes=result.get("total_classes", 0),
            total_files=result.get("total_files", 0),
            broken_connections=len(result.get("broken_connections", [])),
            dead_code_count=len(result.get("dead_code", [])),
            circular_dependencies=len(result.get("circular_dependencies", [])),
            health_score=result.get("health_score", 100),
            services=result.get("services", []),
            protected_zones=[z.get("name") if isinstance(z, dict) else z for z in result.get("protected_zones", [])],
            pipelines=list(result.get("pipelines", {}).keys()),
            recommendations=result.get("recommendations", []),
            nodes_data=result.get("nodes", {}),
            connections_data=result.get("connections", []),
            broken_data=result.get("broken_connections", []),
            dead_code_data=result.get("dead_code", []),
            circular_data=result.get("circular_dependencies", [])
        )
        self.db.merge(analysis)
        self.db.commit()
        return analysis
    
    def get_latest(self) -> Optional[AnalysisResult]:
        """Get the most recent analysis"""
        return self.db.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).first()
    
    def get_by_id(self, analysis_id: str) -> Optional[AnalysisResult]:
        """Get analysis by ID"""
        return self.db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    
    def get_all(self, limit: int = 10) -> List[AnalysisResult]:
        """Get recent analyses"""
        return self.db.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).limit(limit).all()


class ChangeHistoryRepository:
    """Repository for change history"""
    
    def __init__(self, db):
        self.db = db
    
    def save(self, change: Dict[str, Any]) -> ChangeHistory:
        """Save change to history"""
        history = ChangeHistory(
            id=change.get("id"),
            file_path=change.get("file_path"),
            change_type=change.get("change_type"),
            description=change.get("description", ""),
            old_content=change.get("old_content"),
            new_content=change.get("new_content"),
            line_start=change.get("line_start", 0),
            line_end=change.get("line_end", 0),
            risk_level=change.get("risk_level", "low"),
            impact_score=change.get("impact_score", 0.0),
            cascade_depth=change.get("cascade_depth", 0),
            affected_services=change.get("affected_services", []),
            affected_files=change.get("affected_files", []),
            warnings=change.get("warnings", []),
            blockers=change.get("blockers", []),
            suggested_tests=change.get("suggested_tests", []),
            validation_status=change.get("validation_status", "pending")
        )
        self.db.merge(history)
        self.db.commit()
        return history
    
    def get_by_id(self, change_id: str) -> Optional[ChangeHistory]:
        """Get change by ID"""
        return self.db.query(ChangeHistory).filter(ChangeHistory.id == change_id).first()
    
    def get_by_file(self, file_path: str, limit: int = 10) -> List[ChangeHistory]:
        """Get changes for a specific file"""
        return self.db.query(ChangeHistory).filter(
            ChangeHistory.file_path == file_path
        ).order_by(ChangeHistory.created_at.desc()).limit(limit).all()
    
    def get_recent(self, limit: int = 50) -> List[ChangeHistory]:
        """Get recent changes"""
        return self.db.query(ChangeHistory).order_by(ChangeHistory.created_at.desc()).limit(limit).all()
    
    def mark_applied(self, change_id: str, applied_by: str = "cascade") -> Optional[ChangeHistory]:
        """Mark change as applied"""
        change = self.get_by_id(change_id)
        if change:
            change.applied = True
            change.applied_at = datetime.utcnow()
            change.applied_by = applied_by
            self.db.commit()
        return change


class SnapshotRepository:
    """Repository for snapshots"""
    
    def __init__(self, db):
        self.db = db
    
    def create(self, description: str, trigger: str, files: Dict[str, str], analysis_id: str = None) -> Snapshot:
        """Create a new snapshot"""
        import uuid
        snapshot = Snapshot(
            id=str(uuid.uuid4()),
            description=description,
            trigger=trigger,
            files_snapshot=files,
            analysis_id=analysis_id
        )
        self.db.add(snapshot)
        self.db.commit()
        return snapshot
    
    def get_latest(self) -> Optional[Snapshot]:
        """Get the most recent valid snapshot"""
        return self.db.query(Snapshot).filter(
            Snapshot.is_valid == True
        ).order_by(Snapshot.created_at.desc()).first()
    
    def get_by_id(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get snapshot by ID"""
        return self.db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    
    def invalidate(self, snapshot_id: str) -> Optional[Snapshot]:
        """Invalidate a snapshot"""
        snapshot = self.get_by_id(snapshot_id)
        if snapshot:
            snapshot.is_valid = False
            self.db.commit()
        return snapshot


class AlertRepository:
    """Repository for alerts"""
    
    def __init__(self, db):
        self.db = db
    
    def create(self, agent_name: str, level: str, message: str, details: Dict = None, change_id: str = None) -> Alert:
        """Create a new alert"""
        import uuid
        alert = Alert(
            id=str(uuid.uuid4()),
            agent_name=agent_name,
            level=level,
            message=message,
            details=details or {},
            change_id=change_id
        )
        self.db.add(alert)
        self.db.commit()
        return alert
    
    def get_unacknowledged(self) -> List[Alert]:
        """Get all unacknowledged alerts"""
        return self.db.query(Alert).filter(Alert.acknowledged == False).order_by(Alert.created_at.desc()).all()
    
    def get_by_level(self, level: str) -> List[Alert]:
        """Get alerts by level"""
        return self.db.query(Alert).filter(Alert.level == level).order_by(Alert.created_at.desc()).all()
    
    def acknowledge(self, alert_id: str, acknowledged_by: str = "user") -> Optional[Alert]:
        """Acknowledge an alert"""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if alert:
            alert.acknowledged = True
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            self.db.commit()
        return alert


class AuditLogRepository:
    """Repository for audit logs"""
    
    def __init__(self, db):
        self.db = db
    
    def log(self, action: str, actor: str = "system", target: str = None, details: Dict = None, result: str = "success", error: str = None) -> AuditLog:
        """Create an audit log entry"""
        import uuid
        log = AuditLog(
            id=str(uuid.uuid4()),
            action=action,
            actor=actor,
            target=target,
            details=details or {},
            result=result,
            error_message=error
        )
        self.db.add(log)
        self.db.commit()
        return log
    
    def get_recent(self, limit: int = 100) -> List[AuditLog]:
        """Get recent audit logs"""
        return self.db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    def get_by_action(self, action: str, limit: int = 50) -> List[AuditLog]:
        """Get logs by action type"""
        return self.db.query(AuditLog).filter(AuditLog.action == action).order_by(AuditLog.created_at.desc()).limit(limit).all()
