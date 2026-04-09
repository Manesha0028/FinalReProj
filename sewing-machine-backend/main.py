# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.database import Database
from app.routes import auth, protected, ml  # Add ml here
import os
from dotenv import load_dotenv
from app.routes import auth, protected, ml, machines
from app.routes import auth, protected, ml, machines, websocket

load_dotenv()

app = FastAPI(title="Sewing Machine Management API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(protected.router, prefix="/api", tags=["protected"])
app.include_router(ml.router, prefix="/api", tags=["machine-learning"])  
app.include_router(machines.router, prefix="/api", tags=["machines"])
app.include_router(websocket.router, tags=["websocket"])  #IOT WebSocket route

@app.on_event("startup")
async def startup_event():
    try:
        Database.connect()
        print("🚀 Application started successfully")
    except Exception as e:
        print(f"⚠️ Application starting without database connection: {e}")

@app.on_event("startup")
async def print_routes():
    print("\n📋 Registered Routes:")
    for route in app.routes:
        if hasattr(route, "methods"):
            print(f"   {route.methods} {route.path}")
    print()

@app.on_event("shutdown")
async def shutdown_event():
    Database.close()

@app.get("/")
async def root():
    return {
        "message": "Sewing Machine Management API",
        "endpoints": {
            "auth": "/auth",
            "api": "/api",
            "ml": "/api/ml",  # Add this
            "docs": "/docs",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    try:
        db = Database.get_db()
        db.command('ping')
        return {
            "status": "healthy",
            "database": "connected",
            "ml_model": "loaded"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "database": "disconnected",
            "error": str(e)
        }