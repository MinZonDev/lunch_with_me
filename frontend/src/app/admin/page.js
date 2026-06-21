'use client';

import { useState, useEffect, useCallback } from 'react';
import { membersAPI, ordersAPI, getTodayString } from '@/lib/api';
import Link from 'next/link';
import { useToast } from '@/components/Toast';

export default function AdminPage() {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddMember, setShowAddMember] = useState(false);
  const [newMemberName, setNewMemberName] = useState('');
  const [showCreateOrder, setShowCreateOrder] = useState(false);
  const [orderDate, setOrderDate] = useState(getTodayString());
  const [menuLink, setMenuLink] = useState('');
  const [menuLinkChay, setMenuLinkChay] = useState('');
  const [deadlineTime, setDeadlineTime] = useState('11:30');
  const [editingMember, setEditingMember] = useState(null);
  const [editName, setEditName] = useState('');
  const addToast = useToast();

  const fetchMembers = useCallback(async () => {
    try {
      const data = await membersAPI.list(false);
      setMembers(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  const handleAddMember = async () => {
    if (!newMemberName.trim()) {
      addToast('Nhập tên!', 'error');
      return;
    }
    try {
      await membersAPI.create({ name: newMemberName.trim() });
      addToast('Đã thêm thành viên! 🎉');
      setNewMemberName('');
      setShowAddMember(false);
      fetchMembers();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleToggleActive = async (member) => {
    try {
      await membersAPI.update(member.id, { is_active: !member.is_active });
      addToast(member.is_active ? 'Đã deactivate' : 'Đã activate');
      fetchMembers();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleUpdateName = async (id) => {
    if (!editName.trim()) return;
    try {
      await membersAPI.update(id, { name: editName.trim() });
      addToast('Đã cập nhật tên');
      setEditingMember(null);
      fetchMembers();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleCreateOrder = async () => {
    try {
      const order = await ordersAPI.create({
        order_date: orderDate,
        menu_link: menuLink || null,
        menu_link_chay: menuLinkChay || null,
        deadline_time: deadlineTime || '11:30',
      });
      addToast('Đã tạo order! 🍚');
      setShowCreateOrder(false);
      setMenuLink('');
      setMenuLinkChay('');
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  if (loading) {
    return <div className="loading-spinner"><div className="spinner" /></div>;
  }

  const activeMembers = members.filter((m) => m.is_active);
  const inactiveMembers = members.filter((m) => !m.is_active);

  return (
    <>
      <div className="page-header">
        <h1>⚙️ Quản Lý</h1>
        <p>Quản lý thành viên và tạo order</p>
      </div>

      {/* Quick Actions */}
      <div className="stats-grid mb-24">
        <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => setShowCreateOrder(true)}>
          <div className="stat-icon orange">📋</div>
          <div className="stat-info"><h3 style={{ fontSize: '1rem' }}>Tạo Order</h3><p>Tạo order cho ngày bất kỳ</p></div>
        </div>
        <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => setShowAddMember(true)}>
          <div className="stat-icon green">👤</div>
          <div className="stat-info"><h3 style={{ fontSize: '1rem' }}>Thêm Thành Viên</h3><p>Thêm người mới vào team</p></div>
        </div>
        <Link href="/admin/users" className="stat-card" style={{ textDecoration: 'none' }}>
          <div className="stat-icon blue">🔑</div>
          <div className="stat-info"><h3 style={{ fontSize: '1rem' }}>Quản Lý Users</h3><p>Tài khoản đăng nhập</p></div>
        </Link>
        <Link href="/admin/import" className="stat-card" style={{ textDecoration: 'none' }}>
          <div className="stat-icon yellow">📥</div>
          <div className="stat-info"><h3 style={{ fontSize: '1rem' }}>Import Excel</h3><p>Import dữ liệu lịch sử</p></div>
        </Link>
      </div>

      {/* Members List */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">👥 Thành Viên ({activeMembers.length} active)</div>
          <button className="btn btn-primary btn-sm" onClick={() => setShowAddMember(true)}>
            ➕ Thêm
          </button>
        </div>

        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Tên</th>
                <th>Trạng thái</th>
                <th>Ngày tham gia</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.id} style={!member.is_active ? { opacity: 0.5 } : {}}>
                  <td>
                    {editingMember === member.id ? (
                      <div className="flex gap-8">
                        <input
                          type="text"
                          className="form-input"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleUpdateName(member.id)}
                          style={{ padding: '6px 12px', fontSize: '0.85rem' }}
                          autoFocus
                        />
                        <button className="btn btn-primary btn-sm" onClick={() => handleUpdateName(member.id)}>💾</button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setEditingMember(null)}>✕</button>
                      </div>
                    ) : (
                      <span style={{ fontWeight: '600' }}>{member.name}</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${member.is_active ? 'badge-success' : 'badge-debt'}`}>
                      {member.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                    {new Date(member.created_at).toLocaleDateString('vi-VN')}
                  </td>
                  <td>
                    <div className="flex gap-8">
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => {
                          setEditingMember(member.id);
                          setEditName(member.name);
                        }}
                        title="Sửa tên"
                      >
                        ✏️
                      </button>
                      <button
                        className={`btn btn-sm ${member.is_active ? 'btn-danger' : 'btn-secondary'}`}
                        onClick={() => handleToggleActive(member)}
                      >
                        {member.is_active ? '🚫' : '✅'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Member Modal */}
      {showAddMember && (
        <div className="modal-overlay" onClick={() => setShowAddMember(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">👤 Thêm Thành Viên</div>
            <div className="form-group">
              <label className="form-label">Tên</label>
              <input
                type="text"
                className="form-input"
                placeholder="VD: Nguyễn Văn A"
                value={newMemberName}
                onChange={(e) => setNewMemberName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddMember()}
                autoFocus
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowAddMember(false)}>Hủy</button>
              <button className="btn btn-primary" onClick={handleAddMember}>Thêm</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Order Modal */}
      {showCreateOrder && (
        <div className="modal-overlay" onClick={() => setShowCreateOrder(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">📋 Tạo Order</div>
            <div className="form-group">
              <label className="form-label">Ngày</label>
              <input
                type="date"
                className="form-input"
                value={orderDate}
                onChange={(e) => setOrderDate(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Link Menu</label>
              <input
                type="text"
                className="form-input"
                placeholder="Paste link menu từ app Be..."
                value={menuLink}
                onChange={(e) => setMenuLink(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Link Menu Chay (tùy chọn)</label>
              <input type="text" className="form-input" placeholder="Paste link menu chay..." value={menuLinkChay} onChange={e => setMenuLinkChay(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Deadline chọn món</label>
              <input type="time" className="form-input" value={deadlineTime} onChange={e => setDeadlineTime(e.target.value)} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowCreateOrder(false)}>Hủy</button>
              <button className="btn btn-primary" onClick={handleCreateOrder}>Tạo Order</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
