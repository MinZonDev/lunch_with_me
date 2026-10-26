from fastapi import APIRouter, BackgroundTasks, Depends
from app.core.auth import get_current_user, get_current_admin
from app.database import get_db
from app.collective_schemas import PickupSession, PickupState
from app.services import collective_pickup as service

router = APIRouter(prefix='/api/orders/{order_id}/collective-pickup', tags=['collective pickup'])


@router.get('', response_model=PickupState, response_model_exclude_none=True)
def get_session(order_id: int, background: BackgroundTasks,
                db=Depends(get_db), user=Depends(get_current_user)):
    result = service.get(db, order_id)
    if result.pop('_auto_finalized', False):
        background.add_task(service.notify, db, result['session']['id'], 'result')
    if result['session'] and user.role != 'admin':
        result['session'].pop('notifications', None)
    return result


@router.get('/history', response_model=list[PickupSession], response_model_exclude_none=True)
def history(order_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    service.require_order(db, order_id)
    sessions = [service.view(s.to_dict()) for s in db.collection('pickup_sessions')
                .where('order_id', '==', order_id).stream()]
    for state in sessions:
        if user.role != 'admin':
            state.pop('notifications', None)
    return sorted(sessions, key=lambda s: s['created_at'], reverse=True)


@router.post('', response_model=PickupSession, response_model_exclude_none=True)
def open_session(order_id: int, background: BackgroundTasks, db=Depends(get_db),
                 user=Depends(get_current_admin)):
    result = service.open_session(db, order_id, user.id)
    background.add_task(service.notify, db, result['id'], 'invite')
    return result


@router.post('/{session_id}/spin', response_model=PickupSession, response_model_exclude_none=True)
def spin(order_id: int, session_id: str, background: BackgroundTasks,
         db=Depends(get_db), user=Depends(get_current_user)):
    result = service.transition(db, order_id, session_id, 'spin', user.id, getattr(user, 'member_id', None))
    if result['status'] == 'finalized':
        background.add_task(service.notify, db, session_id, 'result')
    if user.role != 'admin':
        result.pop('notifications', None)
    return result


@router.post('/{session_id}/skip', response_model=PickupSession, response_model_exclude_none=True)
def skip(order_id: int, session_id: str, background: BackgroundTasks,
         db=Depends(get_db), user=Depends(get_current_user)):
    result = service.transition(db, order_id, session_id, 'skip', user.id, getattr(user, 'member_id', None))
    if result['status'] == 'finalized':
        background.add_task(service.notify, db, session_id, 'result')
    if user.role != 'admin':
        result.pop('notifications', None)
    return result


@router.post('/{session_id}/{action}', response_model=PickupSession, response_model_exclude_none=True)
def manage(order_id: int, session_id: str, action: str, background: BackgroundTasks,
           db=Depends(get_db), user=Depends(get_current_admin)):
    result = service.transition(db, order_id, session_id, action, user.id)
    if action in ('finalize', 'cancel', 'legacy'):
        background.add_task(service.notify, db, session_id, 'result' if action == 'finalize' else 'cancel')
    return result


@router.post('/{session_id}/notifications/{event}')
def retry_notifications(order_id: int, session_id: str, event: str, background: BackgroundTasks,
                        db=Depends(get_db), user=Depends(get_current_admin)):
    from fastapi import HTTPException
    state = service.get(db, order_id)['session']
    if not state or state['id'] != session_id:
        raise HTTPException(404, 'Không tìm thấy phiên hiện tại')
    allowed = {'invite': ('random', 'ready'), 'result': ('finalized',), 'cancel': ('cancelled',)}
    if state['status'] not in allowed.get(event, ()):
        raise HTTPException(409, 'Thông báo không phù hợp với trạng thái phiên')
    background.add_task(service.notify, db, session_id, event)
    return {'status': 'queued'}
