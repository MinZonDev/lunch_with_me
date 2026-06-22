'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';
import { setAuth, isLoggedIn } from '@/lib/auth';

const RESEND_COOLDOWN = 60; // seconds

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState(1); // 1 = form, 2 = otp
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    email: '',
  });
  const [otpCode, setOtpCode] = useState('');
  const [countdown, setCountdown] = useState(0);
  const timerRef = useRef(null);
  const otpInputRef = useRef(null);

  useEffect(() => {
    if (isLoggedIn()) router.replace('/');
  }, [router]);

  useEffect(() => {
    return () => clearInterval(timerRef.current);
  }, []);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const startCountdown = () => {
    setCountdown(RESEND_COOLDOWN);
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { clearInterval(timerRef.current); return 0; }
        return c - 1;
      });
    }, 1000);
  };

  const handleSendOtp = async (e) => {
    e?.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authAPI.sendOtp(form.email.trim());
      setStep(2);
      startCountdown();
      setTimeout(() => otpInputRef.current?.focus(), 100);
    } catch (err) {
      setError(err.message || 'Không gửi được OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (countdown > 0) return;
    setError('');
    setLoading(true);
    try {
      await authAPI.sendOtp(form.email.trim());
      setOtpCode('');
      startCountdown();
      otpInputRef.current?.focus();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    if (otpCode.length !== 6) { setError('Nhập đủ 6 chữ số OTP'); return; }
    setLoading(true);
    try {
      await authAPI.register({
        username: form.username.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        otp_code: otpCode,
      });
      setStep(3); // pending approval screen
    } catch (err) {
      setError(err.message || 'Đăng ký thất bại');
    } finally {
      setLoading(false);
    }
  };

  const isFormValid =
    form.username.trim().length >= 3 &&
    form.password.length >= 6 &&
    form.confirmPassword === form.password &&
    form.full_name.trim() &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim());

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <span className="logo-icon-lg">🍱</span>
          <h1>Tạo Tài Khoản</h1>
          <p>Lunch With Me — Đăng ký để bắt đầu</p>
        </div>

        {/* Step indicator — hidden on success screen */}
        {step < 3 && (
          <>
            <div className="step-indicator">
              <div className={`step-dot ${step >= 1 ? 'active' : ''}`}>1</div>
              <div className="step-line" />
              <div className={`step-dot ${step >= 2 ? 'active' : ''}`}>2</div>
              <div className="step-line" />
              <div className={`step-dot ${step >= 3 ? 'active' : ''}`}>3</div>
            </div>
            <div className="step-labels">
              <span className={step === 1 ? 'active-label' : ''}>Thông tin</span>
              <span className={step === 2 ? 'active-label' : ''}>Xác thực OTP</span>
              <span>Chờ duyệt</span>
            </div>
          </>
        )}

        {error && <div className="login-error">⚠️ {error}</div>}

        {/* ── Step 1: Form ── */}
        {step === 1 && (
          <form onSubmit={handleSendOtp} className="login-form">
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
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Mã OTP sẽ được gửi tới email này
              </span>
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
              disabled={loading || !isFormValid}
            >
              {loading ? '⏳ Đang gửi OTP...' : '📧 Gửi Mã OTP'}
            </button>
          </form>
        )}

        {/* ── Step 2: OTP ── */}
        {step === 2 && (
          <form onSubmit={handleRegister} className="login-form">
            <div className="otp-info">
              <div>📧 Mã OTP đã gửi tới</div>
              <strong>{form.email}</strong>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ marginTop: '6px', fontSize: '0.78rem' }}
                onClick={() => { setStep(1); setOtpCode(''); setError(''); clearInterval(timerRef.current); }}
              >
                ← Sửa email
              </button>
            </div>

            <div className="form-group">
              <label className="form-label">Mã OTP (6 chữ số) *</label>
              <input
                ref={otpInputRef}
                className="form-input otp-input"
                placeholder="_ _ _ _ _ _"
                value={otpCode}
                onChange={e => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Hiệu lực trong 10 phút
                </span>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.78rem', padding: '4px 10px', opacity: countdown > 0 ? 0.5 : 1 }}
                  onClick={handleResend}
                  disabled={countdown > 0 || loading}
                >
                  {countdown > 0 ? `Gửi lại (${countdown}s)` : '🔄 Gửi lại'}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary w-full btn-lg"
              disabled={loading || otpCode.length !== 6}
            >
              {loading ? '⏳ Đang xác thực...' : '✅ Đăng Ký'}
            </button>
          </form>
        )}

        {/* ── Step 3: Pending approval ── */}
        {step === 3 && (
          <div className="pending-screen">
            <div className="pending-icon">⏳</div>
            <h2>Đăng ký thành công!</h2>
            <p>
              Tài khoản <strong>@{form.username}</strong> đã được tạo và đang chờ admin duyệt.
            </p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Bạn sẽ nhận email thông báo tại <strong>{form.email}</strong> khi tài khoản được kích hoạt.
            </p>
            <Link href="/login" className="btn btn-primary" style={{ marginTop: '20px', display: 'inline-block' }}>
              Về trang đăng nhập
            </Link>
          </div>
        )}

        {step < 3 && (
          <p className="login-hint">
            Đã có tài khoản?{' '}
            <Link href="/login" style={{ color: 'var(--accent-primary)' }}>Đăng nhập</Link>
          </p>
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
          max-width: 440px;
          background: var(--bg-card);
          border: 1px solid var(--border-medium);
          border-radius: var(--radius-xl);
          padding: 40px 32px;
          box-shadow: var(--shadow-lg), 0 0 60px rgba(255, 140, 66, 0.06);
        }
        .login-logo {
          text-align: center;
          margin-bottom: 20px;
        }
        .logo-icon-lg { font-size: 2.5rem; display: block; margin-bottom: 10px; }
        .login-logo h1 { font-size: 1.4rem; font-weight: 700; color: var(--text-primary); margin: 0 0 4px; }
        .login-logo p { color: var(--text-muted); font-size: 0.875rem; margin: 0; }

        /* Step indicator */
        .step-indicator {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0;
          margin-bottom: 4px;
        }
        .step-dot {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.75rem;
          font-weight: 700;
          border: 2px solid var(--border-medium);
          color: var(--text-muted);
          background: var(--bg-input);
          transition: all 0.2s;
        }
        .step-dot.active {
          border-color: var(--accent-primary);
          color: var(--accent-primary);
          background: rgba(255,140,66,0.1);
        }
        .step-line {
          width: 60px;
          height: 2px;
          background: var(--border-subtle);
        }
        .step-labels {
          display: flex;
          justify-content: space-between;
          padding: 0 4px;
          margin-bottom: 20px;
          font-size: 0.72rem;
          color: var(--text-muted);
        }
        .step-labels .active-label {
          color: var(--accent-primary);
          font-weight: 600;
        }

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
          margin-bottom: 4px;
        }
        .input-error { border-color: #ff6b6b !important; }

        .otp-info {
          background: rgba(78,205,196,0.07);
          border: 1px solid rgba(78,205,196,0.2);
          border-radius: var(--radius-md);
          padding: 12px 16px;
          font-size: 0.85rem;
          color: var(--text-secondary);
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 2px;
        }
        .otp-info strong {
          color: var(--text-primary);
          font-size: 0.9rem;
        }
        .otp-input {
          font-size: 1.6rem;
          font-weight: 700;
          letter-spacing: 12px;
          text-align: center;
          font-family: monospace;
        }
        .login-hint {
          text-align: center;
          color: var(--text-muted);
          font-size: 0.8rem;
          margin-top: 18px;
          margin-bottom: 0;
        }
        .pending-screen {
          text-align: center;
          padding: 8px 0;
        }
        .pending-icon {
          font-size: 3rem;
          margin-bottom: 12px;
          animation: pulse 2s infinite;
        }
        .pending-screen h2 {
          font-size: 1.2rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 10px;
        }
        .pending-screen p {
          color: var(--text-secondary);
          font-size: 0.9rem;
          margin: 0;
          line-height: 1.6;
        }
        @keyframes pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.1); }
        }
      `}</style>
    </div>
  );
}
