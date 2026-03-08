import pytest
from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    Admin, ClassEconomy, ClassMembership, TeacherBlock, Transaction, StudentBlock,
    TapEvent, HallPassLog, RedemptionAuditLog, StudentItem, AnalyticsEvent,
    AnalyticsSnapshot, Issue, IssueResolutionAction, InsuranceClaim,
    StudentInsurance, RentPayment, Announcement, StoreItemBlock, StoreItem,
    Student, StudentTeacher, PayrollSettings, RentSettings,
    IssueCategory, InsurancePolicy, InsurancePolicyBlock
)
from app.utils.deletion import collapse_universe

def test_collapse_universe_cascades_and_cleans_up(client):
    admin = Admin(username="collapse_admin", totp_secret="secret")
    db.session.add(admin)
    db.session.flush()

    student = Student(first_name="Collapse", last_initial="S", block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()
    
    student_b = Student(first_name="Survive", last_initial="B", block="A", salt=b"salt")
    db.session.add(student_b)
    db.session.flush()

    join_code = "COLL01"
    
    economy = ClassEconomy(join_code=join_code, status="active", created_by_admin_id=admin.id)
    membership = ClassMembership(join_code=join_code, admin_id=admin.id, role="admin", status="active")
    
    # We add a student membership for student A (who has no other class)
    student_membership = ClassMembership(join_code=join_code, student_id=student.id, role="student", status="active")
    
    # We add a student membership for student B (who has another class)
    student_b_membership = ClassMembership(join_code=join_code, student_id=student_b.id, role="student", status="active")
    
    db.session.add_all([economy, membership, student_membership, student_b_membership])
    db.session.flush()
    
    # Student B has another class
    join_code_survive = "SURV01"
    economy_survive = ClassEconomy(join_code=join_code_survive, status="active", created_by_admin_id=admin.id)
    student_b_membership_survive = ClassMembership(join_code=join_code_survive, student_id=student_b.id, role="student", status="active")
    db.session.add_all([economy_survive, student_b_membership_survive])
    
    # Bridge row
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin.id))
    db.session.add(StudentTeacher(student_id=student_b.id, teacher_id=admin.id))

    # TeacherBlock
    db.session.add(TeacherBlock(teacher_id=admin.id, block="A", join_code=join_code, is_claimed=True, student_id=student.id, first_name="C", last_initial="S", last_name_hash_by_part=[], dob_sum=0, salt=b"s", first_half_hash="h"))
    
    # Settings
    db.session.add(PayrollSettings(teacher_id=admin.id, block="A"))
    db.session.add(RentSettings(teacher_id=admin.id, block="A"))

    # Transaction
    db.session.add(Transaction(student_id=student.id, teacher_id=admin.id, join_code=join_code, amount=10, account_type="checking", type="deposit", is_void=False))
    
    # Store Item and Block
    store_item = StoreItem(teacher_id=admin.id, join_code=join_code, name="Item", price=10, item_type='immediate')
    db.session.add(store_item)
    db.session.flush()
    
    db.session.add(StoreItemBlock(store_item_id=store_item.id, block="A"))
    
    # Issue
    issue_cat = IssueCategory(name="Issue", category_type="transaction", is_active=True)
    db.session.add(issue_cat)
    db.session.flush()
    
    issue = Issue(
        student_id=student.id, 
        student_first_name="Collapse",
        student_last_initial="S",
        opaque_student_reference="ref",
        class_label="A",
        teacher_id=admin.id, 
        join_code=join_code, 
        category_id=issue_cat.id, 
        issue_type="transaction",
        student_explanation="Test explanation"
    )
    db.session.add(issue)
    
    db.session.commit()

    # Pre-collapse assertions
    assert db.session.get(ClassEconomy, join_code) is not None
    assert db.session.query(Transaction).filter_by(join_code=join_code).count() == 1
    assert db.session.query(StoreItemBlock).filter_by(store_item_id=store_item.id).count() == 1
    assert db.session.query(StoreItem).filter_by(id=store_item.id).count() == 1
    assert db.session.get(Student, student.id) is not None
    assert db.session.get(Student, student_b.id) is not None

    store_item_id_val = store_item.id
    student_id_val = student.id
    student_b_id_val = student_b.id
    admin_id_val = admin.id

    # Do the collapse
    success = collapse_universe(join_code, reason="Test collapse", actor_membership_id=membership.id)
    assert success is True

    # Post-collapse assertions
    assert db.session.get(ClassEconomy, join_code) is None
    assert db.session.query(ClassMembership).filter_by(join_code=join_code).count() == 0
    assert db.session.query(Transaction).filter_by(join_code=join_code).count() == 0
    assert db.session.query(TeacherBlock).filter_by(join_code=join_code).count() == 0
    assert db.session.query(Issue).filter_by(join_code=join_code).count() == 0
    
    # Store settings cleanup
    assert db.session.query(StoreItemBlock).filter_by(store_item_id=store_item_id_val).count() == 0
    # Store item should be deleted because it has no remaining visibility blocks
    assert db.session.query(StoreItem).filter_by(id=store_item_id_val).count() == 0
    
    # Settings Cleanup
    assert db.session.query(PayrollSettings).filter_by(teacher_id=admin_id_val, block="A").count() == 0
    assert db.session.query(RentSettings).filter_by(teacher_id=admin_id_val, block="A").count() == 0

    # Student A should be entirely deleted because they have no other classes
    assert db.session.get(Student, student_id_val) is None
    
    # Student B should survive because they have another class
    assert db.session.get(Student, student_b_id_val) is not None


def test_admin_join_code_delete_route(client):
    admin = Admin(username="route_admin", totp_secret="secret")
    db.session.add(admin)
    db.session.flush()

    join_code = "ROUT01"
    db.session.add(ClassEconomy(join_code=join_code, status="active", created_by_admin_id=admin.id))
    db.session.add(ClassMembership(join_code=join_code, admin_id=admin.id, role="admin", status="active"))
    db.session.commit()

    with client.session_transaction() as sess:
        sess["admin_id"] = admin.id
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
        
    # Valid deletion
    response = client.post("/admin/join-code/delete", json={
        "join_code": join_code,
        "confirm_join_code": join_code
    })
    
    assert response.status_code == 200
    assert db.session.get(ClassEconomy, join_code) is None
