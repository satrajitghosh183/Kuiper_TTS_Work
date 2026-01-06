# WebSocket Manager for Training Updates
# Handles real-time communication during training

import asyncio
import json
from typing import List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum


class MessageType(Enum):
    """WebSocket message types."""
    TRAINING_STATUS = "training_status"
    TRAINING_PROGRESS = "training_progress"
    TRAINING_LOG = "training_log"
    TRAINING_ERROR = "training_error"
    SYSTEM_STATUS = "system_status"
    PING = "ping"
    PONG = "pong"


@dataclass
class WebSocketMessage:
    """A WebSocket message."""
    
    type: MessageType
    data: Dict[str, Any]
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps({
            "type": self.type.value,
            "data": self.data
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """Parse from JSON string."""
        parsed = json.loads(json_str)
        return cls(
            type=MessageType(parsed["type"]),
            data=parsed.get("data", {})
        )


class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting.
    
    Provides:
    - Client connection tracking
    - Message broadcasting to all clients
    - Room-based messaging (e.g., per-training-session)
    - Automatic reconnection handling
    """
    
    def __init__(self):
        self.active_connections: List = []
        self.rooms: Dict[str, List] = {}
    
    async def connect(self, websocket, room: str = "default"):
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            room: Optional room to join
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if room not in self.rooms:
            self.rooms[room] = []
        self.rooms[room].append(websocket)
    
    def disconnect(self, websocket, room: str = "default"):
        """
        Remove a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            room: Room to leave
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if room in self.rooms and websocket in self.rooms[room]:
            self.rooms[room].remove(websocket)
    
    async def send_personal(self, message: WebSocketMessage, websocket):
        """
        Send a message to a specific client.
        
        Args:
            message: The message to send
            websocket: The target WebSocket connection
        """
        try:
            await websocket.send_text(message.to_json())
        except Exception:
            self.disconnect(websocket)
    
    async def broadcast(self, message: WebSocketMessage, room: str = None):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
            room: Optional room to broadcast to (None = all clients)
        """
        targets = self.rooms.get(room, self.active_connections) if room else self.active_connections
        
        disconnected = []
        for connection in targets:
            try:
                await connection.send_text(message.to_json())
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn, room)
    
    async def broadcast_json(self, data: Dict[str, Any], room: str = None):
        """
        Broadcast raw JSON data to all clients.
        
        Args:
            data: Dictionary to send as JSON
            room: Optional room to broadcast to
        """
        targets = self.rooms.get(room, self.active_connections) if room else self.active_connections
        
        json_str = json.dumps(data)
        disconnected = []
        
        for connection in targets:
            try:
                await connection.send_text(json_str)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn, room)
    
    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
    
    def get_room_count(self, room: str) -> int:
        """Get the number of connections in a room."""
        return len(self.rooms.get(room, []))


class TrainingProgressBroadcaster:
    """
    Helper class to broadcast training progress updates.
    
    Wraps the ConnectionManager with training-specific functionality.
    """
    
    ROOM = "training"
    
    def __init__(self, manager: ConnectionManager):
        self.manager = manager
    
    async def send_status(self, status: str, message: str = ""):
        """Send a status update."""
        await self.manager.broadcast(
            WebSocketMessage(
                type=MessageType.TRAINING_STATUS,
                data={"status": status, "message": message}
            ),
            room=self.ROOM
        )
    
    async def send_progress(
        self,
        epoch: int,
        total_epochs: int,
        loss: float,
        val_loss: float = None,
        elapsed_seconds: float = 0,
        remaining_seconds: float = 0,
        **extra
    ):
        """Send a progress update."""
        data = {
            "epoch": epoch,
            "total_epochs": total_epochs,
            "loss": loss,
            "val_loss": val_loss,
            "percent_complete": (epoch / total_epochs * 100) if total_epochs > 0 else 0,
            "elapsed_seconds": elapsed_seconds,
            "estimated_remaining_seconds": remaining_seconds,
            **extra
        }
        
        await self.manager.broadcast(
            WebSocketMessage(
                type=MessageType.TRAINING_PROGRESS,
                data=data
            ),
            room=self.ROOM
        )
    
    async def send_log(self, level: str, message: str):
        """Send a log message."""
        await self.manager.broadcast(
            WebSocketMessage(
                type=MessageType.TRAINING_LOG,
                data={"level": level, "message": message}
            ),
            room=self.ROOM
        )
    
    async def send_error(self, error: str, details: str = None):
        """Send an error message."""
        await self.manager.broadcast(
            WebSocketMessage(
                type=MessageType.TRAINING_ERROR,
                data={"error": error, "details": details}
            ),
            room=self.ROOM
        )


# Global connection manager instance
connection_manager = ConnectionManager()
training_broadcaster = TrainingProgressBroadcaster(connection_manager)


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return connection_manager


def get_training_broadcaster() -> TrainingProgressBroadcaster:
    """Get the global training broadcaster."""
    return training_broadcaster

