import os
import ast
import re
import sys
import collections
import hashlib

# Configuration
EXCLUDE_DIRS = {'migrations', 'tests', 'tools', '.git', '.github', '.agent', '.claude', 'deploy', 'docs', 'static', 'templates'}
EXCLUDE_FILES = {'audit_script.py', 'setup.py', 'wsgi.py'} # audit_script is excluded implicitly by location, but good to be safe.
MIN_DUPLICATE_LINES = 6
MAX_FUNC_LINES = 75
MAX_NESTING_DEPTH = 3

class Finding:
    def __init__(self, severity, file_path, line_range, category, description, why, confidence):
        self.severity = severity
        self.file_path = file_path
        self.line_range = line_range
        self.category = category
        self.description = description
        self.why = why
        self.confidence = confidence

    def to_markdown(self):
        return (
            f"**Severity:** {self.severity}\n"
            f"**File:** `{self.file_path}`\n"
            f"**Line Range:** {self.line_range}\n"
            f"**Category:** {self.category}\n"
            f"**Description:** {self.description}\n"
            f"**Why This Matters:** {self.why}\n"
            f"**Confidence Level:** {self.confidence}\n"
            "---\n"
        )

findings = []
definitions = collections.defaultdict(list) # name -> [file_paths]
references = collections.defaultdict(set) # name -> {file_paths}
all_source_lines = {} # file_path -> [lines]

def get_line_range(node):
    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
        return f"{node.lineno}-{node.end_lineno}"
    if hasattr(node, 'lineno'):
        return str(node.lineno)
    return "Unknown"

def get_complexity(node):
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.AsyncFor)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity

class ASTAnalyzer(ast.NodeVisitor):
    def __init__(self, file_path, source_lines):
        self.file_path = file_path
        self.source_lines = source_lines
        self.current_function = None
        self.in_loop = 0

    def visit_FunctionDef(self, node):
        self.current_function = node.name

        # Function Length
        length = node.end_lineno - node.lineno + 1
        if length > MAX_FUNC_LINES:
            findings.append(Finding(
                "Medium", self.file_path, f"{node.lineno}-{node.end_lineno}", "Complexity",
                f"Function `{node.name}` is {length} lines long (max {MAX_FUNC_LINES}).",
                "Long functions are harder to read, test, and maintain.", "High"
            ))

        # Cyclomatic Complexity
        complexity = get_complexity(node)
        if complexity > 10: # Standard threshold
            findings.append(Finding(
                "Medium" if complexity <= 20 else "High", self.file_path, f"{node.lineno}", "Complexity",
                f"Function `{node.name}` has cyclomatic complexity of {complexity}.",
                "High complexity indicates hard-to-test logic.", "High"
            ))

        # Collect Definition
        definitions[node.name].append((self.file_path, node.lineno))

        # Inconsistent Returns
        returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
        has_value = any(r.value is not None for r in returns)
        has_none = any(r.value is None for r in returns) or (not returns and length > 1) # implicit None if no return
        # Be careful with implicit None. If there are explicit Returns with value, and some execution paths don't return, that's implicit None.
        # Strict check: mixed explicit returns with value and without value.
        explicit_values = [r.value is not None for r in returns]
        if all(explicit_values) is False and any(explicit_values) is True:
             findings.append(Finding(
                "Low", self.file_path, f"{node.lineno}", "Risk Pattern",
                f"Function `{node.name}` has inconsistent return statements (mixed value/no-value).",
                "Inconsistent returns can lead to type errors and confusing behavior.", "Medium"
            ))

        self.generic_visit(node)
        self.current_function = None

    def visit_ClassDef(self, node):
        definitions[node.name].append((self.file_path, node.lineno))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Import(self, node):
        for alias in node.names:
            definitions[alias.asname or alias.name].append((self.file_path, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
             definitions[alias.asname or alias.name].append((self.file_path, node.lineno))
        self.generic_visit(node)

    def visit_If(self, node):
        self.check_nesting(node)
        self.generic_visit(node)

    def visit_For(self, node):
        self.check_nesting(node)
        self.generic_visit(node)

    def visit_While(self, node):
        self.check_nesting(node)
        self.generic_visit(node)

    def check_nesting(self, node):
        depth = 0
        parent = getattr(node, 'parent', None) # We don't have parent links by default in standard AST
        # To do nesting properly, we need to track depth in the visitor
        pass

    def visit(self, node):
        # Tracking nesting depth
        # We can do this by maintaining a stack or counter
        # Standard recursive visit doesn't pass depth.
        # Let's handle generic_visit manually or just trust the stack?
        # A simple way is to re-implement visit to track depth, but visit is the entry point.
        # Instead, let's just inspect specific nodes and their parents if we linked them,
        # or recursively call with depth.
        # Since I can't easily modify the signature of visit in a standard way compatible with generic_visit,
        # I'll rely on a separate depth counter or just checking indentation of lines (heuristic) or
        # do a separate pass for nesting.
        # Actually, let's just use a custom recursive walker for nesting if needed, or
        # extend NodeVisitor properly.
        # Let's try to infer depth from col_offset? No, formatting might vary.
        # Let's skip precise nesting depth > 3 check inside NodeVisitor for now and do it with a custom walker.
        super().visit(node)

    def visit_ExceptHandler(self, node):
        if len(node.body) == 0 or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
            findings.append(Finding(
                "Medium", self.file_path, f"{node.lineno}", "Risk Pattern",
                "Empty except block detected.",
                "Swallowing exceptions hides errors and makes debugging difficult.", "High"
            ))
        self.generic_visit(node)

    def visit_Pass(self, node):
        # We generally flag pass if it's not the only thing in a function/class/except (which we catch elsewhere)
        # But 'Detect pass statements' is a requirement.
        findings.append(Finding(
            "Low", self.file_path, f"{node.lineno}", "Structural Smell",
            "`pass` statement detected.",
            "Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.", "High"
        ))

    def visit_Call(self, node):
        # Track references for unused function detection
        if isinstance(node.func, ast.Name):
            references[node.func.id].add(self.file_path)
        elif isinstance(node.func, ast.Attribute):
            references[node.func.attr].add(self.file_path)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            references[node.id].add(self.file_path)
        self.generic_visit(node)


def check_nesting_depth(node, depth=0):
    max_depth = depth
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)):
        depth += 1

    if depth > MAX_NESTING_DEPTH:
        # We only report once for the threshold
        pass # Collected by caller or we return max depth

    for child in ast.iter_child_nodes(node):
        child_depth = check_nesting_depth(child, depth)
        max_depth = max(max_depth, child_depth)

    return max_depth

