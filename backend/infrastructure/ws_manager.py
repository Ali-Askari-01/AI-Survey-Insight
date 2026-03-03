"""
WebSocket Manager — Enhanced Real-Time Infrastructure (Section 13)
═══════════════════════════════════════════════════════
Insight updates must feel alive.

WebSocket Layer:
  /ws/insights  — Used for:
    ✅ live dashboard updates
    ✅ processing status
    ✅ alerts

This module implements:
  - Channel-based WebSocket routing (dashboard, insights, alerts, tasks)
  - Room support (per-survey, per-org isolation)
  - Presence tracking (who's connected)
  - Message broadcasting with filtering
  - Connection lifecycle management (heartbeat, reconnect)
  - Integration with event bus for AI pipeline status
  - Metrics and observability
"""

import time
import json
import asyncio
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect


# ═══════════════════════════════════════════════════
# CHANNEL TYPES
# ═══════════════════════════════════════════════════
class WSChannel(Enum):
    """WebSocket channel types for message routing."""
    DASHBOARD = "dashboard"         # Live dashboard metric updates
    INSIGHTS = "insights"           # New insight/theme discoveries
    ALERTS = "alerts"               # Critical alerts and notifications
    TASKS = "tasks"                 # Task queue / pipeline status
    PROCESSING = "processing"       # AI processing progress
    SYSTEM = "system"               # System health and status


# ═══════════════════════════════════════════════════
# MESSAGE TYPES
# ═══════════════════════════════════════════════════
class WSMessageType(Enum):
    UPDATE = "update"                # Data update
    ALERT = "alert"                  # Alert/notification
    STATUS = "status"                # Status change
    PROGRESS = "progress"            # Processing progress
    HEARTBEAT = "heartbeat"          # Keep-alive
    ACK = "ack"                      # Acknowledgment
    ERROR = "error"                  # Error notification
    SUBSCRIBE = "subscribe"          # Channel subscription
    UNSUBSCRIBE = "unsubscribe"      # Channel unsubscription


# ═══════════════════════════════════════════════════
# CLIENT CONNECTION
# ═══════════════════════════════════════════════════
@dataclass
class WSClient:
    """Represents a connected WebSocket client."""
    client_id: str
    websocket: WebSocket
    channels: Set[str] = field(default_factory=set)
    rooms: Set[str] = field(default_factory=set)       # e.g., "survey:1", "org:default"
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    messages_sent: int = 0
    messages_received: int = 0
    user_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "channels": list(self.channels),
            "rooms": list(self.rooms),
            "connected_at": datetime.fromtimestamp(self.connected_at).isoformat(),
            "uptime_seconds": round(time.time() - self.connected_at, 1),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "user_id": self.user_id,
        }


