import React, { useState, useEffect } from 'react';
import { api, AdminStats, AdminLog, QueueItem } from './api';
import {
  AlertTriangle,
  Ban,
  Bell,
  CheckCircle2,
  XCircle,
  Flag,
  LayoutDashboard,
  Brain,
  Plus,
  Receipt,
  Settings,
  SlidersHorizontal,
  TrendingDown,
  LogOut,
  UserCheck,
  Trash2,
  X
} from 'lucide-react';

export default function AdminDashboard({ onLogout }: { onLogout: () => void }) {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [logs, setLogs] = useState<AdminLog[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [adminName, setAdminName] = useState('Admin Staff');
  const [activeTab, setActiveTab] = useState<'overview' | 'queue' | 'logs'>('overview');
  const [selectedLog, setSelectedLog] = useState<AdminLog | null>(null);

  // Load stats, logs, queue
  const loadDashboardData = async () => {
    try {
      const adminStats = await api.getAdminStats();
      setStats(adminStats);

      const adminLogs = await api.getAdminLogs(20, 0);
      setLogs(adminLogs);

      const adminQueue = await api.getAdminQueue();
      setQueue(adminQueue);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    }
  };

  useEffect(() => {
    const name = localStorage.getItem('userName') || 'Admin Staff';
    setAdminName(name);

    async function initialLoad() {
      setLoading(true);
      await loadDashboardData();
      setLoading(false);
    }
    initialLoad();

    // Auto refresh logs & stats every 10 seconds
    const interval = setInterval(() => {
      loadDashboardData();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const handleDecision = async (reviewId: number, decision: 'approved' | 'rejected') => {
    setActionLoading(reviewId);
    try {
      await api.decideQueueItem(reviewId, decision);
      // Reload dashboard
      await loadDashboardData();
    } catch (err: any) {
      alert(`Error processing decision: ${err.message || 'Server error'}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleClearLogs = () => {
    if (window.confirm('Are you sure you want to clear the logs from the view? This action is client-side only.')) {
      setLogs([]);
    }
  };

  return (
    <div className="bg-[#E4E3E0] text-[#141414] min-h-screen flex flex-col lg:flex-row overflow-hidden font-sans xl:items-center xl:justify-center">
      <div className="w-full xl:max-w-screen-2xl flex flex-col lg:flex-row h-full overflow-hidden border-x-0 xl:border-x-8 xl:border-b-8 border-gray-100 bg-[#fdfdfc]">
        
        {/* TopNavBar */}
        <header className="bg-[#fdfdfc] text-[#141414] relative lg:absolute z-10 w-full h-14 border-b border-[#141414] flex justify-between items-center px-4 sm:px-6 max-w-full xl:max-w-[calc(1536px-16px)]">
          <div className="flex items-center gap-2 sm:gap-6">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 sm:w-6 sm:h-6 bg-[#141414] rounded-sm flex items-center justify-center">
                <div className="w-2.5 h-0.5 sm:w-3 sm:h-1 bg-[#fdfdfc] rotate-45"></div>
              </div>
              <span className="font-bold text-base sm:text-lg tracking-tight uppercase">Refund<span className="italic font-serif">AI</span></span>
            </div>
            <nav className="hidden md:flex gap-4 lg:gap-6 items-center lg:ml-8">
              <a href="#" className="text-[10px] sm:text-xs font-bold uppercase tracking-widest border-b-2 border-[#141414] py-1 text-[#141414]">
                Admin Dashboard
              </a>
            </nav>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <div className="hidden sm:flex items-center gap-1.5 text-[10px] font-mono mr-2">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
              SYSTEM RUNNING
            </div>
            
            <span className="text-xs font-bold uppercase tracking-wider hidden sm:inline-block">
              {adminName}
            </span>

            <button 
              onClick={onLogout} 
              className="p-1.5 hover:bg-gray-100 border border-transparent hover:border-[#141414] transition-all flex items-center gap-1 text-xs font-bold uppercase tracking-widest"
              title="Logout"
            >
              <LogOut size={14} /> <span className="hidden md:inline">Sign Out</span>
            </button>
          </div>
        </header>

        {/* SideNavBar (Desktop Only) */}
        <aside className="bg-[#fdfdfc] text-[#141414] border-r border-[#141414] flex flex-col h-full lg:h-screen w-48 lg:pt-14 hidden lg:flex flex-shrink-0 z-0 font-sans">
          <nav className="flex flex-col flex-grow">
            <button
              onClick={() => setActiveTab('overview')}
              className={`p-4 text-[10px] uppercase font-bold tracking-widest flex items-center gap-3 transition-all border-b border-[#141414] text-left cursor-pointer ${
                activeTab === 'overview' ? 'bg-[#141414] text-white font-extrabold' : 'hover:bg-[#E4E3E0]'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('queue')}
              className={`p-4 text-[10px] uppercase font-bold tracking-widest flex items-center gap-3 transition-all border-b border-[#141414] text-left cursor-pointer ${
                activeTab === 'queue' ? 'bg-[#141414] text-white font-extrabold' : 'hover:bg-[#E4E3E0]'
              }`}
            >
              Queue Tasks ({queue.length})
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`p-4 text-[10px] uppercase font-bold tracking-widest flex items-center gap-3 transition-all border-b border-[#141414] text-left cursor-pointer ${
                activeTab === 'logs' ? 'bg-[#141414] text-white font-extrabold' : 'hover:bg-[#E4E3E0]'
              }`}
            >
              AI Logs ({logs.length})
            </button>
          </nav>
          <div className="p-4 text-[10px] font-mono opacity-50 border-t border-[#141414] text-center">
            RefundGuard v1.0
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-grow p-4 sm:p-6 lg:pt-20 overflow-y-auto w-full h-full lg:h-screen flex flex-col lg:grid lg:grid-cols-12 gap-4 sm:gap-6 bg-[#E4E3E0]">
          
          {activeTab === 'overview' && (
            <>
              {/* Top KPIs Section */}
              <section className="col-span-12 lg:col-span-12 grid grid-cols-1 sm:grid-cols-3 border border-[#141414] bg-[#fdfdfc] shrink-0 font-sans">
                {/* KPI 1 */}
                <div className="p-4 border-b sm:border-b-0 sm:border-r border-[#141414] flex flex-col justify-between">
                  <span className="text-[10px] uppercase font-bold opacity-40">Auto-Approval Success Rate</span>
                  <div className="text-3xl font-mono mt-1 font-bold">
                    {stats ? `${stats.success_rate}` : '0.0'}
                    <span className="text-sm opacity-60">%</span>
                  </div>
                </div>

                {/* KPI 2 */}
                <div className="p-4 border-b sm:border-b-0 sm:border-r border-[#141414] flex flex-col justify-between">
                  <span className="text-[10px] uppercase font-bold opacity-40">Avg Resolution Speed</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <div className="text-3xl font-mono font-bold">
                      {stats ? `${stats.avg_resolution_seconds}s` : '0.0s'}
                    </div>
                    <div className="flex items-center text-[10px] font-bold text-green-700 uppercase tracking-widest">
                      <TrendingDown size={12} className="mr-1" />
                      REALTIME
                    </div>
                  </div>
                </div>

                {/* KPI 3 */}
                <div className="p-4 flex flex-col justify-between">
                  <span className="text-[10px] uppercase font-bold opacity-40">Total Decisions Handled</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <div className="text-3xl font-mono font-bold">
                      {stats ? stats.total_processed : '0'}
                    </div>
                    <div className="flex items-center text-[10px] font-bold text-blue-600 uppercase tracking-widest">
                      {stats ? `${stats.pending_count} pending review` : ''}
                    </div>
                  </div>
                </div>
              </section>

              {/* Left Panel: Live Reasoning Logs */}
              <section className="col-span-12 lg:col-span-7 bg-[#fdfdfc] border border-[#141414] flex flex-col h-[400px] md:h-[500px] lg:h-[600px] overflow-hidden shadow-[2px_2px_0px_#141414]">
                <div className="bg-[#141414] text-white p-2 text-[10px] uppercase font-bold tracking-widest flex justify-between">
                  <span className="flex items-center gap-2">
                    <div className="pulse-dot bg-white"></div>
                    Live Decision Logs
                  </span>
                  <span className="opacity-50 font-sans">Auto-updates</span>
                </div>

                <div className="flex-1 bg-white p-4 font-mono text-xs leading-tight space-y-4 overflow-y-auto">
                  {loading ? (
                    <div className="text-center text-gray-500 py-8">Loading logs...</div>
                  ) : logs.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">No refund logs yet.</div>
                  ) : (
                    logs.map((log) => (
                      <div
                        key={log.id}
                        className={`log-entry border-l-4 pl-3 py-1 ${
                          log.decision === 'approved'
                            ? 'border-green-500 bg-green-50/20'
                            : log.decision === 'rejected'
                            ? 'border-red-500 bg-red-50/20'
                            : 'border-yellow-500 bg-yellow-50/20'
                        }`}
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-bold text-[#141414]">DECISION #{log.id} (REQ-{log.refund_request_id})</span>
                          <span className="text-[9px] opacity-50">
                            {log.decided_at ? new Date(log.decided_at + 'Z').toLocaleTimeString() : new Date(log.created_at + 'Z').toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="opacity-90 text-[11px] font-sans">
                          <strong>Customer:</strong> {log.customer_name} | <strong>Reason:</strong> "{log.reason}"
                        </p>
                        <p className="opacity-75 text-[10px] mt-1 font-sans whitespace-pre-wrap">
                          <strong>Audit Review:</strong> {log.review || 'No audit context available.'}
                        </p>
                        <div className="mt-1 flex justify-between items-center w-full">
                          <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 border ${
                            log.decision === 'approved'
                              ? 'text-green-700 border-green-700 bg-green-50'
                              : 'text-red-700 border-red-700 bg-red-50'
                          }`}>
                            {log.decision}
                          </span>
                          <span className="font-bold text-gray-800 font-mono text-xs">
                            ₹{log.refunded_amount.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              {/* Right Panel: Decision Center (Human Review Queue) */}
              <section className="col-span-12 lg:col-span-5 bg-[#E4E3E0] border border-[#141414] flex flex-col h-[400px] md:h-[500px] lg:h-[600px] overflow-hidden shadow-[2px_2px_0px_#141414]">
                <h2 className="font-serif italic text-lg font-semibold border-b border-[#141414] p-4 bg-[#fdfdfc] flex justify-between items-center">
                  <span>Review Queue</span>
                  <span className="text-xs font-mono font-bold bg-yellow-100 text-yellow-800 border border-yellow-800 px-2 py-0.5">
                    {queue.length} Pending
                  </span>
                </h2>
                <div className="flex-grow overflow-y-auto p-4 space-y-4 font-sans">
                  {loading ? (
                    <div className="text-center text-gray-500 py-8">Loading queue...</div>
                  ) : queue.length === 0 ? (
                    <div className="bg-[#fdfdfc] border border-[#141414] p-6 text-center text-xs text-gray-500 font-mono">
                      No pending refund decisions in queue.
                    </div>
                  ) : (
                    queue.map((item) => (
                      <div
                        key={item.review_id}
                        className="bg-[#fdfdfc] border border-[#141414] p-4 flex flex-col gap-3 shadow-[2px_2px_0px_#141414] hover:bg-gray-50/50 transition-all text-left"
                      >
                        <div>
                          <div className="flex justify-between items-center">
                            <span className="font-mono text-xs font-bold text-yellow-800 uppercase tracking-widest bg-yellow-50 border border-yellow-400 px-1.5 py-0.5">
                              Fraud Score: {item.fraud_score}
                            </span>
                            <span className="font-mono text-[10px] text-gray-500 font-mono">
                              {new Date(item.review_created_at + 'Z').toLocaleDateString()}
                            </span>
                          </div>
                          
                          <div className="mt-2.5">
                            <div className="font-bold text-sm text-[#141414]">ORD-{item.order_item_id} by {item.customer_name}</div>
                            <div className="text-[11px] font-medium text-gray-600 mt-1">
                              <strong>Reason:</strong> "{item.reason}"
                            </div>
                          </div>

                          {item.signals && item.signals.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2.5">
                              {item.signals.map((sig, idx) => (
                                <span
                                  key={idx}
                                  className="text-[9px] uppercase font-mono font-bold px-1.5 py-0.5 bg-red-50 text-red-700 border border-red-200"
                                >
                                  {sig.replace('_', ' ')}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="flex gap-2 border-t border-dashed border-gray-300 pt-3 mt-1 justify-between items-center w-full">
                          <span className="text-sm font-mono font-bold text-green-700">
                            ₹{item.requested_refund_amount.toFixed(2)}
                          </span>
                          
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleDecision(item.review_id, 'rejected')}
                              disabled={actionLoading !== null}
                              className="px-2.5 py-1 text-[10px] uppercase font-bold tracking-wider bg-red-100 text-red-800 border border-red-800 hover:bg-red-200 active:translate-y-0.5 disabled:opacity-50 cursor-pointer"
                            >
                              Reject
                            </button>
                            <button
                              onClick={() => handleDecision(item.review_id, 'approved')}
                              disabled={actionLoading !== null}
                              className="px-2.5 py-1 text-[10px] uppercase font-bold tracking-wider bg-green-100 text-green-800 border border-green-800 hover:bg-green-200 active:translate-y-0.5 disabled:opacity-50 cursor-pointer"
                            >
                              Approve
                            </button>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>
            </>
          )}

          {activeTab === 'queue' && (
            <section className="col-span-12 bg-[#fdfdfc] border border-[#141414] flex flex-col min-h-[500px] overflow-hidden shadow-[2px_2px_0px_#141414] font-sans">
              <div className="bg-[#141414] text-white p-3 text-xs uppercase font-bold tracking-widest flex justify-between items-center">
                <span>Task Review Queue</span>
                <span className="bg-yellow-100 text-yellow-800 border border-yellow-800 px-2.5 py-0.5 text-[10px] font-mono">
                  {queue.length} Tasks Pending Review
                </span>
              </div>
              
              <div className="p-6 flex-grow overflow-y-auto bg-gray-50 flex flex-col gap-4">
                {queue.length === 0 ? (
                  <div className="bg-[#fdfdfc] border border-[#141414] p-12 text-center text-sm text-gray-500 font-mono">
                    No escalated tasks awaiting manual decision override.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {queue.map((item) => (
                      <div key={item.review_id} className="bg-white border border-[#141414] p-4 flex flex-col justify-between gap-4 shadow-[2px_2px_0px_#141414] text-left">
                        <div>
                          <div className="flex justify-between items-start">
                            <span className="font-mono text-xs font-bold text-yellow-800 bg-yellow-50 border border-yellow-400 px-2 py-0.5">
                              Fraud Risk Score: {item.fraud_score}
                            </span>
                            <span className="text-[10px] font-mono text-gray-400 font-mono">
                              Escalated {new Date(item.review_created_at + 'Z').toLocaleDateString()} at {new Date(item.review_created_at + 'Z').toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                            </span>
                          </div>
                          
                          <h3 className="font-bold text-base text-[#141414] mt-3">Order #{item.order_item_id} • {item.customer_name}</h3>
                          <p className="text-xs text-gray-500 font-mono mt-1">Customer ID: #{item.customer_id} | Category: {item.reason_category}</p>
                          
                          <div className="mt-3 bg-gray-50 p-2.5 border border-dashed border-gray-300 text-xs">
                            <strong>Customer Statement:</strong> "{item.reason}"
                          </div>

                          {item.signals && item.signals.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-3">
                              {item.signals.map((sig, idx) => (
                                <span key={idx} className="text-[9px] uppercase font-mono font-bold px-2 py-0.5 bg-red-50 text-red-700 border border-red-200">
                                  {sig.replace('_', ' ')}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="flex justify-between items-center border-t border-gray-200 pt-3">
                          <span className="text-base font-mono font-bold text-green-700 font-mono">
                            ₹{item.requested_refund_amount.toLocaleString('en-IN')}
                          </span>
                          
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleDecision(item.review_id, 'rejected')}
                              disabled={actionLoading !== null}
                              className="px-4 py-1.5 text-[10px] uppercase font-bold tracking-widest bg-red-100 text-red-800 border border-red-800 hover:bg-red-200 active:translate-y-0.5 disabled:opacity-50 cursor-pointer"
                            >
                              Deny Refund
                            </button>
                            <button
                              onClick={() => handleDecision(item.review_id, 'approved')}
                              disabled={actionLoading !== null}
                              className="px-4 py-1.5 text-[10px] uppercase font-bold tracking-widest bg-green-100 text-green-800 border border-green-800 hover:bg-green-200 active:translate-y-0.5 disabled:opacity-50 cursor-pointer"
                            >
                              Approve Refund
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          )}

          {activeTab === 'logs' && (
            <section className="col-span-12 bg-[#fdfdfc] border border-[#141414] flex flex-col min-h-[500px] overflow-hidden shadow-[2px_2px_0px_#141414] font-sans">
              <div className="bg-[#141414] text-white p-3 text-xs uppercase font-bold tracking-widest flex justify-between items-center">
                <span>AI Decision Logs</span>
                <div className="flex items-center gap-4">
                  <span className="opacity-60 text-[10px] font-mono">Total logs: {logs.length}</span>
                  <button 
                    onClick={handleClearLogs}
                    className="flex items-center gap-1.5 px-2 py-1 bg-red-600 hover:bg-red-700 text-white text-[10px] uppercase tracking-wider font-bold transition-colors border border-red-800"
                    title="Clear current log view"
                  >
                    <Trash2 size={12} /> Clear Logs
                  </button>
                </div>
              </div>
              
              <div className="p-6 overflow-x-auto bg-white">
                {logs.length === 0 ? (
                  <div className="text-center text-gray-500 py-12 font-mono text-sm">
                    No logs found.
                  </div>
                ) : (
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-[#141414] bg-gray-50 text-[10px] uppercase font-mono tracking-wider font-bold">
                        <th className="p-3">Log ID</th>
                        <th className="p-3">Request ID</th>
                        <th className="p-3">Customer</th>
                        <th className="p-3">Reason</th>
                        <th className="p-3">Verdict</th>
                        <th className="p-3">Amount</th>
                        <th className="p-3">Resolved Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {logs.map((log) => (
                        <tr 
                          key={log.id} 
                          className="hover:bg-gray-100 transition-colors cursor-pointer"
                          onClick={() => setSelectedLog(log)}
                        >
                          <td className="p-3 font-mono font-bold text-[#141414]">#{log.id}</td>
                          <td className="p-3 font-mono">REQ-{log.refund_request_id}</td>
                          <td className="p-3 font-bold">{log.customer_name} (ID: {log.customer_id})</td>
                          <td className="p-3 max-w-xs truncate" title={log.reason}>"{log.reason}"</td>
                          <td className="p-3">
                            <span className={`text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 border ${
                              log.decision === 'approved'
                                ? 'bg-green-100 text-green-800 border-green-800'
                                : log.decision === 'rejected' 
                                ? 'bg-red-100 text-red-800 border-red-800'
                                : 'bg-yellow-100 text-yellow-800 border-yellow-800'
                            }`}>
                              {log.decision}
                            </span>
                          </td>
                          <td className="p-3 font-mono font-bold text-gray-800">₹{log.refunded_amount.toFixed(2)}</td>
                          <td className="p-3 text-gray-500 font-mono">
                            {log.decided_at ? new Date(log.decided_at + 'Z').toLocaleString() : new Date(log.created_at + 'Z').toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          )}

        </main>
      </div>

      {/* Modal Popup for Selected Log */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-[#fdfdfc] border border-[#141414] shadow-[4px_4px_0px_#141414] w-full max-w-2xl max-h-[90vh] flex flex-col font-sans relative">
            <div className="bg-[#141414] text-white p-3 flex justify-between items-center">
              <h2 className="text-xs uppercase font-bold tracking-widest flex items-center gap-2">
                <Brain size={14} /> AI Decision Audit Log #{selectedLog.id}
              </h2>
              <button 
                onClick={() => setSelectedLog(null)}
                className="text-white hover:text-red-400 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto space-y-6">
              {/* Header Info */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 border-b border-gray-200 pb-4">
                <div>
                  <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Request ID</div>
                  <div className="font-mono font-bold text-sm text-[#141414]">REQ-{selectedLog.refund_request_id}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Customer</div>
                  <div className="font-bold text-sm text-[#141414]">{selectedLog.customer_name}</div>
                  <div className="text-[10px] font-mono text-gray-500">ID: {selectedLog.customer_id}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Amount</div>
                  <div className="font-mono font-bold text-sm text-[#141414]">₹{selectedLog.refunded_amount.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase font-bold text-gray-500 mb-1">Verdict</div>
                  <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 border ${
                    selectedLog.decision === 'approved'
                      ? 'bg-green-100 text-green-800 border-green-800'
                      : selectedLog.decision === 'rejected'
                      ? 'bg-red-100 text-red-800 border-red-800'
                      : 'bg-yellow-100 text-yellow-800 border-yellow-800'
                  }`}>
                    {selectedLog.decision}
                  </span>
                </div>
              </div>

              {/* Customer Reason */}
              <div>
                <div className="text-[10px] uppercase font-bold text-gray-500 mb-2 border-b border-[#141414] inline-block">Customer Statement</div>
                <div className="bg-gray-50 p-3 text-sm italic border-l-2 border-gray-300">
                  "{selectedLog.reason}"
                </div>
              </div>

              {/* AI Audit Review / Reasoning */}
              <div>
                <div className="text-[10px] uppercase font-bold text-purple-700 mb-2 border-b border-purple-700 inline-block flex items-center gap-1">
                  Step-by-Step AI Reasoning
                </div>
                <div className="bg-purple-50/30 p-4 border border-purple-200 text-xs font-mono whitespace-pre-wrap leading-relaxed text-gray-800">
                  {selectedLog.review || "No detailed audit reasoning available for this log."}
                </div>
              </div>

              {/* Metadata */}
              <div className="flex justify-between items-center text-[10px] font-mono text-gray-400 pt-4 border-t border-gray-100">
                <span>Created: {new Date(selectedLog.created_at + 'Z').toLocaleString()}</span>
                {selectedLog.decided_at && (
                  <span>Decided: {new Date(selectedLog.decided_at + 'Z').toLocaleString()}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
