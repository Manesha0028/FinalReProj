import React, { useState, useEffect } from 'react';
import api from '../services/api';
import './MaintenancePredictor.css';

const MaintenancePredictor = () => {
  // Define all components manually to ensure they're always available
  const COMPONENTS_LIST = [
    'Take up Spring',
    'Take up Rubber',
    'Bobbin Case',
    'Feed Dog',
    'Presser Foot',
    'Tension Assembly',
    'Hook Assembly',
    'Timing Components',
    'Oil Filling',
    'Dust Remove'
  ];

  // Fixed values
  const FIXED_BRAND = "JUKI";
  const FIXED_MACHINE_TYPE = "Single Needle Lock Stitch";

  const [components, setComponents] = useState(COMPONENTS_LIST);
  const [machineId, setMachineId] = useState('');
  const [fabricType, setFabricType] = useState('');
  const [manufacturingYear, setManufacturingYear] = useState('');
  const [usageHours, setUsageHours] = useState({});
  const [predictions, setPredictions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showPopup, setShowPopup] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [touched, setTouched] = useState({});
  const [predictionProgress, setPredictionProgress] = useState(0);
  const [predictionStage, setPredictionStage] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [savedMachines, setSavedMachines] = useState([]);

  useEffect(() => {
    fetchComponents();
    initializeUsageHours();
    fetchSavedMachines();
  }, []);

  const fetchComponents = async () => {
    try {
      const response = await api.get('/api/components');
      if (response.data && response.data.components) {
        setComponents(response.data.components);
      }
    } catch (err) {
      console.log('Using default components list');
    }
  };

  const fetchSavedMachines = async () => {
    try {
      // You'll need to create this endpoint in your backend
      const response = await api.get('/api/machines');
      if (response.data && response.data.machines) {
        setSavedMachines(response.data.machines);
      }
    } catch (err) {
      console.log('Could not fetch saved machines');
      // Fallback to localStorage
      const localSaved = localStorage.getItem('savedMachines');
      if (localSaved) {
        setSavedMachines(JSON.parse(localSaved));
      }
    }
  };

  const initializeUsageHours = () => {
    const initialUsage = {};
    const initialTouched = {};
    COMPONENTS_LIST.forEach(comp => {
      initialUsage[comp] = '';
      initialTouched[comp] = false;
    });
    setUsageHours(initialUsage);
    setTouched(initialTouched);
  };

  const handleUsageChange = (component, value) => {
    setUsageHours({
      ...usageHours,
      [component]: value
    });
  };

  const handleBlur = (component) => {
    setTouched({
      ...touched,
      [component]: true
    });
  };

  const validateInputs = () => {
    if (!machineId.trim()) {
      setError('Please enter Machine ID');
      return false;
    }

    if (!fabricType) {
      setError('Please select Fabric Type');
      return false;
    }

    if (!manufacturingYear) {
      setError('Please select Manufacturing Year');
      return false;
    }
    
    const emptyFields = [];
    const invalidFields = [];
    
    Object.entries(usageHours).forEach(([component, value]) => {
      if (value === '' || value === null || value === undefined) {
        emptyFields.push(component);
      } else {
        const numValue = Number(value);
        if (isNaN(numValue) || numValue < 0) {
          invalidFields.push(component);
        }
      }
    });
    
    if (emptyFields.length > 0) {
      setError(`Please fill usage hours for: ${emptyFields.join(', ')}`);
      return false;
    }
    
    if (invalidFields.length > 0) {
      setError(`Please enter valid numbers for: ${invalidFields.join(', ')}`);
      return false;
    }
    
    return true;
  };

  // Simulate prediction progress with longer duration
  const simulatePredictionProgress = () => {
    const stages = [
      'Initializing prediction engine...',
      'Analyzing component wear patterns...',
      'Calculating remaining useful life (RUL)...',
      'Processing machine learning model...',
      'Comparing with historical data...',
      'Generating maintenance recommendations...',
      'Finalizing predictions...'
    ];
    
    let progress = 0;
    let stageIndex = 0;
    
    const interval = setInterval(() => {
      // Slower progression (3 seconds total instead of 2)
      progress += Math.random() * 8;
      if (progress > 100) progress = 100;
      
      setPredictionProgress(Math.min(100, Math.floor(progress)));
      
      if (progress > (stageIndex + 1) * 14.28 && stageIndex < stages.length - 1) {
        stageIndex++;
        setPredictionStage(stages[stageIndex]);
      }
      
      if (progress >= 100) {
        clearInterval(interval);
      }
    }, 300); // Slower interval (300ms instead of 200ms)
    
    return interval;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateInputs()) return;
    
    setLoading(true);
    setShowPopup(true);
    setPredictionProgress(0);
    setPredictionStage('Initializing prediction engine...');
    setError('');
    setSaveSuccess(false);

    // Start progress simulation with longer duration
    const progressInterval = simulatePredictionProgress();

    try {
      // Convert strings to numbers
      const processedUsage = {};
      Object.keys(usageHours).forEach(key => {
        processedUsage[key] = Number(usageHours[key]) || 0;
      });

      const response = await api.post('/api/ml/predict', {
        Fabric_Type: fabricType,
        M_Year: Number(manufacturingYear),
        usageDict: processedUsage
      });
      
      // Ensure progress reaches 100% before showing results
      setPredictionProgress(100);
      setPredictionStage('Prediction complete!');
      
      // Longer delay to show 100% completion
      setTimeout(() => {
        const predictionData = {
          ...response.data.predictions,
          machineId,
          brandName: FIXED_BRAND,
          machineType: FIXED_MACHINE_TYPE,
          fabricType,
          manufacturingYear,
          usageHours: processedUsage,
          timestamp: new Date().toISOString()
        };
        
        setPredictions(predictionData);
        setLoading(false);
        // Keep popup open to show results
      }, 800);

    } catch (err) {
      clearInterval(progressInterval);
      setError(err.response?.data?.detail || 'Prediction failed');
      setLoading(false);
      setShowPopup(false);
    }
  };

  const handleSaveMachine = async () => {
    if (!predictions) return;
    
    setSaving(true);
    setError('');
    setSuccess('');
    
    try {
      // Prepare machine data for saving
      const machineData = {
        machineId: predictions.machineId,
        brandName: predictions.brandName,
        machineType: predictions.machineType,
        fabricType: predictions.fabricType,
        manufacturingYear: predictions.manufacturingYear,
        usageHours: predictions.usageHours,
        predictions: predictions,
        lastPrediction: new Date().toISOString()
      };
      
      // Save to MongoDB via API
      // You'll need to create this endpoint in your backend
      const response = await api.post('/api/machines', machineData);
      
      if (response.status === 200 || response.status === 201) {
        // Refresh saved machines list
        fetchSavedMachines();
        
        // Save to localStorage as backup
        const localSaved = JSON.parse(localStorage.getItem('savedMachines') || '[]');
        const updatedLocal = [machineData, ...localSaved].slice(0, 50);
        localStorage.setItem('savedMachines', JSON.stringify(updatedLocal));

        clearForm();
        setShowPopup(false);
        setSuccess('Machine saved successfully to database!');
        
        // Clear success message after 3 seconds
        setTimeout(() => {
          setSuccess('');
        }, 3000);
      }
    } catch (err) {
      setError('Failed to save machine: ' + (err.response?.data?.detail || err.message));
      
      // Fallback to localStorage if API fails
      try {
        const machineData = {
          machineId: predictions.machineId,
          brandName: predictions.brandName,
          machineType: predictions.machineType,
          fabricType: predictions.fabricType,
          manufacturingYear: predictions.manufacturingYear,
          usageHours: predictions.usageHours,
          predictions: predictions,
          lastPrediction: new Date().toISOString()
        };
        
        const localSaved = JSON.parse(localStorage.getItem('savedMachines') || '[]');
        const updatedLocal = [machineData, ...localSaved].slice(0, 50);
        localStorage.setItem('savedMachines', JSON.stringify(updatedLocal));
        setSavedMachines(updatedLocal);

        clearForm();
        setShowPopup(false);
        setSuccess('Machine saved locally (database connection unavailable)');
        
        setTimeout(() => {
          setSuccess('');
        }, 3000);
      } catch (localErr) {
        setError('Failed to save machine');
      }
    } finally {
      setSaving(false);
    }
  };

  const loadMachineFromHistory = (entry) => {
    setMachineId(entry.machineId);
    setFabricType(entry.fabricType || '');
    setManufacturingYear(entry.manufacturingYear || entry.year || '');
    setUsageHours(entry.usageHours || entry.usage || {});
    if (entry.predictions) {
      setPredictions(entry.predictions);
    }
    setShowHistory(false);
    setError('');
  };

  const clearForm = () => {
    setMachineId('');
    setFabricType('');
    setManufacturingYear('');
    const resetUsage = {};
    const resetTouched = {};
    components.forEach(comp => {
      resetUsage[comp] = '';
      resetTouched[comp] = false;
    });
    setUsageHours(resetUsage);
    setTouched(resetTouched);
    setPredictions(null);
    setError('');
    setSuccess('');
    setSaveSuccess(false);
  };

  const closePopup = () => {
    setShowPopup(false);
    // Don't clear predictions immediately to allow viewing
  };

  const getStatusColor = (message) => {
    if (message.includes('Maintenance Required')) return '#e53e3e';
    if (message.includes('hours remaining')) return '#38a169';
    return '#718096';
  };

  const getStatusIcon = (message) => {
    if (message.includes('Maintenance Required')) return '🔴';
    if (message.includes('hours remaining')) {
      const hours = parseInt(message.split(' ')[1]);
      if (hours < 100) return '🟡';
      return '🟢';
    }
    return '⚪';
  };

  const isFieldInvalid = (component) => {
    if (!touched[component]) return false;
    const value = usageHours[component];
    return value === '' || value === null || value === undefined || isNaN(Number(value)) || Number(value) < 0;
  };

  const calculateOverallHealth = () => {
    if (!predictions) return 0;
    
    let total = 0;
    let count = 0;
    
    Object.entries(predictions).forEach(([component, message]) => {
      if (!['machineId', 'brandName', 'machineType', 'fabricType', 'manufacturingYear', 'usageHours', 'timestamp'].includes(component)) {
        if (message.includes('hours remaining')) {
          const hours = parseInt(message.split(' ')[1]);
          total += Math.min(100, (hours / 500) * 100);
        } else if (message.includes('Maintenance Required')) {
          total += 0;
        }
        count++;
      }
    });
    
    return count > 0 ? Math.round(total / count) : 0;
  };

  // Combine history from API and localStorage
  const predictionHistory = savedMachines.length > 0 ? savedMachines : 
    JSON.parse(localStorage.getItem('savedMachines') || '[]');

  return (
    <div className="predictor-container">
      <div className="predictor-header">
        <h2>🔧 JUKI Machine Maintenance Predictor</h2>
        <div className="header-buttons">
          <button 
            type="button"
            className="clear-btn"
            onClick={clearForm}
          >
            Clear Form 🧹
          </button>
        </div>
      </div>
      
      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}
      
      {showHistory && predictionHistory.length > 0 && (
        <div className="history-panel">
          <h3>Saved Machines</h3>
          <div className="history-list">
            {predictionHistory.map((entry, index) => (
              <div 
                key={entry.id || index} 
                className="history-item"
                onClick={() => loadMachineFromHistory(entry)}
              >
                <strong>{entry.machineId}</strong> - {entry.brandName} ({entry.machineType})
                <br />
                <small>Last: {new Date(entry.lastPrediction || entry.timestamp).toLocaleString()}</small>
              </div>
            ))}
          </div>
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="predictor-form" noValidate>
        <div className="form-section">
          <h3>📋 Machine Information</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Machine ID <span className="required">*</span>:</label>
              <input
                type="text"
                value={machineId}
                onChange={(e) => setMachineId(e.target.value)}
                placeholder="e.g., SM-001"
              />
            </div>
            
            <div className="form-group">
              <label>Brand Name:</label>
              <input
                type="text"
                value={FIXED_BRAND}
                className="fixed-input"
                readOnly
                disabled
              />
            </div>
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>Machine Type:</label>
              <input
                type="text"
                value={FIXED_MACHINE_TYPE}
                className="fixed-input"
                readOnly
                disabled
              />
            </div>
            <div className="form-group">
              {/* Empty div for spacing */}
            </div>
          </div>
        </div>

        <div className="form-section">
          <h3>⚙️ Operating Parameters</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Fabric Type:</label>
              <select 
                value={fabricType} 
                onChange={(e) => setFabricType(e.target.value)}
              >
                <option value="">Select fabric type</option>
                <option value="Medium">Medium</option>
                <option value="Heavy">Heavy</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Manufacturing Year:</label>
              <select
                value={manufacturingYear}
                onChange={(e) => setManufacturingYear(e.target.value)}
              >
                <option value="">Select manufacturing year</option>
                {Array.from({ length: 2020 - 2006 + 1 }, (_, index) => {
                  const year = 2020 - index;
                  return (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  );
                })}
              </select>
            </div>
          </div>
        </div>
        
        <div className="form-section">
          <h3>⏱️ Component Usage Hours <span className="required">*</span></h3>
          <p className="section-note">Enter the number of hours each component has been used</p>
          
          {/* First row of components */}
          <div className="usage-grid">
            {components.slice(0, 5).map(component => (
              <div key={component} className="usage-item">
                <label>{component}:</label>
                <input
                  type="number"
                  value={usageHours[component] || ''}
                  onChange={(e) => handleUsageChange(component, e.target.value)}
                  onBlur={() => handleBlur(component)}
                  min="0"
                  step="1"
                  placeholder="Enter hours"
                  className={isFieldInvalid(component) ? 'invalid' : ''}
                />
                {isFieldInvalid(component) && (
                  <span className="field-error">Please enter a valid number</span>
                )}
              </div>
            ))}
          </div>
          
          {/* Second row of components */}
          <div className="usage-grid">
            {components.slice(5, 10).map(component => (
              <div key={component} className="usage-item">
                <label>{component}:</label>
                <input
                  type="number"
                  value={usageHours[component] || ''}
                  onChange={(e) => handleUsageChange(component, e.target.value)}
                  onBlur={() => handleBlur(component)}
                  min="0"
                  step="1"
                  placeholder="Enter hours"
                  className={isFieldInvalid(component) ? 'invalid' : ''}
                />
                {isFieldInvalid(component) && (
                  <span className="field-error">Please enter a valid number</span>
                )}
              </div>
            ))}
          </div>
        </div>
        
        <button 
          type="submit" 
          disabled={loading} 
          className={`predict-btn ${loading ? 'loading' : ''}`}
        >
          {loading ? '🔮 Predicting RUL...' : '🔮 Predict Maintenance'}
        </button>
      </form>

      {/* Loading and Results Popup */}
      {showPopup && (
        <div className="popup-overlay">
          <div className="popup-content">
            <button className="popup-close" onClick={closePopup}>×</button>
            
            {loading && !predictions ? (
              <div className="loading-container">
                <h3>🔮 Predicting Remaining Useful Life (RUL)</h3>
                <div className="ruler-animation">
                  <div className="ruler">
                    <div className="ruler-mark"></div>
                    <div className="ruler-mark"></div>
                    <div className="ruler-mark"></div>
                    <div className="ruler-mark"></div>
                    <div className="ruler-mark"></div>
                    <div className="ruler-mark"></div>
                    <div className="ruler-mark"></div>
                    <div className="ruler-mark"></div>
                  </div>
                  <div className="gear-animation">
                    <div className="gear">⚙️</div>
                    <div className="gear">⚙️</div>
                    <div className="gear">⚙️</div>
                    <div className="gear">⚙️</div>
                  </div>
                </div>
                <div className="progress-bar-container">
                  <div 
                    className="progress-bar-fill"
                    style={{ width: `${predictionProgress}%` }}
                  >
                    <span className="progress-text">{predictionProgress}%</span>
                  </div>
                </div>
                <p className="prediction-stage">{predictionStage}</p>
                <p className="machine-info-loading">
                  Machine: {machineId} | {FIXED_BRAND} | {FIXED_MACHINE_TYPE}
                </p>
              </div>
            ) : predictions && (
              <div className="results-container">
                <h3>📊 Prediction Results</h3>
                
                {success && <div className="success-message popup-success">{success}</div>}
                {error && <div className="error-message popup-error">{error}</div>}
                
                <div className="results-header">
                  <div className="machine-badge">
                    <span className="machine-id">{predictions.machineId}</span>
                    <span className="machine-brand">{predictions.brandName}</span>
                    <span className="machine-type">{predictions.machineType}</span>
                  </div>
                  <div className="overall-health">
                    <div className="health-gauge">
                      <div 
                        className="health-fill"
                        style={{ 
                          width: `${calculateOverallHealth()}%`,
                          backgroundColor: calculateOverallHealth() > 70 ? '#38a169' : 
                                         calculateOverallHealth() > 40 ? '#ecc94b' : '#e53e3e'
                        }}
                      ></div>
                    </div>
                    <span>Overall Health: {calculateOverallHealth()}%</span>
                  </div>
                </div>
                
                <div className="popup-results-grid">
                  {Object.entries(predictions).map(([component, message]) => {
                    if (['machineId', 'brandName', 'machineType', 'fabricType', 'manufacturingYear', 'usageHours', 'timestamp'].includes(component)) return null;
                    
                    const hours = message.includes('hours remaining') ? parseInt(message.split(' ')[1]) : 0;
                    const isCritical = message.includes('Maintenance Required');
                    
                    return (
                      <div 
                        key={component} 
                        className="popup-result-card"
                        style={{ borderLeftColor: getStatusColor(message) }}
                      >
                        <div className="popup-result-header">
                          <span className="status-icon">{getStatusIcon(message)}</span>
                          <h4>{component}</h4>
                        </div>
                        <p className="result-message">{message}</p>
                        {!isCritical && (
                          <div className="result-rul">
                            <span className="rul-label">RUL:</span>
                            <span className="rul-value">{hours} hours</span>
                          </div>
                        )}
                        {isCritical && (
                          <div className="critical-badge">
                            ⚠️ Immediate Attention Required
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="popup-footer">
                  <p className="timestamp">
                    Predicted on: {new Date().toLocaleString()}
                  </p>
                  <div className="popup-actions">
                    <button 
                      className="save-machine-btn"
                      onClick={handleSaveMachine}
                      disabled={saving || saveSuccess}
                    >
                      {saving ? '💾 Saving...' : saveSuccess ? '✅ Saved!' : '💾 Add Machine'}
                    </button>
                    <button 
                      className="close-btn"
                      onClick={closePopup}
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MaintenancePredictor;