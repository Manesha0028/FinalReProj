# app/routes/websocket.py
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, Optional
from datetime import datetime
from app.config.database import get_database
import json
import logging
import asyncio
from time import monotonic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Simple in-memory storage for device status
device_status = {}

# Count-based online window used by UI/logic.
ONLINE_TIMEOUT_SECONDS = 5
COUNT_PERSIST_INTERVAL_SECONDS = 0.25
COUNT_PERSIST_STEP = 3

# Store connected WebSocket clients
connected_clients: Dict[str, WebSocket] = {}


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def persist_offline_if_inactive(machine_id: str, machine: Optional[dict] = None) -> Optional[dict]:
    """If machine timed out by inactivity, persist offline state at exact stop time (lastSeenAt)."""
    db = get_database()
    machines_collection = db["machines"]
    machine_doc = machine or machines_collection.find_one({"machineId": machine_id})
    if not machine_doc:
        return None

    if machine_doc.get("currentStatus") != "online":
        return machine_doc

    now = datetime.now()
    now_iso = now.isoformat()
    last_seen_at = parse_iso_datetime(machine_doc.get("lastSeenAt"))
    online_since = parse_iso_datetime(machine_doc.get("currentOnlineSince"))

    if not last_seen_at or not online_since:
        return machine_doc

    if (now - last_seen_at).total_seconds() <= ONLINE_TIMEOUT_SECONDS:
        return machine_doc

    persisted_seconds = int(machine_doc.get("workingTimeSeconds", 0) or 0)
    elapsed_until_stop = max(0, int((last_seen_at - online_since).total_seconds()))
    total_seconds = persisted_seconds + elapsed_until_stop

    machines_collection.update_one(
        {"machineId": machine_id},
        {
            "$set": {
                "currentStatus": "offline",
                "currentOnlineSince": None,
                "workingTimeSeconds": total_seconds,
                "lastSeenAt": last_seen_at.isoformat(),
                "updatedAt": now_iso,
            }
        },
    )

    return machines_collection.find_one({"machineId": machine_id})


def build_machine_status(machine_id: str, fallback_last_count: int = 0) -> dict:
    """Read persisted status fields from MongoDB and normalize for websocket/API responses."""
    db = get_database()
    machines_collection = db["machines"]
    machine = machines_collection.find_one({"machineId": machine_id}) or {}
    if machine:
        machine = persist_offline_if_inactive(machine_id, machine) or machine

    persisted_seconds = int(machine.get("workingTimeSeconds", 0) or 0)
    online_since = machine.get("currentOnlineSince")
    current_status = machine.get("currentStatus", "offline")

    # Keep last count in sync with DB if available, otherwise use fallback.
    last_count = machine.get("last_count")
    if last_count is None:
        last_count = device_status.get(machine_id, {}).get("last_count", fallback_last_count)

    return {
        "machine_id": machine_id,
        "current_status": current_status,
        "online": current_status == "online",
        "online_since": online_since,
        "working_time_seconds": persisted_seconds,
        "last_count": int(last_count or 0),
        "last_seen": machine.get("lastSeenAt") or device_status.get(machine_id, {}).get("last_seen"),
    }


