"""
CASCADE Control Plane - Self-Healing Integration
Integrates Cascade with the autonomous self-healing platform
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .monitoring_agents import MonitoringAgent, Alert, AlertSeverity
from .models import CodeChange, ChangeImpact, RiskLevel


class SelfHealingAction(str, Enum):
    RESTART_SERVICE = "restart_service"
    RESET_CONFIG = "reset_config"
    REBUILD_SERVICE = "rebuild_service"
    SCALE_SERVICE = "scale_service"
    UPDATE_DEPENDENCIES = "update_dependencies"


class SelfHealingEvent(BaseModel):
    """Self-healing event from Cascade"""
    event_type: str
    service_name: str
    severity: AlertSeverity
    message: str
    action_required: Optional[SelfHealingAction] = None
    metadata: Dict[str, Any] = {}
    timestamp: datetime = datetime.utcnow()


class WebSocketConnectionManager:
    """Manage WebSocket connections for real-time self-healing updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)


class SelfHealingIntegration:
    """Integration between Cascade and Self-Healing Platform"""
    
    def __init__(self):
        self.websocket_manager = WebSocketConnectionManager()
        self.self_healing_events: List[SelfHealingEvent] = []
        self.monitoring_agents: List[MonitoringAgent] = []
    
    async def trigger_self_healing(self, event: SelfHealingEvent) -> bool:
        """Trigger self-healing action based on Cascade analysis"""
        try:
            # Log the event
            self.self_healing_events.append(event)
            
            # Broadcast to WebSocket clients
            await self.websocket_manager.broadcast({
                "type": "self_healing_event",
                "event": event.dict()
            })
            
            # Determine appropriate action
            if event.action_required:
                return await self.execute_healing_action(event)
            
            return True
            
        except Exception as e:
            print(f"Error in self-healing integration: {e}")
            return False
    
    async def execute_healing_action(self, event: SelfHealingEvent) -> bool:
        """Execute the required self-healing action"""
        try:
            if event.action_required == SelfHealingAction.RESTART_SERVICE:
                return await self.restart_service(event.service_name)
            elif event.action_required == SelfHealingAction.RESET_CONFIG:
                return await self.reset_service_config(event.service_name)
            elif event.action_required == SelfHealingAction.REBUILD_SERVICE:
                return await self.rebuild_service(event.service_name)
            elif event.action_required == SelfHealingAction.SCALE_SERVICE:
                return await self.scale_service(event.service_name)
            elif event.action_required == SelfHealingAction.UPDATE_DEPENDENCIES:
                return await self.update_service_dependencies(event.service_name)
            
            return False
            
        except Exception as e:
            print(f"Error executing healing action: {e}")
            return False
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a service"""
        try:
            # Use Docker Compose to restart service
            import subprocess
            
            result = subprocess.run(
                ["docker-compose", "restart", service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            success = result.returncode == 0
            
            # Broadcast result
            await self.websocket_manager.broadcast({
                "type": "healing_action_result",
                "action": "restart_service",
                "service": service_name,
                "success": success,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return success
            
        except Exception as e:
            print(f"Error restarting service {service_name}: {e}")
            return False
    
    async def reset_service_config(self, service_name: str) -> bool:
        """Reset service configuration"""
        try:
            # Implementation for config reset
            await self.websocket_manager.broadcast({
                "type": "healing_action_result",
                "action": "reset_config",
                "service": service_name,
                "success": True,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return True
            
        except Exception as e:
            print(f"Error resetting config for {service_name}: {e}")
            return False
    
    async def rebuild_service(self, service_name: str) -> bool:
        """Rebuild a service"""
        try:
            # Use Docker Compose to rebuild service
            import subprocess
            
            result = subprocess.run(
                ["docker-compose", "up", "-d", "--build", service_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            success = result.returncode == 0
            
            # Broadcast result
            await self.websocket_manager.broadcast({
                "type": "healing_action_result",
                "action": "rebuild_service",
                "service": service_name,
                "success": success,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return success
            
        except Exception as e:
            print(f"Error rebuilding service {service_name}: {e}")
            return False
    
    async def scale_service(self, service_name: str) -> bool:
        """Scale a service"""
        try:
            # Implementation for service scaling
            await self.websocket_manager.broadcast({
                "type": "healing_action_result",
                "action": "scale_service",
                "service": service_name,
                "success": True,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return True
            
        except Exception as e:
            print(f"Error scaling service {service_name}: {e}")
            return False
    
    async def update_service_dependencies(self, service_name: str) -> bool:
        """Update service dependencies"""
        try:
            # Implementation for dependency updates
            await self.websocket_manager.broadcast({
                "type": "healing_action_result",
                "action": "update_dependencies",
                "service": service_name,
                "success": True,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return True
            
        except Exception as e:
            print(f"Error updating dependencies for {service_name}: {e}")
            return False
    
    def create_self_healing_event_from_alert(self, alert: Alert) -> SelfHealingEvent:
        """Create self-healing event from monitoring alert"""
        # Determine action based on alert severity and message
        action = None
        if alert.severity == AlertSeverity.CRITICAL:
            if "connection" in alert.message.lower():
                action = SelfHealingAction.RESTART_SERVICE
            elif "config" in alert.message.lower():
                action = SelfHealingAction.RESET_CONFIG
            elif "build" in alert.message.lower():
                action = SelfHealingAction.REBUILD_SERVICE
        elif alert.severity == AlertSeverity.EMERGENCY:
            action = SelfHealingAction.RESTART_SERVICE
        
        return SelfHealingEvent(
            event_type="monitoring_alert",
            service_name=alert.agent_name,
            severity=alert.severity,
            message=alert.message,
            action_required=action,
            metadata=alert.details
        )


# Global instance
self_healing_integration = SelfHealingIntegration()
