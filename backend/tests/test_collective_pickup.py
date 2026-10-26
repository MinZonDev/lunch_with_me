import random
from datetime import datetime, timezone

import pytest
from app.services import collective_pickup as service, pickup
from tests.conftest import auth_headers, seed_member, seed_user


@pytest.fixture
def session_order(db, admin):
    db.collection('daily_orders').document('90').set({
        'id': 90, 'pickup_count': 2, 'order_date': '2026-07-10',
        'order_deadline': datetime(2026, 7, 10, 3, tzinfo=timezone.utc)})
    for mid in (2, 3, 4):
        seed_member(db, mid, f'Person {mid}')
        seed_user(db, mid, f'user{mid}', member_id=mid)
        db.collection('order_items').document(str(mid)).set({
            'member_id': mid, 'daily_order_id': 90, 'is_eating': True})
    return service.open_session(db, 90, 1)


def test_one_turn_retry_and_auto_finalize(db, session_order):
    sid = session_order['id']
    first = service.transition(db, 90, sid, 'spin', 2, 2, random.Random(4))
    retry = service.transition(db, 90, sid, 'spin', 2, 2, random.Random(1))
    assert retry['votes'] == first['votes']
    assert len(retry['votes']) == 1
    with pytest.raises(Exception) as error:
        service.transition(db, 90, sid, 'skip', 2, 2)
    assert error.value.status_code == 409
    service.transition(db, 90, sid, 'skip', 3, 3)
    with pytest.raises(Exception) as error:
        service.transition(db, 90, sid, 'spin', 3, 3)
    assert error.value.status_code == 409
    result = service.transition(db, 90, sid, 'spin', 4, 4)
    assert result['status'] == 'finalized'
    assert result['finalized_by'] is None
    assert len(result['selected_ids']) == 2
    assert sum(result['scores'].values()) == 2
    order = db.collection('daily_orders').document('90').get().to_dict()
    assert order['pickup_member_ids'] == result['selected_ids']


def test_all_skipped_still_auto_finalizes(db, session_order):
    sid = session_order['id']
    service.transition(db, 90, sid, 'skip', 2, 2)
    service.transition(db, 90, sid, 'skip', 3, 3)
    result = service.transition(db, 90, sid, 'skip', 4, 4, random.Random(3))
    assert result['status'] == 'finalized'
    assert result['votes'] == {}
    assert len(result['selected_ids']) == 2
    assert set(result['selected_ids']).issubset({2, 3, 4})


def test_last_turn_queues_result_email(client, db, session_order, monkeypatch):
    sid = session_order['id']
    calls = []
    monkeypatch.setattr(service, 'notify', lambda *args: calls.append(args))
    base = f'/api/orders/90/collective-pickup/{sid}'
    assert client.post(base + '/spin', headers=auth_headers(2)).status_code == 200
    assert client.post(base + '/skip', headers=auth_headers(3)).status_code == 200
    response = client.post(base + '/skip', headers=auth_headers(4))
    assert response.status_code == 200
    assert response.json()['status'] == 'finalized'
    assert calls == [(db, sid, 'result')]


def test_get_reconciles_completed_ready_session(client, db, session_order, monkeypatch):
    sid = session_order['id']
    ref = service.session_ref(db, sid)
    state = ref.get().to_dict()
    state.update(votes={'2': 3, '3': 3, '4': 2}, status='ready')
    ref.set(state)
    calls = []
    monkeypatch.setattr(service, 'notify', lambda *args: calls.append(args))

    response = client.get('/api/orders/90/collective-pickup', headers=auth_headers(2))

    assert response.status_code == 200
    assert response.json()['session']['status'] == 'finalized'
    assert len(response.json()['session']['selected_ids']) == 2
    assert calls == [(db, sid, 'result')]
    order = db.collection('daily_orders').document('90').get().to_dict()
    assert order['pickup_member_ids'] == response.json()['session']['selected_ids']


def test_permissions_and_legacy_guard(client, db, session_order):
    sid = session_order['id']
    base = f'/api/orders/90/collective-pickup/{sid}'
    assert client.post(base + '/finalize', headers=auth_headers(2)).status_code == 403
    assert client.post(base + '/spin', headers=auth_headers(1)).status_code == 403
    assert client.post('/api/orders/90/collective-pickup', headers=auth_headers(2)).status_code == 403
    assert pickup.pick(db, db.collection('daily_orders').document('90'), reroll=True) is None
    assert pickup.run_due(db, datetime(2026, 7, 10, 5, tzinfo=timezone.utc)) == 0
    assert 'notifications' not in client.get('/api/orders/90/collective-pickup', headers=auth_headers(2)).json()['session']


