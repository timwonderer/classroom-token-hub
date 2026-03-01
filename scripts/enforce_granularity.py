import os

ACTION_LOG_FILE = "docs/audits/documentation_action_log.md"

def log_action(action, file_path, details):
    with open(ACTION_LOG_FILE, "a") as f:
        f.write(f"- **{action}**: `{file_path}` - {details}\n")

teacher_features = [
    "managing-students",
    "attendance-and-payroll",
    "store",
    "economy-and-analytics",
    "rent",
    "insurance",
    "banking",
    "student-issues",
    "account-customization",
    "class-management",
    "system-features"
]

student_features = [
    "starting-and-ending-work",
    "store",
    "rent",
    "insurance",
    "banking",
    "reporting-issues",
    "student-account-actions"
]

required_files = [
    "setup.md",
    "configuration.md",
    "behavioral-rules.md",
    "edge-cases.md"
]

def enforce_granularity(base_dir, features, role):
    for feature in features:
        feature_dir = os.path.join(base_dir, feature)
        os.makedirs(feature_dir, exist_ok=True)
        for req_file in required_files:
            file_path = os.path.join(feature_dir, req_file)
            if not os.path.exists(file_path):
                # Create boilerplate
                title = req_file.replace(".md", "").replace("-", " ").title()
                content = f"""---
title: {title} ({feature.replace('-', ' ').title()})
category: features
subcategory: {role}-{feature}
roles: [{role}]
---

# {title}

Documentation for {title.lower()} regarding {feature.replace('-', ' ')}.

"""
                with open(file_path, "w") as f:
                    f.write(content)
                log_action("Create", file_path, f"Generated boilerplate for missing granularity ({req_file})")

enforce_granularity("docs/user-guides/features/teacher", teacher_features, "teacher")
enforce_granularity("docs/user-guides/features/student", student_features, "student")

print("Granularity check complete.")
