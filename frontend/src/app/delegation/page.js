'use client';

import { useState, useEffect, useCallback } from 'react';
import { delegationsAPI, membersAPI } from '@/lib/api';
import { getUser } from '@/lib/auth';
import { useToast } from '@/components/Toast';
import logger from '@/lib/logger';

export default function DelegationPage() {
  const [delegations, setDelegations] = useState([]);
  const [members, setMembers] = useState([]);
  const [selectedMember, setSelectedMember] = useState('');
  const [loading, setLoading] = useState(true);
  const [granting, setGranting] = useState(false);
  const addToast = useToast();
  const currentUser = getUser();

  const myMemberId = currentUser?.member_id;

  const fetchData = useCallback(async () => {
    try {
      const [delegList, memberList] = await Promise.all([
        delegationsAPI.list(),
        membersAPI.list(),
      ]);
      setDelegations(delegList);
      setMembers(memberList);
    } catch (err) {
      logger.error('Failed to load delegations', { error: err.message });
      addToast('Không tải được dữ liệu ủy quyền', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Delegations I granted (I am the grantor)
  const myGranted = delegations.filter(
    d => d.grantor_member_id === myMemberId && d.status === 'active'
  );

  // Delegations granted to me (I am the delegate)
  const grantedToMe = delegations.filter(
    d => d.delegate_member_id === myMemberId && d.status === 'active'
  );

  // Members I haven't granted yet (exclude myself and already-granted)
  const grantedMemberIds = new Set(myGranted.map(d => d.delegate_member_id));
  const availableMembers = members.filter(
    m => m.id !== myMemberId && !grantedMemberIds.has(m.id)
  );

  const handleGrant = async () => {
    if (!selectedMember) { addToast('Chọn thành viên trước!', 'error'); return; }
    setGranting(true);
    try {
      await delegationsAPI.grant(Number(selectedMember));
      addToast('Đã ủy quyền thành công!');
      setSelectedMember('');
      fetchData();
    } catch (err) {
      logger.error('Grant delegation failed', { error: err.message });
      addToast(err.message, 'error');
    } finally {
      setGranting(false);
    }
  };

  const handleRevoke = async (delegation) => {
    if (!confirm(`Thu hồi ủy quyền của ${delegation.delegate_name}?`)) return;
    try {
      await delegationsAPI.revoke(delegation.id);
      addToast('Đã thu hồi ủy quyền');
      fetchData();
    } catch (err) {
      logger.error('Revoke delegation failed', { error: err.message });
      addToast(err.message, 'error');
    }
  };

  if (loading) return <div className="loading-spinner"><div className="spinner" /></div>;

  if (!myMemberId) {
    return (
      <>
        <div className="page-header">
          <h1>🤝 Ủy Quyền Đặt Món</h1>
        </div>
        <div className="card" style={{ borderColor: 'rgba(255,230,109,0.4)', background: 'rgba(255,230,109,0.06)' }}>
          <div style={{ fontSize: '1.5rem', marginBottom: '12px' }}>⚠️</div>
          <div style={{ fontWeight: 700, marginBottom: '8px', color: 'var(--status-locked)' }}>
            Tài khoản chưa liên kết với thành viên
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>
            Để sử dụng tính năng ủy quyền, tài khoản của bạn cần được liên kết với một thành viên trong danh sách.
            Liên hệ admin để cập nhật.
          </p>
          <a href="/admin/users" className="btn btn-secondary btn-sm">
            ⚙️ Admin → Quản lý Users
          </a>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1>🤝 Ủy Quyền Đặt Món</h1>
        <p>Cho phép người khác đặt giùm bạn, hoặc xem ai đã ủy quyền cho bạn</p>
      </div>

      <div className="grid-2">
        {/* Grant section */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: '16px' }}>
            ➕ Ủy Quyền Cho Người Khác
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
            Chọn thành viên bạn muốn cho phép đặt món thay bạn.
          </p>

          {availableMembers.length > 0 ? (
            <div style={{ display: 'flex', gap: '8px' }}>
              <select
                className="form-select"
                value={selectedMember}
                onChange={e => setSelectedMember(e.target.value)}
                style={{ flex: 1 }}
              >
                <option value="">— Chọn thành viên —</option>
                {availableMembers.map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
              <button
                className="btn btn-primary"
                onClick={handleGrant}
                disabled={granting || !selectedMember}
              >
                {granting ? '...' : 'Ủy quyền'}
              </button>
            </div>
          ) : (
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Tất cả thành viên đã được ủy quyền.
            </p>
          )}

          {/* Active grants */}
          <div style={{ marginTop: '20px' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
              Đang ủy quyền ({myGranted.length})
            </div>
            {myGranted.length === 0 ? (
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Chưa ủy quyền cho ai.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {myGranted.map(d => (
                  <div key={d.id} className="delegation-row">
                    <div className="member-avatar sm">{d.delegate_name.slice(0, 2).toUpperCase()}</div>
                    <span style={{ flex: 1, fontSize: '0.875rem' }}>{d.delegate_name}</span>
                    <span className="badge badge-open" style={{ fontSize: '0.7rem' }}>Đang hoạt động</span>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleRevoke(d)}
                      title="Thu hồi"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Received delegations */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: '16px' }}>
            📋 Được Ủy Quyền Bởi
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
            Những người đã cho phép bạn đặt món thay họ.
          </p>

          {grantedToMe.length === 0 ? (
            <div className="empty-state" style={{ padding: '30px' }}>
              <div className="empty-icon">🤷</div>
              <p>Chưa ai ủy quyền cho bạn.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {grantedToMe.map(d => (
                <div key={d.id} className="delegation-row">
                  <div className="member-avatar sm">{d.grantor_name.slice(0, 2).toUpperCase()}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{d.grantor_name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Bạn có thể đặt món thay họ
                    </div>
                  </div>
                  <span className="badge badge-open" style={{ fontSize: '0.7rem' }}>Đang hoạt động</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: '16px' }}>
        <div className="card-title" style={{ marginBottom: '8px' }}>ℹ️ Hướng Dẫn</div>
        <ul style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.8, paddingLeft: '18px', margin: 0 }}>
          <li>Mỗi người chỉ có thể tự đặt món cho mình.</li>
          <li>Nếu bạn muốn đặt giùm người khác, họ phải ủy quyền cho bạn tại trang này.</li>
          <li>Bạn có thể thu hồi ủy quyền bất cứ lúc nào.</li>
          <li>Admin luôn có quyền đặt món cho tất cả mọi người.</li>
        </ul>
      </div>

      <style jsx>{`
        .delegation-row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 12px;
          background: var(--bg-input);
          border-radius: var(--radius-md);
          border: 1px solid var(--border-subtle);
        }
        .member-avatar.sm {
          width: 30px;
          height: 30px;
          border-radius: 50%;
          background: var(--gradient-accent);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.7rem;
          font-weight: 700;
          color: #fff;
          flex-shrink: 0;
        }
      `}</style>
    </>
  );
}
