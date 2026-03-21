"""
CASCADE Control Plane - Main FastAPI Application
Intelligent Code Navigation, Execution, and Protection System
"""

import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .models import (
    CodeChange, ChangeImpact, GhostChange, ChangeHistoryEntry,
    DependencyGraph, ProtectedZone, IsolationLayer,
    AnalyzeImpactRequest, CreateGhostRequest, ValidateChangeRequest,
    ApproveChangeRequest, RollbackRequest, RiskLevel, ValidationStatus,
    DEFAULT_PROTECTED_ZONES, DEFAULT_ISOLATION_LAYERS
)
from .dependency_engine import DependencyEngine
from .impact_analyzer import ImpactAnalyzer, MultiChangeAnalyzer
from .state_manager import StateManager
from .monitoring_agents import MonitoringAgentRunner, IsolationStrategyEnforcer, Alert
from .unified_analyzer import UnifiedAnalyzer, UnifiedAnalysisResult
from .database import (
    init_db, get_db, SessionLocal,
    AnalysisRepository, ChangeHistoryRepository, SnapshotRepository,
    AlertRepository, AuditLogRepository
)
from .enforcement import (
    EffectBoundary, classify_file, enforce_changes,
    EnforcementResult, FileClassification, EFFECT_BOUNDARIES
)
from .self_healing_integration import self_healing_integration, SelfHealingEvent
from .websocket_endpoints import (
    websocket_monitoring_endpoint, websocket_self_healing_endpoint,
    websocket_code_analysis_endpoint, broadcast_monitoring_alert,
    broadcast_self_healing_event, broadcast_code_analysis_update
)


# Global instances
dependency_engine = DependencyEngine()
state_manager = StateManager()
monitoring_runner = MonitoringAgentRunner()
isolation_enforcer = IsolationStrategyEnforcer()
unified_analyzer = UnifiedAnalyzer()
impact_analyzer: Optional[ImpactAnalyzer] = None
multi_analyzer: Optional[MultiChangeAnalyzer] = None

# Current analysis
current_graph: Optional[DependencyGraph] = None
unified_result: Optional[UnifiedAnalysisResult] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global impact_analyzer, multi_analyzer
    
    # Initialize database
    try:
        init_db()
        print("CASCADE database initialized successfully")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print("CASCADE will run without persistent storage")
    
    # Initialize analyzers
    impact_analyzer = ImpactAnalyzer(dependency_engine)
    multi_analyzer = MultiChangeAnalyzer(impact_analyzer)
    
    # Register alert callback
    monitoring_runner.register_alert_callback(lambda alert: print(f"🚨 ALERT: {alert.message}"))
    
    yield
    
    # Cleanup
    pass


