'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { getUser, isAdmin, clearAuth } from '@/lib/auth';
import { getInitials } from '@/lib/api';

export default function Sidebar({ isOpen, onClose }) {
  const pathname = usePathname();
  const router = useRouter();
  const user = getUser();
  const admin = isAdmin();

  const navItems = [
    { href: '/', icon: '🍚', label: 'Hôm Nay' },
    { href: '/history', icon: '📋', label: 'Lịch Sử' },
    { href: '/deposit', icon: '💰', label: 'Deposit' },
    { href: '/reports', icon: '📊', label: 'Báo Cáo' },
    { href: '/reviews', icon: '⭐', label: 'Review Món' },
    { href: '/delegation', icon: '🤝', label: 'Ủy Quyền' },
    { href: '/profile', icon: '👤', label: 'Hồ Sơ' },
  ];

  const adminItems = [
    { href: '/admin', icon: '⚙️', label: 'Quản Lý' },
    { href: '/admin/restaurants', icon: '🏪', label: 'Quán Ăn' },
    { href: '/admin/reminders', icon: '🔔', label: 'Nhắc Nợ' },
    { href: '/admin/users', icon: '🔑', label: 'Users' },
    { href: '/admin/import', icon: '📥', label: 'Import Excel' },
  ];

  const handleLogout = () => {
    clearAuth();
    router.replace('/login');
  };

  return (
    <>
      {isOpen && <div className="sidebar-backdrop" onClick={onClose} />}
      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-logo">
          <div className="logo-icon">🍱</div>
          <div>
            <h2>Lunch With Me</h2>
            <span>Team Order</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-title">Menu</div>
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${pathname === item.href ? 'active' : ''}`}
              onClick={onClose}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </Link>
          ))}

          {admin && (
            <>
              <div className="nav-section-title">Admin</div>
              {adminItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-link ${pathname === item.href ? 'active' : ''}`}
                  onClick={onClose}
                >
                  <span className="nav-icon">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </>
          )}
        </nav>

        <div className="sidebar-user">
          {user && (
            <div className="user-info">
              <div className="user-avatar">
            {user.avatar_url
              ? <img src={user.avatar_url} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
              : getInitials(user.full_name || user.username)
            }
          </div>
              <div className="user-details">
                <div className="user-name">{user.full_name}</div>
                <div className="user-role">{user.role === 'admin' ? '👑 Admin' : '👤 User'}</div>
              </div>
            </div>
          )}
          <button className="logout-btn" onClick={handleLogout} title="Đăng xuất">
            🚪 Đăng xuất
          </button>
        </div>
      </aside>

      <style jsx>{`
        .sidebar-backdrop {
          display: none;
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.5);
          z-index: 99;
        }
        @media (max-width: 768px) {
          .sidebar-backdrop {
            display: block;
          }
        }
        .sidebar-user {
          padding: 12px 16px;
          border-top: 1px solid var(--border-subtle);
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .user-info {
          display: flex;
          align-items: center;
          gap: 10px;
          flex: 1;
          min-width: 0;
        }
        .user-avatar {
          width: 34px;
          height: 34px;
          border-radius: 50%;
          background: var(--gradient-accent);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.75rem;
          font-weight: 700;
          color: #fff;
          flex-shrink: 0;
        }
        .user-details {
          min-width: 0;
        }
        .user-name {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-primary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .user-role {
          font-size: 0.7rem;
          color: var(--text-muted);
        }
        .logout-btn {
          display: flex;
          align-items: center;
          gap: 5px;
          padding: 6px 10px;
          border-radius: var(--radius-md);
          border: 1px solid var(--border-subtle);
          background: transparent;
          color: var(--text-muted);
          font-size: 0.78rem;
          cursor: pointer;
          flex-shrink: 0;
          transition: background 0.15s, color 0.15s;
          white-space: nowrap;
        }
        .logout-btn:hover {
          background: rgba(255, 107, 107, 0.12);
          color: #ff6b6b;
          border-color: rgba(255, 107, 107, 0.3);
        }
      `}</style>
    </>
  );
}
