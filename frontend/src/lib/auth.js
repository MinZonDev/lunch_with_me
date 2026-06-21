const TOKEN_KEY = 'lwm_token';
const USER_KEY = 'lwm_user';

export function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getUser() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function isLoggedIn() {
  const token = getToken();
  if (!token) return false;

  try {
    const [, payload] = token.split('.');
    const decoded = JSON.parse(atob(payload));
    return decoded.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export function isAdmin() {
  const user = getUser();
  return user?.role === 'admin';
}
