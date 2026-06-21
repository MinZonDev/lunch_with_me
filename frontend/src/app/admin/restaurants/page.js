'use client';

import { useState, useEffect } from 'react';
import { restaurantsAPI } from '@/lib/api';
import { useToast } from '@/components/Toast';

export default function RestaurantsPage() {
  const [restaurants, setRestaurants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null); // null = create, object = edit
  const [name, setName] = useState('');
  const [link, setLink] = useState('');
  const [saving, setSaving] = useState(false);
  const addToast = useToast();

  const load = async () => {
    try {
      setRestaurants(await restaurantsAPI.list());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditing(null); setName(''); setLink(''); setShowForm(true); };
  const openEdit = (r) => { setEditing(r); setName(r.name); setLink(r.link || ''); setShowForm(true); };

  const handleSave = async () => {
    if (!name.trim()) { addToast('Nhập tên quán!', 'error'); return; }
    setSaving(true);
    try {
      if (editing) {
        await restaurantsAPI.update(editing.id, { name: name.trim(), link: link.trim() || null });
        addToast('Đã cập nhật quán!');
      } else {
        await restaurantsAPI.create({ name: name.trim(), link: link.trim() || null });
        addToast('Đã thêm quán mới!');
      }
      setShowForm(false);
      load();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (r) => {
    if (!confirm(`Xóa quán "${r.name}"?`)) return;
    try {
      await restaurantsAPI.delete(r.id);
      addToast('Đã xóa quán');
      load();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1>🏪 Quản Lý Quán Ăn</h1>
            <p>Thêm quán để chọn nhanh khi tạo đơn hàng ngày</p>
          </div>
          <button className="btn btn-primary" onClick={openCreate}>+ Thêm Quán</button>
        </div>
      </div>

      {loading ? (
        <div className="loading-spinner"><div className="spinner" /></div>
      ) : restaurants.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🏪</div>
          <h3>Chưa có quán nào</h3>
          <p>Thêm quán để mỗi ngày chỉ cần chọn tên quán khi tạo đơn.</p>
          <button className="btn btn-primary mt-24" onClick={openCreate}>+ Thêm Quán Đầu Tiên</button>
        </div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Tên quán</th>
                <th>Link menu</th>
                <th style={{ width: 120 }}></th>
              </tr>
            </thead>
            <tbody>
              {restaurants.map(r => (
                <tr key={r.id}>
                  <td style={{ fontWeight: 600 }}>{r.name}</td>
                  <td>
                    {r.link
                      ? <a href={r.link} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-primary)', fontSize: '0.85rem' }}>🔗 Xem link</a>
                      : <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Chưa có link</span>}
                  </td>
                  <td>
                    <div className="flex gap-8">
                      <button className="btn btn-ghost btn-sm" onClick={() => openEdit(r)}>✏️</button>
                      <button className="btn btn-ghost btn-sm" style={{ color: 'var(--status-finalized)' }} onClick={() => handleDelete(r)}>🗑️</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">{editing ? '✏️ Sửa Quán' : '+ Thêm Quán Mới'}</div>
            <div className="form-group">
              <label className="form-label">Tên quán *</label>
              <input
                className="form-input"
                placeholder="VD: Cơm tấm Nguyễn Trãi, Bún bò Huế..."
                value={name}
                onChange={e => setName(e.target.value)}
                autoFocus
                onKeyDown={e => e.key === 'Enter' && handleSave()}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Link menu <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(tùy chọn)</span></label>
              <input
                className="form-input"
                placeholder="https://..."
                value={link}
                onChange={e => setLink(e.target.value)}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowForm(false)}>Hủy</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving || !name.trim()}>
                {saving ? '⏳ Đang lưu...' : '💾 Lưu'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
