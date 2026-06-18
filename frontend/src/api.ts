// Frontend API Client

const API_BASE_URL = 'http://localhost:8000';

function getHeaders() {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      ...getHeaders(),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorMessage = 'An error occurred';
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      // Ignore
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}

export interface UserProfile {
  id: number;
  full_name: string;
  name?: string; // fallback
  email: string;
  phone_number?: string;
  address?: string;
  created_at?: string;
  role?: string;
}

export interface OrderItem {
  order_item_id: number;
  unit_price: number;
  quantity: number;
  status: string;
  product_name: string;
  product_category: string;
  return_window_days: number;
}

export interface Order {
  order_id: number;
  ordered_at: string;
  status: string;
  total_amount: number;
  payment_method: string;
  delivered_at: string | null;
  item_count: number;
  items?: OrderItem[];
}

export interface RefundHistoryItem {
  id: number;
  order_item_id: number;
  reason: string;
  reason_category: string;
  status: string;
  requested_refund_amount: number;
  created_at: string;
  decision: string | null;
  refunded_amount: number | null;
  review: string | null;
  decided_at: string | null;
  product_name: string;
}

export interface SubmitRefundPayload {
  order_id: string;
  order_item_id: string;
  reason: string;
  evidence_urls: string[];
}

export interface RefundResponse {
  refund_request_id: number;
  decision: string;
  refund_amount: number;
  message: string;
  review_id: number | null;
}

export interface AdminStats {
  total_processed: number;
  approved_count: number;
  rejected_count: number;
  pending_count: number;
  success_rate: number;
  avg_resolution_seconds: number;
}

export interface AdminLog {
  id: number;
  refund_request_id: number;
  decision: string;
  refunded_amount: number;
  review: string | null;
  created_at: string;
  decided_at: string | null;
  customer_id: number;
  order_item_id: number;
  reason: string;
  customer_name: string;
}

export interface QueueItem {
  review_id: number;
  refund_request_id: number;
  review: string;
  review_created_at: string;
  customer_id: number;
  order_item_id: number;
  reason: string;
  reason_category: string;
  requested_refund_amount: number;
  request_created_at: string;
  customer_name: string;
  fraud_score: number;
  signals: string[];
}

export interface CustomerSummary {
  id: number;
  full_name: string;
  email: string;
  created_at: string;
  refund_requests_count: number;
  total_refunded_amount: number | null;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  role: string;
  name: string;
  id: number;
}

export const api = {
  loginCustomer: (email: string, password: string) =>
    request<LoginResult>('/auth/customer/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  loginAdmin: (email: string, password: string) =>
    request<LoginResult>('/auth/admin/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  getMe: () => request<UserProfile>('/auth/me'),

  getCustomerProfile: () => request<UserProfile>('/customer/profile'),

  getCustomerOrders: () => request<Order[]>('/customer/orders'),

  getOrderDetail: (orderId: string) => request<Order>(`/customer/orders/${orderId}`),

  getCustomerRefunds: () => request<RefundHistoryItem[]>('/customer/refunds'),

  submitRefund: (payload: SubmitRefundPayload) =>
    request<RefundResponse>('/refund/submit', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getAdminStats: () => request<AdminStats>('/admin/stats'),

  getAdminLogs: (limit: number = 20, offset: number = 0) =>
    request<AdminLog[]>(`/admin/logs?limit=${limit}&offset=${offset}`),

  getAdminQueue: () => request<QueueItem[]>('/admin/queue'),

  decideQueueItem: (reviewId: number, decision: 'approved' | 'rejected') =>
    request<{ ok: boolean }>(`/admin/queue/${reviewId}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    }),

  getAdminCustomers: () => request<CustomerSummary[]>('/admin/customers'),
};
