'use client';

import { useState } from 'react';
import Link from 'next/link';
import { authAPI } from '@/lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    setError('');
    try {
      await authAPI.forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setError(err.message || 'Có lỗi xảy ra');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <span className="logo-icon-lg">🔑</span>
          <h1>Quên Mật Khẩu</h1>
          <p>Nhập email để nhận link đặt lại mật khẩu</p>
        </div>

        {sent ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>📧</div>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>
              Nếu email <strong style={{ color: 'var(--text-primary)' }}>{email}</strong> tồn tại trong hệ thống,
              bạn sẽ nhận được link đặt lại mật khẩu trong vài phút.
            </p>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>Link có hiệu lực trong 1 giờ. Kiểm tra cả hòm thư Spam.</p>
            <Link href="/login" className="btn btn-primary w-full btn-lg" style={{ display: 'block', marginTop: '24px', textAlign: 'center' }}>
              ← Quay lại đăng nhập
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="login-form">
            {error && <div className="login-error">⚠️ {error}</div>}
            <div className="form-group">
              <label className="form-label">Email đã đăng ký</label>
              <input
                type="email"
                className="form-input"
                placeholder="your@gmail.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                autoFocus
                autoComplete="email"
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary w-full btn-lg"
              disabled={loading || !email.trim()}
            >
              {loading ? '⏳ Đang gửi...' : '📧 Gửi Link Đặt Lại'}
            </button>
            <p className="login-hint">
              <Link href="/login" style={{ color: 'var(--accent-primary)' }}>← Quay lại đăng nhập</Link>
            </p>
          </form>
        )}
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
        .login-hint { text-align: center; color: var(--text-muted); font-size: 0.8rem; margin: 4px 0 0; }
      `}</style>
    </div>
  );
}
