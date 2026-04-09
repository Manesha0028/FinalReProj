# test_import.py
print("Testing imports...")

try:
    from app.config.database import Database, get_database
    print("✅ Successfully imported Database and get_database")
    print(f"Database class: {Database}")
    print(f"get_database function: {get_database}")
except Exception as e:
    print(f"❌ Import failed: {e}")
    
print("\nChecking if file exists...")
import os
print(f"Current directory: {os.getcwd()}")
print(f"Files in current directory: {os.listdir('.')}")
print(f"Files in app/config: {os.listdir('app/config')}")