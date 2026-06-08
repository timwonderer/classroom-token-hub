def TeacherBlock(**kwargs):
    from app.models import Seat
    from datetime import datetime, timezone

    supported_keys = ['class_id', 'join_code', 'block', 'block_identifier', 'role', 'claimed_at', 'student_id']
    seat_kwargs = {k: v for k, v in kwargs.items() if k in supported_keys}
    
    if 'role' not in seat_kwargs:
        seat_kwargs['role'] = 'student'
    if 'block' in kwargs and 'block_identifier' not in seat_kwargs:
        seat_kwargs['block_identifier'] = kwargs['block']
    if kwargs.get('is_claimed'):
        seat_kwargs['claimed_at'] = datetime.now(timezone.utc)
        
    return Seat(**seat_kwargs)
