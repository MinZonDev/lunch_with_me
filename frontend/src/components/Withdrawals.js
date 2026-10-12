'use client';

import { useState, useEffect } from 'react';
import { withdrawalsAPI, formatMoney, txnMeta } from '@/lib/api';

// Used when api.vietqr.io is unreachable; codes work with img.vietqr.io
const FALLBACK_BANKS = [
  { code: 'VCB', shortName: 'Vietcombank' },
  { code: 'TCB', shortName: 'Techcombank' },
  { code: 'MB', shortName: 'MBBank' },
  { code: 'ICB', shortName: 'VietinBank' },
  { code: 'BIDV', shortName: 'BIDV' },
  { code: 'VBA', shortName: 'Agribank' },
  { code: 'ACB', shortName: 'ACB' },
  { code: 'VPB', shortName: 'VPBank' },
  { code: 'TPB', shortName: 'TPBank' },
  { code: 'STB', shortName: 'Sacombank' },
  { code: 'VIB', shortName: 'VIB' },
  { code: 'HDB', shortName: 'HDBank' },
  { code: 'MSB', shortName: 'MSB' },
  { code: 'SHB', shortName: 'SHB' },
  { code: 'OCB', shortName: 'OCB' },
  { code: 'TIMO', shortName: 'Timo' },
  { code: 'CAKE', shortName: 'CAKE by VPBank' },
  { code: 'VIKKI', shortName: 'Vikki Digital Bank' },
];

let banksPromise = null;
function loadBanks() {
  if (!banksPromise) {
    banksPromise = fetch('https://api.vietqr.io/v2/banks')
      .then(r => r.json())
      .then(j => (j.data?.length ? j.data.map(b => ({ code: b.code, shortName: b.shortName })) : FALLBACK_BANKS))
      .catch(() => FALLBACK_BANKS);
  }
  return banksPromise;
}

function payoutQRUrl(w) {
  const params = new URLSearchParams({
    accountName: w.account_name,
    amount: String(w.amount * 1000),
    addInfo: `Lunch With Me rut tien ${w.id}`,
  });
  return `https://img.vietqr.io/image/${w.bank_code}-${w.account_number}-compact2.png?${params}`;
}

function StatusBadge({ w }) {
  const meta = txnMeta('withdrawal', w.status);
  return <span className="badge" style={{ border: '1px solid var(--border-medium)' }}>{meta.badge}</span>;
}

