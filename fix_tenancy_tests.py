import re

file_path = "tests/test_api_tenancy.py"
with open(file_path, "r") as f:
    content = f.read()

# Replace _create_student to create User
new_create = """def _create_student(first_name: str, primary_teacher: Admin = None, linked_teachers: list[Admin] = None) -> Student:
    from app.models import User
    user = User(username_hash=first_name.lower() + "_hash", password_hash="test_pass", user_role="student")
    db.session.add(user)
    db.session.flush()

    salt = get_random_salt()
    student = Student(
"""
content = re.sub(r'def _create_student\(first_name: str, primary_teacher: Admin = None, linked_teachers: list\[Admin\] = None\) -> Student:\n    """\n    Create a student for testing.\n    \n    Args:\n        first_name: Student\'s first name\n        primary_teacher: Primary owner \(sets teacher_id\)\n        linked_teachers: List of teachers to link via student_teachers\n    """\n    salt = get_random_salt\(\)\n    student = Student\(', new_create, content)

# Replace _create_claimed_seat to link user
new_seat = """    seat = TeacherBlock(
        user_id=student.seats[0].user_id if student.seats else None,
        teacher_id=teacher.id,"""
content = re.sub(r'    seat = TeacherBlock\(\n        teacher_id=teacher.id,', new_seat, content)

# But wait! _create_claimed_seat might not be able to get user_id this easily.
# Let's fix _create_claimed_seat properly by querying the user we created.
# Actually, it's easier to just pass the user to _create_claimed_seat or fetch it.
