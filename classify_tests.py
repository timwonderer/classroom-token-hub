import re
from pathlib import Path

files = Path('tests_to_fix.txt').read_text().splitlines()

legacy_keywords = ['legacy', 'cleanup', 'unclaimed', 'placeholder_badge']

bucket1 = []
bucket2 = []

for f in files:
    if not f.strip(): continue
    name = Path(f).name
    if any(k in name for k in legacy_keywords):
        bucket1.append(f)
    elif name in ['test_link_student_to_admin.py', 'test_pending_student_deletion.py', 'test_v2_authority_guardrails.py', 'test_teacher_block_cleanup.py', 'test_student_block_cleanup.py']:
        bucket1.append(f)
    else:
        bucket2.append(f)

print(f"Bucket 1 (Legacy/Skip): {len(bucket1)}")
for f in bucket1: print("  " + f)
print(f"\nBucket 2 (Rewrite): {len(bucket2)}")
for f in bucket2: print("  " + f)
