# test_ml_endpoint.py
import requests
import json

# First, login to get session cookie
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
print(f"Session cookies: {session.cookies.get_dict()}")
print()

# Test the ML predict endpoint
print("2. Testing ML prediction endpoint...")
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

if response.status_code == 200:
    print("✅ Prediction successful!")
    print("\nPredictions:")
    predictions = response.json()["predictions"]
    for component, status in predictions.items():
        print(f"  {component}: {status}")
else:
    print(f"❌ Prediction failed: {response.status_code}")
    print(response.text)

print()

# Test health status endpoint
print("3. Testing health status endpoint...")
response = session.post("http://localhost:8000/api/ml/health-status", json=predict_data)

if response.status_code == 200:
    print("✅ Health status successful!")
    health_data = response.json()
    print("\nHealth Status:")
    for component, status in health_data.items():
        print(f"  {component}: {status['status']} - {status['message']}")
else:
    print(f"❌ Health status failed: {response.status_code}")
    print(response.text)