app = FastAPI(
    title="CASCADE Control Plane",
    description="Intelligent Code Navigation, Execution, and Protection System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== HEALTH & INFO ==============

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "cascade_control_plane", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/info")
async def get_info():
    """Get service information"""
    return {
        "name": "CASCADE Control Plane",
        "version": "1.0.0",
        "description": "Intelligent Code Navigation, Execution, and Protection System",
        "features": [
            "Dependency Graph Analysis",
            "Change Impact Analysis",
            "Protected Zone Monitoring",
            "Ghost Changes (Preview)",
            "Rollback Capability",
            "AI Monitoring Agents",
            "Isolation Strategy Enforcement"
        ],
        "graph_loaded": current_graph is not None,
        "total_nodes": len(current_graph.nodes) if current_graph else 0,
        "total_services": len(current_graph.services) if current_graph else 0,
        "active_alerts": len(await monitoring_runner.get_active_alerts())
    }


# ============== DEPENDENCY GRAPH ==============

class AnalyzeRequest(BaseModel):
    path: str


@app.post("/api/analyze")
async def analyze_codebase(request: AnalyzeRequest):
    """Analyze a codebase and build the dependency graph"""
    global current_graph
    
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail=f"Path not found: {request.path}")
    
    try:
        current_graph = await dependency_engine.build_graph(request.path)
        
        return {
            "id": current_graph.id,
            "services": current_graph.services,
            "total_nodes": len(current_graph.nodes),
            "total_connections": len(current_graph.connections),
            "protected_zones": [z.name for z in current_graph.protected_zones],
            "created_at": current_graph.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph")
async def get_graph():
    """Get the current dependency graph"""
    if not current_graph:
        raise HTTPException(status_code=404, detail="No graph loaded. Call /api/analyze first.")
    
    return {
        "id": current_graph.id,
        "services": current_graph.services,
        "nodes": [n.dict() for n in current_graph.nodes.values()],
        "connections": [c.dict() for c in current_graph.connections],
        "protected_zones": [z.dict() for z in current_graph.protected_zones]
    }


# ============== UNIFIED ANALYSIS (Combined Code Visualizer + CASCADE) ==============

@app.post("/api/unified/analyze")
async def unified_analyze(request: AnalyzeRequest):
    """Run unified analysis combining Code Visualizer + CASCADE features"""
    global unified_result, current_graph
    
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail=f"Path not found: {request.path}")
    
    try:
        # Run unified analysis
        unified_result = unified_analyzer.analyze(request.path)
        
        # Also build the CASCADE graph for impact analysis
        current_graph = await dependency_engine.build_graph(request.path)
        
        return {
            "id": unified_result.id,
            "services": unified_result.services,
            "stats": {
                "total_nodes": unified_result.total_nodes,
                "total_connections": unified_result.total_connections,
                "total_endpoints": unified_result.total_endpoints,
                "total_functions": unified_result.total_functions,
                "total_classes": unified_result.total_classes,
                "total_files": unified_result.total_files,
                "total_services": len(unified_result.services),
                "broken_connections": len(unified_result.broken_connections),
                "dead_code_count": len(unified_result.dead_code),
                "circular_dependencies": len(unified_result.circular_dependencies),
                "protected_zones": len(unified_result.protected_zones),
                "pipelines": len(unified_result.pipelines)
            },
            "protected_zones": [z.name for z in unified_result.protected_zones],
            "pipelines": list(unified_result.pipelines.keys()),
            "created_at": unified_result.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unified analysis failed: {str(e)}")


@app.get("/api/unified/full")
async def get_unified_full():
    """Get full unified analysis result"""
    if not unified_result:
        raise HTTPException(status_code=404, detail="No unified analysis. Call /api/unified/analyze first.")
    
    return unified_result.to_dict()


@app.get("/api/unified/broken")
async def get_broken_connections():
    """Get all broken connections"""
    if not unified_result:
        raise HTTPException(status_code=404, detail="No unified analysis. Call /api/unified/analyze first.")
    
    return {
        "count": len(unified_result.broken_connections),
        "broken_connections": [c.to_dict() for c in unified_result.broken_connections]
    }


@app.get("/api/unified/dead-code")
async def get_dead_code():
    """Get all detected dead code"""
    if not unified_result:
        raise HTTPException(status_code=404, detail="No unified analysis. Call /api/unified/analyze first.")
    
    return {
        "count": len(unified_result.dead_code),
        "dead_code": [n.to_dict() for n in unified_result.dead_code]
    }


@app.get("/api/unified/circular")
async def get_circular_dependencies():
    """Get all circular dependencies"""
    if not unified_result:
        raise HTTPException(status_code=404, detail="No unified analysis. Call /api/unified/analyze first.")
    
    return {
        "count": len(unified_result.circular_dependencies),
        "circular_dependencies": unified_result.circular_dependencies
    }


@app.get("/api/unified/pipelines")
async def get_pipelines():
    """Get all detected pipelines"""
    if not unified_result:
        raise HTTPException(status_code=404, detail="No unified analysis. Call /api/unified/analyze first.")
    
    return {
        "count": len(unified_result.pipelines),
        "pipelines": {k: v.to_dict() for k, v in unified_result.pipelines.items()}
    }


@app.get("/api/unified/endpoints")
async def get_endpoints():
    """Get all API endpoints"""
    if not unified_result:
        raise HTTPException(status_code=404, detail="No unified analysis. Call /api/unified/analyze first.")
    
    endpoints = [n.to_dict() for n in unified_result.nodes.values() if n.is_endpoint]
    
    return {
        "count": len(endpoints),
        "endpoints": endpoints
    }


@app.get("/api/unified/service/{service_name}")
async def get_service_details(service_name: str):
    """Get detailed analysis for a specific service"""
    if not unified_result:
        raise HTTPException(status_code=404, detail="No unified analysis. Call /api/unified/analyze first.")
    
    if service_name not in unified_result.services:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_name}")
    
    # Get all nodes for this service
    service_nodes = [n.to_dict() for n in unified_result.nodes.values() if n.service == service_name]
    
    # Get connections involving this service
    service_connections = [c.to_dict() for c in unified_result.connections 
                          if service_name in c.source_id or service_name in c.target_id]
    
    # Get protected zones for this service
    zones = set()
    for node in unified_result.nodes.values():
        if node.service == service_name and node.protected_zone:
            zones.add(node.protected_zone)
    
    # Count by type
    endpoints = [n for n in service_nodes if n.get("is_endpoint")]
    functions = [n for n in service_nodes if n.get("type") == "function"]
    classes = [n for n in service_nodes if n.get("type") == "class"]
    files = [n for n in service_nodes if n.get("type") == "file"]
    
    return {
        "service": service_name,
        "stats": {
            "total_nodes": len(service_nodes),
            "total_connections": len(service_connections),
            "endpoints": len(endpoints),
            "functions": len(functions),
            "classes": len(classes),
            "files": len(files)
        },
        "protected_zones": list(zones),
        "nodes": service_nodes,
        "connections": service_connections
    }


