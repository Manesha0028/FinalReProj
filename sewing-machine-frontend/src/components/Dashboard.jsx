import React, { useState } from 'react';
import MaintenancePredictor from './MaintenancePredictor';
import './Dashboard.css';

const Dashboard = ({ user, onLogout }) => {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div className="dashboard">
      {/* Remove the navbar from here - it's now in App.jsx */}
      
      <div className="dashboard-content">
        <div className="dashboard-tabs">
          <button 
            className={`tab ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            📊 Overview
          </button>
          <button 
            className={`tab ${activeTab === 'predictor' ? 'active' : ''}`}
            onClick={() => setActiveTab('predictor')}
          >
            🔧 Maintenance Predictor
          </button>
        </div>

        {activeTab === 'dashboard' && (
          <div className="welcome-section">
            <h1>Welcome, {user?.username}!</h1>
            <p>Role: <span className="role-highlight">{user?.role}</span></p>
            
            <div className="dashboard-cards">
              <div className="card">
                <h3>Quick Actions</h3>
                <div className="quick-actions">
                  <button className="action-btn">View All Machines</button>
                  <button className="action-btn">Generate Reports</button>
                  <button className="action-btn">Check Maintenance</button>
                </div>
              </div>
              
              <div className="card">
                <h3>System Status</h3>
                <p>✅ All systems operational</p>
                <p>📊 ML Model: Active</p>
                <p>🔗 Database: Connected</p>
              </div>
              
              <div className="card">
                <h3>Recent Activity</h3>
                <p>No recent activity</p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'predictor' && (
          <MaintenancePredictor />
        )}
      </div>
    </div>
  );
};

export default Dashboard;