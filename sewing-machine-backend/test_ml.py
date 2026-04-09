# test_ml.py
import requests
import json

base_url = "http://localhost:8000"

# First, login to get session cookie
print("1. Logging in...")
login_data = {
    "username": "admin",
    "password": "admin123",
    "role": "admin"
}

session = requests.Session()
response = session.post(f"{base_url}/auth/login", json=login_data)

if response.status_code != 200:
    print(f"Login failed: {response.text}")
    exit()

print("✅ Login successful")
print(f"Session cookies: {session.cookies.get_dict()}")
print()

# Test get components list
print("2. Getting components list...")
response = session.get(f"{base_url}/api/components")
print(f"Status: {response.status_code}")
print(f"Components: {json.dumps(response.json(), indent=2)}")
print()

# Test predict endpoint
print("3. Testing prediction...")
predict_data = {
    "Fabric_Type": "Medium",
    "M_Year": 2020,
    "usageDict": {
        "Take up Spring": 500,
        "Take up Rubber": 300,
        "Bobbin Case": 200,
        "Feed Dog": 400,
        "Presser Foot": 350,
        "Tension Assembly": 250,
        "Hook Assembly": 150,
        "Timing Components": 100,
        "Oil Filling": 50,
        "Dust Remove": 75
    }
}

response = session.post(f"{base_url}/api/ml/predict", json=predict_data)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"Predictions: {json.dumps(response.json(), indent=2)}")
else:
    print(f"Error: {response.text}")
print()

# Test health status endpoint
print("4. Testing health status...")
response = session.post(f"{base_url}/api/ml/health-status", json=predict_data)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"Health Status: {json.dumps(response.json(), indent=2)}")
else:
    print(f"Error: {response.text}")