@app.get("/api/unified/health-report")
async def get_health_report():
    """Get overall codebase health report"""
    if not unified_result:
        raise HTTPException(status_code=404, detail="No unified analysis. Call /api/unified/analyze first.")
    
    # Calculate health score (0-100)
    total_issues = (
        len(unified_result.broken_connections) * 10 +
        len(unified_result.dead_code) * 2 +
        len(unified_result.circular_dependencies) * 5
    )
    
    health_score = max(0, 100 - total_issues)
    
    # Determine status
    if health_score >= 90:
        status = "excellent"
    elif health_score >= 70:
        status = "good"
    elif health_score >= 50:
        status = "fair"
    else:
        status = "needs_attention"
    
    # Count nodes by protected zone
    zone_counts = {}
    for node in unified_result.nodes.values():
        if node.protected_zone:
            zone_counts[node.protected_zone] = zone_counts.get(node.protected_zone, 0) + 1
    
    return {
        "health_score": health_score,
        "status": status,
        "summary": {
            "total_services": len(unified_result.services),
            "total_nodes": unified_result.total_nodes,
            "total_connections": unified_result.total_connections,
            "total_endpoints": unified_result.total_endpoints,
            "protected_zones": len(unified_result.protected_zones)
        },
        "issues": {
            "broken_connections": len(unified_result.broken_connections),
            "dead_code": len(unified_result.dead_code),
            "circular_dependencies": len(unified_result.circular_dependencies)
        },
        "protected_zone_coverage": zone_counts,
        "pipelines_detected": list(unified_result.pipelines.keys()),
        "recommendations": _generate_recommendations(unified_result)
    }


def _generate_recommendations(result: UnifiedAnalysisResult) -> List[str]:
    """Generate recommendations based on analysis"""
    recommendations = []
    
    if len(result.broken_connections) > 0:
        recommendations.append(f"Fix {len(result.broken_connections)} broken import connections")
    
    if len(result.dead_code) > 10:
        recommendations.append(f"Consider removing {len(result.dead_code)} unused functions/classes")
    
    if len(result.circular_dependencies) > 0:
        recommendations.append(f"Resolve {len(result.circular_dependencies)} circular dependency chains")
    
    # Check for services without protected zones
    unprotected = set()
    for node in result.nodes.values():
        if node.type == "service" and not node.protected_zone:
            unprotected.add(node.name)
    
    if unprotected:
        recommendations.append(f"Consider adding protection for services: {', '.join(list(unprotected)[:5])}")
    
    if not recommendations:
        recommendations.append("Codebase is in good health!")
    
    return recommendations


@app.get("/api/graph/services")
async def get_services():
    """Get list of services"""
    if not current_graph:
        raise HTTPException(status_code=404, detail="No graph loaded")
    return {"services": current_graph.services}


