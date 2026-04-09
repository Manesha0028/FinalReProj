import sys
import os

print(f"Python path: {sys.path}")
print(f"Current directory: {os.getcwd()}")

# Try direct import
try:
    import app
    print("✅ app module imported")
    print(f"app location: {app.__file__}")
except Exception as e:
    print(f"❌ Cannot import app: {e}")

# Try importing from app.config
try:
    from app.config import database
    print("✅ app.config.database imported")
    print(f"database location: {database.__file__}")
    print(f"Database attributes: {dir(database)}")
except Exception as e:
    print(f"❌ Cannot import app.config.database: {e}")

# Check if file exists
config_file = os.path.join('app', 'config', 'database.py')
if os.path.exists(config_file):
    print(f"✅ File exists: {config_file}")
    with open(config_file, 'r') as f:
        first_line = f.readline().strip()
        print(f"First line: {first_line}")
else:
    print(f"❌ File not found: {config_file}")