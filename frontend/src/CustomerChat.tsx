import React, { useState, useEffect, useRef } from 'react';
import { api, Order, OrderItem, RefundResponse, UserProfile } from './api';
import { Bell, Bot, CheckCircle2, XCircle, AlertCircle, Filter, Send, LogOut, ArrowRight, User } from 'lucide-react';

export default function CustomerChat({ onLogout }: { onLogout: () => void }) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string>('');
  const [reason, setReason] = useState<string>('');
  const [loadingOrders, setLoadingOrders] = useState(true);
  
  // Chat state
  const [messages, setMessages] = useState<Array<{
    id: string;
    sender: 'ai' | 'user';
    text: string;
    timestamp: string;
    decisionCard?: {
      decision: string;
      amount: number;
      request_id: number;
      review_id?: number | null;
    }
  }>>([]);
  const [chatHistories, setChatHistories] = useState<Record<number, Array<{
    id: string;
    sender: 'ai' | 'user';
    text: string;
    timestamp: string;
    decisionCard?: {
      decision: string;
      amount: number;
      request_id: number;
      review_id?: number | null;
    }
  }>>>({});
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch initial profile and orders
  useEffect(() => {
    async function loadData() {
      try {
        const userProfile = await api.getCustomerProfile();
        setProfile(userProfile);

        const customerOrders = await api.getCustomerOrders();
        setOrders(customerOrders);
        
        // Welcome message
        setMessages([
          {
            id: 'welcome',
            sender: 'ai',
            text: `Welcome back, ${userProfile.full_name || 'Customer'}! I am your RefundAI assistant. Select an eligible order from your history on the left to initiate a refund request.`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      } catch (err) {
        console.error('Failed to load profile/orders', err);
      } finally {
        setLoadingOrders(false);
      }
    }
    loadData();
  }, []);

  // Scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatLoading]);

  // Handle selecting an order
  const handleSelectOrder = async (orderId: number) => {
    if (selectedOrder?.order_id === orderId) {
      return;
    }
    try {
      setChatLoading(true);
      const detail = await api.getOrderDetail(String(orderId));
      setSelectedOrder(detail);
      setSelectedItemId(detail.items && detail.items.length > 0 ? String(detail.items[0].order_item_id) : '');
      
      if (chatHistories[orderId]) {
        setMessages(chatHistories[orderId]);
      } else {
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const welcomeText = profile
          ? `Welcome back, ${profile.full_name || 'Customer'}! I am your RefundAI assistant. Select an eligible order from your history on the left to initiate a refund request.`
          : 'Welcome back! I am your RefundAI assistant. Select an eligible order from your history on the left to initiate a refund request.';
        
        const newHistory = [
          {
            id: 'welcome',
            sender: 'ai' as const,
            text: welcomeText,
            timestamp: timeStr
          },
          {
            id: `select-${orderId}`,
            sender: 'ai' as const,
            text: `You have selected Order #${orderId} (${detail.items ? detail.items.map(i => i.product_name).join(', ') : 'no items'}). Please select the item you wish to refund, explain your reason below, and click submit.`,
            timestamp: timeStr
          }
        ];
        
        setChatHistories(prev => ({
          ...prev,
          [orderId]: newHistory
        }));
        setMessages(newHistory);
      }
    } catch (err: any) {
      console.error(err);
      alert('Failed to fetch order details');
    } finally {
      setChatLoading(false);
    }
  };

  // Submit refund request
  const handleSubmitRefund = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrder || !selectedItemId || !reason.trim()) {
      return;
    }

    const itemToRefund = selectedOrder.items?.find(i => String(i.order_item_id) === selectedItemId);
    const itemName = itemToRefund ? itemToRefund.product_name : 'Item';

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    // 1. Add user message
    const userMsg = {
      id: `user-msg-${Date.now()}`,
      sender: 'user' as const,
      text: `Requesting refund for "${itemName}" from Order #${selectedOrder.order_id}. Reason: ${reason}`,
      timestamp
    };

    setMessages(prev => {
      const next = [...prev, userMsg];
      setChatHistories(hist => ({
        ...hist,
        [selectedOrder.order_id]: next
      }));
      return next;
    });
    setChatLoading(true);

    const payload = {
      order_id: String(selectedOrder.order_id),
      order_item_id: selectedItemId,
      reason: reason.trim(),
      evidence_urls: []
    };

    // Reset input fields
    setReason('');

    try {
      const result = await api.submitRefund(payload);
      
      // 2. Add AI response message
      const aiMsg = {
        id: `ai-res-${Date.now()}`,
        sender: 'ai' as const,
        text: result.message,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        decisionCard: {
          decision: result.decision,
          amount: result.refund_amount,
          request_id: result.refund_request_id,
          review_id: result.review_id
        }
      };

      setMessages(prev => {
        const next = [...prev, aiMsg];
        setChatHistories(hist => ({
          ...hist,
          [selectedOrder.order_id]: next
        }));
        return next;
      });

      // Refresh orders list to update statuses
      const updatedOrders = await api.getCustomerOrders();
      setOrders(updatedOrders);

    } catch (err: any) {
      const errMsg = {
        id: `ai-err-${Date.now()}`,
        sender: 'ai' as const,
        text: `Error processing request: ${err.message || 'Server timeout. Please try again.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => {
        const next = [...prev, errMsg];
        setChatHistories(hist => ({
          ...hist,
          [selectedOrder.order_id]: next
        }));
        return next;
      });
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="bg-[#fdfdfc] text-[#141414] h-screen flex flex-col font-sans xl:items-center">
      <div className="w-full xl:max-w-screen-2xl flex flex-col h-full overflow-hidden border-x-0 xl:border-x-8 xl:border-b-8 border-gray-100">
        
        {/* TopNavBar */}
        <header className="bg-[#fdfdfc] relative z-50 flex justify-between items-center h-14 w-full px-4 sm:px-6 border-b border-[#141414] shrink-0">
          <div className="flex items-center gap-2 sm:gap-6">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 sm:w-6 sm:h-6 bg-[#141414] rounded-sm flex items-center justify-center">
                <div className="w-2.5 h-0.5 sm:w-3 sm:h-1 bg-[#fdfdfc] rotate-45"></div>
              </div>
              <span className="font-bold text-base sm:text-lg tracking-tight uppercase">Refund<span className="italic font-serif">AI</span></span>
            </div>
            <nav className="hidden md:flex gap-4 lg:gap-6 items-center md:ml-4 lg:ml-8">
              <a href="#" className="text-[10px] sm:text-xs font-bold uppercase tracking-widest border-b-2 border-[#141414] py-1 text-[#141414]">
                Customer View
              </a>
            </nav>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <div className="hidden sm:flex items-center gap-1.5 text-[10px] font-mono mr-2">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              PORTAL ACTIVE
            </div>
            
            {profile && (
              <span className="text-xs font-bold uppercase tracking-wider hidden sm:inline-block">
                {profile.full_name}
              </span>
            )}

            <button 
              onClick={onLogout} 
              className="p-1.5 hover:bg-gray-100 border border-transparent hover:border-[#141414] transition-all flex items-center gap-1 text-xs font-bold uppercase tracking-widest"
              title="Logout"
            >
              <LogOut size={14} /> <span className="hidden md:inline">Sign Out</span>
            </button>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 flex flex-col lg:grid lg:grid-cols-12 overflow-hidden min-h-0">
          
          {/* Left Panel: Order History */}
          <aside className="hidden lg:flex flex-col lg:col-span-4 bg-[#fdfdfc] border-r border-[#141414] h-full overflow-y-auto shrink-0">
            <div className="p-4 border-b border-[#141414] bg-[#E4E3E0] flex items-center justify-between">
              <h2 className="font-serif italic text-sm font-semibold">Your Orders</h2>
              <Filter size={16} className="text-[#141414] opacity-60" />
            </div>

            <div className="flex flex-col gap-4 p-4">
              {loadingOrders ? (
                // Skeletons
                [1, 2, 3].map(i => (
                  <div key={i} className="p-3 border border-[#141414] bg-[#fdfdfc] flex flex-col gap-2 animate-pulse">
                    <div className="h-3 bg-gray-200 w-1/2"></div>
                    <div className="h-2 bg-gray-200 w-3/4"></div>
                    <div className="h-2 bg-gray-200 w-1/3"></div>
                  </div>
                ))
              ) : orders.length === 0 ? (
                <div className="text-xs font-mono text-gray-500 text-center py-8">
                  No orders found.
                </div>
              ) : (
                orders.map((o) => (
                  <button
                    key={o.order_id}
                    onClick={() => handleSelectOrder(o.order_id)}
                    className={`text-left p-3 border border-[#141414] flex flex-col gap-1 transition-all ${
                      selectedOrder?.order_id === o.order_id
                        ? 'bg-[#E4E3E0] shadow-[2px_2px_0px_#141414] translate-x-[-2px] translate-y-[-2px]'
                        : 'bg-[#fdfdfc] hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex justify-between items-center w-full">
                      <span className="font-mono text-xs font-bold">ORD-{o.order_id}</span>
                      <span className="text-[10px] uppercase font-bold text-gray-500">{o.payment_method}</span>
                    </div>
                    <div className="text-[11px] font-medium text-gray-700 truncate mt-1">
                      {o.item_count} items ordered
                    </div>
                    <div className="flex justify-between items-center mt-2 pt-2 border-t border-dashed border-gray-300 w-full text-[10px]">
                      <span className="font-mono font-bold text-green-700">₹{o.total_amount.toLocaleString('en-IN')}</span>
                      <span className="uppercase font-mono text-[9px] px-1.5 py-0.5 bg-gray-100 border border-gray-300">
                        {o.status}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </aside>

          {/* Right Panel: Chat and Selection Form */}
          <section className="flex-1 lg:col-span-8 flex flex-col bg-[#E4E3E0] relative h-full min-h-0 overflow-hidden min-w-0">
            
            {/* Chat Header */}
            <div className="bg-[#fdfdfc] border-b border-[#141414] p-4 flex justify-between items-center shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 border border-[#141414] flex items-center justify-center text-[#141414] bg-white">
                  <Bot size={16} />
                </div>
                <div>
                  <h2 className="font-serif italic text-sm font-semibold m-0 leading-none">Refund Assistant</h2>
                  <span className="text-[10px] uppercase font-mono tracking-wider opacity-60 mt-1 block">AI AGENT ACTIVE</span>
                </div>
              </div>
            </div>

            {/* Chat Window */}
            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex gap-2 max-w-2xl ${
                    m.sender === 'user' ? 'self-end flex-row-reverse' : 'self-start'
                  }`}
                >
                  <div className={`w-6 h-6 border border-[#141414] flex-shrink-0 flex items-center justify-center text-[#141414] ${
                    m.sender === 'user' ? 'bg-[#E4E3E0]' : 'bg-[#fdfdfc]'
                  }`}>
                    {m.sender === 'user' ? <User size={12} /> : <Bot size={12} />}
                  </div>
                  
                  <div className={`border border-[#141414] p-3 text-sm flex flex-col gap-2 shadow-[2px_2px_0px_#141414] ${
                    m.sender === 'user' ? 'bg-[#E4E3E0]' : 'bg-[#fdfdfc]'
                  }`}>
                    <p className="leading-relaxed m-0 font-medium whitespace-pre-wrap">{m.text}</p>
                    
                    {/* Embedded Refund Decision Card */}
                    {m.decisionCard && (
                      <div className="border border-[#141414] p-3 bg-gray-50 flex flex-col gap-1.5 mt-2">
                        <div className="flex justify-between items-center border-b border-gray-200 pb-1.5">
                          <span className="text-[10px] font-bold text-[#141414] opacity-50 uppercase tracking-widest">
                            Refund Verdict
                          </span>
                          <span className={`text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 border flex items-center gap-1 ${
                            m.decisionCard.decision === 'approve'
                              ? 'bg-green-100 text-green-800 border-green-800'
                              : m.decisionCard.decision === 'human_review'
                              ? 'bg-yellow-100 text-yellow-800 border-yellow-800'
                              : 'bg-red-100 text-red-800 border-red-800'
                          }`}>
                            {m.decisionCard.decision === 'approve' && <CheckCircle2 size={10} />}
                            {m.decisionCard.decision === 'human_review' && <AlertCircle size={10} />}
                            {m.decisionCard.decision === 'reject' && <XCircle size={10} />}
                            {m.decisionCard.decision.replace('_', ' ')}
                          </span>
                        </div>
                        <div className="flex justify-between items-end mt-1">
                          <div>
                            <h3 className="font-serif italic text-sm font-semibold m-0">
                              {m.decisionCard.decision === 'approve' ? 'Refund Approved' : m.decisionCard.decision === 'human_review' ? 'Escalated to Agent' : 'Refund Rejected'}
                            </h3>
                            <span className="text-[9px] font-mono text-gray-500 uppercase">
                              Req ID: #{m.decisionCard.request_id}
                              {m.decisionCard.review_id && ` | Review ID: ${m.decisionCard.review_id}`}
                            </span>
                          </div>
                          <span className="text-lg font-mono font-bold text-gray-800">
                            ₹{m.decisionCard.amount.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    )}

                    <span className="text-[9px] font-mono opacity-50 block text-right mt-1">
                      {m.timestamp}
                    </span>
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {chatLoading && (
                <div className="flex gap-2 max-w-2xl self-start">
                  <div className="w-6 h-6 border border-[#141414] bg-[#fdfdfc] flex-shrink-0 flex items-center justify-center text-[#141414]">
                    <Bot size={12} />
                  </div>
                  <div className="bg-[#fdfdfc] border border-[#141414] p-3 shadow-[2px_2px_0px_#141414] flex items-center gap-1">
                    <div className="w-1.5 h-1.5 bg-[#141414] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-1.5 h-1.5 bg-[#141414] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-1.5 h-1.5 bg-[#141414] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Refund Selection Form / Inputs */}
            <div className="p-4 border-t border-[#141414] bg-[#fdfdfc] shrink-0">
              {selectedOrder ? (
                <form onSubmit={handleSubmitRefund} className="flex flex-col gap-3">
                  <div className="flex flex-col sm:flex-row gap-3">
                    {/* Item selector */}
                    <div className="flex-1 flex flex-col gap-1">
                      <label className="text-[10px] uppercase font-bold tracking-wider opacity-60">Item to Refund</label>
                      <select
                        value={selectedItemId}
                        onChange={(e) => setSelectedItemId(e.target.value)}
                        className="border border-[#141414] p-1.5 text-xs bg-[#E4E3E0] font-mono font-medium focus:outline-none focus:bg-white"
                      >
                        {selectedOrder.items && selectedOrder.items.map((item) => (
                          <option key={item.order_item_id} value={item.order_item_id}>
                            {item.product_name} (₹{item.unit_price * item.quantity})
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Reason input */}
                    <div className="flex-[2] flex flex-col gap-1">
                      <label className="text-[10px] uppercase font-bold tracking-wider opacity-60">Reason for Request</label>
                      <div className="flex gap-2 border border-[#141414] p-1 bg-[#E4E3E0] items-center">
                        <input
                          type="text"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          placeholder="Why are you requesting a refund? (e.g. damaged, wrong size...)"
                          className="flex-1 bg-transparent border-none text-xs py-1 px-2 focus:outline-none text-[#141414] font-medium"
                        />
                        <button
                          type="submit"
                          disabled={chatLoading || !reason.trim()}
                          className="w-6 h-6 bg-[#141414] text-white flex justify-center items-center hover:opacity-90 disabled:opacity-50"
                        >
                          <Send size={12} />
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="text-[10px] font-mono text-gray-500">
                    Selected Order: <span className="font-bold text-[#141414]">ORD-{selectedOrder.order_id}</span>
                  </div>
                </form>
              ) : (
                <div className="flex items-center justify-center p-3 bg-gray-50 border border-gray-300 text-xs text-gray-500 font-mono">
                  Select an order from the list on the left to start the refund process.
                </div>
              )}
            </div>

          </section>
        </main>
      </div>
    </div>
  );
}