def mark_machine_online(machine_id: str, device_id: Optional[str], count_value: Optional[int] = None, rssi: Optional[int] = None, persist_db: bool = True) -> dict:
    """Mark machine online and keep websocket state fast even when DB writes are throttled."""
    now = datetime.now()
    now_iso = now.isoformat()
    cached_state = device_status.get(machine_id, {})

    if persist_db:
        db = get_database()
        machines_collection = db["machines"]

        machine = machines_collection.find_one({"machineId": machine_id})
        if machine:
            machine = persist_offline_if_inactive(machine_id, machine) or machine

        if machine:
            update_fields = {
                "currentStatus": "online",
                "lastSeenAt": now_iso,
                "updatedAt": now_iso,
            }

            if machine.get("currentStatus") != "online" or not machine.get("currentOnlineSince"):
                update_fields["currentOnlineSince"] = now_iso

            if count_value is not None:
                update_fields["last_count"] = int(count_value)

            machines_collection.update_one({"machineId": machine_id}, {"$set": update_fields})

        status_snapshot = build_machine_status(machine_id, fallback_last_count=int(count_value or 0))
    else:
        status_snapshot = {
            "machine_id": machine_id,
            "current_status": "online",
            "online": True,
            "online_since": cached_state.get("online_since") or now_iso,
            "working_time_seconds": int(cached_state.get("working_time_seconds", 0) or 0),
            "last_count": int(count_value if count_value is not None else cached_state.get("last_count", 0) or 0),
            "last_seen": now_iso,
        }

    device_status[machine_id] = {
        **cached_state,
        "online": True,
        "last_seen": status_snapshot.get("last_seen") or now_iso,
        "device_id": device_id,
        "last_count": status_snapshot["last_count"],
        "rssi": rssi if rssi is not None else cached_state.get("rssi"),
        "online_since": status_snapshot["online_since"],
        "working_time_seconds": status_snapshot["working_time_seconds"],
    }

    return status_snapshot


def should_persist_count(machine_id: str, count_value: int) -> bool:
    state = device_status.setdefault(machine_id, {})
    now = monotonic()
    last_persisted_at = float(state.get("last_persisted_at", 0.0) or 0.0)
    raw_last_persisted_count = state.get("last_persisted_count")
    last_persisted_count = int(raw_last_persisted_count) if raw_last_persisted_count is not None else -1

    should_persist = (
        last_persisted_count < 0
        or abs(int(count_value) - last_persisted_count) >= COUNT_PERSIST_STEP
        or (now - last_persisted_at) >= COUNT_PERSIST_INTERVAL_SECONDS
    )

    if should_persist:
        state["last_persisted_at"] = now
        state["last_persisted_count"] = int(count_value)

    return should_persist


def persist_count_update_sync(machine_id: str, device_id: Optional[str], count_value: int) -> None:
    db = get_database()
    counter_collection = db["counter_readings"]
    counter_collection.insert_one({
        "count": int(count_value),
        "timestamp": datetime.now(),
        "machine_id": machine_id,
        "device_id": device_id,
    })
    mark_machine_online(machine_id, device_id, count_value=int(count_value), persist_db=True)


async def persist_count_update_async(machine_id: str, device_id: Optional[str], count_value: int) -> None:
    try:
        await asyncio.to_thread(persist_count_update_sync, machine_id, device_id, int(count_value))
    except Exception as e:
        logger.error(f"Failed to persist count for {machine_id}: {e}")


def mark_machine_offline(machine_id: str) -> dict:
    """Close online session and persist accumulated working time when machine disconnects."""
    now = datetime.now()
    now_iso = now.isoformat()
    db = get_database()
    machines_collection = db["machines"]
    machine = machines_collection.find_one({"machineId": machine_id}) or {}

    persisted_seconds = int(machine.get("workingTimeSeconds", 0) or 0)
    online_since = parse_iso_datetime(machine.get("currentOnlineSince"))

    stop_time = parse_iso_datetime(machine.get("lastSeenAt")) or now
    stop_time_iso = stop_time.isoformat()

    elapsed = 0
    if machine.get("currentStatus") == "online" and online_since:
        elapsed = max(0, int((stop_time - online_since).total_seconds()))

    total_seconds = persisted_seconds + elapsed

    if machine:
        machines_collection.update_one(
            {"machineId": machine_id},
            {
                "$set": {
                    "currentStatus": "offline",
                    "currentOnlineSince": None,
                    "workingTimeSeconds": total_seconds,
                    "lastSeenAt": stop_time_iso,
                    "updatedAt": now_iso,
                }
            },
        )

    previous = device_status.get(machine_id, {})
    device_status[machine_id] = {
        **previous,
        "online": False,
        "online_since": None,
        "last_seen": stop_time_iso,
        "working_time_seconds": total_seconds,
    }

    return {
        "machine_id": machine_id,
        "current_status": "offline",
        "online": False,
        "online_since": None,
        "working_time_seconds": total_seconds,
        "last_count": int(device_status[machine_id].get("last_count", 0) or 0),
        "last_seen": stop_time_iso,
    }

