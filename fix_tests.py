import os
import re

for root, _, files in os.walk('tests'):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r') as f:
                content = f.read()
            
            if 'StudentItem(' in content:
                # Replace StudentItem( with StudentItem(correlation_id='corr_test', 
                new_content = content.replace('StudentItem(', "StudentItem(correlation_id='corr_test', ")
                with open(filepath, 'w') as f:
                    f.write(new_content)
                print(f"Fixed {filepath}")
