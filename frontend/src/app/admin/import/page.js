'use client';

import { useState, useCallback } from 'react';
import { getToken } from '@/lib/auth';
import { useToast } from '@/components/Toast';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function apiUpload(endpoint, file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}` },
    body: fd,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Upload failed');
  return data;
}

export default function ImportPage() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [nameMap, setNameMap] = useState({});
  const [members, setMembers] = useState([]);
  const [step, setStep] = useState(1); // 1=upload, 2=mapping, 3=done
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const addToast = useToast();

  const handlePreview = async () => {
    if (!file) { addToast('Chọn file trước!', 'error'); return; }
    setLoading(true);
    try {
      const data = await apiUpload('/api/admin/import/preview', file);
      setPreview(data);

      // Fetch members for mapping
      const res = await fetch(`${API_BASE}/api/admin/members/name-map`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      const mems = await res.json();
      setMembers(mems);

      // Auto-map by exact name match
      const auto = {};
      for (const name of data.unknown_names) {
        const match = mems.find(m => m.name === name);
        if (match) auto[name] = match.id;
      }
      setNameMap(auto);
      setStep(2);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API_BASE}/api/admin/import/commit`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ member_name_map: nameMap }),
      });
      // Commit sends JSON body, not file — use preview result
      // We need a different approach: send file + mapping as multipart
      // For now, re-upload file + mapping in a combined request
      const fd2 = new FormData();
      fd2.append('file', file);
      const res2 = await fetch(`${API_BASE}/api/admin/import/commit?` + new URLSearchParams(
        Object.entries(nameMap).map(([k, v]) => [`member_name_map[${k}]`, v])
      ), {
        method: 'POST',
        headers: { Authorization: `Bearer ${getToken()}` },
        body: fd2,
      });
      const data = await res2.json();
      setResult(data);
      setStep(3);
      addToast(`Import xong! ${data.imported} ngày thành công.`);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>📥 Import Excel</h1>
        <p>Import lịch sử dữ liệu từ file ĐẶT CƠM 2026.xlsx</p>
      </div>

      {/* Step indicator */}
      <div className="flex gap-16 mb-24" style={{ fontSize: '0.85rem' }}>
        {['Upload file', 'Kiểm tra & mapping', 'Hoàn tất'].map((s, i) => (
          <span key={i} style={{ color: step === i + 1 ? 'var(--accent-primary)' : step > i + 1 ? 'var(--status-success)' : 'var(--text-muted)', fontWeight: step === i + 1 ? '700' : '400' }}>
            {step > i + 1 ? '✅' : `${i + 1}.`} {s}
          </span>
        ))}
      </div>

      {/* Step 1: Upload */}
      {step === 1 && (
        <div className="card">
          <div className="card-title mb-16">📁 Chọn File Excel</div>
          <div className="form-group">
            <label className="form-label">File .xlsx</label>
            <input type="file" accept=".xlsx" className="form-input" onChange={e => setFile(e.target.files[0])} />
          </div>
          {file && <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>✅ {file.name} ({Math.round(file.size / 1024)}KB)</p>}
          <div className="mt-16">
            <button className="btn btn-primary" onClick={handlePreview} disabled={!file || loading}>
              {loading ? '⏳ Đang phân tích...' : '🔍 Xem Preview'}
            </button>
          </div>
          <div className="mt-16" style={{ background: 'rgba(255,140,66,0.06)', border: '1px solid var(--border-accent)', borderRadius: 'var(--radius-md)', padding: '12px 16px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <strong>Lưu ý:</strong> Hệ thống sẽ đọc các sheet có tên dạng <code>DD-MM-YYYY</code>. Các ngày đã có trong DB sẽ được bỏ qua (không overwrite).
          </div>
        </div>
      )}

      {/* Step 2: Preview + Mapping */}
      {step === 2 && preview && (
        <>
          <div className="stats-grid mb-24">
            <div className="stat-card"><div className="stat-icon orange">📅</div><div className="stat-info"><h3>{preview.total_days}</h3><p>Ngày tìm thấy</p></div></div>
            <div className="stat-card"><div className="stat-icon red">❓</div><div className="stat-info"><h3>{preview.unknown_names.length}</h3><p>Tên chưa khớp</p></div></div>
            <div className="stat-card"><div className="stat-icon blue">📋</div><div className="stat-info"><h3>{preview.skipped_sheets.length}</h3><p>Sheet bỏ qua</p></div></div>
          </div>

          {preview.unknown_names.length > 0 && (
            <div className="card mb-24">
              <div className="card-title mb-16">🔗 Mapping Tên</div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '16px' }}>
                Các tên trong Excel chưa khớp với member trong hệ thống. Hãy chọn member tương ứng:
              </p>
              {preview.unknown_names.map(name => (
                <div key={name} className="flex gap-12 items-center mb-12">
                  <span style={{ minWidth: '120px', fontWeight: '600' }}>{name}</span>
                  <span style={{ color: 'var(--text-muted)' }}>→</span>
                  <select className="form-select" style={{ flex: 1 }} value={nameMap[name] || ''} onChange={e => setNameMap(m => ({ ...m, [name]: Number(e.target.value) }))}>
                    <option value="">— Bỏ qua —</option>
                    {members.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                  </select>
                </div>
              ))}
            </div>
          )}

          {/* Preview days */}
          <div className="card mb-24">
            <div className="card-title mb-16">📋 Preview ({preview.days.length} ngày)</div>
            <div className="table-wrapper">
              <table className="table">
                <thead><tr><th>Ngày</th><th>Tổng bill</th><th>Số người ăn</th></tr></thead>
                <tbody>
                  {preview.days.slice(0, 20).map(d => (
                    <tr key={d.date}>
                      <td>{new Date(d.date).toLocaleDateString('vi-VN')}</td>
                      <td>{d.total_bill ? Number(d.total_bill).toLocaleString('vi-VN') : <span style={{ color: 'var(--text-muted)' }}>Chưa rõ</span>}</td>
                      <td>{d.members.filter(m => m.is_eating).length} người</td>
                    </tr>
                  ))}
                  {preview.days.length > 20 && <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>... và {preview.days.length - 20} ngày nữa</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex gap-12">
            <button className="btn btn-secondary" onClick={() => setStep(1)}>← Quay lại</button>
            <button className="btn btn-primary" onClick={handleCommit} disabled={loading}>
              {loading ? '⏳ Đang import...' : '✅ Xác nhận Import'}
            </button>
          </div>
        </>
      )}

      {/* Step 3: Done */}
      {step === 3 && result && (
        <div className="card">
          <div className="empty-state" style={{ padding: '40px' }}>
            <div className="empty-icon">🎉</div>
            <h3>Import Hoàn Tất!</h3>
            <div className="stats-grid mt-24" style={{ maxWidth: '400px', margin: '24px auto 0' }}>
              <div className="stat-card"><div className="stat-icon green">✅</div><div className="stat-info"><h3>{result.imported}</h3><p>Đã import</p></div></div>
              <div className="stat-card"><div className="stat-icon yellow">⏭️</div><div className="stat-info"><h3>{result.skipped}</h3><p>Đã tồn tại (bỏ qua)</p></div></div>
            </div>
            {result.errors?.length > 0 && (
              <div style={{ marginTop: '16px', color: 'var(--status-finalized)', fontSize: '0.85rem' }}>
                <strong>Lỗi:</strong> {result.errors.join('; ')}
              </div>
            )}
            <button className="btn btn-primary mt-24" onClick={() => { setStep(1); setPreview(null); setFile(null); setResult(null); }}>
              Import thêm
            </button>
          </div>
        </div>
      )}
    </>
  );
}