async def broadcast_update(message: dict):
    """Broadcast a message to all connected clients"""
    disconnected_clients = []
    for client_id, websocket in connected_clients.items():
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send to client {client_id}: {e}")
            disconnected_clients.append(client_id)
    
    # Remove disconnected clients
    for client_id in disconnected_clients:
        del connected_clients[client_id]

@router.websocket("/ws/counter")
async def websocket_endpoint(websocket: WebSocket):
    # Accept the connection first
    await websocket.accept()
    logger.info("✅ WebSocket connection accepted")
    
    # Generate unique client ID
    client_id = f"{datetime.now().timestamp()}_{id(websocket)}"
    connected_clients[client_id] = websocket
    logger.info(f"👤 Client {client_id} connected. Total clients: {len(connected_clients)}")
    
    device_id = None
    machine_id = None
    is_device_connection = False
    
    try:
        while True:
            try:
                # Set a timeout to receive messages (60 seconds)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                logger.debug(f"📩 Received: {data}")
                
                try:
                    message = json.loads(data)
                    msg_type = message.get("type")
                    
                    if msg_type == "get_machine_status":
                        device_id = message.get("device_id")
                        machine_id = message.get("machine_id")
                        
                        logger.info(f"📱 Device {device_id} connecting for machine {machine_id}")
                        
                        # Get last count from database
                        db = get_database()
                        counter_collection = db["counter_readings"]
                        last_reading = counter_collection.find_one(
                            {"machine_id": machine_id},
                            sort=[("timestamp", -1)]
                        )
                        last_count = last_reading["count"] if last_reading else 0
                        
                        persisted_status = build_machine_status(machine_id, fallback_last_count=last_count)

                        # Keep cache in sync for UI readers.
                        device_status[machine_id] = {
                            "online": persisted_status["online"],
                            "last_seen": persisted_status["last_seen"],
                            "device_id": device_id,
                            "last_count": persisted_status["last_count"],
                            "online_since": persisted_status["online_since"],
                            "working_time_seconds": persisted_status["working_time_seconds"],
                        }
                        
                        # Send response
                        response = {
                            "type": "machine_status",
                            "machine_id": machine_id,
                            "last_count": persisted_status["last_count"],
                            "status": persisted_status["current_status"],
                            "online": persisted_status["online"],
                            "online_since": persisted_status["online_since"],
                            "working_time_seconds": persisted_status["working_time_seconds"],
                            "last_seen": persisted_status["last_seen"],
                        }
                        await websocket.send_text(json.dumps(response))
                        logger.info(f"📤 Sent machine {machine_id} status, last count: {persisted_status['last_count']}")
                        
                    elif msg_type == "count":
                        device_id = message.get("device_id")
                        machine_id = message.get("machine_id")
                        count_value = message.get("count")

                        if count_value is not None:
                            is_device_connection = True
                            count_value = int(count_value)
                            logger.debug(f"📊 Count from {machine_id}: {count_value}")

                            # Update websocket clients immediately without waiting on MongoDB.
                            status_snapshot = mark_machine_online(
                                machine_id,
                                device_id,
                                count_value=count_value,
                                persist_db=False,
                            )

                            update_message = {
                                "type": "count_update",
                                "machine_id": machine_id,
                                "count": count_value,
                                "timestamp": datetime.now().isoformat(),
                                "db_id": None,
                                "status": status_snapshot["current_status"],
                                "online": status_snapshot["online"],
                                "online_since": status_snapshot["online_since"],
                                "working_time_seconds": status_snapshot["working_time_seconds"],
                                "last_seen": status_snapshot["last_seen"],
                            }
                            await broadcast_update(update_message)

                            # Persist snapshots in the background at a controlled rate.
                            if should_persist_count(machine_id, count_value):
                                asyncio.create_task(persist_count_update_async(machine_id, device_id, count_value))

                            await websocket.send_text(json.dumps({
                                "type": "count_ack",
                                "machine_id": machine_id,
                                "count": count_value,
                            }))
                            
                    elif msg_type == "heartbeat":
                        device_id = message.get("device_id")
                        machine_id = message.get("machine_id")
                        count_value = message.get("count")
                        rssi = message.get("rssi")

                        is_device_connection = True
                        
                        logger.debug(f"💓 Heartbeat from {machine_id}, count: {count_value}")

                        # Heartbeat should not change machine online/offline state.
                        # Machine is considered online only when a new count update arrives.
                        status_snapshot = build_machine_status(machine_id, fallback_last_count=int(count_value or 0))

                        existing_state = device_status.get(machine_id, {})
                        device_status[machine_id] = {
                            **existing_state,
                            "device_id": device_id,
                            "rssi": rssi,
                            "last_count": int(count_value or status_snapshot["last_count"] or 0),
                            "online": status_snapshot["online"],
                            "online_since": status_snapshot["online_since"],
                            "working_time_seconds": status_snapshot["working_time_seconds"],
                        }

                        if count_value is not None and should_persist_count(machine_id, int(count_value)):
                            asyncio.create_task(persist_count_update_async(machine_id, device_id, int(count_value)))
                        
                        # Broadcast heartbeat to all connected clients
                        heartbeat_message = {
                            "type": "heartbeat",
                            "machine_id": machine_id,
                            "count": count_value,
                            "timestamp": datetime.now().isoformat(),
                            "rssi": rssi,
                            "status": status_snapshot["current_status"],
                            "online": status_snapshot["online"],
                            "online_since": status_snapshot["online_since"],
                            "working_time_seconds": status_snapshot["working_time_seconds"],
                            "last_seen": status_snapshot["last_seen"],
                        }
                        await broadcast_update(heartbeat_message)
                        
                        # Send heartbeat acknowledgment to sender
                        await websocket.send_text(json.dumps({
                            "type": "heartbeat_ack",
                            "machine_id": machine_id,
                            "timestamp": datetime.now().isoformat()
                        }))
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON: {e}")
                    
            except asyncio.TimeoutError:
                # Send a ping to keep connection alive
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    logger.debug("📡 Ping sent")
                except:
                    break
            except WebSocketDisconnect:
                logger.info(f"❌ WebSocket disconnected for machine {machine_id}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"❌ WebSocket disconnected for machine {machine_id}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        # Remove client from connected clients
        if client_id in connected_clients:
            del connected_clients[client_id]
            logger.info(f"👤 Client {client_id} disconnected. Total clients: {len(connected_clients)}")
        
        # Only device sockets should change machine presence on disconnect.
        if machine_id and is_device_connection:
            offline_snapshot = mark_machine_offline(machine_id)
            logger.info(f"📴 Machine {machine_id} marked as offline")
            await broadcast_update({
                "type": "machine_status",
                "machine_id": machine_id,
                "status": offline_snapshot["current_status"],
                "online": offline_snapshot["online"],
                "online_since": offline_snapshot["online_since"],
                "working_time_seconds": offline_snapshot["working_time_seconds"],
                "last_count": offline_snapshot["last_count"],
                "last_seen": offline_snapshot["last_seen"],
            })

# ============== REST API ENDPOINTS ==============

@router.get("/api/machines/status")
async def get_all_machines_status():
    """Get status of all machines"""
    try:
        db = get_database()
        machines_collection = db["machines"]
        machine_ids = [m.get("machineId") for m in machines_collection.find({}, {"machineId": 1, "_id": 0}) if m.get("machineId")]

        status_map = {}
        for machine_id in machine_ids:
            status_map[machine_id] = build_machine_status(machine_id)

        # Include ephemeral entries that might not be saved in machines collection yet.
        for machine_id, state in device_status.items():
            if machine_id not in status_map:
                status_map[machine_id] = {
                    "machine_id": machine_id,
                    "current_status": "online" if state.get("online") else "offline",
                    "online": bool(state.get("online")),
                    "online_since": state.get("online_since"),
                    "working_time_seconds": int(state.get("working_time_seconds", 0) or 0),
                    "last_count": int(state.get("last_count", 0) or 0),
                    "last_seen": state.get("last_seen"),
                }

        return status_map
    except Exception as e:
        logger.error(f"Error fetching machine status map: {e}")
        return device_status

@router.get("/api/machines/{machine_id}/status")
async def get_single_machine_status(machine_id: str):
    """Get status of specific machine"""
    try:
        return build_machine_status(machine_id)
    except Exception as e:
        logger.error(f"Error fetching machine status for {machine_id}: {e}")
        fallback = device_status.get(machine_id, {})
        return {
            "machine_id": machine_id,
            "current_status": "online" if fallback.get("online") else "offline",
            "online": bool(fallback.get("online")),
            "online_since": fallback.get("online_since"),
            "working_time_seconds": int(fallback.get("working_time_seconds", 0) or 0),
            "last_count": int(fallback.get("last_count", 0) or 0),
            "last_seen": fallback.get("last_seen"),
        }

@router.get("/api/counter/history")
async def get_counter_history(device_id: str = "0028", limit: int = 20):
    """Get counter history for a specific device"""
    try:
        db = get_database()
        counter_collection = db["counter_readings"]
        
        # Query using device_id or machine_id
        query = {
            "$or": [
                {"device_id": device_id},
                {"machine_id": device_id}
            ]
        }
        
        readings = counter_collection.find(query).sort("timestamp", -1).limit(limit)
        
        result = []
        for reading in readings:
            result.append({
                "id": str(reading["_id"]),
                "count": reading["count"],
                "timestamp": reading["timestamp"].isoformat(),
                "machine_id": reading.get("machine_id"),
                "device_id": reading.get("device_id")
            })
        
        logger.info(f"📊 Found {len(result)} readings for device {device_id}")
        return {"readings": result, "total": len(result)}
        
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return {"readings": [], "total": 0, "error": str(e)}

@router.get("/api/counter/latest")
async def get_latest_reading(device_id: str = "0028"):
    """Get the latest counter reading for a device"""
    try:
        db = get_database()
        counter_collection = db["counter_readings"]
        
        # Query using device_id or machine_id
        query = {
            "$or": [
                {"device_id": device_id},
                {"machine_id": device_id}
            ]
        }
        
        latest = counter_collection.find_one(
            query,
            sort=[("timestamp", -1)]
        )
        
        if latest:
            return {
                "id": str(latest["_id"]),
                "count": latest["count"],
                "timestamp": latest["timestamp"].isoformat(),
                "machine_id": latest.get("machine_id"),
                "device_id": latest.get("device_id")
            }
        else:
            return {"count": 0, "message": "No readings yet", "device_id": device_id}
            
    except Exception as e:
        logger.error(f"Error fetching latest: {e}")
        return {"count": 0, "error": str(e)}

@router.get("/api/counter/stats/{device_id}")
async def get_counter_stats(device_id: str = "0028"):
    """Get statistics for a device counter"""
    try:
        db = get_database()
        counter_collection = db["counter_readings"]
        
        query = {
            "$or": [
                {"device_id": device_id},
                {"machine_id": device_id}
            ]
        }
        
        # Get total count
        total_readings = counter_collection.count_documents(query)
        
        # Get first and last reading
        first = counter_collection.find_one(query, sort=[("timestamp", 1)])
        last = counter_collection.find_one(query, sort=[("timestamp", -1)])
        
        # Get today's readings
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_query = {
            "$and": [
                query,
                {"timestamp": {"$gte": today_start}}
            ]
        }
        today_count = counter_collection.count_documents(today_query)
        
        return {
            "device_id": device_id,
            "total_readings": total_readings,
            "first_reading": first["timestamp"].isoformat() if first else None,
            "last_reading": last["timestamp"].isoformat() if last else None,
            "last_count": last["count"] if last else 0,
            "today_readings": today_count
        }
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {"error": str(e)}