@app.get("/api/graph/node/{node_id}")
async def get_node(node_id: str):
    """Get a specific node and its connections"""
    if not current_graph:
        raise HTTPException(status_code=404, detail="No graph loaded")
    
    node = current_graph.nodes.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    
    incoming = current_graph.get_connections_to(node_id)
    outgoing = current_graph.get_connections_from(node_id)
    
    return {
        "node": node.dict(),
        "incoming_connections": [c.dict() for c in incoming],
        "outgoing_connections": [c.dict() for c in outgoing]
    }


# ============== CHANGE IMPACT ANALYSIS ==============

@app.post("/api/impact")
async def analyze_impact(request: AnalyzeImpactRequest):
    """Analyze the impact of a proposed change"""
    if not impact_analyzer:
        raise HTTPException(status_code=500, detail="Impact analyzer not initialized")
    
    try:
        change = CodeChange(
            file_path=request.file_path,
            change_type=request.change_type,
            old_content=request.old_content,
            new_content=request.new_content,
            line_start=request.line_start,
            line_end=request.line_end,
            description=request.description
        )
        
        impact = await impact_analyzer.analyze_change(change)
        
        # Check with monitoring agents
        alerts = await monitoring_runner.check_change(change, impact)
        
        return {
            "change_id": change.id,
            "impact": impact.dict(),
            "alerts": [a.to_dict() for a in alerts]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Impact analysis failed: {str(e)}")


@app.post("/api/impact/batch")
async def analyze_batch_impact(changes: List[AnalyzeImpactRequest]):
    """Analyze the combined impact of multiple changes"""
    if not multi_analyzer:
        raise HTTPException(status_code=500, detail="Multi analyzer not initialized")
    
    code_changes = [
        CodeChange(
            file_path=r.file_path,
            change_type=r.change_type,
            old_content=r.old_content,
            new_content=r.new_content,
            line_start=r.line_start,
            line_end=r.line_end,
            description=r.description
        )
        for r in changes
    ]
    
    impact = await multi_analyzer.analyze_batch(code_changes)
    
    return {"impact": impact.dict()}


# ============== PROTECTED ZONES ==============

@app.get("/api/protected")
async def get_protected_zones():
    """Get all protected zones"""
    return {
        "zones": [z.dict() for z in DEFAULT_PROTECTED_ZONES]
    }


@app.get("/api/protected/{zone_name}")
async def get_protected_zone(zone_name: str):
    """Get a specific protected zone"""
    zone = next((z for z in DEFAULT_PROTECTED_ZONES if z.name == zone_name), None)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_name}")
    return zone.dict()


# ============== GHOST CHANGES ==============

@app.post("/api/ghost")
async def create_ghost(request: CreateGhostRequest):
    """Create a ghost change (preview before applying)"""
    if not impact_analyzer:
        raise HTTPException(status_code=500, detail="Impact analyzer not initialized")
    
    # Analyze combined impact
    if multi_analyzer:
        impact = await multi_analyzer.analyze_batch(request.changes)
    else:
        impact = ChangeImpact(change_id="ghost")
    
    ghost = await state_manager.create_ghost(request.changes, impact)
    
    return {
        "ghost_id": ghost.id,
        "changes": len(ghost.changes),
        "impact": ghost.impact.dict() if ghost.impact else None,
        "validation_status": ghost.validation_status.value
    }


@app.get("/api/ghost/{ghost_id}")
async def get_ghost(ghost_id: str):
    """Get a ghost change"""
    ghost = await state_manager.get_ghost(ghost_id)
    if not ghost:
        raise HTTPException(status_code=404, detail=f"Ghost not found: {ghost_id}")
    return ghost.dict()


