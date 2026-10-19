'use client';

import Link from 'next/link';
import BankQR from '@/components/BankQR';
import { formatMoney } from '@/lib/api';

// Popup for a blacklisted member: ordering is locked until the debt is paid.
export default function DebtLockModal({ debt, fullName, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
          <div className="modal-title" style={{ margin: 0 }}>⛔ Tạm khoá đặt cơm</div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} title="Đóng">✕</button>
        </div>
        <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
          Bạn đang nợ <strong style={{ color: 'var(--status-finalized)' }}>{formatMoney(debt)} đ</strong>,
          vui lòng thanh toán để được mở tính năng đặt cơm.
        </p>
        <BankQR amount={debt} info={`${fullName || ''} nap com`.trim()} />
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
          Chuyển khoản xong, hãy tạo yêu cầu nạp tiền. Tính năng đặt cơm tự mở lại khi admin duyệt và số dư không còn âm.
        </p>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>Đóng</button>
          <Link href="/deposit" className="btn btn-primary">💳 Tạo yêu cầu nạp tiền</Link>
        </div>
      </div>
    </div>
  );
}
