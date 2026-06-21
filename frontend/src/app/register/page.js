'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';
import { setAuth, isLoggedIn } from '@/lib/auth';

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    email: '',
  });

  useEffect(() => {
    if (isLoggedIn()) router.replace('/');
  }, [router]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirmPassword) {
      setError('Mật khẩu xác nhận không khớp');
      return;
    }
    setLoading(true);
    try {
      const res = await authAPI.register({
        username: form.username.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
        email: form.email.trim(),
      });
      setAuth(res.access_token, res.user);
      router.replace('/');
    } catch (err) {
      setError(err.message || 'Đăng ký thất bại');
    } finally {
      setLoading(false);
    }
  };

  const isValid =
    form.username.trim().length >= 3 &&
    form.password.length >= 6 &&
    form.confirmPassword === form.password &&
    form.full_name.trim() &&
    form.email.trim();

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <span className="logo-icon-lg">🍱</span>
          <h1>Tạo Tài Khoản</h1>
          <p>Lunch With Me — Đăng ký để bắt đầu</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="login-error">⚠️ {error}</div>}

          <div className="form-group">
            <label className="form-label">Họ tên *</label>
            <input
              className="form-input"
              placeholder="Nguyễn Văn A"
              value={form.full_name}
              onChange={set('full_name')}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label">Username *</label>
            <input
              className="form-input"
              placeholder="Tối thiểu 3 ký tự, không dấu"
              value={form.username}
              onChange={set('username')}
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Email *</label>
            <input
              type="email"
              className="form-input"
              placeholder="your@gmail.com"
              value={form.email}
              onChange={set('email')}
              autoComplete="email"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Mật khẩu *</label>
              <input
                type="password"
                className="form-input"
                placeholder="Tối thiểu 6 ký tự"
                value={form.password}
                onChange={set('password')}
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Xác nhận mật khẩu *</label>
              <input
                type="password"
                className={`form-input ${form.confirmPassword && form.confirmPassword !== form.password ? 'input-error' : ''}`}
                placeholder="••••••"
                value={form.confirmPassword}
                onChange={set('confirmPassword')}
                autoComplete="new-password"
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary w-full btn-lg"
            disabled={loading || !isValid}
          >
            {loading ? '⏳ Đang tạo tài khoản...' : '✅ Đăng Ký'}
          </button>
        </form>

        <p className="login-hint">
          Đã có tài khoản?{' '}
          <Link href="/login" style={{ color: 'var(--accent-primary)' }}>Đăng nhập</Link>
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
          max-width: 420px;
          background: var(--bg-card);
          border: 1px solid var(--border-medium);
          border-radius: var(--radius-xl);
          padding: 40px 32px;
          box-shadow: var(--shadow-lg), 0 0 60px rgba(255, 140, 66, 0.06);
        }
        .login-logo {
          text-align: center;
          margin-bottom: 28px;
        }
        .logo-icon-lg { font-size: 2.5rem; display: block; margin-bottom: 10px; }
        .login-logo h1 { font-size: 1.4rem; font-weight: 700; color: var(--text-primary); margin: 0 0 4px; }
        .login-logo p { color: var(--text-muted); font-size: 0.875rem; margin: 0; }
        .login-form { display: flex; flex-direction: column; gap: 14px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        @media (max-width: 480px) { .form-row { grid-template-columns: 1fr; } }
        .login-error {
          background: rgba(255,107,107,0.1);
          border: 1px solid rgba(255,107,107,0.3);
          border-radius: var(--radius-md);
          padding: 10px 14px;
          color: #ff6b6b;
          font-size: 0.875rem;
        }
        .input-error { border-color: #ff6b6b !important; }
        .login-hint {
          text-align: center;
          color: var(--text-muted);
          font-size: 0.8rem;
          margin-top: 18px;
          margin-bottom: 0;
        }
      `}</style>
    </div>
  );
}
