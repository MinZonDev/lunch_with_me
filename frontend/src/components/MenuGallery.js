'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { restaurantsAPI } from '@/lib/api';

// ── Viewer: thumbnails + full-screen lightbox with prev/next ──
export function MenuGallery({ images, title = '🖼️ Menu' }) {
  const [open, setOpen] = useState(null); // index of the enlarged image

  const step = useCallback((delta) => {
    setOpen(i => (i === null ? null : (i + delta + images.length) % images.length));
  }, [images.length]);

  useEffect(() => {
    if (open === null) return;
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(null);
      if (e.key === 'ArrowRight') step(1);
      if (e.key === 'ArrowLeft') step(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, step]);

  if (!images?.length) return null;

  return (
    <div className="card mb-24">
      <div className="card-title" style={{ marginBottom: 12 }}>{title} ({images.length} ảnh)</div>
      <div className="flex gap-8" style={{ flexWrap: 'wrap' }}>
        {images.map((img, idx) => (
          <button key={img.path} onClick={() => setOpen(idx)} title="Xem ảnh lớn"
            style={{ padding: 0, border: '1px solid var(--border-color)', borderRadius: 8, overflow: 'hidden', cursor: 'zoom-in', background: 'none' }}>
            <img src={img.url} alt={`Menu ${idx + 1}`} loading="lazy"
              style={{ width: 120, height: 120, objectFit: 'cover', display: 'block' }} />
          </button>
        ))}
      </div>

      {open !== null && (
        <div className="modal-overlay" onClick={() => setOpen(null)}
          style={{ flexDirection: 'column', gap: 12, padding: 16 }}>
          <img src={images[open].url} alt={`Menu ${open + 1}`} onClick={e => e.stopPropagation()}
            style={{ maxWidth: '100%', maxHeight: 'calc(100vh - 100px)', objectFit: 'contain', borderRadius: 8, background: '#fff' }} />
          <div className="flex gap-8 items-center" onClick={e => e.stopPropagation()}>
            {images.length > 1 && <button className="btn btn-secondary btn-sm" onClick={() => step(-1)}>‹ Trước</button>}
            <span style={{ color: '#fff', fontSize: '0.85rem' }}>{open + 1} / {images.length}</span>
            {images.length > 1 && <button className="btn btn-secondary btn-sm" onClick={() => step(1)}>Sau ›</button>}
            <a className="btn btn-ghost btn-sm" href={images[open].url} target="_blank" rel="noopener noreferrer" style={{ color: '#fff' }}>Mở tab mới</a>
            <button className="btn btn-ghost btn-sm" style={{ color: '#fff' }} onClick={() => setOpen(null)}>✕ Đóng</button>
          </div>
        </div>
      )}
    </div>
  );
}

const MAX_MB = 5;
const ACCEPT = 'image/jpeg,image/png,image/webp,image/gif';

// ── Admin: upload / delete a restaurant's menu photos ──
export function MenuImagesManager({ restaurant, onClose, onChanged, addToast }) {
  const [images, setImages] = useState(restaurant.menu_images || []);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const inputRef = useRef(null);

  const upload = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length || uploading) return;
    const tooBig = files.find(f => f.size > MAX_MB * 1024 * 1024);
    if (tooBig) { addToast(`${tooBig.name} lớn hơn ${MAX_MB}MB`, 'error'); return; }
    setUploading(true);
    try {
      const updated = await restaurantsAPI.uploadMenuImages(restaurant.id, files);
      setImages(updated.menu_images);
      addToast(`Đã tải lên ${files.length} ảnh`);
      onChanged();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const remove = async (img) => {
    if (!confirm('Xoá ảnh menu này?')) return;
    setDeleting(img.path);
    try {
      const updated = await restaurantsAPI.deleteMenuImage(restaurant.id, img.path);
      setImages(updated.menu_images);
      onChanged();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 640 }}>
        <div className="modal-title">🖼️ Ảnh menu · {restaurant.name}</div>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 0 }}>
          Dùng cho quán đặt ngoài chỉ có ảnh menu. JPG/PNG/WebP, tối đa {MAX_MB}MB mỗi ảnh.
        </p>
        <div className="flex gap-8" style={{ flexWrap: 'wrap', marginBottom: 16 }}>
          {images.map((img, idx) => (
            <div key={img.path} style={{ position: 'relative' }}>
              <a href={img.url} target="_blank" rel="noopener noreferrer">
                <img src={img.url} alt={`Menu ${idx + 1}`}
                  style={{ width: 110, height: 110, objectFit: 'cover', borderRadius: 8, border: '1px solid var(--border-color)', display: 'block' }} />
              </a>
              <button onClick={() => remove(img)} disabled={deleting === img.path} title="Xoá ảnh"
                style={{
                  position: 'absolute', top: 4, right: 4, width: 26, height: 26, borderRadius: '50%',
                  border: 'none', background: 'rgba(0,0,0,0.65)', color: '#fff', cursor: 'pointer',
                }}>{deleting === img.path ? '…' : '✕'}</button>
            </div>
          ))}
          {images.length === 0 && (
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Chưa có ảnh menu.</span>
          )}
        </div>
        <input ref={inputRef} type="file" accept={ACCEPT} multiple hidden onChange={e => upload(e.target.files)} />
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>Đóng</button>
          <button className="btn btn-primary" onClick={() => inputRef.current?.click()} disabled={uploading}>
            {uploading ? '⏳ Đang tải lên...' : '📤 Thêm ảnh'}
          </button>
        </div>
      </div>
    </div>
  );
}
