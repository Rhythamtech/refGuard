import React, { useState, useEffect } from 'react';
import CustomerChat from './CustomerChat';
import AdminDashboard from './AdminDashboard';
import LoginPage from './LoginPage';

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [role, setRole] = useState<string | null>(localStorage.getItem('role'));
  const [userName, setUserName] = useState<string | null>(localStorage.getItem('userName'));
  const [userId, setUserId] = useState<string | null>(localStorage.getItem('userId'));

  const handleLoginSuccess = (jwtToken: string, userRole: string, name: string) => {
    localStorage.setItem('token', jwtToken);
    localStorage.setItem('role', userRole);
    localStorage.setItem('userName', name);
    setToken(jwtToken);
    setRole(userRole);
    setUserName(name);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('userName');
    localStorage.removeItem('userId');
    setToken(null);
    setRole(null);
    setUserName(null);
    setUserId(null);
  };

  if (!token) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  // If customer is logged in, show CustomerChat
  if (role === 'customer') {
    return <CustomerChat onLogout={handleLogout} />;
  }

  // If admin, supervisor or agent is logged in, show AdminDashboard
  if (role === 'admin' || role === 'supervisor' || role === 'agent') {
    return <AdminDashboard onLogout={handleLogout} />;
  }

  // Fallback
  return <LoginPage onLoginSuccess={handleLoginSuccess} />;
}
