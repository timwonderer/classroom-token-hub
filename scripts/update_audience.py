import os
import glob
import re

ACTION_LOG_FILE = "docs/audits/documentation_action_log.md"

def log_action(action, file_path, details):
    with open(ACTION_LOG_FILE, "a") as f:
        f.write(f"- **{action}**: `{file_path}` - {details}\n")

def get_audience(file_path):
    if "features/teacher" in file_path or "teacher" in file_path.lower():
        return "teacher-facing"
    elif "features/student" in file_path or "student" in file_path.lower():
        return "student-facing"
    elif "docs/development" in file_path or "docs/technical-reference" in file_path or "scripts/" in file_path or "docs/operations" in file_path or "docs/security" in file_path:
        return "developer-facing"
    elif "docs/README.md" in file_path or "README.md" == file_path or "CHANGELOG.md" in file_path or "docs/user-guides/README.md" in file_path or "docs/user-guides/legal" in file_path:
        return "mixed-audience"
    return "mixed-audience"

md_files = glob.glob('docs/**/*.md', recursive=True) + glob.glob('*.md') + glob.glob('scripts/**/*.md', recursive=True)

for file_path in md_files:
    if "archive" in file_path or "docs/audits" in file_path:
        continue # skip archives and audits

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    audience = get_audience(file_path)
    updated = False

    # Ensure audience frontmatter or indicator
    if "Audience:" not in content:
        # Try to inject below frontmatter if it exists
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                # Add to frontmatter
                if "roles:" not in parts[1]:
                    if audience == "teacher-facing":
                        parts[1] += "roles: [teacher]\nAudience: teacher-facing\n"
                    elif audience == "student-facing":
                        parts[1] += "roles: [student]\nAudience: student-facing\n"
                    elif audience == "developer-facing":
                        parts[1] += "roles: [developer]\nAudience: developer-facing\n"
                    else:
                        parts[1] += "roles: [teacher, student, developer]\nAudience: mixed-audience\n"
                else:
                     parts[1] += f"Audience: {audience}\n"

                content = "---" + parts[1] + "---" + parts[2]
                updated = True
        else:
            # Add to top of file
            if audience == "teacher-facing":
                content = "---\nroles: [teacher]\nAudience: teacher-facing\n---\n" + content
            elif audience == "student-facing":
                content = "---\nroles: [student]\nAudience: student-facing\n---\n" + content
            elif audience == "developer-facing":
                content = "---\nroles: [developer]\nAudience: developer-facing\n---\n" + content
            else:
                content = "---\nroles: [teacher, student, developer]\nAudience: mixed-audience\n---\n" + content
            updated = True

    # Add mixed-audience justification if missing and needed
    if audience == "mixed-audience" and "This page is relevant to multiple audiences because" not in content and "Audience: mixed-audience" in content:
        # inject just below the first heading
        if "\n# " in content or content.startswith("# "):
            replacement = "\n> **Note:** This page is relevant to multiple audiences because it covers system-wide information applicable to all roles.\n\n"
            content = re.sub(r'^(# .*)$', r'\1' + replacement, content, count=1, flags=re.MULTILINE)
            updated = True

    if updated:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        log_action("Update", file_path, f"Injected audience indicator: {audience}")

print("Audience update complete.")
