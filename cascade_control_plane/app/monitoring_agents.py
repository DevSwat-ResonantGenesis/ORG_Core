"""
CASCADE Control Plane - AI Monitoring Agents
Autonomous agents that monitor for dangerous changes and alert on violations.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from .models import (
    MonitoringAgent, MonitoringAgentStatus, ProtectedZone,
    CodeChange, ChangeImpact, RiskLevel, DEFAULT_MONITORING_AGENTS
)


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class Alert:
    """An alert raised by a monitoring agent"""
    
    def __init__(
        self,
        agent_name: str,
        severity: AlertSeverity,
        message: str,
        details: Dict[str, Any] = None,
        change_id: Optional[str] = None
    ):
        self.id = f"alert_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        self.agent_name = agent_name
        self.severity = severity
        self.message = message
        self.details = details or {}
        self.change_id = change_id
        self.timestamp = datetime.utcnow()
        self.acknowledged = False
        self.resolved = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "change_id": self.change_id,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "resolved": self.resolved
        }


class MonitoringAgentRunner:
    """Runs and manages monitoring agents"""
    
    def __init__(self):
        self.agents: Dict[str, MonitoringAgent] = {}
        self.alerts: List[Alert] = []
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        self._running = False
        
        # Initialize default agents
        for agent in DEFAULT_MONITORING_AGENTS:
            self.agents[agent.name] = agent
    
    def register_alert_callback(self, callback: Callable[[Alert], None]):
        """Register a callback to be called when an alert is raised"""
        self.alert_callbacks.append(callback)
    
    async def check_change(self, change: CodeChange, impact: ChangeImpact) -> List[Alert]:
        """Check a change against all monitoring agents"""
        alerts = []
        
        for agent in self.agents.values():
            if agent.status != MonitoringAgentStatus.ACTIVE:
                continue
            
            # Check if this change affects zones this agent monitors
            affected_zones = set(impact.protected_zones_affected)
            monitored_zones = set(agent.protected_zones)
            
            overlap = affected_zones.intersection(monitored_zones)
            if overlap:
                # Generate alert based on risk level
                alert = self._generate_alert(agent, change, impact, list(overlap))
                if alert:
                    alerts.append(alert)
                    self.alerts.append(alert)
                    
                    # Update agent status
                    agent.status = MonitoringAgentStatus.ALERT
                    agent.alerts.append(alert.id)
                    agent.last_check = datetime.utcnow()
                    
                    # Call callbacks
                    for callback in self.alert_callbacks:
                        try:
                            callback(alert)
                        except:
                            pass
        
        return alerts
    
    def _generate_alert(
        self,
        agent: MonitoringAgent,
        change: CodeChange,
        impact: ChangeImpact,
        affected_zones: List[str]
    ) -> Optional[Alert]:
        """Generate an alert for a change"""
        
        # Determine severity based on risk level
        if impact.risk_level == RiskLevel.CRITICAL:
            severity = AlertSeverity.EMERGENCY
        elif impact.risk_level == RiskLevel.HIGH:
            severity = AlertSeverity.CRITICAL
        elif impact.risk_level == RiskLevel.MEDIUM:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO
        
        # Build message
        zones_str = ", ".join(affected_zones)
        message = f"[{agent.name}] Change to protected zone(s): {zones_str}"
        
        if impact.blockers:
            message += f" - BLOCKED: {impact.blockers[0]}"
        elif impact.warnings:
            message += f" - {impact.warnings[0]}"
        
        return Alert(
            agent_name=agent.name,
            severity=severity,
            message=message,
            details={
                "file_path": change.file_path,
                "change_type": change.change_type if isinstance(change.change_type, str) else change.change_type.value,
                "affected_zones": affected_zones,
                "impact_score": impact.impact_score,
                "cascade_depth": impact.cascade_depth,
                "affected_services": impact.affected_services,
                "warnings": impact.warnings,
                "blockers": impact.blockers
            },
            change_id=change.id
        )
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                
                # Update agent status if all alerts resolved
                agent = self.agents.get(alert.agent_name)
                if agent:
                    unresolved = [a for a in self.alerts 
                                 if a.agent_name == agent.name and not a.resolved]
                    if not unresolved:
                        agent.status = MonitoringAgentStatus.ACTIVE
                
                return True
        return False
    
    async def get_active_alerts(self) -> List[Alert]:
        """Get all unresolved alerts"""
        return [a for a in self.alerts if not a.resolved]
    
    async def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all monitoring agents"""
        status = {}
        for name, agent in self.agents.items():
            unresolved_alerts = [a for a in self.alerts 
                                if a.agent_name == name and not a.resolved]
            status[name] = {
                "name": agent.name,
                "description": agent.description,
                "status": agent.status.value,
                "protected_zones": agent.protected_zones,
                "last_check": agent.last_check.isoformat() if agent.last_check else None,
                "active_alerts": len(unresolved_alerts)
            }
        return status
    
    async def pause_agent(self, agent_name: str) -> bool:
        """Pause a monitoring agent"""
        if agent_name in self.agents:
            self.agents[agent_name].status = MonitoringAgentStatus.PAUSED
            return True
        return False
    
    async def resume_agent(self, agent_name: str) -> bool:
        """Resume a paused monitoring agent"""
        if agent_name in self.agents:
            self.agents[agent_name].status = MonitoringAgentStatus.ACTIVE
            return True
        return False