def find_deep_nesting(node, file_path, depth=0):
    if depth > MAX_NESTING_DEPTH:
        findings.append(Finding(
            "Medium", file_path, f"{node.lineno}", "Complexity",
            f"Nesting depth > {MAX_NESTING_DEPTH} detected.",
            "Deep nesting reduces readability and increases complexity.", "High"
        ))
        return # Don't report children to avoid noise

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.FunctionDef, ast.AsyncFunctionDef)):
            find_deep_nesting(child, file_path, depth + 1)
        else:
            find_deep_nesting(child, file_path, depth)

def check_unreachable(node, file_path):
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            body = getattr(child, 'body', [])
            for i, stmt in enumerate(body):
                if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    if i + 1 < len(body):
                        findings.append(Finding(
                            "Medium", file_path, f"{body[i+1].lineno}", "Dead Code",
                            "Unreachable code detected after return/raise/break/continue.",
                            "Unreachable code clutters the codebase and may indicate logic errors.", "High"
                        ))
                        break # Only report first unreachable block in a scope

def analyze_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    all_source_lines[file_path] = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return

    # AST Analysis
    visitor = ASTAnalyzer(file_path, all_source_lines[file_path])
    visitor.visit(tree)

    # Nesting
    find_deep_nesting(tree, file_path)

    # Unreachable
    check_unreachable(tree, file_path)

    # Regex Analysis
    lines = source.splitlines()
    for i, line in enumerate(lines):
        line_num = i + 1

        # TODO / FIXME
        if re.search(r'#\s*(TODO|FIXME)', line):
            findings.append(Finding(
                "Low", file_path, f"{line_num}", "Structural Smell",
                f"Found TODO/FIXME marker: {line.strip()}",
                "Incomplete code markers should be addressed or tracked.", "Medium"
            ))

        # Commented out code (heuristic: line starts with # and looks like code)
        # Simple heuristic: contains common keywords or symbols
        stripped = line.strip()
        if stripped.startswith('#') and not stripped.startswith('# ') and len(stripped) > 5:
            # Very rough. Let's look for valid python syntax in comments? Too hard.
            # Let's look for indentation + # + valid start of statement
            pass

        # Commented out code: check for lines starting with # followed by common keywords
        if re.match(r'\s*#\s*(def|class|if|for|while|return|import|from|try|except)\s+', line):
             findings.append(Finding(
                "Low", file_path, f"{line_num}", "Dead Code",
                "Potential commented-out code detected.",
                "Commented-out code rots and confuses readers. Use version control instead.", "Medium"
            ))


