# app/routes/machines.py
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.config.database import get_database
from app.utils.auth import get_current_user_from_session
from bson import ObjectId

router = APIRouter(prefix="/machines", tags=["machines"])

class MachineData(BaseModel):
    machineId: str
    brandName: str
    machineType: str
    fabricType: str
    manufacturingYear: int
    usageHours: Dict[str, float]
    predictions: Dict[str, Any]
    lastPrediction: str
    workingTimeSeconds: Optional[int] = 0
    currentStatus: Optional[str] = "offline"
    currentOnlineSince: Optional[str] = None

class MachineResponse(MachineData):
    id: str
    createdAt: str

async def get_current_user(request: Request):
    user = await get_current_user_from_session(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

@router.post("")
async def save_machine(
    request: Request,
    machine_data: MachineData,
    user: dict = Depends(get_current_user)
):
    """Save machine data to MongoDB"""
    try:
        db = get_database()
        machines_collection = db["machines"]
        
        # Add metadata
        machine_dict = machine_data.dict()
        machine_dict["createdAt"] = datetime.now().isoformat()
        machine_dict["createdBy"] = user.get("username")
        machine_dict["updatedAt"] = datetime.now().isoformat()

        # Check if machine already exists
        existing = machines_collection.find_one({"machineId": machine_data.machineId})

        # Preserve live-status fields if the machine already exists
        if existing:
            incoming_working_seconds = int(machine_dict.get("workingTimeSeconds", 0) or 0)
            existing_working_seconds = int(existing.get("workingTimeSeconds", 0) or 0)
            machine_dict["workingTimeSeconds"] = max(existing_working_seconds, incoming_working_seconds)
            machine_dict["currentStatus"] = existing.get("currentStatus", "offline")
            machine_dict["currentOnlineSince"] = existing.get("currentOnlineSince")
        else:
            machine_dict["workingTimeSeconds"] = int(machine_dict.get("workingTimeSeconds", 0) or 0)
            machine_dict["currentStatus"] = machine_dict.get("currentStatus") or "offline"
            machine_dict["currentOnlineSince"] = machine_dict.get("currentOnlineSince")
        
        if existing:
            # Update existing machine
            result = machines_collection.update_one(
                {"machineId": machine_data.machineId},
                {"$set": {
                    **machine_dict,
                    "updatedAt": datetime.now().isoformat()
                }}
            )
            return {
                "message": "Machine updated successfully",
                "machineId": machine_data.machineId,
                "updated": True
            }
        else:
            # Insert new machine
            result = machines_collection.insert_one(machine_dict)
            return {
                "message": "Machine saved successfully",
                "machineId": machine_data.machineId,
                "id": str(result.inserted_id)
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save machine: {str(e)}"
        )

@router.get("")
async def get_machines(
    request: Request,
    user: dict = Depends(get_current_user),
    limit: int = 50,
    skip: int = 0
):
    """Get all saved machines"""
    try:
        db = get_database()
        machines_collection = db["machines"]
        
        machines = machines_collection.find(
            {"createdBy": user.get("username")}
        ).sort("createdAt", -1).skip(skip).limit(limit)
        
        result = []
        for machine in machines:
            machine["id"] = str(machine["_id"])
            del machine["_id"]
            result.append(machine)
        
        return {"machines": result, "total": len(result)}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch machines: {str(e)}"
        )

@router.get("/{machine_id}")
async def get_machine(
    request: Request,
    machine_id: str,
    user: dict = Depends(get_current_user)
):
    """Get a specific machine by ID"""
    try:
        db = get_database()
        machines_collection = db["machines"]
        
        machine = machines_collection.find_one({
            "$or": [
                {"machineId": machine_id},
                {"_id": ObjectId(machine_id) if ObjectId.is_valid(machine_id) else None}
            ]
        })
        
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Machine not found"
            )
        
        machine["id"] = str(machine["_id"])
        del machine["_id"]
        
        return machine
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch machine: {str(e)}"
        )

@router.delete("/{machine_id}")
async def delete_machine(
    request: Request,
    machine_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a machine by ID"""
    try:
        db = get_database()
        machines_collection = db["machines"]
        
        result = machines_collection.delete_one({
            "$and": [
                {"machineId": machine_id},
                {"createdBy": user.get("username")}
            ]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Machine not found"
            )
        
        return {"message": "Machine deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete machine: {str(e)}"
        )