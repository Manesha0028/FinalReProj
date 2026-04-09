from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException, status
from app.models.user import UserInDB, verify_password, generate_session_id
from app.config.database import get_users_collection, get_sessions_collection
import os
from dotenv import load_dotenv

load_dotenv()

# Security settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 15  # minutes

async def authenticate_user(username: str, password: str, role: str, request: Request):
    """Authenticate user with MongoDB verification"""
    users_collection = get_users_collection()
    
    # Find user in MongoDB
    user_data = users_collection.find_one({"username": username, "role": role})
    
    if not user_data:
        return None, "User not found"
    
    user = UserInDB(**user_data)
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.now():
        remaining = (user.locked_until - datetime.now()).seconds // 60
        return None, f"Account locked. Try again in {remaining} minutes"
    
    # Verify password
    if not verify_password(password, user.hashed_password):
        # Increment login attempts
        users_collection.update_one(
            {"username": username},
            {
                "$inc": {"login_attempts": 1},
                "$set": {"last_login_attempt": datetime.now()}
            }
        )
        
        # Check if should lock account
        if user.login_attempts + 1 >= MAX_LOGIN_ATTEMPTS:
            users_collection.update_one(
                {"username": username},
                {"$set": {"locked_until": datetime.now() + timedelta(minutes=LOCKOUT_TIME)}}
            )
            return None, f"Too many failed attempts. Account locked for {LOCKOUT_TIME} minutes"
        
        remaining_attempts = MAX_LOGIN_ATTEMPTS - (user.login_attempts + 1)
        return None, f"Invalid password. {remaining_attempts} attempts remaining"
    
    # Successful login - reset attempts and update last login
    users_collection.update_one(
        {"username": username},
        {
            "$set": {
                "last_login": datetime.now(),
                "login_attempts": 0,
                "locked_until": None
            }
        }
    )
    
    return user, "Login successful"

async def create_session(user: UserInDB, request: Request):
    """Create a new session in MongoDB"""
    sessions_collection = get_sessions_collection()
    
    # Generate unique session ID
    session_id = generate_session_id()
    
    # Create session document
    session = {
        "session_id": session_id,
        "username": user.username,
        "role": user.role,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(days=1),
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent")
    }
    
    # Store in MongoDB
    sessions_collection.insert_one(session)
    
    return session_id, session["expires_at"]

async def verify_session(session_id: str) -> Optional[dict]:
    """Verify if session is valid in MongoDB"""
    if not session_id:
        return None
    
    sessions_collection = get_sessions_collection()
    
    # Find active session
    session = sessions_collection.find_one({
        "session_id": session_id,
        "expires_at": {"$gt": datetime.now()}
    })
    
    if session:
        # Get user data
        users_collection = get_users_collection()
        user = users_collection.find_one({"username": session["username"]})
        if user and not user.get("disabled", False):
            return {
                "username": session["username"],
                "role": session["role"],
                "session_id": session_id
            }
    
    return None

async def delete_session(session_id: str):
    """Delete session from MongoDB (logout)"""
    sessions_collection = get_sessions_collection()
    sessions_collection.delete_one({"session_id": session_id})

async def cleanup_expired_sessions():
    """Remove expired sessions from MongoDB"""
    sessions_collection = get_sessions_collection()
    sessions_collection.delete_many({"expires_at": {"$lt": datetime.now()}})

async def get_current_user_from_session(request: Request):
    """Extract user from session cookie and verify with MongoDB"""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        return None
    
    return await verify_session(session_id)