@app.post("/api/validate")
async def validate_change(request: ValidateChangeRequest):
    """Validate a ghost change"""
    try:
        ghost = await state_manager.validate_ghost(request.ghost_id)
        return {
            "ghost_id": ghost.id,
            "validation_status": ghost.validation_status.value,
            "can_apply": ghost.validation_status == ValidationStatus.APPROVED
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/approve")
async def approve_change(request: ApproveChangeRequest):
    """Approve a ghost change that requires review"""
    try:
        ghost = await state_manager.approve_ghost(
            request.ghost_id,
            request.approver,
            request.reason
        )
        return {
            "ghost_id": ghost.id,
            "validation_status": ghost.validation_status.value,
            "approved_by": request.approver
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/ghost/{ghost_id}/apply")
async def apply_ghost(ghost_id: str):
    """Apply an approved ghost change"""
    try:
        history_entry = await state_manager.apply_ghost(ghost_id)
        return {
            "success": True,
            "history_id": history_entry.id,
            "applied_at": history_entry.applied_at.isoformat(),
            "rollback_available": history_entry.rollback_available
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== HISTORY & ROLLBACK ==============

@app.get("/api/history")
async def get_history(limit: int = 50):
    """Get change history"""
    history = await state_manager.get_history(limit)
    return {"history": [h.dict() for h in history]}


@app.post("/api/rollback")
async def rollback(request: RollbackRequest):
    """Rollback to a previous state"""
    try:
        success = await state_manager.rollback(request.history_id, request.reason)
        return {"success": success, "rolled_back_to": request.history_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== MONITORING AGENTS ==============

@app.get("/api/agents/status")
async def get_agents_status():
    """Get status of all monitoring agents"""
    return await monitoring_runner.get_agent_status()


@app.get("/api/agents/alerts")
async def get_alerts():
    """Get all active alerts"""
    alerts = await monitoring_runner.get_active_alerts()
    return {"alerts": [a.to_dict() for a in alerts]}


@app.post("/api/agents/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert"""
    success = await monitoring_runner.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
    return {"success": True}


@app.post("/api/agents/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve an alert"""
    success = await monitoring_runner.resolve_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
    return {"success": True}


@app.post("/api/agents/{agent_name}/pause")
async def pause_agent(agent_name: str):
    """Pause a monitoring agent"""
    success = await monitoring_runner.pause_agent(agent_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return {"success": True}


@app.post("/api/agents/{agent_name}/resume")
async def resume_agent(agent_name: str):
    """Resume a paused monitoring agent"""
    success = await monitoring_runner.resume_agent(agent_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return {"success": True}


# ============== ISOLATION STRATEGY ==============

@app.get("/api/isolation")
async def get_isolation_strategy():
    """Get the isolation strategy"""
    return isolation_enforcer.get_isolation_report()


@app.post("/api/isolation/check")
async def check_isolation(source_service: str, target_service: str):
    """Check if a change violates isolation strategy"""
    violation = isolation_enforcer.check_isolation_violation(source_service, target_service)
    return {
        "source_service": source_service,
        "target_service": target_service,
        "violation": violation,
        "allowed": violation is None
    }


@app.post("/api/isolation/fix-order")
async def get_fix_order(services: List[str]):
    """Get the correct order to fix services"""
    order = isolation_enforcer.get_fix_order(services)
    return {"fix_order": order}


# ============== SNAPSHOTS ==============

class CreateSnapshotRequest(BaseModel):
    name: str
    paths: List[str]


@app.post("/api/snapshots")
async def create_snapshot(request: CreateSnapshotRequest):
    """Create a named snapshot"""
    snapshot_id = await state_manager.create_snapshot(request.name, request.paths)
    return {"snapshot_id": snapshot_id}


@app.get("/api/snapshots")
async def list_snapshots():
    """List all snapshots"""
    snapshots = await state_manager.list_snapshots()
    return {"snapshots": snapshots}


# ============== ENFORCEMENT (HARD CONSTRAINTS) ==============

class EnforceRequest(BaseModel):
    """Request to enforce effect boundaries"""
    files: List[str]
    approved_boundaries: List[str] = []


@app.post("/api/enforce")
async def enforce_effect_boundaries(request: EnforceRequest):
    """
    HARD CONSTRAINT: Enforce effect boundary rules.
    Returns blocked if any file violates boundaries without approval.
    """
    approved = {EffectBoundary(b) for b in request.approved_boundaries if b in [e.value for e in EffectBoundary]}
    result = enforce_changes(request.files, approved)
    
    return {
        "allowed": result.allowed,
        "blocked_files": [f.dict() for f in result.blocked_files],
        "unclassified_files": result.unclassified_files,
        "warnings": result.warnings,
        "requires_approval": result.requires_approval,
        "approval_reason": result.approval_reason
    }


@app.get("/api/enforce/classify/{file_path:path}")
async def classify_single_file(file_path: str):
    """Classify a single file by effect boundary"""
    classification = classify_file(file_path)
    return classification.dict()


@app.get("/api/enforce/boundaries")
async def get_effect_boundaries():
    """Get all effect boundary definitions"""
    return {
        "boundaries": {
            b.value: {
                "name": b.value,
                "patterns": patterns,
                "description": {
                    "auth": "Authentication, sessions, tokens - identity verification",
                    "money": "Payments, billing, subscriptions - financial transactions",
                    "identity": "User data, PII, profiles - personal information",
                    "irreversible": "Database migrations, deletions - cannot be undone"
                }.get(b.value, "")
            }
            for b, patterns in EFFECT_BOUNDARIES.items()
        }
    }


@app.post("/api/audit")
async def log_audit_event(action: str = "", files: str = "", actor: str = "unknown"):
    """Log an audit event (used by git hooks)"""
    try:
        db = SessionLocal()
        repo = AuditLogRepository(db)
        repo.log(
            action=action,
            actor=actor,
            files=files
        )
        return {"status": "logged"}
    finally:
        db.close()


@app.websocket("/ws/monitoring/{connection_id}")
async def websocket_monitoring(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for real-time monitoring"""
    await websocket_monitoring_endpoint(websocket, connection_id)


@app.websocket("/ws/self-healing/{connection_id}")
async def websocket_self_healing(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for self-healing updates"""
    await websocket_self_healing_endpoint(websocket, connection_id)


@app.websocket("/ws/code-analysis/{connection_id}")
async def websocket_code_analysis(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for real-time code analysis updates"""
    await websocket_code_analysis_endpoint(websocket, connection_id)


@app.post("/api/self-healing/trigger")
async def trigger_self_healing(event: SelfHealingEvent):
    """Trigger self-healing action"""
    success = await self_healing_integration.trigger_self_healing(event)
    return {
        "success": success,
        "event": event.dict(),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/self-healing/status")
async def get_self_healing_status():
    """Get self-healing system status"""
    return {
        "active_events": len(self_healing_integration.self_healing_events),
        "recent_events": [
            event.dict() for event in 
            self_healing_integration.self_healing_events[-10:]
        ],
        "websocket_connections": len(self_healing_integration.websocket_manager.active_connections),
        "timestamp": datetime.utcnow().isoformat()
    }


# ============== FRONTEND ==============

@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    """Serve the control plane frontend"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(html_path):
        with open(html_path, 'r') as f:
            return f.read()
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CASCADE Control Plane</title>
        <style>
            body { font-family: sans-serif; background: #0a0a0f; color: #fff; padding: 40px; }
            h1 { color: #64c8ff; }
            .card { background: #1a1a2e; padding: 20px; border-radius: 8px; margin: 20px 0; }
            a { color: #64c8ff; }
        </style>
    </head>
    <body>
        <h1>🎛️ CASCADE Control Plane</h1>
        <div class="card">
            <h2>API Endpoints</h2>
            <ul>
                <li><a href="/docs">/docs</a> - OpenAPI Documentation</li>
                <li><a href="/api/info">/api/info</a> - Service Information</li>
                <li><a href="/api/protected">/api/protected</a> - Protected Zones</li>
                <li><a href="/api/isolation">/api/isolation</a> - Isolation Strategy</li>
                <li><a href="/api/agents/status">/api/agents/status</a> - Monitoring Agents</li>
            </ul>
        </div>
        <div class="card">
            <h2>Quick Start</h2>
            <p>1. Analyze codebase: POST /api/analyze {"path": "/path/to/code"}</p>
            <p>2. Check impact: POST /api/impact {"file_path": "...", "change_type": "modify"}</p>
            <p>3. Create ghost: POST /api/ghost {"changes": [...]}</p>
            <p>4. Validate: POST /api/validate {"ghost_id": "..."}</p>
            <p>5. Apply: POST /api/ghost/{id}/apply</p>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8095)
