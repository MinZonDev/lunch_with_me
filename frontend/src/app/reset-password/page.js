'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) setError('Link không hợp lệ. Vui lòng yêu cầu lại.');
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirm) { setError('Mật khẩu xác nhận không khớp'); return; }
    setLoading(true);
    setError('');
    try {
      await authAPI.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err.message || 'Token không hợp lệ hoặc đã hết hạn');
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '3rem', marginBottom: '16px' }}>✅</div>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>Đặt lại mật khẩu thành công!</p>
        <Link href="/login" className="btn btn-primary w-full btn-lg" style={{ display: 'block', textAlign: 'center' }}>
          Đăng nhập ngay →
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="login-form">
      {error && <div className="login-error">⚠️ {error}</div>}
      {!token ? null : (
        <>
          <div className="form-group">
            <label className="form-label">Mật khẩu mới *</label>
            <input
              type="password"
              className="form-input"
              placeholder="Tối thiểu 6 ký tự"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoFocus
              autoComplete="new-password"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Xác nhận mật khẩu *</label>
            <input
              type="password"
              className={`form-input ${confirm && confirm !== password ? 'input-error' : ''}`}
              placeholder="••••••"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary w-full btn-lg"
            disabled={loading || password.length < 6 || password !== confirm}
          >
            {loading ? '⏳ Đang đặt lại...' : '🔑 Đặt Lại Mật Khẩu'}
          </button>
        </>
      )}
      <p className="login-hint">
        <Link href="/login" style={{ color: 'var(--accent-primary)' }}>← Quay lại đăng nhập</Link>
      </p>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <span className="logo-icon-lg">🔒</span>
          <h1>Đặt Lại Mật Khẩu</h1>
          <p>Nhập mật khẩu mới cho tài khoản của bạn</p>
        </div>
        <Suspense fallback={<div className="loading-spinner"><div className="spinner" /></div>}>
          <ResetPasswordForm />
        </Suspense>
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
        .login-logo { text-align: center; margin-bottom: 28px; }
        .logo-icon-lg { font-size: 2.5rem; display: block; margin-bottom: 10px; }
        .login-logo h1 { font-size: 1.4rem; font-weight: 700; color: var(--text-primary); margin: 0 0 4px; }
        .login-logo p { color: var(--text-muted); font-size: 0.875rem; margin: 0; }
        .login-form { display: flex; flex-direction: column; gap: 14px; }
        .login-error {
          background: rgba(255,107,107,0.1);
          border: 1px solid rgba(255,107,107,0.3);
          border-radius: var(--radius-md);
          padding: 10px 14px;
          color: #ff6b6b;
          font-size: 0.875rem;
        }
        .input-error { border-color: #ff6b6b !important; }
        .login-hint { text-align: center; color: var(--text-muted); font-size: 0.8rem; margin: 4px 0 0; }
      `}</style>
    </div>
  );
}
