# test_ml_fixed.py
import requests
import json

# Login
print("1. Logging in...")
login_data = {
    "username": "admin",
    "password": "admin123",
    "role": "admin"
}

session = requests.Session()
login_response = session.post("http://localhost:8000/auth/login", json=login_data)

if login_response.status_code != 200:
    print(f"❌ Login failed: {login_response.text}")
    exit()

print("✅ Login successful")
print()

# Test components list
print("2. Getting components list...")
response = session.get("http://localhost:8000/api/components")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
print()

# Test prediction
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

response = session.post("http://localhost:8000/api/ml/predict", json=predict_data)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"Predictions: {json.dumps(response.json(), indent=2)}")
else:
    print(f"Error: {response.text}")