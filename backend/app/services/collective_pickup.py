"""Free collective pickup sessions. All state transitions share the order lock."""
import random
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from firebase_admin import firestore

from app.services.pickup import _eater_ids


def now():
    return datetime.now(timezone.utc)


def session_ref(db, sid):
    return db.collection('pickup_sessions').document(sid)


def require_order(db, oid):
    ref = db.collection('daily_orders').document(str(oid))
    order = ref.get().to_dict()
    if not order:
        raise HTTPException(404, 'Order not found')
    return ref, order


def view(session):
    if not session:
        return None
    points = Counter(session['votes'].values())
    return {**session, 'scores': {str(p['id']): points.get(p['id'], 0)
                                for p in session['participants']}}


def get(db, oid):
    _, order = require_order(db, oid)
    sid = order.get('pickup_session_id')
    state = session_ref(db, sid).get().to_dict() if sid else None
    auto_finalized = False
    if state and state['status'] in ('random', 'ready'):
        completed = len(state['votes']) + len(state['skipped'])
        if completed == len(state['participants']):
            state = transition(db, oid, sid, 'auto_finalize', None)
            auto_finalized = state.pop('_auto_finalized', False)
    return {'method': order.get('pickup_method', 'legacy'),
            'session': view(state), '_auto_finalized': auto_finalized}


def open_session(db, oid, actor):
    ref, _ = require_order(db, oid)
    ids = _eater_ids(db, oid)
    if not ids:
        raise HTTPException(400, 'Chưa có người đăng ký ăn')
    participants = []
    for mid in ids:
        member = db.collection('members').document(str(mid)).get().to_dict() or {}
        participants.append({'id': mid, 'name': member.get('name', str(mid))})
    sid = uuid4().hex
    new = {'id': sid, 'order_id': oid, 'participants': participants,
           'votes': {}, 'skipped': [], 'status': 'random', 'selected_ids': [],
           'created_by': actor, 'created_at': now(), 'notifications': {}}

    @firestore.transactional
    def claim(tx):
        order = ref.get(transaction=tx).to_dict()
        if not order:
            raise HTTPException(404, 'Order not found')
        previous = order.get('pickup_session_id')
        if previous:
            old = session_ref(db, previous).get(transaction=tx).to_dict()
            if old and old['status'] != 'cancelled':
                raise HTTPException(409, 'Hãy hủy phiên hiện tại trước khi mở phiên mới')
        tx.set(session_ref(db, sid), new)
        tx.update(ref, {'pickup_method': 'collective', 'pickup_session_id': sid,
                        'pickup_member_ids': [], 'pickup_names': [], 'pickup_picked_at': None})
    claim(db.transaction())
    return view(new)


