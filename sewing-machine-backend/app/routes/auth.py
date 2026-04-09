# app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from app.models.user import UserCreate, UserLogin, UserInDB, get_password_hash
from app.utils.auth import (
    authenticate_user, create_session, verify_session, 
    delete_session, get_current_user_from_session,
    cleanup_expired_sessions
)
from app.config.database import get_users_collection
from typing import Any
import logging

# Notice: NO prefix here - the prefix is set in main.py
router = APIRouter()

@router.post("/register")
async def register_user(user: UserCreate):
    """Register a new user"""
    users_collection = get_users_collection()
    
    # Check if username already exists
    existing_user = users_collection.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if role is valid
    if user.role not in ["admin", "manager", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be admin, manager, or supervisor"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict.pop("password")
    
    user_in_db = UserInDB(
        **user_dict,
        hashed_password=hashed_password,
        login_attempts=0,
        disabled=False
    )
    
    # Insert into database
    result = users_collection.insert_one(user_in_db.dict())
    
    return {
        "message": "User created successfully",
        "username": user.username,
        "role": user.role,
        "id": str(result.inserted_id)
    }

@router.post("/login")
async def login(response: Response, login_data: UserLogin, request: Request):
    """Login user and create session"""
    # Clean up expired sessions
    await cleanup_expired_sessions()
    
    # Authenticate user with MongoDB
    user, message = await authenticate_user(
        login_data.username, 
        login_data.password, 
        login_data.role,
        request
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message
        )
    
    # Create session in MongoDB
    session_id, expires_at = await create_session(user, request)
    
    # Set HTTP-only cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=24*60*60,
        path="/"
    )
    
    # Calculate expires in seconds
    expires_in = int((expires_at - datetime.now()).total_seconds())
    
    return {
        "message": "Login successful",
        "username": user.username,
        "role": user.role,
        "expires_in": expires_in
    }

@router.post("/logout")
async def logout(response: Response, request: Request):
    """Logout user and destroy session"""
    session_id = request.cookies.get("session_id")
    
    if session_id:
        await delete_session(session_id)
    
    response.delete_cookie(
        key="session_id",
        path="/",
        httponly=True,
        samesite="lax"
    )
    
    return {"message": "Logged out successfully"}

@router.get("/verify")
async def verify_auth(request: Request):
    """Verify if user is authenticated"""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        return {"authenticated": False}
    
    user_data = await verify_session(session_id)
    
    if user_data:
        return {
            "authenticated": True,
            "username": user_data["username"],
            "role": user_data["role"]
        }
    
    return {"authenticated": False}

@router.get("/me")
async def get_current_user(request: Request):
    """Get current authenticated user info"""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    user_data = await verify_session(session_id)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    return {
        "username": user_data["username"],
        "role": user_data["role"],
        "authenticated": True
    }