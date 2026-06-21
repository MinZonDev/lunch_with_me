'use client';

import { useState, useEffect, useRef } from 'react';
import { authAPI, getInitials } from '@/lib/api';
import { getUser, setAuth, getToken } from '@/lib/auth';
import { useToast } from '@/components/Toast';

export default function ProfilePage() {
  const addToast = useToast();
  const fileInputRef = useRef(null);
  const [user, setUser] = useState(null);
  const [saving, setSaving] = useState(false);
  const [changingPw, setChangingPw] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState(null);

  const [form, setForm] = useState({
    full_name: '',
    nickname: '',
    email: '',
    date_of_birth: '',
    avatar_url: '',
  });

  const [pwForm, setPwForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  useEffect(() => {
    authAPI.me().then(u => {
      setUser(u);
      setForm({
        full_name: u.full_name || '',
        nickname: u.nickname || '',
        email: u.email || '',
        date_of_birth: u.date_of_birth || '',
        avatar_url: u.avatar_url || '',
      });
      if (u.avatar_url) setAvatarPreview(u.avatar_url);
    });
  }, []);

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }));

  const handleAvatarFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 200 * 1024) {
      addToast('Ảnh quá lớn! Tối đa 200KB.', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target.result;
      setAvatarPreview(dataUrl);
      setForm(f => ({ ...f, avatar_url: dataUrl }));
    };
    reader.readAsDataURL(file);
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const updated = await authAPI.updateMe({
        full_name: form.full_name.trim() || undefined,
        nickname: form.nickname.trim() || undefined,
        email: form.email.trim() || undefined,
        date_of_birth: form.date_of_birth || undefined,
        avatar_url: form.avatar_url || undefined,
      });
      // Update local auth storage
      const token = getToken();
      setAuth(token, updated);
      setUser(updated);
      addToast('Đã cập nhật thông tin! ✅');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (pwForm.new_password !== pwForm.confirm_password) {
      addToast('Mật khẩu xác nhận không khớp', 'error');
      return;
    }
    setChangingPw(true);
    try {
      await authAPI.changePassword({
        current_password: pwForm.current_password,
        new_password: pwForm.new_password,
      });
      addToast('Đổi mật khẩu thành công! 🔑');
      setPwForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setChangingPw(false);
    }
  };

  if (!user) return <div className="loading-spinner"><div className="spinner" /></div>;

  const displayName = user.nickname || user.full_name;
  const initials = getInitials(user.full_name || user.username);

  return (
    <>
      <div className="page-header">
        <h1>👤 Hồ Sơ Của Tôi</h1>
        <p>Cập nhật thông tin cá nhân</p>
      </div>

      <div className="profile-layout">
        {/* Avatar card */}
        <div className="card profile-avatar-card">
          <div
            className="avatar-display"
            onClick={() => fileInputRef.current?.click()}
            title="Bấm để đổi ảnh"
          >
            {avatarPreview ? (
              <img src={avatarPreview} alt="avatar" className="avatar-img" />
            ) : (
              <div className="avatar-initials">{initials}</div>
            )}
            <div className="avatar-overlay">📷</div>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleAvatarFile}
          />
          <div style={{ textAlign: 'center', marginTop: '12px' }}>
            <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{displayName}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', fontFamily: 'monospace' }}>@{user.username}</div>
            <span className="badge" style={{ marginTop: '6px', display: 'inline-block' }}>
              {user.role === 'admin' ? '👑 Admin' : '👤 User'}
            </span>
          </div>
          <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '8px' }}>
            Bấm vào ảnh để đổi · Tối đa 200KB
          </p>
          {avatarPreview && (
            <button
              className="btn btn-ghost btn-sm"
              style={{ width: '100%', marginTop: '4px', color: 'var(--status-finalized)', fontSize: '0.78rem' }}
              onClick={() => { setAvatarPreview(null); setForm(f => ({ ...f, avatar_url: '' })); }}
            >
              🗑️ Xoá ảnh
            </button>
          )}
        </div>

        {/* Info form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
          <div className="card">
            <div className="card-title" style={{ marginBottom: '16px' }}>✏️ Thông Tin Cá Nhân</div>

            <div className="form-group">
              <label className="form-label">Username</label>
              <input
                className="form-input"
                value={user.username}
                disabled
                style={{ opacity: 0.5, cursor: 'not-allowed' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Username không thể thay đổi</span>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Họ tên</label>
                <input
                  className="form-input"
                  value={form.full_name}
                  onChange={set('full_name')}
                  placeholder="Nguyễn Văn A"
                />
              </div>
              <div className="form-group">
                <label className="form-label">
                  Nickname
                  <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> (hiển thị thay họ tên)</span>
                </label>
                <input
                  className="form-input"
                  value={form.nickname}
                  onChange={set('nickname')}
                  placeholder="VD: Trọng, Nam, Hà..."
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Email</label>
                <input
                  type="email"
                  className="form-input"
                  value={form.email}
                  onChange={set('email')}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Ngày sinh</label>
                <input
                  type="date"
                  className="form-input"
                  value={form.date_of_birth}
                  onChange={set('date_of_birth')}
                />
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleSaveProfile}
              disabled={saving}
              style={{ marginTop: '4px' }}
            >
              {saving ? '⏳ Đang lưu...' : '💾 Lưu Thông Tin'}
            </button>
          </div>

          {/* Change password */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: '16px' }}>🔑 Đổi Mật Khẩu</div>

            <div className="form-group">
              <label className="form-label">Mật khẩu hiện tại</label>
              <input
                type="password"
                className="form-input"
                value={pwForm.current_password}
                onChange={e => setPwForm(f => ({ ...f, current_password: e.target.value }))}
                placeholder="••••••"
                autoComplete="current-password"
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Mật khẩu mới</label>
                <input
                  type="password"
                  className="form-input"
                  value={pwForm.new_password}
                  onChange={e => setPwForm(f => ({ ...f, new_password: e.target.value }))}
                  placeholder="Tối thiểu 6 ký tự"
                  autoComplete="new-password"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Xác nhận mật khẩu mới</label>
                <input
                  type="password"
                  className={`form-input ${pwForm.confirm_password && pwForm.confirm_password !== pwForm.new_password ? 'input-error' : ''}`}
                  value={pwForm.confirm_password}
                  onChange={e => setPwForm(f => ({ ...f, confirm_password: e.target.value }))}
                  placeholder="••••••"
                  autoComplete="new-password"
                />
              </div>
            </div>

            <button
              className="btn btn-secondary"
              onClick={handleChangePassword}
              disabled={changingPw || !pwForm.current_password || pwForm.new_password.length < 6 || pwForm.new_password !== pwForm.confirm_password}
              style={{ marginTop: '4px' }}
            >
              {changingPw ? '⏳ Đang đổi...' : '🔑 Đổi Mật Khẩu'}
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        .profile-layout {
          display: grid;
          grid-template-columns: 220px 1fr;
          gap: 20px;
          align-items: start;
        }
        @media (max-width: 700px) {
          .profile-layout { grid-template-columns: 1fr; }
        }
        .profile-avatar-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0;
        }
        .avatar-display {
          position: relative;
          width: 100px;
          height: 100px;
          border-radius: 50%;
          cursor: pointer;
          overflow: hidden;
          border: 3px solid var(--border-medium);
          transition: border-color 0.2s;
        }
        .avatar-display:hover { border-color: var(--accent-primary); }
        .avatar-img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
        .avatar-initials {
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--gradient-accent);
          font-size: 2rem;
          font-weight: 700;
          color: #0a0a0f;
        }
        .avatar-overlay {
          position: absolute;
          inset: 0;
          background: rgba(0,0,0,0.45);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.4rem;
          opacity: 0;
          transition: opacity 0.2s;
        }
        .avatar-display:hover .avatar-overlay { opacity: 1; }
        .form-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }
        @media (max-width: 500px) { .form-row { grid-template-columns: 1fr; } }
        .input-error { border-color: #ff6b6b !important; }
      `}</style>
    </>
  );
}
