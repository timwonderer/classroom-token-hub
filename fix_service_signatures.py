import os
import re

files_to_check = [
    "app/feats/attendance.py",
    "app/feats/rent_payment_feat.py",
    "app/feats/rent_cycle_feat.py",
    "app/feats/store_purchase_feat.py",
    "app/services/tlcp.py",
    "app/services/obligations_service.py",
    "app/services/store_service.py",
    "app/services/identity_service.py",
]

for filename in files_to_check:
    if not os.path.exists(filename):
        continue
    with open(filename, "r") as f:
        content = f.read()

    # Remove join_code parameter from defs
    content = re.sub(r"[ \t]*join_code:[ \t]*str(?:[ \t]*\|[ \t]*None)?(?:[ \t]*=[ \t]*None)?,?\n", "", content)
    # Remove join_code kwarg passes
    content = re.sub(r"[ \t]*join_code=.*?,\n", "", content)
    
    # In tlcp.py, replace _resolve_class_id(join_code) calls since they used it as fallback
    if "tlcp.py" in filename:
        content = re.sub(r"\[\"current_join_code\"\]", "['current_class_id']", content) # just to be safe if any exist
        content = re.sub(r"session\.get\(\"current_join_code\"\)", "None", content)
        content = re.sub(r"current_seat\.join_code", "None", content)

    with open(filename, "w") as f:
        f.write(content)
