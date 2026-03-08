import os
import re
from datetime import datetime

DOCS_DIR = 'docs'
TODAY = '2026-03-08'

def process_frontmatter(content):
    lines = content.split('\n')
    in_table = False
    table_lines = []
    start_idx = -1
    end_idx = -1
    
    for i, line in enumerate(lines):
        if line.strip().startswith('| Reference Number |'):
            in_table = True
            start_idx = i
        if in_table and not line.strip().startswith('|') and line.strip() != '':
            end_idx = i
            break
        if in_table:
            table_lines.append(line)
            
    if start_idx == -1:
        return content # No frontmatter
        
    if end_idx == -1:
        end_idx = len(lines)
        
    # Process table
    # Example row: | ARC-CORE-000 | 1.0 | 2026-03-01 | N/A | Constitutional |
    new_table_lines = []
    old_version = "None"
    for line in table_lines:
        if line.strip().startswith('|') and not 'Reference Number' in line and not '---' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 7:
                ref = parts[1]
                old_version = parts[2]
                
                # Increment version
                try:
                    major, minor = old_version.split('.')
                    new_version = f"{major}.{int(minor)+1}"
                except:
                    new_version = old_version
                    
                parts[2] = f" {new_version} "
                parts[3] = f" {TODAY} "
                parts[4] = f" {old_version} "
                new_line = "|" + "|".join(parts[1:-1]) + "|"
                new_table_lines.append(new_line)
            else:
                new_table_lines.append(line)
        else:
            new_table_lines.append(line)
            
    return '\n'.join(lines[:start_idx] + new_table_lines + lines[end_idx:])

def fix_sections(content):
    # This is a basic conversion from "1. Purpose" to "I. Purpose", etc.
    # We will try to replace "^## 1\. Purpose" with "## I. Purpose"
    content = re.sub(r'(?m)^## 1\.\s+Purpose', '## I. Purpose', content, flags=re.IGNORECASE)
    content = re.sub(r'(?m)^## 2\.\s+Scope', '## II. Scope', content, flags=re.IGNORECASE)
    content = re.sub(r'(?m)^## 3\.\s+Authority Level', '## III. Authority Level', content, flags=re.IGNORECASE)
    content = re.sub(r'(?m)^## 4\.\s+Dependencies', '## IV. Dependencies', content, flags=re.IGNORECASE)
    
    # Also standardize if they are missing numbers
    content = re.sub(r'(?m)^## Purpose$', '## I. Purpose', content, flags=re.IGNORECASE)
    content = re.sub(r'(?m)^## Scope$', '## II. Scope', content, flags=re.IGNORECASE)
    content = re.sub(r'(?m)^## Authority Level$', '## III. Authority Level', content, flags=re.IGNORECASE)
    content = re.sub(r'(?m)^## Dependencies$', '## IV. Dependencies', content, flags=re.IGNORECASE)

    # Note: adding missing sections like VIII. Amendment would be complex here, 
    # we might just do frontmatter and known headers.
    return content

processed = 0
for root, _, files in os.walk(DOCS_DIR):
    for f in files:
        if f.endswith('.md') and f != 'SOP-DOC-000_Writing_Specification.md':
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            new_content = process_frontmatter(content)
            new_content = fix_sections(new_content)
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(new_content)
                processed += 1
                print(f"Updated {path}")

print(f"Total updated: {processed}")
