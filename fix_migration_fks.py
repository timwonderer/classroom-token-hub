
import re

path = 'migrations/versions/f3fe270c6f0e_refactor_timezone_handling.py'
with open(path, 'r') as f:
    lines = f.readlines()

new_lines = []
current_table = None

for line in lines:
    # Detect table context
    m_start = re.search(r"with op\.batch_alter_table\('([^']+)'", line)
    if m_start:
        current_table = m_start.group(1)
    
    # Reset table context on exit? No, batch block is indented.
    # We rely on indentation to know if we are in a block, BUT for this simple script, 
    # we just track the last seen table. 
    # Since batch_alter_table is a context manager, it's safe to assume lines following it 
    # (indented) belong to it.
    
    indent = line.split('batch_op')[0] if 'batch_op' in line else line.split('op.')[0] if 'op.' in line else "    "
    if not indent.strip() == "":
        indent_str = indent
    else:
        indent_str = "        "

    # 1. Drop Constraint (FK)
    if 'batch_op.drop_constraint' in line and (
        'class_economies' in line or 
        'join_code' in line or 
        'actor_membership_id' in line
    ):
        # Extract constraint name e.g. batch_op.f('name')
        m_name = re.search(r"batch_op\.f\('([^']+)'\)", line)
        if m_name and current_table:
            name = m_name.group(1)
            new_lines.append(f"{indent_str}if foreign_key_exists('{current_table}', '{name}'):\n")
            new_lines.append(f"    {line}")
        continue

    # 2. Drop Index
    if 'batch_op.drop_index' in line:
        m_name = re.search(r"batch_op\.f\('([^']+)'\)", line)
        if m_name and current_table:
            name = m_name.group(1)
            new_lines.append(f"{indent_str}if index_exists('{current_table}', '{name}'):\n")
            new_lines.append(f"    {line}")
        continue
    
    # 3. Drop Column
    if 'batch_op.drop_column' in line:
        m_col = re.search(r"\.drop_column\('([^']+)'\)", line)
        if m_col and current_table:
            col = m_col.group(1)
            new_lines.append(f"{indent_str}if column_exists('{current_table}', '{col}'):\n")
            new_lines.append(f"    {line}")
        continue

    # 4. Drop Table (top-level op)
    if 'op.drop_table' in line:
        m_tbl = re.search(r"op\.drop_table\('([^']+)'\)", line)
        if m_tbl:
            tbl = m_tbl.group(1)
            # Indent for op.drop_table is usually 4 spaces (inside upgrade)
            # Use detected indent or default
            curr_indent = line.split('op.')[0]
            new_lines.append(f"{curr_indent}if table_exists('{tbl}'):\n")
            new_lines.append(f"    {line}")
        continue

    # If no match, append line as is
    new_lines.append(line)

with open(path, 'w') as f:
    f.writelines(new_lines)

print("Updated file with conditional checks.")
