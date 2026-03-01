import os
import glob
import re

md_files = glob.glob('docs/**/*.md', recursive=True)

# Collect all valid targets
valid_targets = set()
for f in md_files:
    # normalize path relative to docs/
    norm = f.replace("docs/", "")
    valid_targets.add(norm)
    # add version without .md
    if norm.endswith(".md"):
        valid_targets.add(norm[:-3])
    # also add with absolute path for links starting with /docs/
    valid_targets.add("/docs/" + norm)
    if norm.endswith(".md"):
        valid_targets.add("/docs/" + norm[:-3])

# regex to find markdown links: [text](link)
link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

errors = []
linked_files = set()

for f in md_files:
    if "archive" in f or "audits" in f: continue
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    for match in link_pattern.finditer(content):
        text, link = match.groups()
        # ignore external links and anchors
        if link.startswith("http") or link.startswith("#") or "mailto:" in link:
            continue

        # strip anchors
        target = link.split("#")[0]
        if not target: continue

        # Resolve relative paths
        if target.startswith("../"):
            # Simple resolution
            base = os.path.dirname(f)
            while target.startswith("../"):
                target = target[3:]
                base = os.path.dirname(base)
            target = os.path.join(base, target).replace("\\", "/")
            # remove 'docs/' prefix to match norm
            if target.startswith("docs/"):
                target = target[5:]
        elif target.startswith("./"):
            target = os.path.join(os.path.dirname(f).replace("docs/", ""), target[2:])
        elif not target.startswith("/"):
            # relative to current dir
            target = os.path.join(os.path.dirname(f).replace("docs/", ""), target)

        if target not in valid_targets and target != "":
            # Maybe it maps to a README
            if target == "README":
                 target = "README.md"

            # Add some leeway
            if target + ".md" not in valid_targets and target.replace("/docs/", "") not in valid_targets:
                 errors.append(f"Dead link in {f}: {link} -> Resolved: {target}")

        # Track for orphans
        target_norm = target.replace("/docs/", "")
        if target_norm.endswith(".md"): target_norm = target_norm[:-3]
        linked_files.add(target_norm)

for e in errors:
    print(e)

# Check for orphans
for f in valid_targets:
    if "archive" in f or "audits" in f or "README" in f or f == "index": continue
    # Only check .md versions
    if not f.endswith(".md"): continue
    norm = f[:-3]
    if norm not in linked_files and not norm.startswith("development/") and not norm.startswith("operations/") and not norm.startswith("technical-reference/") and not norm.startswith("security/"):
        print(f"Orphaned file: {f}")

print("Link check complete.")
