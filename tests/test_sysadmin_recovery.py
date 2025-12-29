import pytest
from app import db
from app.models import Admin, SystemAdmin
import pyotp

def test_sysadmin_reset_totp(client):
    # Create system admin
    sysadmin = SystemAdmin(username="sysadmin_test", totp_secret=pyotp.random_base32())
    db.session.add(sysadmin)

    # Create teacher
    old_secret = pyotp.random_base32()
    teacher = Admin(username="teacher_to_reset", totp_secret=old_secret)
    db.session.add(teacher)
    db.session.commit()

    # Login as sysadmin
    with client.session_transaction() as sess:
        sess['is_system_admin'] = True
        sess['sysadmin_id'] = sysadmin.id

    # Call reset endpoint
    response = client.post(f'/sysadmin/admins/{teacher.id}/reset-totp')
    assert response.status_code == 200
    data = response.json
    assert data['status'] == 'success'
    assert data['totp_secret'] != old_secret
    assert 'qr_code' in data

    # Verify in DB
    db.session.expire(teacher)
    assert teacher.totp_secret == data['totp_secret']
    assert teacher.totp_secret != old_secret

def test_sysadmin_reset_totp_unauthorized(client):
    # Create teacher
    teacher = Admin(username="teacher_fail", totp_secret=pyotp.random_base32())
    db.session.add(teacher)
    db.session.commit()

    # Call reset endpoint without login
    response = client.post(f'/sysadmin/admins/{teacher.id}/reset-totp')
    assert response.status_code == 302 # Redirect to login
