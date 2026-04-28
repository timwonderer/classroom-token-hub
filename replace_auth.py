import os
import glob

print("Realignment: Beginning Auth")

# First, we need to completely replace `app/auth.py`
with open("app/auth.py", "w") as f:
    f.write("""from functools import wraps
from flask import session, redirect, url_for, flash, g, request, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import hmac
import hashlib
from app.extensions import db
from app.models import User, Seat, Class, IdentityProfile

def get_current_user():
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None

def get_current_seat():
    if 'active_seat_id' in session:
        return db.session.get(Seat, session['active_seat_id'])
    return None

def get_current_class_id():
    return session.get('active_class_id')

def login_user(user, seat=None):
    session['user_id'] = user.id
    if seat:
        session['active_seat_id'] = seat.id
        session['active_class_id'] = seat.class_id
    elif user.last_active_seat_id:
        last_seat = db.session.get(Seat, user.last_active_seat_id)
        if last_seat:
            session['active_seat_id'] = last_seat.id
            session['active_class_id'] = last_seat.class_id

def logout_user():
    session.pop('user_id', None)
    session.pop('active_seat_id', None)
    session.pop('active_class_id', None)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        seat = get_current_seat()
        if not user or user.user_role not in ['TEACHER', 'SYSADMIN']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.login'))
        if user.user_role == 'TEACHER' and (not seat or seat.role != 'TEACHER'):
            flash('Active teacher seat required.', 'danger')
            return redirect(url_for('main.select_class'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        seat = get_current_seat()
        if not user or user.user_role != 'STUDENT':
            flash('Student access required.', 'danger')
            return redirect(url_for('main.login'))
        if not seat or seat.role != 'STUDENT':
            flash('Active student seat required.', 'danger')
            return redirect(url_for('student.select_class'))
        return f(*args, **kwargs)
    return decorated_function

def sysadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or user.user_role != 'SYSADMIN':
            flash('Sysadmin access required.', 'danger')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

def load_user_context():
    g.user = get_current_user()
    g.seat = get_current_seat()
    g.class_id = get_current_class_id()
""")
