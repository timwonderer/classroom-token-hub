import os
import glob
import re

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
    "setup",
    "configuration",
    "behavioral-rules",
    "edge-cases"
]

def add_links_to_index(base_dir, features, role):
    for feature in features:
        feature_dir = os.path.join(base_dir, feature)
        index_file = os.path.join(feature_dir, "index.md")

        # If no index exists, create it
        if not os.path.exists(index_file):
            title = feature.replace("-", " ").title()
            content = f"""---
title: {title} ({role.title()})
category: features
subcategory: {role}-{feature}
roles: [{role}]
---

# {title}

Use this guide to understand and configure {feature.replace('-', ' ')}.

"""
            with open(index_file, "w") as f:
                f.write(content)

        # Read index and inject links if missing
        with open(index_file, "r") as f:
            content = f.read()

        updated = False
        if "## Core Documentation" not in content:
            links = "\n## Core Documentation\n\n"
            for req in required_files:
                title = req.replace("-", " ").title()
                link = f"/docs/user-guides/features/{role}/{feature}/{req}"
                if req not in content and link not in content:
                    links += f"- [{title}]({link})\n"
                    updated = True

            if updated:
                content += links
                with open(index_file, "w") as f:
                    f.write(content)

add_links_to_index("docs/user-guides/features/teacher", teacher_features, "teacher")
add_links_to_index("docs/user-guides/features/student", student_features, "student")
