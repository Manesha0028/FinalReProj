from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from passlib.context import CryptContext
import secrets
import string

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str  # admin, manager, supervisor
    disabled: Optional[bool] = False
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    login_attempts: int = 0
    locked_until: Optional[datetime] = None

class UserInDB(User):
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str

class UserLogin(BaseModel):
    username: str
    password: str
    role: str

class UserResponse(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    created_at: datetime

class Session(BaseModel):
    session_id: str
    username: str
    role: str
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(default_factory=lambda: datetime.now() + timedelta(days=1))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class LoginResponse(BaseModel):
    message: str
    username: str
    role: str
    expires_in: int  # seconds

# Password utilities
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def generate_session_id():
    """Generate a secure random session ID"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))