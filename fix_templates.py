print("Realignment: Fixing Templates")
import os
os.system("rm -rf templates/*")
os.makedirs("templates/admin", exist_ok=True)
os.makedirs("templates/student", exist_ok=True)

with open("templates/admin/dashboard.html", "w") as f:
    f.write("Admin Dashboard")

with open("templates/student/dashboard.html", "w") as f:
    f.write("Student Dashboard")

with open("templates/base.html", "w") as f:
    f.write("Base Template")
