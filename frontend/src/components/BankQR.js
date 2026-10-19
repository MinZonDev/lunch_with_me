// Bank transfer QR (VietQR) + account details. Amounts are in k (thousand VND).
const BANK = {
  id: process.env.NEXT_PUBLIC_BANK_ID || 'VIKKI',
  account: process.env.NEXT_PUBLIC_BANK_ACCOUNT || '880011988',
  name: process.env.NEXT_PUBLIC_BANK_ACCOUNT_NAME || 'PHAM MINH TRONG',
  bankName: process.env.NEXT_PUBLIC_BANK_NAME || 'Vikki Digital Bank',
};

export function vietQRUrl(amount = 0, info = '') {
  const params = new URLSearchParams({ accountName: BANK.name });
  if (amount > 0) params.set('amount', String(amount * 1000));
  if (info) params.set('addInfo', info);
  return `https://img.vietqr.io/image/${BANK.id}-${BANK.account}-compact2.png?${params}`;
}

export default function BankQR({ amount = 0, info = '' }) {
  return (
    <div style={{ textAlign: 'center', padding: '16px 0' }}>
      <img src={vietQRUrl(amount, info)} alt="QR chuyển khoản"
        style={{ width: 180, height: 180, borderRadius: 12, border: '3px solid var(--border-medium)', background: '#fff' }} />
      <div style={{ marginTop: 10, fontSize: '0.8rem', color: 'var(--text-muted)' }}>Quét bằng app ngân hàng bất kỳ</div>
      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.82rem', color: 'var(--text-secondary)', alignItems: 'center' }}>
        <span><span style={{ color: 'var(--text-muted)' }}>Ngân hàng:</span> <strong>{BANK.bankName}</strong></span>
        <span><span style={{ color: 'var(--text-muted)' }}>Tên:</span> <strong>{BANK.name}</strong></span>
        <span><span style={{ color: 'var(--text-muted)' }}>STK:</span> <strong style={{ fontSize: '1rem', letterSpacing: 1, color: '#ffe66d' }}>{BANK.account}</strong></span>
        {info && <span><span style={{ color: 'var(--text-muted)' }}>ND:</span> <strong>{info}</strong></span>}
        {amount > 0 && <span><span style={{ color: 'var(--text-muted)' }}>Số tiền:</span> <strong style={{ color: '#ff8c42' }}>{(Number(amount) * 1000).toLocaleString('vi-VN')} đ</strong></span>}
      </div>
    </div>
  );
}
