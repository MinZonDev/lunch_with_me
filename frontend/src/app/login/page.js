'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';
import { setAuth, isLoggedIn } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isLoggedIn()) router.replace('/');
  }, [router]);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) return;

    setLoading(true);
    setError('');
    try {
      const res = await authAPI.login({ username: username.trim(), password });
      setAuth(res.access_token, res.user);
      router.replace('/');
    } catch (err) {
      setError(err.message || 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <span className="logo-icon-lg">🍱</span>
          <h1>Lunch With Me</h1>
          <p>Hệ thống đặt cơm nhóm</p>
        </div>

        <form onSubmit={handleLogin} className="login-form">
          {error && (
            <div className="login-error">
              ⚠️ {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              type="text"
              className="form-input"
              placeholder="Nhập username..."
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Mật khẩu</label>
            <input
              type="password"
              className="form-input"
              placeholder="Nhập mật khẩu..."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary w-full btn-lg"
            disabled={loading || !username.trim() || !password}
          >
            {loading ? '⏳ Đang đăng nhập...' : '🚪 Đăng Nhập'}
          </button>
        </form>

        <p className="login-hint" style={{ marginBottom: '6px' }}>
          <Link href="/forgot-password" style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Quên mật khẩu?</Link>
        </p>
        <p className="login-hint">
          Chưa có tài khoản?{' '}
          <Link href="/register" style={{ color: 'var(--accent-primary)' }}>Đăng ký ngay</Link>
        </p>
      </div>

      <style jsx>{`
        .login-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--bg-primary);
          padding: 24px;
        }

        .login-card {
          width: 100%;
          max-width: 400px;
          background: var(--bg-card);
          border: 1px solid var(--border-medium);
          border-radius: var(--radius-xl);
          padding: 40px 32px;
          box-shadow: var(--shadow-lg), 0 0 60px rgba(255, 140, 66, 0.06);
        }

        .login-logo {
          text-align: center;
          margin-bottom: 32px;
        }

        .logo-icon-lg {
          font-size: 3rem;
          display: block;
          margin-bottom: 12px;
        }

        .login-logo h1 {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 4px;
        }

        .login-logo p {
          color: var(--text-muted);
          font-size: 0.875rem;
          margin: 0;
        }

        .login-form {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .login-error {
          background: rgba(255, 107, 107, 0.1);
          border: 1px solid rgba(255, 107, 107, 0.3);
          border-radius: var(--radius-md);
          padding: 12px 16px;
          color: #ff6b6b;
          font-size: 0.875rem;
        }

        .login-hint {
          text-align: center;
          color: var(--text-muted);
          font-size: 0.8rem;
          margin-top: 20px;
          margin-bottom: 0;
        }
      `}</style>
    </div>
  );
}
