import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import './SavedMachines.css';

const SavedMachines = () => {
  const [machines, setMachines] = useState([]);
  const [filteredMachines, setFilteredMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: 'lastPrediction', direction: 'desc' });
  const [selectedMachine, setSelectedMachine] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [fabricFilter, setFabricFilter] = useState('all');
  const [yearFilter, setYearFilter] = useState('all');
  
  // New state for repredict feature
  const [repredictMode, setRepredictMode] = useState(false);
  const [selectedComponent, setSelectedComponent] = useState(null);
  const [newUsageHours, setNewUsageHours] = useState('');
  const [repredictLoading, setRepredictLoading] = useState(false);
  const [repredictResult, setRepredictResult] = useState(null);
  
  // State for real-time status
  const [machineStatus, setMachineStatus] = useState({});
  const [wsConnected, setWsConnected] = useState(false);
  const [showCounterModal, setShowCounterModal] = useState(false);
  const [counterMachine, setCounterMachine] = useState(null);
  const [counterHistory, setCounterHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  
  const wsRef = useRef(null);
  const machineStatusRef = useRef({});
  const [statusUpdateTrigger, setStatusUpdateTrigger] = useState(0);

  // Returns base seconds safely as a non-negative integer
  const toSafeSeconds = (value) => {
    const parsed = Number(value);
    if (Number.isNaN(parsed) || parsed < 0) return 0;
    return Math.floor(parsed);
  };

  const calculateCurrentFromSnapshot = (status, atMs = Date.now()) => {
    const base = toSafeSeconds(status?.base_seconds ?? 0);
    const sessionStart = status?.session_start_ms;
    const lastSeen = status?.last_seen_ms;

    if (!sessionStart || !lastSeen) return base;

    const isOnline = (atMs - lastSeen) <= 5000;
    if (isOnline) {
      return base + Math.max(0, Math.floor((atMs - sessionStart) / 1000));
    }

    return base + Math.max(0, Math.floor((lastSeen - sessionStart) / 1000));
  };

  const mergeLiveStatus = (prevStatus = {}, data = {}, forceOnline = false) => {
    const nowMs = Date.now();
    const isOnline = forceOnline || data.online === true;
    const prevBaseSeconds = toSafeSeconds(prevStatus.base_seconds ?? 0);
    const incomingBaseSeconds = toSafeSeconds(data.working_time_seconds ?? prevBaseSeconds);
    const incomingLastSeenMs = data.last_seen
      ? new Date(data.last_seen).getTime()
      : (data.timestamp ? new Date(data.timestamp).getTime() : (isOnline ? nowMs : prevStatus.last_seen_ms ?? null));

    const hadActiveSession = Boolean(
      prevStatus.session_start_ms &&
      prevStatus.last_seen_ms &&
      (nowMs - prevStatus.last_seen_ms) <= 5000
    );

    const baseAdvanced = incomingBaseSeconds > prevBaseSeconds;

    return {
      ...prevStatus,
      base_seconds: baseAdvanced ? incomingBaseSeconds : prevBaseSeconds,
      session_start_ms: isOnline
        ? (hadActiveSession && !baseAdvanced ? prevStatus.session_start_ms : (incomingLastSeenMs || nowMs))
        : null,
      last_seen_ms: incomingLastSeenMs ?? prevStatus.last_seen_ms ?? null,
      last_count: data.last_count ?? data.count ?? prevStatus.last_count,
      rssi: data.rssi ?? prevStatus.rssi,
    };
  };

  useEffect(() => {
    fetchSavedMachines();
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    filterAndSortMachines();
  }, [machines, searchTerm, sortConfig, fabricFilter, yearFilter, statusUpdateTrigger]);

  useEffect(() => {
    machineStatusRef.current = machineStatus;
  }, [machineStatus]);

  // Periodic status update to check online/offline based on time
  useEffect(() => {
    const interval = setInterval(() => {
      setStatusUpdateTrigger(prev => prev + 1);
    }, 1000); // Update every second

    return () => clearInterval(interval);
  }, []);

  const connectWebSocket = () => {
    try {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const wsHost = window.location.hostname || 'localhost';
      const ws = new WebSocket(`${wsProtocol}://${wsHost}:8000/ws/counter`);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log('✅ WebSocket connected');
        setWsConnected(true);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('📩 Received:', data);
          
          // Handle different message types
          if (data.type === 'machine_status') {
            console.log(`🤖 Machine ${data.machine_id} status: online=${data.online} wt=${data.working_time_seconds}`);
            setMachineStatus(prev => ({
              ...prev,
              [data.machine_id]: mergeLiveStatus(prev[data.machine_id] || {}, data)
            }));
          }
          else if (data.type === 'heartbeat' || data.type === 'heartbeat_ack') {
            // Heartbeat only updates signal strength – never changes online/time state
            setMachineStatus(prev => ({
              ...prev,
              [data.machine_id]: {
                ...(prev[data.machine_id] || {}),
                rssi: data.rssi,
              }
            }));
          }
          else if (data.type === 'count_update') {
            console.log(`🔢 Count update for ${data.machine_id}: ${data.count} wt=${data.working_time_seconds}`);
            setMachineStatus(prev => ({
              ...prev,
              [data.machine_id]: mergeLiveStatus(prev[data.machine_id] || {}, data, true)
            }));
            
            // Add to history
            setCounterHistory(prev => {
              const exists = prev.some(item => item.id === data.db_id);
              if (exists) return prev;
              return [{
                id: data.db_id,
                count: data.count,
                timestamp: data.timestamp || new Date().toISOString()
              }, ...prev].slice(0, 20);
            });
          }
        } catch (err) {
          console.error('Error parsing message:', err);
        }
      };
      
      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setWsConnected(false);
      };
      
      ws.onclose = () => {
        console.log('❌ WebSocket disconnected');
        setWsConnected(false);
        // Freeze all machine timers at last_seen when WS disconnects
        setMachineStatus(prev => {
          const updated = { ...prev };
          const nowMs = Date.now();
          Object.keys(updated).forEach(id => {
            const s = updated[id] || {};
            if (s.last_seen_ms && s.session_start_ms) {
              const wasOnline = (nowMs - s.last_seen_ms) <= 5000;
              if (wasOnline) {
                // Freeze: add elapsed-until-last-seen to base, clear session
                const elapsed = Math.max(0, Math.floor((s.last_seen_ms - s.session_start_ms) / 1000));
                updated[id] = {
                  ...s,
                  base_seconds: toSafeSeconds(s.base_seconds || 0) + elapsed,
                  session_start_ms: null,
                };
              }
            }
          });
          return updated;
        });
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setTimeout(connectWebSocket, 3000);
    }
  };

  const fetchSavedMachines = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await api.get('/api/machines');
      if (response.data && response.data.machines) {
        setMachines(response.data.machines);
        
        // Initialize status for all machines
        const initialStatus = {};
        response.data.machines.forEach(m => {
          initialStatus[m.machineId] = {
            base_seconds: toSafeSeconds(m.workingTimeSeconds || 0),
            session_start_ms: null,
            last_seen_ms: null,
            last_count: m.last_count || 0,
          };
        });
        setMachineStatus(initialStatus);
        
        // Request status for all machines
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          response.data.machines.forEach(m => {
            wsRef.current.send(JSON.stringify({
              type: "get_machine_status",
              device_id: m.machineId,
              machine_id: m.machineId
            }));
          });
        }
      }
    } catch (err) {
      console.error('Failed to fetch machines:', err);
      const localSaved = localStorage.getItem('savedMachines');
      if (localSaved) {
        const localMachines = JSON.parse(localSaved);
        setMachines(localMachines);
        const initialStatus = {};
        localMachines.forEach(m => {
          initialStatus[m.machineId] = {
            base_seconds: toSafeSeconds(m.workingTimeSeconds || 0),
            session_start_ms: null,
            last_seen_ms: null,
            last_count: m.last_count || 0,
          };
        });
        setMachineStatus(initialStatus);
        
        // Request status for all machines
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          localMachines.forEach(m => {
            wsRef.current.send(JSON.stringify({
              type: "get_machine_status",
              device_id: m.machineId,
              machine_id: m.machineId
            }));
          });
        }
      }
    } finally {
      setLoading(false);
    }
  };

  const viewCounter = async (machine) => {
    console.log(`🔍 Opening counter for ${machine.machineId}`);
    setCounterMachine(machine);
    
    // Get latest count from machineStatus
    const status = machineStatus[machine.machineId];
    const initialCount = status?.last_count || machine.last_count || 0;
    console.log(`📊 Initial count: ${initialCount}`);
    setLoadingHistory(true);
    
    // Fetch counter history
    try {
      const response = await api.get(`/api/counter/history?device_id=${machine.machineId}&limit=20`);
      if (response.data && response.data.readings) {
        console.log(`📊 Found ${response.data.readings.length} history records`);
        setCounterHistory(response.data.readings);
      } else {
        setCounterHistory([]);
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
      setCounterHistory([]);
    } finally {
      setLoadingHistory(false);
    }
    
    setShowCounterModal(true);
    
    // Request latest status for this machine
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "get_machine_status",
        device_id: machine.machineId,
        machine_id: machine.machineId
      }));
    }
  };

  const filterAndSortMachines = () => {
    let filtered = [...machines];

    if (searchTerm) {
      filtered = filtered.filter(machine => 
        machine.machineId.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (machine.brandName && machine.brandName.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (machine.machineType && machine.machineType.toLowerCase().includes(searchTerm.toLowerCase()))
      );
    }

    if (fabricFilter !== 'all') {
      filtered = filtered.filter(machine => machine.fabricType === fabricFilter);
    }

    if (yearFilter !== 'all') {
      filtered = filtered.filter(machine => {
        const machineYear = Number(machine.manufacturingYear);
        if (Number.isNaN(machineYear)) return false;

        if (yearFilter.startsWith('year-')) {
          const selectedYear = Number(yearFilter.replace('year-', ''));
          return machineYear === selectedYear;
        }

        if (yearFilter.startsWith('range-')) {
          const [, range] = yearFilter.split('range-');
          const [startYear, endYear] = range.split('-').map(Number);
          return machineYear >= startYear && machineYear <= endYear;
        }

        return true;
      });
    }

    filtered.sort((a, b) => {
      let aValue = a[sortConfig.key];
      let bValue = b[sortConfig.key];

      if (sortConfig.key === 'lastPrediction' || sortConfig.key === 'createdAt') {
        aValue = new Date(aValue || a.createdAt || 0);
        bValue = new Date(bValue || b.createdAt || 0);
      }

      if (aValue < bValue) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });

    setFilteredMachines(filtered);
  };

  const handleSort = (key) => {
    setSortConfig({
      key,
      direction: sortConfig.key === key && sortConfig.direction === 'asc' ? 'desc' : 'asc'
    });
  };

  const handleViewDetails = (machine) => {
    setSelectedMachine(machine);
    setShowDetailModal(true);
    setRepredictMode(false);
    setSelectedComponent(null);
    setNewUsageHours('');
    setRepredictResult(null);
  };

  const handleDeleteMachine = async (machineId) => {
    try {
      await api.delete(`/api/machines/${machineId}`);
      setMachines(machines.filter(m => m.machineId !== machineId));
      setDeleteConfirm(null);
      
      const localSaved = JSON.parse(localStorage.getItem('savedMachines') || '[]');
      const updatedLocal = localSaved.filter(m => m.machineId !== machineId);
      localStorage.setItem('savedMachines', JSON.stringify(updatedLocal));
      
    } catch (err) {
      console.error('Failed to delete machine:', err);
      setError('Failed to delete machine. Please try again.');
    }
  };

  // New function to handle component repredict
  const handleRepredictComponent = async (component) => {
    if (!selectedMachine || !newUsageHours) {
      setError('Please enter new usage hours');
      return;
    }

    const hoursValue = Number(newUsageHours);
    if (isNaN(hoursValue) || hoursValue < 0) {
      setError('Please enter valid hours');
      return;
    }

    setRepredictLoading(true);
    setError('');
    setRepredictResult(null);

    try {
      // Prepare updated usage hours
      const updatedUsage = {
        ...selectedMachine.usageHours,
        [component]: hoursValue
      };

      // Call prediction API with updated usage
      const response = await api.post('/api/ml/predict', {
        Fabric_Type: selectedMachine.fabricType,
        M_Year: selectedMachine.manufacturingYear,
        usageDict: updatedUsage
      });

      // Update the predictions for this component
      const updatedPredictions = {
        ...selectedMachine.predictions,
        [component]: response.data.predictions[component]
      };

      // Update the machine in state
      const updatedMachine = {
        ...selectedMachine,
        usageHours: updatedUsage,
        predictions: updatedPredictions,
        lastPrediction: new Date().toISOString()
      };

      // Update in API if available
      try {
        await api.post('/api/machines', updatedMachine);
      } catch (apiErr) {
        console.log('API update failed, saving locally');
      }

      // Update local state
      const updatedMachines = machines.map(m => 
        m.machineId === selectedMachine.machineId ? updatedMachine : m
      );
      setMachines(updatedMachines);
      setSelectedMachine(updatedMachine);

      // Update localStorage
      const localSaved = JSON.parse(localStorage.getItem('savedMachines') || '[]');
      const updatedLocal = localSaved.map(m => 
        m.machineId === selectedMachine.machineId ? updatedMachine : m
      );
      localStorage.setItem('savedMachines', JSON.stringify(updatedLocal));

      // Show result
      setRepredictResult({
        component,
        oldValue: selectedMachine.usageHours[component],
        newValue: hoursValue,
        oldPrediction: selectedMachine.predictions[component],
        newPrediction: response.data.predictions[component]
      });

      // Reset repredict mode
      setTimeout(() => {
        setRepredictMode(false);
        setSelectedComponent(null);
        setNewUsageHours('');
        setRepredictResult(null);
      }, 3000);

    } catch (err) {
      console.error('Repredict failed:', err);
      setError('Failed to repredict component: ' + (err.response?.data?.detail || err.message));
    } finally {
      setRepredictLoading(false);
    }
  };

  const startRepredict = (component) => {
    setSelectedComponent(component);
    const adjustedHours = getAdjustedUsageHours(selectedMachine, selectedMachine.usageHours[component]);
    setNewUsageHours(String(Math.round(adjustedHours * 100) / 100));
    setRepredictMode(true);
    setRepredictResult(null);
  };

  const cancelRepredict = () => {
    setRepredictMode(false);
    setSelectedComponent(null);
    setNewUsageHours('');
    setRepredictResult(null);
    setError('');
  };

  const formatHoursToHourMinute = (hoursValue) => {
    const numericHours = Number(hoursValue);
    if (Number.isNaN(numericHours) || numericHours < 0) return '0h 00m 00s';

    const totalSeconds = Math.round(numericHours * 3600);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${hours}h ${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`;
  };

  const extractRemainingHours = (predictionText) => {
    if (typeof predictionText !== 'string') return 0;
    const match = predictionText.match(/(\d+(?:\.\d+)?)\s*hours?\s*remaining/i);
    return match ? Number(match[1]) : 0;
  };

  const formatPredictionWithHourMinute = (predictionText) => {
    if (typeof predictionText !== 'string') return 'No prediction';

    return predictionText.replace(/(\d+(?:\.\d+)?)\s*hours?\s*remaining/gi, (_, hours) => {
      return `${formatHoursToHourMinute(hours)} remaining`;
    });
  };

  const calculateOverallHealth = (predictions) => {
    if (!predictions) return 0;
    
    let total = 0;
    let count = 0;
    
    Object.entries(predictions).forEach(([component, message]) => {
      if (!['machineId', 'brandName', 'machineType', 'fabricType', 'manufacturingYear', 'usageHours', 'timestamp'].includes(component)) {
        if (typeof message === 'string' && message.includes('hours remaining')) {
          const hours = extractRemainingHours(message);
          total += Math.min(100, (hours / 500) * 100);
          count++;
        } else if (typeof message === 'string' && message.includes('Maintenance Required')) {
          total += 0;
          count++;
        }
      }
    });
    
    return count > 0 ? Math.round(total / count) : 0;
  };

  const getHealthColor = (health) => {
    if (health >= 70) return '#38a169';
    if (health >= 40) return '#ecc94b';
    return '#e53e3e';
  };

  const SortIcon = ({ column }) => {
    if (sortConfig.key !== column) return <span className="sort-icon">↕️</span>;
    return sortConfig.direction === 'asc' ? 
      <span className="sort-icon active">↑</span> : 
      <span className="sort-icon active">↓</span>;
  };

  const yearRanges = [
    { value: 'all', label: 'All Years' },
    { value: 'range-2006-2009', label: '2006 - 2009' },
    { value: 'range-2010-2015', label: '2010 - 2015' },
    { value: 'range-2016-2020', label: '2016 - 2020' },
    ...Array.from({ length: 2020 - 2006 + 1 }, (_, index) => {
      const year = 2006 + index;
      return { value: `year-${year}`, label: `Year ${year}` };
    })
  ];

  const formatTimestamp = (timestamp) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString() + ' ' + date.toLocaleDateString();
    } catch (e) {
      return timestamp;
    }
  };

  // Online = received a count within the last 5 seconds
  const isMachineOnline = (machineId) => {
    const status = machineStatusRef.current[machineId] || machineStatus[machineId];
    if (!status || !status.last_seen_ms) return false;
    return (Date.now() - status.last_seen_ms) <= 5000;
  };

  const formatSecondsToHms = (secondsValue) => {
    const totalSeconds = Math.max(0, Math.floor(Number(secondsValue) || 0));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${hours}h ${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`;
  };

  const getCurrentWorkingSeconds = (machine) => {
    if (!machine || !machine.machineId) return 0;
    const status = machineStatusRef.current[machine.machineId] || {};
    // base_seconds = accumulated total EXCLUDING current session (set by backend on each reconnect)
    const base = toSafeSeconds(status.base_seconds ?? machine.workingTimeSeconds ?? 0);
    const { session_start_ms: sessionStart, last_seen_ms: lastSeen } = status;
    if (!lastSeen || !sessionStart) return base;
    const isOnline = (Date.now() - lastSeen) <= 5000;
    if (isOnline) {
      // Live: count from session start to now
      return base + Math.max(0, Math.floor((Date.now() - sessionStart) / 1000));
    } else {
      // Frozen: count from session start to last received count (never goes up while offline)
      return base + Math.max(0, Math.floor((lastSeen - sessionStart) / 1000));
    }
  };

  const getElapsedWorkingHours = (machine) => {
    if (!machine) return 0;
    const baseSeconds = toSafeSeconds(machine.workingTimeSeconds || 0);
    const currentSeconds = getCurrentWorkingSeconds(machine);
    const elapsedSeconds = Math.max(0, currentSeconds - baseSeconds);
    return elapsedSeconds / 3600;
  };

  const getAdjustedUsageHours = (machine, usageHours) => {
    const baseUsageHours = Number(usageHours);
    const safeBaseUsage = Number.isNaN(baseUsageHours) || baseUsageHours < 0 ? 0 : baseUsageHours;
    return safeBaseUsage + getElapsedWorkingHours(machine);
  };

  const getAdjustedPredictionText = (machine, predictionText) => {
    if (typeof predictionText !== 'string') return 'No prediction';

    const elapsedHours = getElapsedWorkingHours(machine);

    return predictionText.replace(/(\d+(?:\.\d+)?)\s*hours?\s*remaining/gi, (_, hours) => {
      const remaining = Math.max(0, Number(hours) - elapsedHours);
      if (remaining <= 0) return 'Maintenance Required';
      return `${remaining.toFixed(6)} hours remaining`;
    });
  };


  // Get status for machine 0028
  const machine0028Status = machineStatus['0028'] || { online: false, last_count: 0 };

  return (
    <div className="saved-machines-container">
      <div className="saved-machines-header">
        <div>
          <h2>📋 Saved Machines</h2>
        </div>
        <div className="header-actions">
          <button 
            className="refresh-btn"
            onClick={fetchSavedMachines}
            disabled={loading}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="filters-section">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search by Machine ID, Brand, or Type..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
          {searchTerm && (
            <button 
              className="clear-search"
              onClick={() => setSearchTerm('')}
            >
              ×
            </button>
          )}
        </div>

        <div className="filter-controls">
          <select 
            value={fabricFilter} 
            onChange={(e) => setFabricFilter(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Fabric Types</option>
            <option value="Medium">Medium</option>
            <option value="Heavy">Heavy</option>
          </select>

          <select 
            value={yearFilter} 
            onChange={(e) => setYearFilter(e.target.value)}
            className="filter-select"
          >
            {yearRanges.map(range => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>
        </div>

        <div className="results-count">
          Showing {filteredMachines.length} of {machines.length} machines
        </div>
      </div>

      {loading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading saved machines...</p>
        </div>
      ) : filteredMachines.length === 0 ? (
        <div className="empty-state">
          <p>No saved machines found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="machines-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Machine ID</th>
                <th>Brand</th>
                <th>Type</th>
                <th>Fabric</th>
                <th>Year</th>
                <th>Last Count</th>
                <th>Health</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredMachines.map((machine) => {
                const overallHealth = calculateOverallHealth(machine.predictions);
                const status = machineStatus[machine.machineId] || { online: false, last_count: 0 };
                const lastCount = status.last_count !== undefined ? status.last_count : (machine.last_count || 0);
                const isOnline = isMachineOnline(machine.machineId);
                
                return (
                  <tr key={machine.machineId}>
                    <td>
                      <div className="status-cell">
                        <span 
                          className={`status-badge ${isOnline ? 'online' : 'offline'}`}
                          title={isOnline ? 'Device Online' : 'Device Offline'}
                        >
                          ●
                        </span>
                        {isOnline && status.rssi && (
                          <span className="rssi" title={`Signal: ${status.rssi}dBm`}>📶</span>
                        )}
                      </div>
                    </td>
                    <td className="machine-id-cell">{machine.machineId}</td>
                    <td>{machine.brandName || 'JUKI'}</td>
                    <td>{machine.machineType || 'Single Needle Lock Stitch'}</td>
                    <td>
                      <span className={`fabric-badge ${machine.fabricType?.toLowerCase() || 'medium'}`}>
                        {machine.fabricType || 'Medium'}
                      </span>
                    </td>
                    <td>{machine.manufacturingYear || '2020'}</td>
                    <td>
                      <span className="count-badge">{lastCount}</span>
                    </td>
                    <td>
                      <div className="health-cell">
                        <div 
                          className="health-bar"
                          style={{
                            width: `${overallHealth}%`,
                            backgroundColor: getHealthColor(overallHealth)
                          }}
                        ></div>
                        <span className="health-value">{overallHealth}%</span>
                      </div>
                    </td>
                    <td className="actions-cell">
                      <button 
                        className="view-count-btn"
                        onClick={() => viewCounter(machine)}
                      >
                        🔢 View Count
                      </button>
                      <button 
                        className="view-btn"
                        onClick={() => handleViewDetails(machine)}
                      >
                        👁️
                      </button>
                      <button 
                        className="delete-btn"
                        onClick={() => setDeleteConfirm(machine.machineId)}
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Counter Modal */}
      {showCounterModal && counterMachine && (
        <div className="modal-overlay" onClick={() => setShowCounterModal(false)}>
          <div className="modal-content counter-modal" onClick={e => e.stopPropagation()}>
            <button 
              className="modal-close"
              onClick={() => setShowCounterModal(false)}
            >
              ×
            </button>
            
            <h3>🔢 Live Counter - {counterMachine.machineId}</h3>
            
            <div className="live-counter-display">
              <div className="current-count-large">
                <span className="count-number">
                  {machineStatus[counterMachine.machineId]?.last_count || 0}
                </span>
                <span className="count-label">needle movements</span>
              </div>
              <div className="machine-status-indicator">
                <span className={`status-dot ${isMachineOnline(counterMachine.machineId) ? 'connected' : 'disconnected'}`}></span>
                {isMachineOnline(counterMachine.machineId) ? 'Device Online' : 'Device Offline'}
              </div>
            </div>

            <div className="counter-history">
              <h4>Recent Readings</h4>
              {loadingHistory ? (
                <div className="loading-spinner">Loading history...</div>
              ) : (
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {counterHistory.length > 0 ? (
                      counterHistory.map((reading, index) => (
                        <tr key={reading.id || index}>
                          <td>{formatTimestamp(reading.timestamp)}</td>
                          <td className="count-cell">{reading.count}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="2" className="no-data">No readings yet</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              )}
            </div>

            <div className="modal-footer">
              <button 
                className="close-btn"
                onClick={() => setShowCounterModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-content confirm-modal">
            <h3>Confirm Delete</h3>
            <p>Delete machine <strong>{deleteConfirm}</strong>?</p>
            <div className="modal-actions">
              <button onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button onClick={() => handleDeleteMachine(deleteConfirm)}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {/* Details Modal */}
      {showDetailModal && selectedMachine && (
        <div className="modal-overlay" onClick={() => setShowDetailModal(false)}>
          <div className="modal-content detail-modal" onClick={e => e.stopPropagation()}>
            <button
              className="modal-close"
              onClick={() => setShowDetailModal(false)}
            >
              ×
            </button>

            <h3>Machine Details - {selectedMachine.machineId}</h3>

            {repredictResult && (
              <div className="repredict-success">
                <h4>✅ Component Updated Successfully!</h4>
                <p>
                  <strong>{repredictResult.component}</strong> usage hours changed from{' '}
                  {repredictResult.oldValue} to {repredictResult.newValue}
                </p>
                <p>Prediction updated: {repredictResult.newPrediction}</p>
              </div>
            )}

            <div className="detail-section">
              <h4>📋 Basic Information</h4>
              <div className="detail-grid">
                <div className="detail-item">
                  <label>Machine ID:</label>
                  <span>{selectedMachine.machineId}</span>
                </div>
                <div className="detail-item">
                  <label>Brand:</label>
                  <span>{selectedMachine.brandName}</span>
                </div>
                <div className="detail-item">
                  <label>Type:</label>
                  <span>{selectedMachine.machineType}</span>
                </div>
                <div className="detail-item">
                  <label>Fabric Type:</label>
                  <span className={`fabric-badge ${selectedMachine.fabricType?.toLowerCase()}`}>
                    {selectedMachine.fabricType}
                  </span>
                </div>
                <div className="detail-item">
                  <label>Manufacturing Year:</label>
                  <span>{selectedMachine.manufacturingYear}</span>
                </div>
                <div className="detail-item">
                  <label>Last Prediction:</label>
                  <span>{new Date(selectedMachine.lastPrediction || selectedMachine.timestamp).toLocaleString()}</span>
                </div>
                <div className="detail-item">
                  <label>Machine Status:</label>
                  <span className={isMachineOnline(selectedMachine.machineId) ? 'status-online-text' : 'status-offline-text'}>
                    {isMachineOnline(selectedMachine.machineId) ? 'Online' : 'Offline'}
                  </span>
                </div>
                <div className="detail-item">
                  <label>Machine Working Time:</label>
                  <span>{formatSecondsToHms(getCurrentWorkingSeconds(selectedMachine))}</span>
                </div>
              </div>
            </div>

            <div className="detail-section">
              <div className="section-header">
                <h4>⏱️ Component Usage Hours & Predictions</h4>
                {repredictMode && (
                  <button
                    className="cancel-repredict-btn"
                    onClick={cancelRepredict}
                  >
                    Cancel Repredict
                  </button>
                )}
              </div>

              <div className="components-grid">
                {selectedMachine.usageHours && Object.entries(selectedMachine.usageHours).map(([component, hours]) => {
                  const basePrediction = selectedMachine.predictions?.[component] || 'No prediction';
                  const adjustedUsageHours = getAdjustedUsageHours(selectedMachine, hours);
                  const adjustedPrediction = getAdjustedPredictionText(selectedMachine, basePrediction);
                  const formattedPrediction = formatPredictionWithHourMinute(adjustedPrediction);
                  const isSelected = selectedComponent === component;
                  const isCritical = adjustedPrediction.includes('Maintenance Required');
                  const hoursRemaining = extractRemainingHours(adjustedPrediction);

                  return (
                    <div
                      key={component}
                      className={`component-card ${isSelected ? 'selected' : ''} ${isCritical ? 'critical' : ''}`}
                    >
                      <div className="component-header">
                        <strong>{component}</strong>
                        <div className="component-actions">
                          {!repredictMode ? (
                            <button
                              className="repredict-btn"
                              onClick={() => startRepredict(component)}
                              title="Repredict this component"
                            >
                              🔄 Repredict
                            </button>
                          ) : isSelected && (
                            <span className="editing-badge">✏️ Editing</span>
                          )}
                        </div>
                      </div>

                      {isSelected && repredictMode ? (
                        <div className="repredict-form">
                          <div className="repredict-input-group">
                            <label>New Usage Hours:</label>
                            <input
                              type="number"
                              value={newUsageHours}
                              onChange={(e) => setNewUsageHours(e.target.value)}
                              min="0"
                              step="1"
                              autoFocus
                            />
                          </div>
                          <div className="repredict-actions">
                            <button
                              className="repredict-submit-btn"
                              onClick={() => handleRepredictComponent(component)}
                              disabled={repredictLoading}
                            >
                              {repredictLoading ? '⏳ Updating...' : '✅ Update'}
                            </button>
                            <button
                              className="repredict-cancel-btn"
                              onClick={cancelRepredict}
                            >
                              ✖ Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="component-details">
                            <div className="usage-info">
                              <span className="info-label">Used:</span>
                              <span className="info-value">{formatHoursToHourMinute(adjustedUsageHours)}</span>
                            </div>
                            <div className="prediction-info">
                              <span className="info-label">Prediction:</span>
                              <span className={`info-value ${isCritical ? 'critical-text' : ''}`}>
                                {formattedPrediction}
                              </span>
                            </div>
                            {!isCritical && hoursRemaining > 0 && (
                              <div className="rul-info">
                                <div className="rul-bar-container">
                                  <div
                                    className="rul-bar-fill"
                                    style={{
                                      width: `${Math.min(100, (hoursRemaining / 500) * 100)}%`,
                                      backgroundColor: hoursRemaining < 100 ? '#ecc94b' : '#38a169'
                                    }}
                                  ></div>
                                </div>
                                <span className="rul-text">{formatHoursToHourMinute(hoursRemaining)} RUL</span>
                              </div>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="close-btn"
                onClick={() => setShowDetailModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SavedMachines;