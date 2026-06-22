import { getToken } from './auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const isDev = process.env.NODE_ENV === 'development';

function log(level, message, context = {}) {
  const consoleFn = level === 'error' ? console.error : level === 'warn' ? console.warn : console.log;
  consoleFn(`[${level.toUpperCase()}] ${message}`, Object.keys(context).length ? context : '');

  if (level === 'error' && typeof window !== 'undefined') {
    const entry = {
      level,
      message,
      context,
      timestamp: new Date().toISOString(),
      url: window.location.pathname,
    };
    const token = getToken();
    fetch(`${API_BASE}/api/logs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(entry),
      keepalive: true,
    }).catch(() => {});
  }
}

const logger = {
  info: (message, context = {}) => log('info', message, context),
  warn: (message, context = {}) => log('warn', message, context),
  error: (message, context = {}) => log('error', message, context),
};

export default logger;
