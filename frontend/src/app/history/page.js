'use client';

import { useState, useEffect, useCallback } from 'react';
import { ordersAPI, formatMoney } from '@/lib/api';
import Link from 'next/link';

const MONTHS_VI = ['', 'Th1', 'Th2', 'Th3', 'Th4', 'Th5', 'Th6', 'Th7', 'Th8', 'Th9', 'Th10', 'Th11', 'Th12'];

export default function HistoryPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchOrders = useCallback(async () => {
    try {
      const data = await ordersAPI.list({ limit: 100 });
      setOrders(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  if (loading) {
    return <div className="loading-spinner"><div className="spinner" /></div>;
  }

  // Group by month
  const grouped = {};
  orders.forEach((order) => {
    const d = new Date(order.order_date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(order);
  });

  const totalSpent = orders
    .filter((o) => o.status === 'finalized')
    .reduce((sum, o) => sum + (o.total_bill || 0) + (o.total_bill_chay || 0), 0);

  const finalizedCount = orders.filter((o) => o.status === 'finalized').length;

  return (
    <>
      <div className="page-header">
        <h1>📋 Lịch Sử Order</h1>
        <p>Tất cả orders đã đặt</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon orange">📦</div>
          <div className="stat-info">
            <h3>{orders.length}</h3>
            <p>Tổng orders</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green">✅</div>
          <div className="stat-info">
            <h3>{finalizedCount}</h3>
            <p>Đã chốt</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon blue">💰</div>
          <div className="stat-info">
            <h3>{formatMoney(totalSpent)}</h3>
            <p>Tổng chi</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon yellow">📊</div>
          <div className="stat-info">
            <h3>{finalizedCount > 0 ? formatMoney(Math.round(totalSpent / finalizedCount)) : '0'}</h3>
            <p>Trung bình/ngày</p>
          </div>
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>Chưa có order nào</h3>
          <p>Tạo order đầu tiên từ trang chủ!</p>
          <Link href="/" className="btn btn-primary mt-24">← Trang chủ</Link>
        </div>
      ) : (
        Object.entries(grouped).map(([monthKey, monthOrders]) => {
          const [year, month] = monthKey.split('-');
          return (
            <div key={monthKey} className="mb-24">
              <div className="card-title mb-16" style={{ fontSize: '1rem' }}>
                📅 Tháng {parseInt(month)}/{year}
                <span className="text-muted" style={{ fontWeight: '400', fontSize: '0.85rem', marginLeft: '8px' }}>
                  ({monthOrders.length} orders)
                </span>
              </div>
              <div className="history-list">
                {monthOrders.map((order) => {
                  const d = new Date(order.order_date);
                  const day = d.getDate();
                  const month = MONTHS_VI[d.getMonth() + 1];
                  const totalPeople = (order.eater_count || 0) + (order.chay_eater_count || 0);
                  const totalBill = (order.total_bill || 0) + (order.total_bill_chay || 0);

                  return (
                    <Link href={`/order/${order.id}`} key={order.id} className="history-card">
                      <div className="date-badge">
                        <span className="day">{day}</span>
                        <span className="month">{month}</span>
                      </div>
                      <div className="history-info">
                        <h4>
                          {totalPeople} người ăn
                          {order.chay_eater_count > 0 && ` (${order.chay_eater_count} chay)`}
                        </h4>
                        <p>
                          <span className={`badge badge-${order.status}`} style={{ fontSize: '0.65rem' }}>
                            {order.status === 'open' ? 'Đang mở' : order.status === 'locked' ? 'Đã khóa' : 'Đã chốt'}
                          </span>
                        </p>
                      </div>
                      <div className="history-cost">
                        {order.status === 'finalized' ? formatMoney(totalBill) : '—'}
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })
      )}
    </>
  );
}
