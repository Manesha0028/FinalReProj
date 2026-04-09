from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    client: MongoClient = None
    db = None
    
    @classmethod
    def connect(cls):
        try:
            # Get MongoDB URL
            mongodb_url = os.getenv("MONGODB_URL")
            
            if not mongodb_url:
                raise ValueError("MONGODB_URL not found in environment variables")
            
            print("Connecting to MongoDB...")
            
            # Connect with additional options for stability
            cls.client = MongoClient(
                mongodb_url,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                retryWrites=True
            )
            
            # Test connection
            cls.client.admin.command('ping')
            print("MongoDB connection successful")
            
            # Set database
            cls.db = cls.client['sewing_machine_db']
            print(f"Using database: sewing_machine_db")
            
            return cls.db
            
        except ConnectionFailure as e:
            print(f"MongoDB connection failed: {e}")
            print("Check if your IP is whitelisted in MongoDB Atlas")
            raise
        except ConfigurationError as e:
            print(f"MongoDB configuration error: {e}")
            print("Check your connection string format")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise
    
    @classmethod
    def get_db(cls):
        if cls.db is None:
            cls.connect()
        return cls.db
    
    @classmethod
    def get_users_collection(cls):
        db = cls.get_db()
        return db["users"]
    
    @classmethod
    def get_sessions_collection(cls):
        db = cls.get_db()
        return db["sessions"]
    
    @classmethod
    def close(cls):
        if cls.client:
            cls.client.close()
            print("MongoDB connection closed")

# Helper function to get database instance
def get_database():
    return Database.get_db()

def get_users_collection():
    return Database.get_users_collection()

def get_sessions_collection():
    return Database.get_sessions_collection()