def test_finalize_zero_fill_and_no_turns_after_close(db, session_order):
    sid = session_order['id']
    with pytest.raises(Exception) as error:
        service.transition(db, 90, sid, 'finalize', 1)
    assert error.value.status_code == 409
    result = service.transition(db, 90, sid, 'spin', 2, 2)
    winner = result['votes']['2']
    final = service.transition(db, 90, sid, 'finalize', 1)
    assert len(set(final['selected_ids'])) == 2
    assert winner in final['selected_ids']
    assert service.transition(db, 90, sid, 'finalize', 1)['selected_ids'] == final['selected_ids']
    with pytest.raises(Exception):
        service.transition(db, 90, sid, 'spin', 3, 3)
    assert db.collection('daily_orders').document('90').get().to_dict()['pickup_member_ids'] == final['selected_ids']


def test_cancel_history_new_session_and_return_to_legacy(db, session_order):
    sid = session_order['id']
    service.transition(db, 90, sid, 'spin', 2, 2)
    with pytest.raises(Exception):
        service.open_session(db, 90, 1)
    service.transition(db, 90, sid, 'cancel', 1)
    assert service.session_ref(db, sid).get().to_dict()['votes']
    new = service.open_session(db, 90, 1)
    assert new['id'] != sid and new['votes'] == {}
    with pytest.raises(Exception):
        service.transition(db, 90, sid, 'spin', 3, 3)
    service.transition(db, 90, new['id'], 'legacy', 1)
    assert service.get(db, 90)['method'] == 'legacy'
    assert pickup.pick(db, db.collection('daily_orders').document('90'), reroll=True)


def test_fixed_participants_and_self_pick(db, session_order):
    class SelfPicker:
        def choice(self, ids):
            return 2
    db.collection('order_items').document('4').delete()
    result = service.transition(db, 90, session_order['id'], 'spin', 2, 2, SelfPicker())
    assert len(result['participants']) == 3
    assert result['votes']['2'] == 2


def test_uniform_tie_breaks_and_caps_count(db, session_order):
    ref = service.session_ref(db, session_order['id'])
    original = ref.get().to_dict()
    original.update(votes={'2': 2, '3': 3, '4': 4}, status='ready')
    db.collection('daily_orders').document('90').update({'pickup_count': 1})
    winners = set()
    for seed in range(30):
        ref.set(original)
        result = service.transition(db, 90, original['id'], 'finalize', 1, rng=random.Random(seed))
        winners.update(result['selected_ids'])
    assert winners == {2, 3, 4}
    ref.set(original)
    db.collection('daily_orders').document('90').update({'pickup_count': 10})
    assert len(service.transition(db, 90, original['id'], 'finalize', 1)['selected_ids']) == 3


def test_email_failure_retry_and_success_not_repeated(db, session_order, monkeypatch):
    from app.services import email_service
    monkeypatch.setattr(email_service.settings, 'smtp_user', 'test')
    monkeypatch.setattr(email_service.settings, 'smtp_password', 'test')
    calls = []
    monkeypatch.setattr(email_service, '_send', lambda *args: calls.append(args) or False)
    service.notify(db, session_order['id'], 'invite')
    assert len(calls) == 3
    monkeypatch.setattr(email_service, '_send', lambda *args: calls.append(args) or True)
    service.notify(db, session_order['id'], 'invite')
    service.notify(db, session_order['id'], 'invite')
    assert len(calls) == 6


def test_api_lifecycle_history_and_notification_permissions(client, db, admin, session_order, monkeypatch):
    from app.services import email_service
    monkeypatch.setattr(email_service, '_send', lambda *args: True)
    base = '/api/orders/90/collective-pickup'
    sid = session_order['id']
    first = client.post(f'{base}/{sid}/spin', headers=auth_headers(2))
    assert first.status_code == 200
    assert first.json()['votes'] == client.post(f'{base}/{sid}/spin', headers=auth_headers(2)).json()['votes']
    assert client.post(f'{base}/{sid}/finalize', headers=admin['headers']).status_code == 200
    assert client.post(f'{base}/{sid}/notifications/result', headers=auth_headers(2)).status_code == 403
    assert client.post(f'{base}/{sid}/notifications/invite', headers=admin['headers']).status_code == 409
    assert client.post(f'{base}/{sid}/cancel', headers=admin['headers']).status_code == 200
    new = client.post(base, headers=admin['headers'])
    assert new.status_code == 200
    assert new.json()['id'] != sid
    history = client.get(base + '/history', headers=auth_headers(2)).json()
    assert len(history) == 2
    assert any(s['status'] == 'cancelled' and s['votes'] for s in history)
    assert all('notifications' not in s for s in history)
