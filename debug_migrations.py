
import subprocess
import os

commands = [
    ["flask", "db", "heads"],
    ["flask", "db", "current"],
    ["flask", "db", "history", "--limit", "5"]
]

output_file = "migration_debug_output.txt"

with open(output_file, "w") as f:
    for cmd in commands:
        f.write(f"--- Running: {' '.join(cmd)} ---\n")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\nSTDERR:\n")
            f.write(result.stderr)
            f.write(f"\nExit Code: {result.returncode}\n\n")
        except Exception as e:
            f.write(f"Exception: {e}\n\n")

print(f"Done. Check {output_file}")
