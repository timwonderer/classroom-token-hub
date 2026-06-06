import re

file_path = "tests/test_hall_pass_checkout.py"
with open(file_path, "r") as f:
    content = f.read()

# Replace the student setup to also add a user
new_setup = """    # Create user and link to student via seat
    from app.models import User
    user = User(username_hash="test_user_hash", password_hash="test_pass", user_role="student")
    db.session.add(user)
    db.session.flush()

    salt = get_random_salt()
    student = Student(
"""

content = re.sub(r'    # Create user and link to student via seat\n    from app.models import User\n    user = User\(username_hash="test_user_hash", password_hash="test_pass"\)\n    db.session.add\(user\)\n    db.session.flush\(\)\n\n    salt = get_random_salt\(\)\n    student = Student\(', new_setup, content)

with open(file_path, "w") as f:
    f.write(content)
