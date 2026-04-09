import React, { useState, useEffect } from 'react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import SavedMachines from './components/SavedMachines';
import { verifyAuth } from './services/api';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState('dashboard');

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
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setUser(null);
    setCurrentPage('dashboard');
  };

  // Debug logging
  console.log('Current page:', currentPage);
  console.log('Is authenticated:', isAuthenticated);
  console.log('Loading:', loading);

  if (loading) {
    return <div className="loading">Loading application...</div>;
  }

  return (
    <div className="App">
      {!isAuthenticated ? (
        <Login onLogin={handleLogin} />
      ) : (
        <>
          <nav className="main-nav" style={{ border: '2px solid red' }}> {/* Temporary red border */}
            <div className="nav-brand">Sewing Machine Management</div>
            <div className="nav-links">
              <button 
                className={`nav-link ${currentPage === 'dashboard' ? 'active' : ''}`}
                onClick={() => {
                  console.log('Dashboard clicked');
                  setCurrentPage('dashboard');
                }}
              >
                📊 Dashboard
              </button>
              <button 
                className={`nav-link ${currentPage === 'saved-machines' ? 'active' : ''}`}
                onClick={() => {
                  console.log('Saved Machines clicked');
                  setCurrentPage('saved-machines');
                }}
              >
                📋 Saved Machines
              </button>
            </div>
            <div className="nav-user">
              <span className="user-info">
                <span className="username">{user?.username}</span>
                <span className="role-badge">{user?.role}</span>
              </span>
              <button onClick={handleLogout} className="logout-btn">Logout</button>
            </div>
          </nav>

          <div style={{ padding: '1rem', border: '2px solid blue', marginTop: '1rem' }}> {/* Temporary blue border */}
            <h3>Current Page: {currentPage}</h3>
            {currentPage === 'dashboard' && <Dashboard user={user} onLogout={handleLogout} />}
            {currentPage === 'saved-machines' && <SavedMachines />}
          </div>
        </>
      )}
    </div>
  );
}

export default App;