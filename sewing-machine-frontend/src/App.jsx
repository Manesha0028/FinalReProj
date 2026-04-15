import React, { useState, useEffect } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import SavedMachines from './components/SavedMachines';
import MaintenancePredictor from './components/MaintenancePredictor';
import { verifyAuth } from './services/api';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await verifyAuth();
      if (response.data.authenticated) {
        setIsAuthenticated(true);
        setUser({
          username: response.data.username,
          role: response.data.role
        });
      }
    } catch (err) {
      console.error('Auth check failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (userData) => {
    setIsAuthenticated(true);
    setUser(userData);

    const validPaths = ['/dashboard', '/maintenance-predictor', '/saved-machines'];
    navigate(validPaths.includes(location.pathname) ? location.pathname : '/dashboard', { replace: true });
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setUser(null);
    navigate('/', { replace: true });
  };

  if (loading) {
    return <div className="loading">Loading application...</div>;
  }

  return (
    <div className="App min-h-screen bg-slate-50 text-slate-800">
      {!isAuthenticated ? (
        <Login onLogin={handleLogin} />
      ) : (
        <>
          <nav className="main-nav shadow-lg">
            <div className="nav-brand">Sewing Machine Management</div>
            <div className="nav-links">
              <NavLink to="/dashboard" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📊 Dashboard
              </NavLink>
              <NavLink to="/maintenance-predictor" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                🔧 Maintenance Predictor
              </NavLink>
              <NavLink to="/saved-machines" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📋 Saved Machines
              </NavLink>
            </div>
            <div className="nav-user">
              <span className="user-info">
                <span className="username">{user?.username}</span>
                <span className="role-badge">{user?.role}</span>
              </span>
              <button onClick={handleLogout} className="logout-btn">Logout</button>
            </div>
          </nav>

          <div className="w-full mt-4 px-4 py-2 sm:px-6 lg:px-8">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard user={user} onLogout={handleLogout} />} />
              <Route path="/maintenance-predictor" element={<MaintenancePredictor />} />
              <Route path="/saved-machines" element={<SavedMachines />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </div>
        </>
      )}
    </div>
  );
}

export default App;