# ═══════════════════════════════════════════════════
# WEBSOCKET MANAGER
# ═══════════════════════════════════════════════════
class EnhancedWSManager:
    """
    Enhanced WebSocket manager with channels, rooms, and presence.

    Architecture:
      Event Bus → WSManager → Channel/Room → Connected Clients

    Features:
      - Channel-based message routing (subscribe/unsubscribe)
      - Room isolation (per-survey, per-org)
      - Presence tracking (connected users)
      - Heartbeat monitoring
      - Broadcast, channel-cast, room-cast
      - Integration with AI pipeline events
    """

    def __init__(self):
        self._clients: Dict[str, WSClient] = {}      # client_id → WSClient
        self._lock = threading.Lock()
        self._client_counter = 0

        # Metrics
        self._total_connections = 0
        self._total_disconnections = 0
        self._total_messages_broadcast = 0
        self._total_messages_received = 0

    # ─── Connection Lifecycle ───
    async def connect(
        self,
        websocket: WebSocket,
        channels: Optional[List[str]] = None,
        rooms: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Accept a WebSocket connection and register the client.
        Returns the assigned client_id.
        """
        await websocket.accept()
        with self._lock:
            self._client_counter += 1
            client_id = f"ws-{self._client_counter}"

        client = WSClient(
            client_id=client_id,
            websocket=websocket,
            channels=set(channels or [WSChannel.DASHBOARD.value]),
            rooms=set(rooms or []),
            user_id=user_id,
        )

        with self._lock:
            self._clients[client_id] = client
            self._total_connections += 1

        # Send welcome message
        await self._send_to_client(client, {
            "type": WSMessageType.ACK.value,
            "client_id": client_id,
            "channels": list(client.channels),
            "rooms": list(client.rooms),
            "message": "Connected to AI Survey Engine WebSocket",
        })

        return client_id

    async def disconnect(self, client_id: str):
        """Clean up a disconnected client."""
        with self._lock:
            client = self._clients.pop(client_id, None)
            if client:
                self._total_disconnections += 1

    def get_client(self, client_id: str) -> Optional[WSClient]:
        """Get client by ID."""
        return self._clients.get(client_id)

    # ─── Channel Management ───
    async def subscribe(self, client_id: str, channel: str):
        """Subscribe a client to a channel."""
        client = self._clients.get(client_id)
        if client:
            client.channels.add(channel)
            await self._send_to_client(client, {
                "type": WSMessageType.ACK.value,
                "action": "subscribed",
                "channel": channel,
            })

    async def unsubscribe(self, client_id: str, channel: str):
        """Unsubscribe a client from a channel."""
        client = self._clients.get(client_id)
        if client:
            client.channels.discard(channel)
            await self._send_to_client(client, {
                "type": WSMessageType.ACK.value,
                "action": "unsubscribed",
                "channel": channel,
            })

    # ─── Room Management ───
    async def join_room(self, client_id: str, room: str):
        """Join a client to a room (e.g., 'survey:1')."""
        client = self._clients.get(client_id)
        if client:
            client.rooms.add(room)

    async def leave_room(self, client_id: str, room: str):
        """Remove a client from a room."""
        client = self._clients.get(client_id)
        if client:
            client.rooms.discard(room)

    # ─── Message Broadcasting ───
    async def broadcast(self, message: dict):
        """Broadcast a message to ALL connected clients."""
        disconnected = []
        for client_id, client in list(self._clients.items()):
            success = await self._send_to_client(client, message)
            if not success:
                disconnected.append(client_id)
        for cid in disconnected:
            await self.disconnect(cid)
        self._total_messages_broadcast += 1

    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast to all clients subscribed to a specific channel."""
        message["channel"] = channel
        disconnected = []
        for client_id, client in list(self._clients.items()):
            if channel in client.channels:
                success = await self._send_to_client(client, message)
                if not success:
                    disconnected.append(client_id)
        for cid in disconnected:
            await self.disconnect(cid)
        self._total_messages_broadcast += 1

    async def broadcast_to_room(self, room: str, message: dict):
        """Broadcast to all clients in a specific room."""
        message["room"] = room
        disconnected = []
        for client_id, client in list(self._clients.items()):
            if room in client.rooms:
                success = await self._send_to_client(client, message)
                if not success:
                    disconnected.append(client_id)
        for cid in disconnected:
            await self.disconnect(cid)
        self._total_messages_broadcast += 1

    async def send_to_client_by_id(self, client_id: str, message: dict) -> bool:
        """Send a message to a specific client."""
        client = self._clients.get(client_id)
        if client:
            return await self._send_to_client(client, message)
        return False

    # ─── AI Pipeline Integration ───
    async def notify_pipeline_started(self, survey_id: int, pipeline: str, task_id: str):
        """Notify dashboard that an AI pipeline has started."""
        await self.broadcast_to_channel(WSChannel.PROCESSING.value, {
            "type": WSMessageType.PROGRESS.value,
            "event": "pipeline_started",
            "survey_id": survey_id,
            "pipeline": pipeline,
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
        })

    async def notify_pipeline_completed(self, survey_id: int, pipeline: str, result_summary: dict):
        """Notify dashboard that an AI pipeline has completed."""
        await self.broadcast_to_channel(WSChannel.PROCESSING.value, {
            "type": WSMessageType.STATUS.value,
            "event": "pipeline_completed",
            "survey_id": survey_id,
            "pipeline": pipeline,
            "result": result_summary,
            "timestamp": datetime.now().isoformat(),
        })

    async def notify_insight_discovered(self, survey_id: int, insight: dict):
        """Push new insight to dashboard in real-time."""
        await self.broadcast_to_channel(WSChannel.INSIGHTS.value, {
            "type": WSMessageType.UPDATE.value,
            "event": "new_insight",
            "survey_id": survey_id,
            "insight": insight,
            "timestamp": datetime.now().isoformat(),
        })

    async def notify_alert(self, alert: dict):
        """Push an alert to all subscribed clients."""
        await self.broadcast_to_channel(WSChannel.ALERTS.value, {
            "type": WSMessageType.ALERT.value,
            "alert": alert,
            "timestamp": datetime.now().isoformat(),
        })

    async def notify_dashboard_update(self, survey_id: int, metric: str, value: Any):
        """Push a dashboard metric update."""
        await self.broadcast_to_channel(WSChannel.DASHBOARD.value, {
            "type": WSMessageType.UPDATE.value,
            "event": "metric_update",
            "survey_id": survey_id,
            "metric": metric,
            "value": value,
            "timestamp": datetime.now().isoformat(),
        })

    async def notify_task_status(self, task_id: str, status: str, details: dict = None):
        """Push task processing status update."""
        await self.broadcast_to_channel(WSChannel.TASKS.value, {
            "type": WSMessageType.STATUS.value,
            "event": "task_status",
            "task_id": task_id,
            "status": status,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        })

    # ─── Message Handling ───
    async def handle_message(self, client_id: str, raw_message: str):
        """
        Handle an incoming message from a client.
        Supports: subscribe, unsubscribe, heartbeat, join_room, leave_room
        """
        client = self._clients.get(client_id)
        if not client:
            return

        client.messages_received += 1
        self._total_messages_received += 1
        client.last_heartbeat = time.time()

        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_to_client(client, {"type": "error", "message": "Invalid JSON"})
            return

        msg_type = data.get("type", "")

        if msg_type == WSMessageType.SUBSCRIBE.value:
            channel = data.get("channel", "")
            if channel:
                await self.subscribe(client_id, channel)

        elif msg_type == WSMessageType.UNSUBSCRIBE.value:
            channel = data.get("channel", "")
            if channel:
                await self.unsubscribe(client_id, channel)

        elif msg_type == WSMessageType.HEARTBEAT.value:
            await self._send_to_client(client, {
                "type": WSMessageType.HEARTBEAT.value,
                "timestamp": datetime.now().isoformat(),
            })

        elif msg_type == "join_room":
            room = data.get("room", "")
            if room:
                await self.join_room(client_id, room)

        elif msg_type == "leave_room":
            room = data.get("room", "")
            if room:
                await self.leave_room(client_id, room)

        else:
            await self._send_to_client(client, {
                "type": WSMessageType.ACK.value,
                "message": raw_message,
            })

    # ─── Presence ───
    def get_presence(self) -> dict:
        """Get current connection presence information."""
        channels = {}
        rooms = {}
        for client in self._clients.values():
            for ch in client.channels:
                channels[ch] = channels.get(ch, 0) + 1
            for rm in client.rooms:
                rooms[rm] = rooms.get(rm, 0) + 1

        return {
            "total_connected": len(self._clients),
            "by_channel": channels,
            "by_room": rooms,
            "clients": [c.to_dict() for c in self._clients.values()],
        }

    # ─── Internal ───
    async def _send_to_client(self, client: WSClient, message: dict) -> bool:
        """Send a message to a client. Returns False if connection is dead."""
        try:
            await client.websocket.send_json(message)
            client.messages_sent += 1
            return True
        except Exception:
            return False

    # ─── Stats ───
    def stats(self) -> dict:
        """Full WebSocket manager metrics."""
        return {
            "total_connected": len(self._clients),
            "total_connections_lifetime": self._total_connections,
            "total_disconnections": self._total_disconnections,
            "total_messages_broadcast": self._total_messages_broadcast,
            "total_messages_received": self._total_messages_received,
            "presence": self.get_presence(),
            "channels": [ch.value for ch in WSChannel],
        }


# ═══════════════════════════════════════════════════
# GLOBAL ENHANCED WS MANAGER SINGLETON
# ═══════════════════════════════════════════════════
enhanced_ws_manager = EnhancedWSManager()
