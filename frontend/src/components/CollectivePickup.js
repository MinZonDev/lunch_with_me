'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { collectivePickupAPI } from '@/lib/api';
import { isAdmin } from '@/lib/auth';
import PickupWheel from './PickupWheel';

const LABELS = { random: 'Đang quay', ready: 'Chờ admin chốt', finalized: 'Đã chốt', cancelled: 'Đã hủy' };

export default function CollectivePickup({ order, currentMemberId, onChanged, addToast, onMethod }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [busy, setBusy] = useState(false), [wheel, setWheel] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const history = historyData?.orderId === order.id ? historyData.items : null;
  const locked = useRef(false);
  const admin = isAdmin();
  const refresh = useCallback(async () => {
    const next = await collectivePickupAPI.get(order.id);
    setData(next); setError(''); onMethod(next.method);
    return next;
  }, [order.id, onMethod]);
  useEffect(() => {
    let active = true, fetching = false;
    const load = async () => {
      if (fetching) return;
      fetching = true;
      try {
        const next = await collectivePickupAPI.get(order.id);
        if (active) { setData(next); setError(''); onMethod(next.method); }
      } catch (err) { if (active) setError(err.message); }
      finally { fetching = false; }
    };
    load(); const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [order.id, onMethod]);
  const session = data?.session;
  const sessionId = session?.id;
  useEffect(() => {
    let active = true;
    collectivePickupAPI.history(order.id)
      .then(items => { if (active) setHistoryData({ orderId: order.id, items }); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [order.id, sessionId]);
  const mine = session?.votes[String(currentMemberId)];
  const skipped = session?.skipped.includes(currentMemberId);
  const participant = session?.participants.some(p => p.id === currentMemberId);
  const completed = session ? Object.keys(session.votes).length + session.skipped.length : 0;
  const progress = session?.participants.length ? completed / session.participants.length * 100 : 0;
  const action = async (name, message) => {
    if (locked.current || (message && !confirm(message))) return;
    locked.current = true; setBusy(true);
    try {
      if (name === 'open') await collectivePickupAPI.open(order.id);
      else await collectivePickupAPI.action(order.id, session.id, name);
      await refresh(); onChanged();
    } catch (err) { addToast(err.message, 'error'); }
    finally { locked.current = false; setBusy(false); }
  };
  const spin = async () => {
    const result = await collectivePickupAPI.action(order.id, session.id, 'spin');
    // Keep this wheel mounted while the saved result is animated.
    return result.participants.find(p => p.id === result.votes[String(currentMemberId)]);
  };
  const event = session?.status === 'finalized' ? 'result' : session?.status === 'cancelled' ? 'cancel' : 'invite';
  return <>
    {error && <div className="card mb-16" role="alert">{error} <button className="btn btn-secondary btn-sm" onClick={() => refresh().catch(e => setError(e.message))}>Thử lại</button></div>}
    {admin && data && (!session || session.status === 'cancelled') && <div className="card mb-16 pickup-method">
      <div className="method-info">
        <span className="method-icon" aria-hidden="true">{data.method === 'legacy' ? '🥡' : '🎡'}</span>
        <div className="method-copy">
          <p className="method-label">Hình thức random người lấy cơm</p>
          <div className="method-heading">
            <h3>{data.method === 'legacy' ? 'Admin random' : 'Random tập thể'}</h3>
            <span className={`method-badge ${data.method === 'legacy' ? 'active' : 'cancelled'}`}>
              <span aria-hidden="true" />{data.method === 'legacy' ? 'Đang áp dụng' : 'Phiên đã hủy'}
            </span>
          </div>
          <p className="method-description">{data.method === 'legacy'
            ? 'Admin hoặc người đặt cơm random trực tiếp người đi lấy cơm.'
            : 'Mở phiên mới để mọi người cùng quay chọn người lấy cơm.'}</p>
        </div>
      </div>
      <div className="method-actions">
        <button className="btn btn-primary method-start" disabled={busy} onClick={() => action('open', 'Chốt danh sách người đăng ký ăn hiện tại và mở phiên random tập thể?')}>
          <span aria-hidden="true">🎡</span>{busy ? 'Đang xử lý…' : 'Bắt đầu random tập thể'}<span className="method-arrow" aria-hidden="true">→</span>
        </button>
        {data.method === 'collective' && <button className="btn cancel-outline" disabled={busy} onClick={() => action('legacy', 'Đổi sang admin random?')}>Đổi sang admin random</button>}
      </div>
    </div>}
    {session && data.method === 'collective' && <section className="card mb-16 collective-session" aria-label="Tiến độ random người lấy cơm">
      <div className="session-header">
        <div className="session-title"><span className="session-icon" aria-hidden="true">🎡</span><div><p className="session-eyebrow">NGƯỜI LẤY CƠM</p><h3>Random tập thể</h3></div></div>
        <span className={`session-status status-${session.status}`}><span aria-hidden="true" />{LABELS[session.status]}</span>
      </div>
      {session.status === 'cancelled' && <p className="cancelled-notice">Phiên này đã hủy. Kết quả dưới đây chỉ là lịch sử.</p>}
      <div className="session-stats">
        <div><span>Tham gia</span><strong>{session.participants.length}<small>người</small></strong></div>
        <div><span>Đã quay</span><strong className="stat-spun">{Object.keys(session.votes).length}<small>người</small></strong></div>
        <div><span>Bỏ lượt</span><strong>{session.skipped.length}<small>người</small></strong></div>
      </div>
      <div className="session-progress"><span>Tiến độ tham gia</span><span>{completed}/{session.participants.length} hoàn tất</span></div>
      <div className="progress-track" role="progressbar" aria-label="Tiến độ tham gia" aria-valuenow={completed} aria-valuemin={0} aria-valuemax={session.participants.length || 1}><div style={{ width: `${progress}%` }} /></div>
      <div className="session-table-wrap"><table className="table session-table"><thead><tr><th>Thành viên</th><th>Trạng thái / Quay trúng</th><th>Số lượt bị quay trúng</th></tr></thead><tbody>
        {session.participants.map(p => {
          const target = session.participants.find(t => t.id === session.votes[String(p.id)]);
          const hasSkipped = session.skipped.includes(p.id);
          const hits = session.scores[String(p.id)];
          return <tr key={p.id} className={p.id === currentMemberId ? 'my-row' : ''}>
            <td><div className="member-cell"><span className="member-avatar" aria-hidden="true">{p.name.trim().charAt(0).toUpperCase()}</span><span className="member-name">{p.name}{p.id === currentMemberId && <small>Bạn</small>}</span></div></td>
            <td><div className="turn-cell"><span className={`turn-status ${target ? 'turn-done' : hasSkipped ? 'turn-skipped' : 'turn-waiting'}`}><span aria-hidden="true">{target ? '✓' : hasSkipped ? '−' : '○'}</span>{target ? 'Đã quay' : hasSkipped ? 'Đã bỏ lượt' : 'Chưa quay'}</span>{target && <span className="turn-target"><span aria-hidden="true">→</span> {target.name}</span>}</div></td>
            <td><span className={`hit-count ${hits > 0 ? 'has-hits' : ''}`}>{hits}</span></td>
          </tr>;
        })}
      </tbody></table></div>
      {session.status === 'finalized' && <p className="session-result" role="status">🥡 Người lấy cơm: <strong>{session.participants.filter(p => session.selected_ids.includes(p.id)).map(p => p.name).join(', ')}</strong></p>}
      <div className="session-actions">
        {participant && !mine && !skipped && session.status === 'random' && <>
          <button className="btn btn-primary" disabled={busy} onClick={() => setWheel(true)}>🎡 Mở vòng quay</button>
          <button className="btn btn-secondary" disabled={busy} onClick={() => action('skip', 'Bỏ lượt duy nhất của bạn? Bạn vẫn có thể bị người khác quay trúng.')}>Không muốn quay</button>
        </>}
        {mine && session.status !== 'cancelled' && <button className="btn btn-secondary" onClick={() => setWheel(true)}>Xem kết quả của tôi</button>}
        {admin && ['random', 'ready'].includes(session.status) && <button className="btn btn-primary" disabled={busy || !Object.keys(session.votes).length} onClick={() => action('finalize', 'Chốt người lấy cơm theo số lượt bị quay trúng? Các lượt chưa dùng sẽ bị khóa; cùng số lượt sẽ được random.')}>Chốt kết quả</button>}
        {admin && session.status !== 'cancelled' && <>
          <button className="btn session-cancel" disabled={busy} onClick={() => action('cancel', 'Hủy phiên và phân công hiện tại?')}>Hủy phiên</button>
          <button className="btn cancel-outline" disabled={busy} onClick={() => action('legacy', 'Hủy phiên và đổi sang admin random?')}>Đổi sang admin random</button>
        </>}
        {admin && <button className="btn btn-ghost btn-sm" disabled={busy} onClick={async () => {
          try { await collectivePickupAPI.retry(order.id, session.id, event); addToast('Đã yêu cầu thử gửi các email chưa thành công'); } catch (err) { addToast(err.message, 'error'); }
        }}>Thử gửi thông báo còn lỗi</button>}
      </div>
      {admin && session.notifications && <p className="session-email">Email: {Object.values(session.notifications).filter(n => n.status === 'sent').length} đã gửi · {Object.values(session.notifications).filter(n => n.status === 'failed').length} lỗi · {Object.values(session.notifications).filter(n => n.status === 'skipped').length} bỏ qua (chưa cấu hình SMTP)</p>}
    </section>}
    {data && history?.length >= 2 && <details className="session-history mb-16" onToggle={async e => {
      if (!e.currentTarget.open) return;
      try { setHistoryData({ orderId: order.id, items: await collectivePickupAPI.history(order.id) }); }
      catch (err) { setError(err.message); }
    }}>
      <summary className="history-summary">
        <span className="history-icon" aria-hidden="true">↺</span>
        <span className="history-heading"><strong>Lịch sử phiên tập thể</strong><span>Xem lại các phiên và kết quả phân công</span></span>
        <span className="history-chevron" aria-hidden="true">⌄</span>
      </summary>
      <div className="history-content">
        {history === null ? <p className="history-empty" role="status">Đang tải lịch sử…</p> : !history.length ? <p className="history-empty">Chưa có phiên tập thể.</p> : history.map(entry => {
          const s = entry.id === session?.id ? session : entry;
          return <article className={`history-entry ${s.status === 'cancelled' ? 'history-entry-cancelled' : ''}`} key={s.id}>
            <div className="history-entry-top">
              <time dateTime={s.created_at}>{new Date(s.created_at).toLocaleDateString('vi-VN')}<span className="history-time">{new Date(s.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span></time>
              <span className={`session-status status-${s.status}`}><span aria-hidden="true" />{LABELS[s.status]}</span>
            </div>
            <div className="history-meta"><span><strong>{s.participants.length}</strong> người tham gia</span><span><strong>{Object.keys(s.votes).length}</strong> đã quay</span><span><strong>{s.skipped.length}</strong> bỏ lượt</span></div>
            {s.selected_ids.length > 0 && <div className={`history-result ${s.status === 'cancelled' ? 'history-result-cancelled' : ''}`}><span aria-hidden="true">🥡</span><div><span>{s.status === 'cancelled' ? 'Phân công đã hủy' : 'Người được chọn'}</span><strong>{s.participants.filter(p => s.selected_ids.includes(p.id)).map(p => p.name).join(', ')}</strong></div></div>}
          </article>;
        })}
      </div>
    </details>}
    {wheel && session && session.status !== 'cancelled' && <PickupWheel participants={session.participants} savedResult={mine ? session.participants.find(p => p.id === mine) : null}
      onSpin={spin} onClose={() => { setWheel(false); refresh().catch(e => setError(e.message)); }} />}
    <style jsx>{`
      .session-history { border: 1px solid rgba(255, 255, 255, .075); border-radius: 16px; background: var(--bg-card, #1a1a2e); overflow: hidden; }
      .history-summary { display: flex; align-items: center; gap: 12px; padding: 18px 22px; cursor: pointer; list-style: none; }
      .history-summary::-webkit-details-marker { display: none; }
      .history-summary:hover { background: rgba(255, 255, 255, .025); }
      .history-summary:focus-visible { outline: 2px solid var(--accent-primary, #ff8c42); outline-offset: -3px; border-radius: 14px; }
      .history-icon { display: grid; place-items: center; flex-shrink: 0; width: 36px; height: 36px; border-radius: 11px; background: rgba(167, 139, 250, .09); color: #c6b8f2; font-size: 24px; }
      .history-heading { display: flex; flex-direction: column; gap: 5px; flex: 1; min-width: 0; }
      .history-heading strong { font-size: .87rem; font-weight: 600; }
      .history-heading > span { color: var(--text-secondary, #a0a0b8); font-size: .72rem; line-height: 1.5; }
      .history-chevron { color: var(--text-secondary, #a0a0b8); font-size: 20px; }
      .session-history[open] .history-chevron { transform: rotate(180deg); }
      .history-content { display: grid; gap: 10px; padding: 0 22px 20px; }
      .history-empty { padding: 20px; margin: 0; border-radius: 12px; background: rgba(0, 0, 0, .1); color: var(--text-secondary, #a0a0b8); text-align: center; font-size: .8rem; }
      .history-entry { padding: 16px 18px; border: 1px solid rgba(255, 255, 255, .055); border-left: 2px solid rgba(167, 139, 250, .4); border-radius: 12px; background: rgba(0, 0, 0, .1); }
      .history-entry-top { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
      .history-entry time { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; font-weight: 600; font-size: .82rem; font-variant-numeric: tabular-nums; }
      .history-time { color: var(--text-secondary, #a0a0b8); font-size: .74rem; font-weight: 400; }
      .history-meta { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 12px; font-size: .74rem; color: var(--text-secondary, #a0a0b8); }
      .history-meta strong { color: var(--text-primary, #f0f0f5); font-weight: 600; }
      .history-result { display: flex; align-items: center; gap: 10px; padding-top: 12px; margin-top: 14px; border-top: 1px solid rgba(255, 255, 255, .06); }
      .history-result > span { font-size: 22px; }
      .history-result > div { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
      .history-result div > span { font-size: .68rem; color: var(--text-secondary, #a0a0b8); }
      .history-result strong { color: #8be3c4; font-size: .83rem; overflow-wrap: anywhere; }
      .history-entry-cancelled { border-left-color: #f87171; }
      .history-result-cancelled strong, .history-result-cancelled div > span { color: #fca5a5; }
      @media (max-width: 480px) { .history-summary { padding: 16px; } .history-content { padding: 0 14px 14px; } .history-entry { padding: 14px; } }
      .collective-session { padding: 24px; border: 1px solid rgba(255, 255, 255, .08); background: radial-gradient(ellipse at top left, rgba(255, 140, 66, .045), transparent 65%), var(--bg-card, #1a1a2e); }
      .session-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 22px; }
      .session-title { display: flex; align-items: center; gap: 12px; }
      .session-icon { display: grid; place-items: center; width: 46px; height: 46px; border-radius: 14px; font-size: 25px; background: rgba(255, 140, 66, .1); border: 1px solid rgba(255, 140, 66, .13); }
      .session-eyebrow { margin: 0 0 5px; color: var(--text-secondary, #a0a0b8); font-size: .62rem; letter-spacing: .12em; font-weight: 600; }
      .session-title h3 { margin: 0; font-size: 1.15rem; line-height: 1.3; }
      .session-status { display: inline-flex; align-items: center; gap: 7px; padding: 7px 11px; font-size: .75rem; font-weight: 600; border-radius: 100px; background: rgba(255, 140, 66, .1); color: #ffb47d; }
      .session-status > span { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
      .status-ready, .status-finalized { background: rgba(100, 220, 180, .1); color: #64dcb4; }
      .status-cancelled, .method-badge.cancelled { background: rgba(248, 113, 113, .1); color: #fca5a5; }
      .cancelled-notice { padding: 12px 14px; border: 1px solid rgba(248, 113, 113, .2); border-radius: 10px; background: rgba(248, 113, 113, .07); color: #fca5a5; font-size: .82rem; line-height: 1.6; }
      .session-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
      .session-stats > div { padding: 14px 16px; border: 1px solid rgba(255, 255, 255, .055); border-radius: 12px; background: rgba(0, 0, 0, .12); }
      .session-stats > div > span { display: block; font-size: .74rem; color: var(--text-secondary, #a0a0b8); margin-bottom: 7px; }
      .session-stats strong { font-size: 1.55rem; line-height: 1.2; font-variant-numeric: tabular-nums; }
      .session-stats small { margin-left: 7px; font-size: .72rem; font-weight: 400; color: var(--text-secondary, #a0a0b8); }
      .stat-spun { color: #64dcb4; }
      .session-progress { display: flex; justify-content: space-between; gap: 8px; font-size: .72rem; color: var(--text-secondary, #a0a0b8); margin-bottom: 8px; }
      .progress-track { height: 5px; background: rgba(255, 255, 255, .07); border-radius: 10px; overflow: hidden; margin-bottom: 22px; }
      .progress-track > div { height: 100%; background: var(--accent-primary, #ff8c42); border-radius: inherit; }
      .session-table-wrap { overflow-x: auto; border: 1px solid rgba(255, 255, 255, .06); border-radius: 14px; }
      .session-table { margin: 0; width: 100%; }
      .session-table th { padding: 13px 16px; font-size: .68rem; letter-spacing: .035em; color: var(--text-secondary, #a0a0b8); background: rgba(0, 0, 0, .18); }
      .session-table td { padding: 15px 16px; font-size: .85rem; vertical-align: middle; }
      .session-table th:last-child, .session-table td:last-child { text-align: center; width: 180px; }
      .session-table tr:last-child td { border-bottom: 0; }
      .my-row { background: rgba(255, 140, 66, .035); }
      .member-cell { display: flex; align-items: center; gap: 10px; }
      .member-avatar { display: grid; place-items: center; width: 34px; height: 34px; flex-shrink: 0; border-radius: 11px; color: #c6b8f2; background: rgba(167, 139, 250, .12); font-weight: 600; font-size: .78rem; }
      .member-name { overflow-wrap: anywhere; font-weight: 500; }
      .member-name small { display: inline-block; margin-left: 7px; padding: 2px 6px; color: #ffb47d; background: rgba(255, 140, 66, .1); border-radius: 5px; font-size: .62rem; }
      .turn-cell { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
      .turn-status { display: inline-flex; align-items: center; gap: 5px; padding: 4px 8px; border-radius: 6px; font-size: .72rem; white-space: nowrap; }
      .turn-waiting { color: var(--text-secondary, #a0a0b8); background: rgba(255, 255, 255, .045); }
      .turn-done { color: #64dcb4; background: rgba(100, 220, 180, .08); }
      .turn-skipped { color: #e6bd78; background: rgba(230, 189, 120, .08); }
      .turn-target { font-size: .8rem; overflow-wrap: anywhere; }
      .turn-target > span { color: var(--text-secondary, #a0a0b8); margin-right: 4px; }
      .hit-count { display: inline-grid; place-items: center; min-width: 34px; height: 30px; padding: 0 7px; box-sizing: border-box; border-radius: 8px; font-size: .9rem; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--text-secondary, #a0a0b8); background: rgba(255, 255, 255, .035); }
      .has-hits { color: #ffb47d; background: rgba(255, 140, 66, .12); }
      .session-result { padding: 14px 16px; border-radius: 12px; background: rgba(100, 220, 180, .08); border: 1px solid rgba(100, 220, 180, .15); line-height: 1.6; }
      .session-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 22px; padding-top: 18px; border-top: 1px solid rgba(255, 255, 255, .065); }
      .session-actions .btn { min-height: 40px; border-radius: 10px; font-size: .8rem; }
      .session-cancel { background: #b52d43; color: #fff; border: 1px solid #dc4960; }
      .session-cancel:hover:not(:disabled) { background: #cf3550; border-color: #f0798c; }
      .session-cancel:focus-visible { outline: 2px solid #fda4af; outline-offset: 3px; }
      .cancel-outline { color: #fca5a5; background: rgba(248, 113, 113, .07); border: 1px solid rgba(248, 113, 113, .3); }
      .cancel-outline:hover:not(:disabled) { color: #fecaca; background: rgba(248, 113, 113, .14); border-color: #f87171; }
      .cancel-outline:focus-visible { outline: 2px solid #fca5a5; outline-offset: 3px; }
      .session-email { margin: 12px 0 0; color: var(--text-secondary, #a0a0b8); font-size: .7rem; line-height: 1.6; }
      @media (max-width: 600px) { .collective-session { padding: 16px; } .session-stats { gap: 7px; } .session-stats > div { padding: 12px 10px; } .session-stats strong { font-size: 1.3rem; } .session-stats small { display: block; margin: 4px 0 0; } .session-table th, .session-table td { padding: 12px 10px; } .session-table th:last-child, .session-table td:last-child { width: 100px; } .member-avatar { display: none; } .session-actions { gap: 8px; } .session-actions .btn { flex: 1 1 auto; } }
      .pickup-method { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 24px; border: 1px solid rgba(255, 140, 66, .16); background: radial-gradient(ellipse at top left, rgba(255, 140, 66, .07), transparent 65%), var(--bg-card, #1a1a2e); }
      .method-info { display: flex; align-items: center; gap: 16px; min-width: 0; }
      .method-icon { display: grid; place-items: center; width: 56px; height: 56px; flex-shrink: 0; border-radius: 16px; font-size: 28px; background: rgba(255, 140, 66, .1); border: 1px solid rgba(255, 140, 66, .16); }
      .method-copy { min-width: 0; }
      .method-label { margin: 0 0 7px; color: var(--text-secondary, #a0a0b8); font-size: .78rem; font-weight: 500; }
      .method-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
      .method-heading h3 { margin: 0; font-size: 1.15rem; font-weight: 700; line-height: 1.4; }
      .method-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 9px; border-radius: 100px; color: var(--text-secondary, #a0a0b8); background: rgba(255, 255, 255, .05); font-size: .68rem; font-weight: 600; white-space: nowrap; }
      .method-badge span { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
      .method-badge.active { color: #64dcb4; background: rgba(100, 220, 180, .08); }
      .method-description { margin: 7px 0 0; color: var(--text-secondary, #a0a0b8); font-size: .8rem; line-height: 1.6; }
      .method-actions { display: flex; flex-direction: column; gap: 8px; flex-shrink: 0; }
      .method-start { min-height: 44px; gap: 10px; padding: 12px 18px; border-radius: 12px; white-space: nowrap; }
      .method-arrow { margin-left: 6px; }
      @media (max-width: 800px) { .pickup-method { align-items: stretch; flex-direction: column; gap: 20px; } .method-actions { align-self: flex-start; } }
      @media (max-width: 480px) { .pickup-method { padding: 18px; } .method-info { align-items: flex-start; gap: 12px; } .method-icon { width: 44px; height: 44px; border-radius: 13px; font-size: 24px; } .method-heading h3 { font-size: 1.05rem; } .method-actions { align-self: stretch; } .method-start { justify-content: center; white-space: normal; } }
    `}</style>
  </>;
}
