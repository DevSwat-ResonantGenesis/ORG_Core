"""
CASCADE Control Plane - WebSocket Endpoints
WebSocket endpoints for real-time monitoring and self-healing updates
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from .self_healing_integration import self_healing_integration, SelfHealingEvent
from .monitoring_agents import Alert, AlertSeverity


class WebSocketMessage(BaseModel):
    """WebSocket message model"""
    type: str
    data: Dict[str, Any]
    timestamp: datetime = datetime.utcnow()


class WebSocketManager:
    """Enhanced WebSocket manager for Cascade"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str, metadata: Dict[str, Any] = None):
        """Accept WebSocket connection with metadata"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = metadata or {}
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Connected to Cascade Control Plane WebSocket"
        })
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]
    
    async def send_personal_message(self, connection_id: str, message: dict):
        """Send message to specific connection"""
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].send_json(message)
            except Exception as e:
                print(f"Error sending message to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            self.disconnect(connection_id)
    
    async def broadcast_to_type(self, connection_type: str, message: dict):
        """Broadcast to connections of specific type"""
        disconnected = []
        for connection_id, websocket in self.active_connections.items():
            metadata = self.connection_metadata.get(connection_id, {})
            if metadata.get("type") == connection_type:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    print(f"Error broadcasting to {connection_id}: {e}")
                    disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            self.disconnect(connection_id)


# Global WebSocket manager
websocket_manager = WebSocketManager()


async def handle_websocket_message(websocket: WebSocket, connection_id: str, message: dict):
    """Handle incoming WebSocket messages"""
    message_type = message.get("type", "unknown")
    
    if message_type == "ping":
        await websocket.send_json({
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    elif message_type == "subscribe":
        # Handle subscription to specific events
        subscription_type = message.get("subscription", "all")
        metadata = websocket_manager.connection_metadata.get(connection_id, {})
        metadata["subscriptions"] = message.get("subscriptions", ["all"])
        websocket_manager.connection_metadata[connection_id] = metadata
        
        await websocket.send_json({
            "type": "subscription_confirmed",
            "subscription": subscription_type,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    elif message_type == "get_status":
        # Get current status of services
        await websocket.send_json({
            "type": "status_update",
            "data": {
                "active_connections": len(websocket_manager.active_connections),
                "self_healing_events": len(self_healing_integration.self_healing_events),
                "timestamp": datetime.utcnow().isoformat()
            }
        })
    
    elif message_type == "trigger_healing":
        # Trigger self-healing action
        event_data = message.get("event", {})
        event = SelfHealingEvent(**event_data)
        
        success = await self_healing_integration.trigger_self_healing(event)
        
        await websocket.send_json({
            "type": "healing_triggered",
            "success": success,
            "event_id": event.id if hasattr(event, 'id') else None,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {message_type}",
            "timestamp": datetime.utcnow().isoformat()
        })


async def websocket_monitoring_endpoint(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for real-time monitoring"""
    await websocket_manager.connect(websocket, connection_id, {
        "type": "monitoring",
        "connected_at": datetime.utcnow().isoformat()
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_websocket_message(websocket, connection_id, message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                })
    except WebSocketDisconnect:
        websocket_manager.disconnect(connection_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(connection_id)


async def websocket_self_healing_endpoint(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for self-healing updates"""
    await websocket_manager.connect(websocket, connection_id, {
        "type": "self_healing",
        "connected_at": datetime.utcnow().isoformat()
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_websocket_message(websocket, connection_id, message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                })
    except WebSocketDisconnect:
        websocket_manager.disconnect(connection_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(connection_id)


async def websocket_code_analysis_endpoint(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for real-time code analysis updates"""
    await websocket_manager.connect(websocket, connection_id, {
        "type": "code_analysis",
        "connected_at": datetime.utcnow().isoformat()
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_websocket_message(websocket, connection_id, message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                })
    except WebSocketDisconnect:
        websocket_manager.disconnect(connection_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(connection_id)


# Utility functions for broadcasting events
async def broadcast_monitoring_alert(alert: Alert):
    """Broadcast monitoring alert to WebSocket clients"""
    await websocket_manager.broadcast_to_type("monitoring", {
        "type": "monitoring_alert",
        "alert": {
            "id": alert.id,
            "agent_name": alert.agent_name,
            "severity": alert.severity.value,
            "message": alert.message,
            "details": alert.details,
            "timestamp": alert.timestamp.isoformat()
        }
    })


async def broadcast_self_healing_event(event: SelfHealingEvent):
    """Broadcast self-healing event to WebSocket clients"""
    await websocket_manager.broadcast_to_type("self_healing", {
        "type": "self_healing_event",
        "event": event.dict()
    })


async def broadcast_code_analysis_update(analysis_data: dict):
    """Broadcast code analysis update to WebSocket clients"""
    await websocket_manager.broadcast_to_type("code_analysis", {
        "type": "analysis_update",
        "data": analysis_data,
        "timestamp": datetime.utcnow().isoformat()
    })
