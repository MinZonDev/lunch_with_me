'use client';

import { useState, useEffect, useCallback } from 'react';
import { reviewsAPI, membersAPI } from '@/lib/api';
import { useToast } from '@/components/Toast';

export default function ReviewsPage() {
  const [reviews, setReviews] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [dishName, setDishName] = useState('');
  const [rating, setRating] = useState('');
  const [comment, setComment] = useState('');
  const [selectedMember, setSelectedMember] = useState('');
  const addToast = useToast();

  const fetchData = useCallback(async () => {
    try {
      const [reviewsData, membersData] = await Promise.all([
        reviewsAPI.list(),
        membersAPI.list(),
      ]);
      setReviews(reviewsData);
      setMembers(membersData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSubmit = async () => {
    if (!dishName.trim()) {
      addToast('Nhập tên món!', 'error');
      return;
    }
    try {
      await reviewsAPI.create({
        member_id: selectedMember ? parseInt(selectedMember) : null,
        dish_name: dishName.trim(),
        rating: rating || null,
        comment: comment || null,
      });
      addToast('Đã thêm review! ⭐');
      setShowModal(false);
      setDishName('');
      setRating('');
      setComment('');
      setSelectedMember('');
      fetchData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Xóa review này?')) return;
    try {
      await reviewsAPI.delete(id);
      addToast('Đã xóa review');
      fetchData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const getRatingColor = (rating) => {
    if (!rating) return 'var(--text-muted)';
    const num = parseInt(rating);
    if (num >= 8) return 'var(--status-success)';
    if (num >= 5) return 'var(--accent-secondary)';
    return 'var(--status-finalized)';
  };

  if (loading) {
    return <div className="loading-spinner"><div className="spinner" /></div>;
  }

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1>⭐ Review Món</h1>
            <p>Đánh giá chất lượng món ăn</p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            ✍️ Thêm Review
          </button>
        </div>
      </div>

      {reviews.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">⭐</div>
          <h3>Chưa có review nào</h3>
          <p>Thêm review đầu tiên để team biết món nào ngon!</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
          {reviews.map((review) => (
            <div key={review.id} className="card-glass" style={{ position: 'relative' }}>
              <div className="flex items-center justify-between mb-16">
                <h3 style={{ fontSize: '1rem', fontWeight: '700' }}>{review.dish_name}</h3>
                <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(review.id)} style={{ opacity: 0.5 }}>🗑️</button>
              </div>
              {review.rating && (
                <div style={{
                  fontSize: '1.5rem',
                  fontWeight: '800',
                  color: getRatingColor(review.rating),
                  marginBottom: '8px',
                }}>
                  {review.rating}
                </div>
              )}
              {review.comment && (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', fontStyle: 'italic' }}>
                  &ldquo;{review.comment}&rdquo;
                </p>
              )}
              <div className="mt-8" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {review.member_name && <span>👤 {review.member_name} • </span>}
                {new Date(review.created_at).toLocaleDateString('vi-VN')}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Review Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">⭐ Thêm Review</div>
            <div className="form-group">
              <label className="form-label">Tên Món</label>
              <input
                type="text"
                className="form-input"
                placeholder="VD: Cơm gà phi lê"
                value={dishName}
                onChange={(e) => setDishName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Đánh giá</label>
              <input
                type="text"
                className="form-input"
                placeholder="VD: 8/10"
                value={rating}
                onChange={(e) => setRating(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Nhận xét</label>
              <textarea
                className="form-textarea"
                placeholder="VD: Ngon, thịt mềm, nước sốt đậm đà..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Người review (tùy chọn)</label>
              <select className="form-select" value={selectedMember} onChange={(e) => setSelectedMember(e.target.value)}>
                <option value="">-- Ẩn danh --</option>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Hủy</button>
              <button className="btn btn-primary" onClick={handleSubmit}>Thêm Review</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
