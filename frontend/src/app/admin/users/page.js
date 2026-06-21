'use client';

import { useState, useEffect, useCallback } from 'react';
import { authAPI, membersAPI } from '@/lib/api';
import { useToast } from '@/components/Toast';

const EMPTY_FORM = { username: '', password: '', full_name: '', email: '', date_of_birth: '', role: 'user', member_id: '' };

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const addToast = useToast();

  const fetchAll = useCallback(async () => {
    try {
      const [u, m] = await Promise.all([authAPI.listUsers(), membersAPI.list(false)]);
      setUsers(u); setMembers(m);
    } catch (err) { addToast(err.message, 'error'); }
    finally { setLoading(false); }
  }, [addToast]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const openCreate = () => { setEditId(null); setForm(EMPTY_FORM); setShowModal(true); };
  const openEdit = (u) => {
    setEditId(u.id);
    setForm({ username: u.username, password: '', full_name: u.full_name, email: u.email, date_of_birth: u.date_of_birth || '', role: u.role, member_id: u.member_id || '' });
    setShowModal(true);
  };

  const handleSave = async () => {
    try {
      if (editId) {
        await authAPI.updateUser(editId, {
          full_name: form.full_name,
          email: form.email,
          date_of_birth: form.date_of_birth || null,
          member_id: form.member_id ? Number(form.member_id) : null,
          role: form.role,
        });
      } else {
        await authAPI.createUser({ ...form, member_id: form.member_id ? Number(form.member_id) : null, date_of_birth: form.date_of_birth || null });
      }
      addToast(editId ? 'Đã cập nhật user' : 'Đã tạo user mới! 🎉');
      setShowModal(false); fetchAll();
    } catch (err) { addToast(err.message, 'error'); }
  };

  const handleDeactivate = async (id) => {
    if (!confirm('Deactivate user này?')) return;
    try { await authAPI.deleteUser(id); addToast('Đã deactivate'); fetchAll(); }
    catch (err) { addToast(err.message, 'error'); }
  };

  if (loading) return <div className="loading-spinner"><div className="spinner" /></div>;

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div><h1>🔑 Quản Lý Users</h1><p>Tài khoản đăng nhập hệ thống</p></div>
          <button className="btn btn-primary" onClick={openCreate}>➕ Tạo User</button>
        </div>
      </div>

      <div className="card">
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr><th>Họ tên</th><th>Username</th><th>Email</th><th>Role</th><th>Member</th><th>Trạng thái</th><th></th></tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={!u.is_active ? { opacity: 0.5 } : {}}>
                  <td style={{ fontWeight: '600' }}>{u.full_name}</td>
                  <td style={{ color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{u.username}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{u.email}</td>
                  <td><span className={`badge ${u.role === 'admin' ? 'badge-open' : ''}`}>{u.role === 'admin' ? '👑 Admin' : '👤 User'}</span></td>
                  <td style={{ color: 'var(--text-muted)' }}>{members.find(m => m.id === u.member_id)?.name || '—'}</td>
                  <td><span className={`badge ${u.is_active ? 'badge-success' : 'badge-debt'}`}>{u.is_active ? 'Active' : 'Inactive'}</span></td>
                  <td>
                    <div className="flex gap-8">
                      <button className="btn btn-ghost btn-sm" onClick={() => openEdit(u)}>✏️</button>
                      {u.is_active && <button className="btn btn-danger btn-sm" onClick={() => handleDeactivate(u.id)}>🚫</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" style={{ maxWidth: '480px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-title">{editId ? '✏️ Sửa User' : '➕ Tạo User Mới'}</div>

            {!editId && (
              <div className="form-group">
                <label className="form-label">Username *</label>
                <input type="text" className="form-input" value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} placeholder="VD: trong.pm" />
              </div>
            )}
            {!editId && (
              <div className="form-group">
                <label className="form-label">Mật khẩu *</label>
                <input type="password" className="form-input" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} placeholder="Tối thiểu 6 ký tự" />
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Họ tên *</label>
              <input type="text" className="form-input" value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Email *</label>
              <input type="email" className="form-input" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Ngày sinh</label>
              <input type="date" className="form-input" value={form.date_of_birth} onChange={e => setForm(f => ({ ...f, date_of_birth: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Role</label>
              <select className="form-select" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                <option value="user">👤 User</option>
                <option value="admin">👑 Admin</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Liên kết thành viên</label>
              <select className="form-select" value={form.member_id} onChange={e => setForm(f => ({ ...f, member_id: e.target.value }))}>
                <option value="">— Không liên kết —</option>
                {members.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Hủy</button>
              <button className="btn btn-primary" onClick={handleSave}>{editId ? 'Lưu' : 'Tạo'}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
