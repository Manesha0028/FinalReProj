# app/routes/protected.py
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.utils.auth import get_current_user_from_session
from typing import Optional

router = APIRouter()

async def get_current_user_dependency(request: Request):
    user = await get_current_user_from_session(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user

def require_role(required_role: str):
    async def role_checker(request: Request, user: dict = Depends(get_current_user_dependency)):
        if user["role"] != required_role and user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires {required_role} role"
            )
        return user
    return role_checker

@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user_dependency)):
    """Dashboard accessible by all authenticated users"""
    return {
        "message": f"Welcome to your dashboard, {user['username']}!",
        "role": user["role"],
        "permissions": {
            "can_view_all_machines": user["role"] in ["admin", "manager"],
            "can_edit_machines": user["role"] == "admin",
            "can_view_reports": user["role"] != "supervisor",
            "can_manage_users": user["role"] == "admin"
        }
    }

@router.get("/admin-only")
async def admin_endpoint(user: dict = Depends(require_role("admin"))):
    return {
        "message": "This is an admin-only endpoint",
        "user": user["username"],
        "role": user["role"]
    }

@router.get("/manager-only")
async def manager_endpoint(user: dict = Depends(require_role("manager"))):
    return {
        "message": "This endpoint is for managers and admins",
        "user": user["username"],
        "role": user["role"]
    }

@router.get("/supervisor-only")
async def supervisor_endpoint(user: dict = Depends(require_role("supervisor"))):
    return {
        "message": "This endpoint is for supervisors and admins",
        "user": user["username"],
        "role": user["role"]
    }