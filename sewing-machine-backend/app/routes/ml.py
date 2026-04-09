# app/routes/ml.py
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from typing import Dict, Optional, List, Any, Union
from app.ml.service import ml_service, OUTPUT_COLUMNS
from app.utils.auth import get_current_user_from_session
from datetime import datetime

router = APIRouter(prefix="/ml", tags=["machine-learning"])

# ----------------------------
# Request/Response Models
# ----------------------------
class PredictRequest(BaseModel):
    Fabric_Type: str
    M_Year: int
    usageDict: Dict[str, float]

    @field_validator('Fabric_Type')
    @classmethod
    def validate_fabric(cls, v):
        if v not in ['Heavy', 'Medium']:
            raise ValueError("Fabric_Type must be 'Heavy' or 'Medium'")
        return v

class PredictResponse(BaseModel):
    predictions: Dict[str, str]
    timestamp: datetime
    username: Optional[str] = None

class ComponentHealthRequest(BaseModel):
    Fabric_Type: str
    M_Year: int
    usageDict: Dict[str, float]

class ComponentHealthResponse(BaseModel):
    component: str
    status: str
    message: str
    priority: str

class MachineData(BaseModel):
    Fabric_Type: str
    M_Year: int
    usageDict: Dict[str, float]

class BulkPredictRequest(BaseModel):
    machines: List[MachineData]  # Use the MachineData model instead of Dict

class BulkPredictResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_machines: int
    successful: int
    failed: int
    timestamp: datetime
    username: Optional[str] = None

# ----------------------------
# Authentication dependency
# ----------------------------
async def get_current_user_from_request(request: Request):
    user = await get_current_user_from_session(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

# ----------------------------
# ML Routes
# ----------------------------
@router.post("/predict", response_model=PredictResponse)
async def predict_component_maintenance(
    request: Request,
    payload: PredictRequest,
    user: dict = Depends(get_current_user_from_request)
):
    """
    Predict maintenance requirements for sewing machine components.
    Requires authentication.
    """
    # Check if ML service is available
    if ml_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML models not loaded. Please ensure model files are in the correct location."
        )
    
    try:
        # Make prediction using ML service
        predictions = ml_service.predict(
            fabric_type=payload.Fabric_Type,
            manufacturing_year=payload.M_Year,
            usage_dict=payload.usageDict
        )
        
        return PredictResponse(
            predictions=predictions,
            timestamp=datetime.now(),
            username=user.get("username")
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.post("/health-status", response_model=Dict[str, ComponentHealthResponse])
async def get_component_health_status(
    request: Request,
    payload: ComponentHealthRequest,
    user: dict = Depends(get_current_user_from_request)
):
    """
    Get detailed health status for all components with priority levels.
    Requires authentication.
    """
    # Check if ML service is available
    if ml_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML models not loaded. Please ensure model files are in the correct location."
        )
    
    try:
        health_status = ml_service.get_component_health_status(
            fabric_type=payload.Fabric_Type,
            manufacturing_year=payload.M_Year,
            usage_dict=payload.usageDict
        )
        
        return health_status
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/components")
async def get_component_list(
    user: dict = Depends(get_current_user_from_request)
):
    """
    Get list of all components that can be predicted.
    Requires authentication.
    """
    return {
        "components": OUTPUT_COLUMNS,
        "fabric_types": ["Heavy", "Medium"],
        "count": len(OUTPUT_COLUMNS)
    }

@router.post("/bulk-predict", response_model=BulkPredictResponse)
async def bulk_predict(
    request: Request,
    payload: BulkPredictRequest,
    user: dict = Depends(get_current_user_from_request)
):
    """
    Predict maintenance for multiple machines at once.
    Requires authentication.
    """
    # Check if ML service is available
    if ml_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML models not loaded. Please ensure model files are in the correct location."
        )
    
    results = []
    
    for idx, machine in enumerate(payload.machines):
        try:
            # Make prediction
            predictions = ml_service.predict(
                fabric_type=machine.Fabric_Type,
                manufacturing_year=machine.M_Year,
                usage_dict=machine.usageDict
            )
            
            results.append({
                "machine_index": idx,
                "predictions": predictions,
                "success": True
            })
            
        except Exception as e:
            results.append({
                "machine_index": idx,
                "error": str(e),
                "success": False
            })
    
    return BulkPredictResponse(
        results=results,
        total_machines=len(payload.machines),
        successful=sum(1 for r in results if r["success"]),
        failed=sum(1 for r in results if not r["success"]),
        timestamp=datetime.now(),
        username=user.get("username")
    )