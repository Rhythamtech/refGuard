import React, { useState } from 'react';
import { api } from './api';
import { User, ShieldAlert, KeyRound, Bot, HelpCircle } from 'lucide-react';

interface LoginPageProps {
  onLoginSuccess: (token: string, role: string, name: string) => void;
}

export default function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const [activeTab, setActiveTab] = useState<'customer' | 'admin'>('customer');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password');
      return;
    }

    setError('');
    setLoading(true);

    try {
      let result;
      if (activeTab === 'customer') {
        result = await api.loginCustomer(email, password);
      } else {
        result = await api.loginAdmin(email, password);
      }

      onLoginSuccess(result.access_token, result.role, result.name);
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const selectMockUser = (userEmail: string, passWord: string) => {
    setEmail(userEmail);
    setPassword(passWord);
    setError('');
  };

  const mockCustomers = [
    { name: 'Aarav Sharma', email: 'aarav.sharma@gmail.com', pass: 'aarav@pass123' },
    { name: 'Priya Patel', email: 'priya.patel@yahoo.com', pass: 'priya@pass123' },
    { name: 'Rajesh Iyer', email: 'rajesh.iyer@outlook.com', pass: 'rajesh@pass123' },
  ];

  const mockAdmins = [
    { name: 'Suresh Kumar (Admin)', email: 'suresh.admin@ecommerce.com', pass: 'suresh@adminpass' },
    { name: 'Meera Jasmine (Supervisor)', email: 'meera.supervisor@ecommerce.com', pass: 'meera@superpass' },
    { name: 'Vijay Raghavan (Agent)', email: 'vijay.agent@ecommerce.com', pass: 'vijay@agentpass' },
  ];

  return (
    <div className="bg-[#E4E3E0] min-h-screen w-full flex items-center justify-center font-sans p-4">
      <div className="w-full max-w-md bg-[#fdfdfc] border-2 border-[#141414] shadow-[4px_4px_0px_#141414] p-6 sm:p-8 flex flex-col gap-6">
        {/* Brand Header */}
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="w-12 h-12 bg-[#141414] rounded-sm flex items-center justify-center text-white">
            <Bot size={28} />
          </div>
          <h1 className="font-bold text-2xl tracking-tight uppercase mt-2">
            Refund<span className="italic font-serif">AI</span>
          </h1>
          <p className="text-xs text-gray-500 font-mono">INTELLIGENT REFUND DECISION SYSTEM</p>
        </div>

        {/* Tab Toggle */}
        <div className="flex border border-[#141414] bg-[#E4E3E0] p-1 font-mono text-xs">
          <button
            onClick={() => {
              setActiveTab('customer');
              setEmail('');
              setPassword('');
              setError('');
            }}
            className={`flex-1 py-2 font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'customer'
                ? 'bg-[#141414] text-white shadow-[2px_2px_0px_rgba(0,0,0,0.15)]'
                : 'text-[#141414] hover:bg-gray-200'
            }`}
          >
            <User size={14} /> Customer Portal
          </button>
          <button
            onClick={() => {
              setActiveTab('admin');
              setEmail('');
              setPassword('');
              setError('');
            }}
            className={`flex-1 py-2 font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'admin'
                ? 'bg-[#141414] text-white shadow-[2px_2px_0px_rgba(0,0,0,0.15)]'
                : 'text-[#141414] hover:bg-gray-200'
            }`}
          >
            <ShieldAlert size={14} /> Admin Staff
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleLogin} className="flex flex-col gap-4">
          {error && (
            <div className="p-3 border border-red-500 bg-red-50 text-red-700 text-xs font-medium">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label className="text-xs uppercase font-bold tracking-wider opacity-60">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              className="border border-[#141414] bg-[#E4E3E0] p-2 text-sm focus:outline-none focus:bg-white font-medium"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs uppercase font-bold tracking-wider opacity-60">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="border border-[#141414] bg-[#E4E3E0] p-2 text-sm focus:outline-none focus:bg-white font-mono"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#141414] text-white py-3 uppercase tracking-widest font-bold text-xs hover:opacity-90 transition-opacity border-2 border-[#141414] active:translate-y-0.5"
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        {/* Quick Credentials Selection */}
        <div className="border-t border-dashed border-[#141414] pt-4">
          <div className="flex items-center gap-1.5 mb-2.5">
            <HelpCircle size={14} className="opacity-60" />
            <span className="text-[10px] font-mono font-bold uppercase opacity-60 tracking-wider">
              Quick Test Accounts
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {(activeTab === 'customer' ? mockCustomers : mockAdmins).map((item) => (
              <button
                key={item.email}
                onClick={() => selectMockUser(item.email, item.pass)}
                className="text-left w-full p-2 border border-gray-300 bg-gray-50 hover:bg-gray-100 hover:border-[#141414] transition-all flex items-center justify-between text-xs"
              >
                <div>
                  <div className="font-bold text-[#141414]">{item.name}</div>
                  <div className="text-[10px] text-gray-500 font-mono">{item.email}</div>
                </div>
                <KeyRound size={12} className="opacity-40" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
