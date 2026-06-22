import { getToken, clearAuth } from './auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const token = getToken();
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    if (response.status === 401) {
      clearAuth();
      if (typeof window !== 'undefined') window.location.href = '/login';
    }
    const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

// ============== Auth ==============
export const authAPI = {
  sendOtp: (email) => fetchAPI('/api/auth/send-otp', { method: 'POST', body: JSON.stringify({ email }) }),
  register: (data) => fetchAPI('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => fetchAPI('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => fetchAPI('/api/auth/me'),
  updateMe: (data) => fetchAPI('/api/auth/me', { method: 'PUT', body: JSON.stringify(data) }),
  changePassword: (data) => fetchAPI('/api/auth/change-password', { method: 'POST', body: JSON.stringify(data) }),
  forgotPassword: (email) => fetchAPI('/api/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),
  resetPassword: (token, new_password) => fetchAPI('/api/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, new_password }) }),
  listUsers: () => fetchAPI('/api/auth/users'),
  listPendingUsers: () => fetchAPI('/api/auth/users/pending'),
  createUser: (data) => fetchAPI('/api/auth/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id, data) => fetchAPI(`/api/auth/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateUserRole: (id, role) => fetchAPI(`/api/auth/users/${id}`, { method: 'PUT', body: JSON.stringify({ role }) }),
  approveUser: (id) => fetchAPI(`/api/auth/users/${id}/approve`, { method: 'POST' }),
  rejectUser: (id) => fetchAPI(`/api/auth/users/${id}/reject`, { method: 'POST' }),
  reactivateUser: (id) => fetchAPI(`/api/auth/users/${id}/reactivate`, { method: 'POST' }),
  deleteUser: (id) => fetchAPI(`/api/auth/users/${id}`, { method: 'DELETE' }),
};

// ============== Members ==============
export const membersAPI = {
  listPublic: () => fetchAPI('/api/members/public'),
  list: (activeOnly = true) => fetchAPI(`/api/members?active_only=${activeOnly}`),
  get: (id) => fetchAPI(`/api/members/${id}`),
  create: (data) => fetchAPI('/api/members', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => fetchAPI(`/api/members/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => fetchAPI(`/api/members/${id}`, { method: 'DELETE' }),
};

// ============== Orders ==============
export const ordersAPI = {
  list: (params = {}) => {
    const searchParams = new URLSearchParams();
    if (params.start_date) searchParams.set('start_date', params.start_date);
    if (params.end_date) searchParams.set('end_date', params.end_date);
    if (params.limit) searchParams.set('limit', params.limit);
    const qs = searchParams.toString();
    return fetchAPI(`/api/orders${qs ? '?' + qs : ''}`);
  },
  getToday: () => fetchAPI('/api/orders/today'),
  get: (id) => fetchAPI(`/api/orders/${id}`),
  create: (data) => fetchAPI('/api/orders', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => fetchAPI(`/api/orders/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  lock: (id) => fetchAPI(`/api/orders/${id}/lock`, { method: 'POST' }),
  reopen: (id) => fetchAPI(`/api/orders/${id}/reopen`, { method: 'POST' }),
  finalize: (id, data) => fetchAPI(`/api/orders/${id}/finalize`, { method: 'POST', body: JSON.stringify(data) }),
  updateLinks: (id, links) => fetchAPI(`/api/orders/${id}/links`, { method: 'PUT', body: JSON.stringify({ links }) }),
};

// ============== Order Items ==============
export const orderItemsAPI = {
  list: (orderId) => fetchAPI(`/api/orders/${orderId}/items`),
  create: (orderId, data) => fetchAPI(`/api/orders/${orderId}/items`, { method: 'POST', body: JSON.stringify(data) }),
  update: (orderId, itemId, data) => fetchAPI(`/api/orders/${orderId}/items/${itemId}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateExtra: (orderId, itemId, data) => fetchAPI(`/api/orders/${orderId}/items/${itemId}/extra`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (orderId, itemId) => fetchAPI(`/api/orders/${orderId}/items/${itemId}`, { method: 'DELETE' }),
};

// ============== Deposits ==============
export const depositsAPI = {
  summary: () => fetchAPI('/api/deposits/summary'),
  list: () => fetchAPI('/api/deposits'),
  spending: () => fetchAPI('/api/deposits/spending'),
  create: (data) => fetchAPI('/api/deposits', { method: 'POST', body: JSON.stringify(data) }),
  approve: (id) => fetchAPI(`/api/deposits/${id}/approve`, { method: 'POST' }),
  charge: (data) => fetchAPI('/api/deposits/charge', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id) => fetchAPI(`/api/deposits/${id}`, { method: 'DELETE' }),
};

// ============== Restaurants ==============
export const restaurantsAPI = {
  list: () => fetchAPI('/api/restaurants'),
  lastUsed: () => fetchAPI('/api/restaurants/last-used'),
  create: (data) => fetchAPI('/api/restaurants', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => fetchAPI(`/api/restaurants/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => fetchAPI(`/api/restaurants/${id}`, { method: 'DELETE' }),
};

// ============== Reminders ==============
export const remindersAPI = {
  debtors: () => fetchAPI('/api/reminders/debtors'),
  send: (member_id = null) => fetchAPI('/api/reminders/send', { method: 'POST', body: JSON.stringify({ member_id }) }),
  sendOrderReminder: () => fetchAPI('/api/reminders/send-order-reminder', { method: 'POST' }),
  getSettings: () => fetchAPI('/api/reminders/settings'),
  saveSettings: (data) => fetchAPI('/api/reminders/settings', { method: 'PUT', body: JSON.stringify(data) }),
};

// ============== Delegations ==============
export const delegationsAPI = {
  list: () => fetchAPI('/api/delegations'),
  grant: (delegate_member_id) => fetchAPI('/api/delegations', { method: 'POST', body: JSON.stringify({ delegate_member_id }) }),
  revoke: (id) => fetchAPI(`/api/delegations/${id}`, { method: 'DELETE' }),
};

// ============== Reviews ==============
export const reviewsAPI = {
  list: () => fetchAPI('/api/reviews'),
  create: (data) => fetchAPI('/api/reviews', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id) => fetchAPI(`/api/reviews/${id}`, { method: 'DELETE' }),
};

// ============== Helpers ==============
export function formatMoney(amount) {
  if (amount === null || amount === undefined) return '0';
  return (Number(amount) * 1000).toLocaleString('vi-VN');
}

export function formatDate(dateStr) {
  const date = new Date(dateStr);
  return date.toLocaleDateString('vi-VN', {
    weekday: 'long',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

export function formatDateShort(dateStr) {
  const date = new Date(dateStr);
  return date.toLocaleDateString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
  });
}

export function getInitials(name) {
  if (!name) return '?';
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function getStatusLabel(status) {
  const labels = {
    open: '🟢 Đang mở',
    locked: '🟡 Đã khóa',
    finalized: '🔴 Đã chốt',
  };
  return labels[status] || status;
}

export function getTodayString() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}
