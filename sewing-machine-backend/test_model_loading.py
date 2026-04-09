# test_model_loading.py - Updated version
import os
import pickle
import sys
import numpy as np

print("="*50)
print("TESTING MODEL LOADING")
print("="*50)

# Check current directory
print(f"\n📂 Current directory: {os.getcwd()}")

# Check if files exist
data_dir = os.path.join('app', 'ml', 'data')
print(f"\n📁 Checking data directory: {data_dir}")

if os.path.exists(data_dir):
    print(f"✅ Data directory exists")
    files = os.listdir(data_dir)
    print(f"Files in directory: {files}")
    
    # Try to load the scaler
    scaler_path = os.path.join(data_dir, 'standard_scalar.pkl')
    if os.path.exists(scaler_path):
        print(f"\n🔄 Attempting to load scaler from: {scaler_path}")
        try:
            with open(scaler_path, 'rb') as f:
                scaler = pickle.load(f)
            print(f"✅ Scaler loaded successfully!")
            print(f"Scaler type: {type(scaler)}")
            
            # Test scaler with sample data
            test_sample = np.array([[1, 2020]])
            try:
                transformed = scaler.transform(test_sample)
                print(f"✅ Scaler transform works!")
            except Exception as e:
                print(f"❌ Scaler transform failed: {e}")
                
        except Exception as e:
            print(f"❌ Error loading scaler: {e}")
    else:
        print(f"❌ Scaler file not found at: {scaler_path}")
    
    # Try to load the model
    model_path = os.path.join(data_dir, 'xgb.pickle')
    if os.path.exists(model_path):
        print(f"\n🔄 Attempting to load model from: {model_path}")
        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            print(f"✅ Model loaded successfully!")
            print(f"Model type: {type(model)}")
            
            # Check if it's an XGBoost model
            if 'xgboost' in str(type(model)):
                print(f"✅ XGBoost model detected")
            else:
                print(f"⚠️ Model type: {type(model)}")
                
        except Exception as e:
            print(f"❌ Error loading model: {e}")
    else:
        print(f"❌ Model file not found at: {model_path}")
else:
    print(f"❌ Data directory not found at: {data_dir}")

print("\n" + "="*50)