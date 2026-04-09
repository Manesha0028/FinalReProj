# init_db.py
from pymongo import MongoClient
from passlib.context import CryptContext
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_database():
    """Initialize MongoDB with minimal login data"""
    
    # Connect to MongoDB
    mongodb_url = os.getenv("MONGODB_URL")
    if not mongodb_url:
        print("❌ MONGODB_URL not found in .env file")
        return
    
    print("🔄 Connecting to MongoDB Atlas...")
    client = MongoClient(mongodb_url)
    db = client['sewing_machine_db']
    
    # Create users collection (if not exists)
    if 'users' not in db.list_collection_names():
        db.create_collection('users')
        print("✅ Created 'users' collection")
    
    users_collection = db['users']
    
    # Check if admin user exists
    admin_exists = users_collection.find_one({"username": "admin"})
    
    if not admin_exists:
        # Create admin user
        hashed_password = pwd_context.hash("admin123")
        
        admin_user = {
            "username": "admin",
            "email": "admin@sewing.com",
            "full_name": "System Administrator",
            "role": "admin",
            "disabled": False,
            "created_at": datetime.now(),
            "login_attempts": 0,
            "locked_until": None,
            "hashed_password": hashed_password
        }
        
        users_collection.insert_one(admin_user)
        print("✅ Created admin user - Username: admin, Password: admin123")
    else:
        print("ℹ️ Admin user already exists")
    
    # Create manager user (optional)
    manager_exists = users_collection.find_one({"username": "manager"})
    if not manager_exists:
        hashed_password = pwd_context.hash("manager123")
        
        manager_user = {
            "username": "manager",
            "email": "manager@sewing.com",
            "full_name": "Production Manager",
            "role": "manager",
            "disabled": False,
            "created_at": datetime.now(),
            "login_attempts": 0,
            "locked_until": None,
            "hashed_password": hashed_password
        }
        
        users_collection.insert_one(manager_user)
        print("✅ Created manager user - Username: manager, Password: manager123")
    
    # Create supervisor user (optional)
    supervisor_exists = users_collection.find_one({"username": "supervisor"})
    if not supervisor_exists:
        hashed_password = pwd_context.hash("supervisor123")
        
        supervisor_user = {
            "username": "supervisor",
            "email": "supervisor@sewing.com",
            "full_name": "Floor Supervisor",
            "role": "supervisor",
            "disabled": False,
            "created_at": datetime.now(),
            "login_attempts": 0,
            "locked_until": None,
            "hashed_password": hashed_password
        }
        
        users_collection.insert_one(supervisor_user)
        print("✅ Created supervisor user - Username: supervisor, Password: supervisor123")
    
    # List all users
    print("\n📊 Current users in database:")
    for user in users_collection.find({}, {"username": 1, "role": 1, "email": 1, "_id": 0}):
        print(f"   - {user['username']} ({user['role']}) - {user.get('email', 'No email')}")
    
    print(f"\n✅ Database initialization complete!")
    print(f"📁 Database: sewing_machine_db")
    print(f"📁 Collections: {db.list_collection_names()}")
    
    client.close()

if __name__ == "__main__":
    init_database()