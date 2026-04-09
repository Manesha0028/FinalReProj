import axios from 'axios';

const API_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true  // Important for cookies!
});

export const login = (username, password, role) => {
  return api.post('/auth/login', { username, password, role });
};

export const logout = () => {
  return api.post('/auth/logout');
};

export const getDashboard = () => {
  return api.get('/api/dashboard');
};

export const verifyAuth = () => {
  return api.get('/auth/verify');
};

export const getCurrentUser = () => {
  return api.get('/auth/me');
};

export default api;