import os
import re

NORMATIVE_DIRS = [
    'ARCHITECTURE',
    'DOMAINS',
    'FEATURES',
    'STANDARD_OPERATING_PROCEDURES',
    'SECURITY/CONTROLS'
]

def int_to_roman(num):
    val = [
        1000, 900, 500, 400,
        100, 90, 50, 40,
        10, 9, 5, 4,
        1
        ]
    syb = [
        "M", "CM", "D", "CD",
        "C", "XC", "L", "XL",
        "X", "IX", "V", "IV",
        "I"
        ]
    roman_num = ''
    i = 0
    while  num > 0:
        for _ in range(num // val[i]):
            roman_num += syb[i]
            num -= val[i]
        i += 1
    return roman_num

def process_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Determine authority level based on path
    authority = "Normative"
    if "ARCHITECTURE" in path or "DOMAINS" in path:
        authority = "Constitutional"

    # Extract frontmatter and rest
    lines = content.split('\n')
    table_end = 0
    in_table = False
    for i, line in enumerate(lines):
        if line.strip().startswith('| Reference Number |') or line.strip().startswith('|Reference Number|'):
            in_table = True
        elif in_table and not line.strip().startswith('|') and line.strip() != '' and not line.strip().startswith('---'):
            table_end = i
            break
        elif in_table and line.strip().startswith('---'):
            table_end = i
            break
    if table_end == 0:
        # try to find |---|---|
        for i, line in enumerate(lines):
            if '|---' in line and 'Reference' in lines[i-1]:
                table_end = i+1
                while table_end < len(lines) and lines[table_end].strip().startswith('|'):
                    table_end += 1
                break
                
    front_matter = lines[:table_end]
    rest = lines[table_end:]

    body = '\n'.join(rest)
    
    # Check if we have standard sections
    has_purpose = bool(re.search(r'(?i)^## (I\.\s+)?Purpose', body, flags=re.MULTILINE))
    has_scope = bool(re.search(r'(?i)^## (II\.\s+)?Scope', body, flags=re.MULTILINE))
    has_authority = bool(re.search(r'(?i)^## (III\.\s+)?Authority Level', body, flags=re.MULTILINE))
    has_deps = bool(re.search(r'(?i)^## (IV\.\s+)?Dependencies', body, flags=re.MULTILINE))
    has_amendment = bool(re.search(r'(?i)^## (([A-Z]+|Last)\.\s+)?Amendment', body, flags=re.MULTILINE))
    
    if not has_purpose and not has_scope and not has_authority and not has_deps and not has_amendment:
        # If it doesn't even have purpose, maybe it's completely unformatted. We skip highly customized logic for a full rewrite here,
        # but try to inject at least Authority and Dependencies if Purpose/Scope exists.
        pass

    # We will split body by `## ` to get sections.
    sections = re.split(r'^## ', body, flags=re.MULTILINE)
    
    if len(sections) <= 1:
        return # nothing to do

    new_sections = []
    # sections[0] is everything before the first `## `
    
    # We will rebuild
    header_idx = 5 # Start V for content
    
    # Map old sections to new
    purpose_content = ""
    scope_content = ""
    auth_content = f"{authority}. Subordinate to CORE invariant definitions.\n"
    dep_content = "None specified.\n"
    amendment_content = "Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.\n"
    
    other_sections = []
    
    for sec in sections[1:]:
        lines = sec.split('\n', 1)
        title_line = lines[0].strip()
        sec_body = lines[1] if len(lines) > 1 else ""
        
        # strip numeric/roman prefixes
        clean_title = re.sub(r'^([IVXLCDM]+\.|[0-9]+\.)\s*', '', title_line, flags=re.IGNORECASE).strip()
        
        if clean_title.lower() == 'purpose':
            purpose_content = sec_body
        elif clean_title.lower() == 'scope':
            scope_content = sec_body
        elif clean_title.lower() == 'authority level':
            auth_content = sec_body
        elif clean_title.lower() == 'dependencies':
            dep_content = sec_body
        elif clean_title.lower() == 'amendment':
            amendment_content = sec_body
        else:
            other_sections.append((clean_title, sec_body))
            
    # Now assemble
    if not purpose_content.strip(): purpose_content = "\nTBD\n"
    if not scope_content.strip(): scope_content = "\nTBD\n"
    
    assembled = [sections[0]]
    assembled.append(f"## I. Purpose\n{purpose_content}")
    assembled.append(f"## II. Scope\n{scope_content}")
    assembled.append(f"## III. Authority Level\n{auth_content}")
    assembled.append(f"## IV. Dependencies\n{dep_content}")
    
    idx = 5
    for title, cbody in other_sections:
        assembled.append(f"## {int_to_roman(idx)}. {title}\n{cbody}")
        idx += 1
        
    assembled.append(f"## {int_to_roman(idx)}. Amendment\n{amendment_content}")
    
    new_body = "".join(assembled)
    
    final_content = '\n'.join(front_matter) + '\n' + new_body
    
    # Fix multiple newlines
    final_content = re.sub(r'\n{3,}', '\n\n', final_content)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(final_content)

processed = 0
for root, _, files in os.walk('docs'):
    for d in NORMATIVE_DIRS:
        if d in root and 'LOGS' not in root: # avoid informative
            for f in files:
                if f.endswith('.md') and f != 'SOP-DOC-000_Writing_Specification.md':
                    path = os.path.join(root, f)
                    try:
                        process_file(path)
                        processed += 1
                    except Exception as e:
                        print(f"Failed {path}: {e}")
            break

print(f"Processed nicely {processed} normative files")