// ── User: request modal ──
export function WithdrawalModal({ balance, onClose, onDone, addToast }) {
  const [banks, setBanks] = useState(FALLBACK_BANKS);
  const [amount, setAmount] = useState('');
  const [bankCode, setBankCode] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [accountName, setAccountName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { loadBanks().then(setBanks); }, []);

  const value = parseInt(amount) || 0;
  const tooMuch = value > balance;

  const submit = async () => {
    if (submitting) return;
    if (value <= 0) { addToast('Nhập số tiền muốn rút!', 'error'); return; }
    if (tooMuch) { addToast('Số tiền rút không được lớn hơn số dư!', 'error'); return; }
    if (!bankCode) { addToast('Chọn ngân hàng!', 'error'); return; }
    if (!/^[0-9A-Za-z]{4,30}$/.test(accountNumber.trim())) { addToast('Số tài khoản không hợp lệ!', 'error'); return; }
    if (!accountName.trim()) { addToast('Nhập tên người nhận!', 'error'); return; }
    const bank = banks.find(b => b.code === bankCode);
    setSubmitting(true);
    try {
      await withdrawalsAPI.create({
        amount: value,
        bank_code: bankCode,
        bank_name: bank?.shortName || bankCode,
        account_number: accountNumber.trim(),
        account_name: accountName.trim(),
      });
      addToast('Đã gửi yêu cầu rút tiền! Chờ admin chuyển khoản.');
      onDone();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-title">💸 Yêu Cầu Rút Tiền</div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: 0 }}>
          Số dư hiện tại: <strong style={{ color: '#06d6a0' }}>{formatMoney(balance)} đ</strong>
        </p>
        <div className="form-group">
          <label className="form-label">Số tiền rút (k)</label>
          <div className="flex gap-8">
            <input type="number" className="form-input" placeholder="VD: 100" value={amount}
              onChange={e => setAmount(e.target.value)} style={{ flex: 1 }} autoFocus />
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setAmount(String(balance))}>
              Rút toàn bộ
            </button>
          </div>
          {value > 0 && (
            <p style={{ fontSize: '0.8rem', margin: '6px 0 0', color: tooMuch ? '#ff6b6b' : 'var(--text-muted)' }}>
              {tooMuch ? 'Vượt quá số dư!' : <>= <strong>{formatMoney(value)} đ</strong> · còn lại {formatMoney(balance - value)} đ</>}
            </p>
          )}
        </div>
        <div className="form-group">
          <label className="form-label">Ngân hàng</label>
          <select className="form-select" value={bankCode} onChange={e => setBankCode(e.target.value)}>
            <option value="">— Chọn ngân hàng —</option>
            {banks.map(b => <option key={b.code} value={b.code}>{b.shortName}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Số tài khoản</label>
          <input type="text" inputMode="numeric" className="form-input" value={accountNumber}
            onChange={e => setAccountNumber(e.target.value.replace(/\s/g, ''))} />
        </div>
        <div className="form-group">
          <label className="form-label">Tên người nhận</label>
          <input type="text" className="form-input" placeholder="VD: NGUYEN VAN A" value={accountName}
            onChange={e => setAccountName(e.target.value.toUpperCase())} />
        </div>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>Hủy</button>
          <button className="btn btn-primary" onClick={submit} disabled={submitting || tooMuch}>
            {submitting ? '⏳ Đang gửi...' : '📤 Gửi Yêu Cầu'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── User: own requests (pending one can be cancelled) ──
export function MyWithdrawals({ withdrawals, onChanged, addToast }) {
  if (withdrawals.length === 0) return null;
  const cancel = async (id) => {
    if (!confirm('Huỷ yêu cầu rút tiền này?')) return;
    try { await withdrawalsAPI.cancel(id); addToast('Đã huỷ yêu cầu'); onChanged(); }
    catch (err) { addToast(err.message, 'error'); }
  };
  return (
    <div className="card mb-16">
      <div className="card-title" style={{ marginBottom: 10 }}>💸 Yêu cầu rút tiền</div>
      {withdrawals.slice(0, 5).map(w => (
        <div key={w.id} className="flex items-center gap-12" style={{ fontSize: '0.85rem', flexWrap: 'wrap', padding: '6px 0' }}>
          <strong style={{ color: w.status === 'done' ? '#ff6b6b' : 'var(--text-primary)' }}>−{formatMoney(w.amount)}</strong>
          <span style={{ color: 'var(--text-muted)' }}>{w.bank_name} · {w.account_number}</span>
          <StatusBadge w={w} />
          {w.reject_reason && <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>“{w.reject_reason}”</span>}
          <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{new Date(w.created_at).toLocaleDateString('vi-VN')}</span>
          {w.status === 'pending' && (
            <button className="btn btn-ghost btn-sm" style={{ color: 'var(--status-finalized)' }} onClick={() => cancel(w.id)}>Huỷ</button>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Admin: pending queue with payout QR ──
export function PendingWithdrawalsAdmin({ withdrawals, onChanged, addToast }) {
  const [busy, setBusy] = useState(null);
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState('');

  const pending = withdrawals.filter(w => w.status === 'pending');
  if (pending.length === 0) return null;

  const complete = async (w) => {
    if (busy) return;
    if (!confirm(`Xác nhận đã chuyển ${formatMoney(w.amount)} đ cho ${w.member_name}? Số dư sẽ bị trừ.`)) return;
    setBusy(w.id);
    try { await withdrawalsAPI.complete(w.id); addToast('Đã hoàn tất rút tiền 💸'); onChanged(); }
    catch (err) { addToast(err.message, 'error'); }
    finally { setBusy(null); }
  };

  const reject = async (w) => {
    if (busy) return;
    setBusy(w.id);
    try {
      await withdrawalsAPI.reject(w.id, reason.trim() || null);
      addToast('Đã từ chối yêu cầu');
      setRejecting(null); setReason('');
      onChanged();
    } catch (err) { addToast(err.message, 'error'); }
    finally { setBusy(null); }
  };

  return (
    <div className="card mb-24" style={{ borderLeft: '3px solid #ff8c42' }}>
      <div className="card-title" style={{ marginBottom: 12, color: '#ff8c42' }}>
        💸 Yêu Cầu Rút Tiền Chờ Chuyển ({pending.length})
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {pending.map(w => (
          <div key={w.id} className="flex gap-16" style={{ flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <img src={payoutQRUrl(w)} alt={`QR chuyển cho ${w.account_name}`}
              style={{ width: 150, height: 150, borderRadius: 10, background: '#fff', border: '2px solid var(--border-medium)' }} />
            <div style={{ flex: 1, minWidth: 200, fontSize: '0.88rem', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div><strong>{w.member_name}</strong> rút <strong style={{ color: '#ff8c42' }}>{formatMoney(w.amount)} đ</strong></div>
              <div><span style={{ color: 'var(--text-muted)' }}>Ngân hàng:</span> {w.bank_name}</div>
              <div><span style={{ color: 'var(--text-muted)' }}>STK:</span> <strong style={{ letterSpacing: 1 }}>{w.account_number}</strong></div>
              <div><span style={{ color: 'var(--text-muted)' }}>Người nhận:</span> {w.account_name}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{new Date(w.created_at).toLocaleString('vi-VN')}</div>
              {rejecting === w.id ? (
                <div className="flex gap-8 mt-8" style={{ flexWrap: 'wrap' }}>
                  <input className="form-input" placeholder="Lý do (tuỳ chọn)" value={reason}
                    onChange={e => setReason(e.target.value)} style={{ flex: 1, minWidth: 150 }} autoFocus />
                  <button className="btn btn-secondary btn-sm" onClick={() => reject(w)} disabled={busy === w.id}>Xác nhận từ chối</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setRejecting(null)}>✕</button>
                </div>
              ) : (
                <div className="flex gap-8 mt-8">
                  <button className="btn btn-primary btn-sm" onClick={() => complete(w)} disabled={busy === w.id}>
                    {busy === w.id ? '⏳...' : '✅ Đã chuyển khoản'}
                  </button>
                  <button className="btn btn-ghost btn-sm" style={{ color: 'var(--status-finalized)' }}
                    onClick={() => { setRejecting(w.id); setReason(''); }}>Từ chối</button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