def transition(db, oid, sid, action, actor, member_id=None, rng=None):
    ref, _ = require_order(db, oid)
    sref = session_ref(db, sid)
    rng = rng or random.SystemRandom()

    @firestore.transactional
    def apply(tx):
        did_auto_finalize = False
        order = ref.get(transaction=tx).to_dict()
        if not order:
            raise HTTPException(404, 'Order not found')
        state = sref.get(transaction=tx).to_dict()
        if not state or state['order_id'] != oid:
            raise HTTPException(404, 'Không tìm thấy phiên')
        if order.get('pickup_session_id') != sid:
            raise HTTPException(409, 'Phiên đã được thay thế')
        if state['status'] == 'cancelled' and action not in ('cancel', 'legacy'):
            raise HTTPException(409, 'Phiên đã hủy')
        votes = dict(state['votes'])
        skipped = list(state['skipped'])
        ids = [p['id'] for p in state['participants']]
        key = str(member_id)

        def finalize(finalized_by):
            points = Counter(votes.values())
            groups = {}
            for mid in ids:
                groups.setdefault(points[mid], []).append(mid)
            ranked, audit = [], []
            for score in sorted(groups, reverse=True):
                group = groups[score][:]
                rng.shuffle(group)
                ranked.extend(group)
                audit.append({'score': score, 'random_order': group})
            chosen = ranked[:min(max(order.get('pickup_count') or 1, 1), len(ids))]
            names = {p['id']: p['name'] for p in state['participants']}
            state.update(status='finalized', selected_ids=chosen, ranking=audit,
                         finalized_at=now(), finalized_by=finalized_by)
            tx.update(ref, {'pickup_member_ids': chosen,
                            'pickup_names': [names[mid] for mid in chosen],
                            'pickup_picked_at': state['finalized_at']})

        if action in ('spin', 'skip'):
            if member_id not in ids:
                raise HTTPException(403, 'Bạn không thuộc danh sách tham gia phiên')
            # A repeated request returns the stored result, never creates another turn.
            if action == 'spin' and key in votes:
                return view(state)
            if action == 'skip' and member_id in skipped:
                return view(state)
            if state['status'] != 'random':
                raise HTTPException(409, 'Phiên không còn nhận lượt quay')
            if key in votes or member_id in skipped:
                raise HTTPException(409, 'Bạn đã sử dụng hoặc bỏ lượt')
            if action == 'spin':
                votes[key] = rng.choice(ids)
            else:
                skipped.append(member_id)
            state.update(votes=votes, skipped=skipped)
            if len(votes) + len(skipped) == len(ids):
                # The final participant completes the session. Finalize in this
                # transaction so a concurrent turn cannot slip in afterwards.
                finalize(None)
        elif action == 'auto_finalize':
            if state['status'] == 'finalized':
                return view(state)
            completed = len(votes) + len(skipped)
            if state['status'] not in ('random', 'ready') or completed != len(ids):
                raise HTTPException(409, 'Phiên chưa hoàn tất tất cả lượt')
            finalize(None)
            did_auto_finalize = True
        elif action == 'finalize':
            if state['status'] == 'finalized':
                return view(state)
            if state['status'] not in ('random', 'ready') or not votes:
                raise HTTPException(409, 'Cần ít nhất một kết quả quay để chốt')
            finalize(actor)
        elif action in ('cancel', 'legacy'):
            state.update(status='cancelled', cancelled_at=now(), cancelled_by=actor)
            tx.update(ref, {'pickup_method': 'legacy' if action == 'legacy' else 'collective',
                            'pickup_member_ids': [], 'pickup_names': [], 'pickup_picked_at': None})
        else:
            raise HTTPException(400, 'Thao tác không hợp lệ')
        tx.set(sref, state)
        result = view(state)
        if did_auto_finalize:
            result['_auto_finalized'] = True
        return result
    return apply(db.transaction())


def notify(db, sid, event):
    """Persist per-recipient delivery state; retry failures without resending successes."""
    import logging
    from html import escape
    from app.core.config import settings
    from app.services.email_service import _send
    ref = session_ref(db, sid)
    state = ref.get().to_dict()
    ids = {p['id'] for p in state['participants']}
    users = [s.to_dict() for s in db.collection('users').where('is_active', '==', True).stream()]
    labels = {'invite': 'Mời quay người lấy cơm', 'result': 'Kết quả người lấy cơm',
              'cancel': 'Đã hủy phiên người lấy cơm'}
    for user in users:
        if user.get('member_id') not in ids or not user.get('email'):
            continue
        key = f"{event}_{user['id']}"

        @firestore.transactional
        def claim(tx):
            current = ref.get(transaction=tx).to_dict()
            expected = {'invite': ('random', 'ready'), 'result': ('finalized',), 'cancel': ('cancelled',)}
            if current['status'] not in expected.get(event, ()):
                return False
            notifications = dict(current.get('notifications', {}))
            prior = notifications.get(key, {})
            if prior.get('status') in ('sent', 'skipped'):
                return False
            started = prior.get('started_at')
            if prior.get('status') == 'sending' and started and (now() - started).total_seconds() < 120:
                return False
            notifications[key] = {'status': 'sending', 'started_at': now()}
            tx.update(ref, {'notifications': notifications})
            return True
        if not claim(db.transaction()):
            continue
        names = ', '.join(p['name'] for p in state['participants'] if p['id'] in state['selected_ids'])
        body = (f'<p>{escape(labels[event])}</p><p>{escape(names) if event == "result" else ""}</p>'
                f'<a href="{escape(settings.frontend_url, quote=True)}/order/{state["order_id"]}">Xem order</a>')
        try:
            status = 'skipped' if not settings.smtp_user or not settings.smtp_password else (
                'sent' if _send(user['email'], labels[event], body) else 'failed')
        except Exception:
            logging.getLogger(__name__).exception('Collective pickup email failed')
            status = 'failed'

        @firestore.transactional
        def complete(tx):
            current = ref.get(transaction=tx).to_dict()
            notifications = dict(current.get('notifications', {}))
            notifications[key] = {'status': status, 'updated_at': now()}
            tx.update(ref, {'notifications': notifications})
        complete(db.transaction())