def detect_duplicates():
    # Rolling hash or simple block matching
    # We'll map "normalized lines" to locations
    # Normalized: strip whitespace, maybe remove variable names? No, too complex.
    # Just strip whitespace.

    block_map = collections.defaultdict(list)

    for file_path, lines in all_source_lines.items():
        if len(lines) < MIN_DUPLICATE_LINES:
            continue

        # Normalize lines
        norm_lines = [l.strip() for l in lines]

        for i in range(len(norm_lines) - MIN_DUPLICATE_LINES + 1):
            block = tuple(norm_lines[i : i + MIN_DUPLICATE_LINES])
            # Filter out blocks that are just empty lines or comments
            if all(not l or l.startswith('#') for l in block):
                continue

            block_map[block].append((file_path, i + 1))

    for block, locations in block_map.items():
        if len(locations) > 1:
            # We have duplicates
            # Group by file to avoid reporting every single overlap
            # Just report one finding per duplicate set
            desc = "Duplicated logic block detected in: " + ", ".join([f"{f}:{l}" for f, l in locations[:3]])
            if len(locations) > 3:
                desc += "..."

            findings.append(Finding(
                "Medium", locations[0][0], f"{locations[0][1]}", "Structural Smell",
                desc,
                "Duplicated code violates DRY principle and complicates maintenance.", "High"
            ))

def detect_unused():
    # Pass 2: Check definitions against references
    # This is very noisy in Python due to dynamic nature.
    # We will only report if confidence is high (e.g. private methods starting with _)
    # or if we are very sure.
    # But instruction says "String-matched unused detection defaults to Low/Medium"

    for name, def_locs in definitions.items():
        if name not in references:
            # It's potentially unused.
            # Filter out magic methods
            if name.startswith('__') and name.endswith('__'):
                continue

            # Filter out common framework methods (e.g. get, post for flask views if likely)
            # Filter out standard library overrides?

            for fpath, lineno in def_locs:
                # If it's an __init__.py, it might be exporting symbols.
                if fpath.endswith('__init__.py'):
                    continue

                confidence = "Low"
                if name.startswith('_'):
                    confidence = "Medium" # Private method unused is more likely real

                # Instruction: "String-matched “unused” detection defaults to Low/Medium"

                findings.append(Finding(
                    "Low", fpath, str(lineno), "Dead Code",
                    f"Potential unused definition: `{name}`",
                    "Unused code adds noise and cognitive load.", confidence
                ))

def main():
    # 1. Walk files
    files_to_scan = []
    for root, dirs, files in os.walk("."):
        # Exclude dirs
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]

        for file in files:
            if file.endswith(".py") and file not in EXCLUDE_FILES:
                files_to_scan.append(os.path.join(root, file))

    # 2. Analyze each file
    for f in files_to_scan:
        analyze_file(f)

    # 3. Global analysis
    detect_duplicates()
    detect_unused()

    # 4. Generate Report
    report_path = "docs/audits/audit_stage_1.md"

    # Sort findings by severity then file
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    findings.sort(key=lambda x: (severity_order.get(x.severity, 3), x.file_path, x.line_range))

    # Summary stats
    total = len(findings)
    by_severity = collections.Counter(f.severity for f in findings)
    by_category = collections.Counter(f.category for f in findings)

    with open(report_path, "w", encoding='utf-8') as f:
        f.write("# Stage 1 Audit Report: Static Structural Analysis\n\n")

        f.write("## Summary\n")
        f.write(f"- **Total Findings:** {total}\n")
        f.write("- **By Severity:**\n")
        for sev in ["High", "Medium", "Low"]:
            f.write(f"  - {sev}: {by_severity[sev]}\n")
        f.write("- **By Category:**\n")
        for cat, count in by_category.most_common():
            f.write(f"  - {cat}: {count}\n")

        f.write("\n## Known Limitations\n")
        f.write("- **Unused Code Detection:** Uses simple string matching. High false positive rate for public APIs and dynamic calls.\n")
        f.write("- **Inconsistent Returns:** Does not perform type inference, only checks for presence/absence of return values.\n")
        f.write("- **Commented-out Code:** Heuristic-based, may miss some blocks or flag documentation.\n")
        f.write("- **Reachability:** Only checks simple control flow after return/raise/break/continue.\n")
        f.write("- **Scope:** Excludes tests and migrations.\n\n")

        f.write("## Detailed Findings\n\n")
        for finding in findings:
            f.write(finding.to_markdown())

if __name__ == "__main__":
    main()
