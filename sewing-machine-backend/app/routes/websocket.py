# app/routes/websocket.py
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, Optional
from datetime import datetime
from app.config.database import get_database
import json
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Simple in-memory storage for device status
device_status = {}

# Store connected WebSocket clients
connected_clients: Dict[str, WebSocket] = {}

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
    
    try:
        while True:
            try:
                # Set a timeout to receive messages (60 seconds)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                logger.info(f"📩 Received: {data}")
                
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
                        
                        # Update device status
                        device_status[machine_id] = {
                            "online": True,
                            "last_seen": datetime.now().isoformat(),
                            "device_id": device_id,
                            "last_count": last_count
                        }
                        
                        # Send response
                        response = {
                            "type": "machine_status",
                            "machine_id": machine_id,
                            "last_count": last_count,
                            "status": "online"
                        }
                        await websocket.send_text(json.dumps(response))
                        logger.info(f"📤 Sent machine {machine_id} status, last count: {last_count}")
                        
                    elif msg_type == "count":
                        device_id = message.get("device_id")
                        machine_id = message.get("machine_id")
                        count_value = message.get("count")
                        
                        if count_value is not None:
                            logger.info(f"📊 Count from {machine_id}: {count_value}")
                            
                            # Save to database
                            db = get_database()
                            counter_collection = db["counter_readings"]
                            counter_data = {
                                "count": count_value,
                                "timestamp": datetime.now(),
                                "machine_id": machine_id,
                                "device_id": device_id
                            }
                            result = counter_collection.insert_one(counter_data)
                            
                            # Update device status
                            if machine_id in device_status:
                                device_status[machine_id]["last_count"] = count_value
                                device_status[machine_id]["last_seen"] = datetime.now().isoformat()
                            
                            # Broadcast update to all connected clients
                            update_message = {
                                "type": "count_update",
                                "machine_id": machine_id,
                                "count": count_value,
                                "timestamp": datetime.now().isoformat(),
                                "db_id": str(result.inserted_id)
                            }
                            await broadcast_update(update_message)
                            
                            # Send confirmation to sender
                            await websocket.send_text(json.dumps({
                                "type": "count_update",
                                "count": count_value,
                                "status": "saved",
                                "db_id": str(result.inserted_id)
                            }))
                            
                    elif msg_type == "heartbeat":
                        device_id = message.get("device_id")
                        machine_id = message.get("machine_id")
                        count_value = message.get("count")
                        rssi = message.get("rssi")
                        
                        logger.info(f"💓 Heartbeat from {machine_id}, count: {count_value}")
                        
                        # Update device status
                        device_status[machine_id] = {
                            "online": True,
                            "last_seen": datetime.now().isoformat(),
                            "device_id": device_id,
                            "last_count": count_value,
                            "rssi": rssi
                        }
                        
                        # Broadcast heartbeat to all connected clients
                        heartbeat_message = {
                            "type": "heartbeat",
                            "machine_id": machine_id,
                            "count": count_value,
                            "timestamp": datetime.now().isoformat(),
                            "rssi": rssi
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
        
        # Update status to offline when disconnected
        if machine_id and machine_id in device_status:
            device_status[machine_id]["online"] = False
            logger.info(f"📴 Machine {machine_id} marked as offline")

# ============== REST API ENDPOINTS ==============

@router.get("/api/machines/status")
async def get_all_machines_status():
    """Get status of all machines"""
    return device_status

@router.get("/api/machines/{machine_id}/status")
async def get_single_machine_status(machine_id: str):
    """Get status of specific machine"""
    return device_status.get(machine_id, {"online": False})

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