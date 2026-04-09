# app/ml/service.py
import pickle
import numpy as np
from fastapi import HTTPException
from typing import Dict, List, Any
import os

# Constants
FABRIC_TYPE_DICT = {
    'Heavy': 1,
    'Medium': 0
}

OUTPUT_COLUMNS = [
    'Take up Spring', 'Take up Rubber', 'Bobbin Case', 'Feed Dog',
    'Presser Foot', 'Tension Assembly', 'Hook Assembly',
    'Timing Components', 'Oil Filling', 'Dust Remove'
]

class MLService:
    """Service class for ML model operations"""
    
    def __init__(self):
        self.scaler = None
        self.model = None
        self.load_models()
    
    def load_models(self):
        """Load the ML models from disk"""
        try:
            # Get the absolute path to the model files
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Load Standard Scaler
            scaler_path = os.path.join(base_dir, 'data', 'standard_scalar.pkl')
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            print(f"✅ Scaler loaded from {scaler_path}")
            
            # Load XGBoost Model
            model_path = os.path.join(base_dir, 'data', 'xgb.pickle')
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            print(f"✅ Model loaded from {model_path}")
            
        except FileNotFoundError as e:
            print(f"❌ Model file not found: {e}")
            print("Please ensure model files are in app/ml/data/ directory")
            raise
        except Exception as e:
            print(f"❌ Error loading models: {e}")
            raise
    
    def validate_fabric_type(self, fabric_type: str) -> bool:
        """Validate if fabric type is supported"""
        return fabric_type in FABRIC_TYPE_DICT
    
    def predict(self, fabric_type: str, manufacturing_year: int, usage_dict: Dict[str, float]) -> Dict[str, str]:
        """
        Make prediction for component maintenance
        
        Args:
            fabric_type: 'Heavy' or 'Medium'
            manufacturing_year: Year of manufacture
            usage_dict: Dictionary with component usage hours
        
        Returns:
            Dictionary with maintenance predictions for each component
        """
        try:
            # Validate fabric type
            if not self.validate_fabric_type(fabric_type):
                raise ValueError(f"Fabric_Type must be 'Heavy' or 'Medium'")
            
            # Validate that all required components are in usage_dict
            missing_components = [comp for comp in OUTPUT_COLUMNS if comp not in usage_dict]
            if missing_components:
                raise ValueError(f"Missing usage data for components: {missing_components}")
            
            # Prepare input for prediction
            fabric_encoded = FABRIC_TYPE_DICT[fabric_type]
            sample = np.array([[fabric_encoded, manufacturing_year]])
            sample_scaled = self.scaler.transform(sample).astype(np.float32)
            
            # Make prediction
            prediction = self.model.predict(sample_scaled).squeeze().astype(np.int32)
            
            # Calculate remaining hours
            result = {}
            for i, component in enumerate(OUTPUT_COLUMNS):
                used_hours = usage_dict[component]
                predicted_total_hours = int(prediction[i])
                remaining_hours = predicted_total_hours - used_hours
                
                if remaining_hours <= 0:
                    result[component] = "⚠️ Maintenance Required Immediately"
                else:
                    result[component] = f"✅ {int(remaining_hours)} hours remaining"
            
            return result
            
        except Exception as e:
            print(f"Prediction error: {e}")
            raise
    
    def get_component_health_status(self, fabric_type: str, manufacturing_year: int, usage_dict: Dict[str, float]) -> Dict[str, Any]:
        """
        Get detailed health status for all components
        
        Returns:
            Dictionary with component name, health status, and maintenance recommendation
        """
        predictions = self.predict(fabric_type, manufacturing_year, usage_dict)
        
        health_status = {}
        for component, status in predictions.items():
            if "Maintenance Required" in status:
                health_status[component] = {
                    "status": "critical",
                    "message": status,
                    "priority": "high"
                }
            else:
                # Extract hours from status message
                hours = int(status.split()[1])
                if hours < 100:
                    health_status[component] = {
                        "status": "warning",
                        "message": f"⚠️ {hours} hours remaining - Schedule maintenance soon",
                        "priority": "medium"
                    }
                else:
                    health_status[component] = {
                        "status": "good",
                        "message": status,
                        "priority": "low"
                    }
        
        return health_status

# Create singleton instance
ml_service = MLService()