class IsolationStrategyEnforcer:
    """Enforces the isolation strategy for safe fixes"""
    
    def __init__(self):
        from .models import DEFAULT_ISOLATION_LAYERS, IsolationLayer
        self.layers = {l.level: l for l in DEFAULT_ISOLATION_LAYERS}
    
    def get_layer_for_service(self, service: str) -> Optional[int]:
        """Get the isolation layer level for a service"""
        for level, layer in self.layers.items():
            if service in layer.services:
                return level
        return None
    
    def check_isolation_violation(
        self,
        source_service: str,
        target_service: str
    ) -> Optional[str]:
        """Check if a change violates isolation strategy"""
        source_level = self.get_layer_for_service(source_service)
        target_level = self.get_layer_for_service(target_service)
        
        if source_level is None or target_level is None:
            return None
        
        # Higher layer modifying lower layer is a violation
        if source_level > target_level:
            source_layer = self.layers[source_level]
            target_layer = self.layers[target_level]
            
            if not source_layer.can_modify_lower:
                return (
                    f"ISOLATION VIOLATION: {source_service} (Layer {source_level}: {source_layer.name}) "
                    f"cannot modify {target_service} (Layer {target_level}: {target_layer.name}). "
                    f"Fix the issue at Layer {target_level} instead."
                )
        
        return None
    
    def get_fix_order(self, affected_services: List[str]) -> List[str]:
        """Get the correct order to fix services (lowest layer first)"""
        service_levels = []
        for service in affected_services:
            level = self.get_layer_for_service(service)
            if level is not None:
                service_levels.append((level, service))
            else:
                service_levels.append((999, service))
        
        # Sort by level (lowest first)
        service_levels.sort(key=lambda x: x[0])
        return [s for _, s in service_levels]
    
    def get_isolation_report(self) -> Dict[str, Any]:
        """Get a report of the isolation strategy"""
        return {
            "layers": [
                {
                    "level": layer.level,
                    "name": layer.name,
                    "description": layer.description,
                    "services": layer.services,
                    "can_modify_lower": layer.can_modify_lower,
                    "requires_lower_stable": layer.requires_lower_stable
                }
                for layer in sorted(self.layers.values(), key=lambda x: x.level)
            ],
            "rules": [
                "Never modify a lower layer to fix a higher layer issue",
                "Always ensure lower layers are stable before modifying higher layers",
                "Fix issues at the layer where they originate",
                "Test each layer independently before integration"
            ]
        }
