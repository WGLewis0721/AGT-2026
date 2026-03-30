#!/usr/bin/env python3
"""
AI-Generated Code Auditor — AGT-2026
=====================================
Checks changed files against rules defined in:
  - docs/system-context.md
  - .github/copilot-instructions.md

Usage:
    python scripts/ai_audit.py <file1> [file2 ...]

Exits with 0 if all checks pass, 1 if any violation is found.
"""

import re
import sys
import ast
import os

# ─── Colour helpers ────────────────────────────────────────────────────────────
RED    = "\033[31m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ─── Constants ─────────────────────────────────────────────────────────────────

# Patterns that suggest hardcoded secrets
SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']',   "hardcoded password"),
    (r'(?i)(secret|api_?key|apikey)\s*=\s*["\'][^"\']{8,}["\']', "hardcoded secret/API key"),
    (r'(?i)aws_access_key_id\s*=\s*["\'][A-Z0-9]{16,}["\']',    "hardcoded AWS access key"),
    (r'(?i)aws_secret_access_key\s*=\s*["\'][^"\']{20,}["\']',  "hardcoded AWS secret"),
    (r'sk_live_[A-Za-z0-9]{20,}',                                "Stripe live secret key"),
    (r'sk_test_[A-Za-z0-9]{20,}',                                "Stripe test secret key"),
    (r'(?i)(token)\s*=\s*["\'][A-Za-z0-9_\-\.]{16,}["\']',      "hardcoded token"),
    # Generic 40+ char hex/base64 that looks like a real secret (but exclude SHA hashes in comments)
    (r'(?<![#])\b[A-Za-z0-9/+]{40,}={0,2}\b',                   "possible raw secret value"),
]

# Patterns that represent frontend business logic (banned per system-context.md)
FRONTEND_BIZ_LOGIC_PATTERNS = [
    (r'(?i)(price|total|discount|tax|subtotal)\s*[\*\/\+\-]=?\s*\d',
     "pricing/math logic in frontend code"),
    (r'(?i)stripe\.(charges|paymentIntents)\.create',
     "Stripe charge creation in frontend"),
    (r'(?i)dynamodb|DocumentClient',
     "direct DynamoDB access in frontend"),
    (r'(?i)validatePayment|processPayment|calculatePrice|applyDiscount',
     "payment/pricing function in frontend"),
]

# Patterns that indicate unnecessary external dependencies in static/frontend files
FORBIDDEN_DEP_PATTERNS = [
    (r'<script[^>]+src=["\']https?://',   "external CDN script tag (not allowed in index.html)"),
    (r'require\s*\(\s*["\'](?!public/|backend/)',
     "non-Velo require() — may introduce untracked dependency"),
]

# Duplicate logic: identical non-trivial expressions repeated 3+ times signal copy-paste
DUPLICATE_LOGIC_MIN_REPEATS = 3
DUPLICATE_LOGIC_MIN_LEN     = 40   # characters

# Python/JS function complexity thresholds
MAX_FUNCTION_LINES   = 60
MAX_FUNCTION_NESTING = 4   # Python only

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _is_frontend_file(path: str) -> bool:
    """Return True for files that must NOT contain business logic."""
    p = path.lower()
    return (
        p.endswith("index.html")
        or "/pages/" in p
        or p.endswith(".html")
        or (p.endswith(".js") and "/src/pages/" in p)
        or (p.endswith(".js") and "/src/public/" in p)
    )

def _read(path: str):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        print(f"{YELLOW}[SKIP]{RESET} Cannot read {path}: {exc}")
        return None


# ─── Check 1 — hardcoded secrets ───────────────────────────────────────────────

def check_secrets(path: str, source: str) -> list[str]:
    violations = []
    lines = source.splitlines()
    for lineno, line in enumerate(lines, 1):
        # Skip obvious placeholder lines and comment-only lines
        stripped = line.strip()
        if stripped.startswith(("#", "//", "*", "<!--")) :
            continue
        if any(ph in line for ph in ("YOUR_", "YOURHANDLE", "<YOUR", "example", "placeholder")):
            continue
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, line):
                violations.append(f"  line {lineno}: {label} — {stripped[:80]}")
    return violations


# ─── Check 2 — duplicate logic ─────────────────────────────────────────────────

def check_duplicate_logic(path: str, source: str) -> list[str]:
    """Detect non-trivial lines/expressions repeated >= DUPLICATE_LOGIC_MIN_REPEATS times."""
    violations = []
    lines = source.splitlines()

    freq: dict[str, list[int]] = {}
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip blank, comments, imports, single-token lines
        if (
            not stripped
            or stripped.startswith(("#", "//", "import ", "from ", "<!--", "*"))
            or len(stripped) < DUPLICATE_LOGIC_MIN_LEN
        ):
            continue
        freq.setdefault(stripped, []).append(lineno)

    for expr, occurrences in freq.items():
        if len(occurrences) >= DUPLICATE_LOGIC_MIN_REPEATS:
            violations.append(
                f"  Repeated {len(occurrences)}× (lines {occurrences}): {expr[:80]}"
            )
    return violations


# ─── Check 3 — large / complex functions ───────────────────────────────────────

def check_function_complexity_python(path: str, source: str) -> list[str]:
    """AST-based check for Python: function line-length and max nesting depth."""
    violations = []
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.lineno
        end   = getattr(node, "end_lineno", start)
        length = end - start + 1
        if length > MAX_FUNCTION_LINES:
            violations.append(
                f"  function '{node.name}' at line {start} is {length} lines "
                f"(max {MAX_FUNCTION_LINES})"
            )

        # Nesting depth
        depth = _max_nesting(node)
        if depth > MAX_FUNCTION_NESTING:
            violations.append(
                f"  function '{node.name}' at line {start} has nesting depth {depth} "
                f"(max {MAX_FUNCTION_NESTING})"
            )
    return violations


def _max_nesting(node: ast.AST, current: int = 0) -> int:
    BLOCK_NODES = (ast.If, ast.For, ast.While, ast.With, ast.Try,
                   ast.ExceptHandler, ast.AsyncFor, ast.AsyncWith)
    max_depth = current
    for child in ast.iter_child_nodes(node):
        if isinstance(child, BLOCK_NODES):
            max_depth = max(max_depth, _max_nesting(child, current + 1))
        else:
            max_depth = max(max_depth, _max_nesting(child, current))
    return max_depth


def check_function_complexity_js(path: str, source: str) -> list[str]:
    """Heuristic JS/TS check: count lines between function open/close braces."""
    violations = []
    # Match named function declarations and arrow functions assigned to variables
    func_re = re.compile(
        r'(?:^|\s)'
        r'(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>|\w+\s*=>))',
        re.MULTILINE,
    )
    lines = source.splitlines()
    for m in func_re.finditer(source):
        name = m.group(1) or m.group(2) or "<anonymous>"
        start_line = source.count("\n", 0, m.start())
        # Walk forward to find matching closing brace
        brace_depth = 0
        end_line    = start_line
        found_open  = False
        for i, line in enumerate(lines[start_line:], start_line):
            brace_depth += line.count("{") - line.count("}")
            if not found_open and "{" in line:
                found_open = True
            if found_open and brace_depth <= 0:
                end_line = i
                break
        length = end_line - start_line + 1
        if length > MAX_FUNCTION_LINES:
            violations.append(
                f"  function '{name}' at line {start_line + 1} is ~{length} lines "
                f"(max {MAX_FUNCTION_LINES})"
            )
    return violations


# ─── Check 4 — frontend business logic ─────────────────────────────────────────

def check_frontend_biz_logic(path: str, source: str) -> list[str]:
    if not _is_frontend_file(path):
        return []
    violations = []
    lines = source.splitlines()
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("#", "//", "<!--", "*")):
            continue
        for pattern, label in FRONTEND_BIZ_LOGIC_PATTERNS:
            if re.search(pattern, line):
                violations.append(f"  line {lineno}: {label} — {stripped[:80]}")
    return violations


# ─── Check 5 — unnecessary dependencies ────────────────────────────────────────

def check_unnecessary_deps(path: str, source: str) -> list[str]:
    violations = []
    lines = source.splitlines()
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("#", "//", "<!--")):
            continue
        for pattern, label in FORBIDDEN_DEP_PATTERNS:
            if re.search(pattern, line):
                violations.append(f"  line {lineno}: {label} — {stripped[:80]}")
    return violations


# ─── Check 6 — missing input validation ────────────────────────────────────────

def check_input_validation(path: str, source: str) -> list[str]:
    """
    Heuristic: backend functions that accept parameters should contain
    at least one guard/validation expression before performing I/O operations.
    """
    violations = []

    # Only audit backend files
    p = path.lower()
    is_backend = (
        p.endswith(".jsw")
        or "/backend/" in p
        or (p.endswith(".py") and "/lambda" in p)
        or (p.endswith(".py") and "handler" in os.path.basename(p))
    )
    if not is_backend:
        return []

    # Look for exported/public JS functions that do I/O without guards
    exported_func_re = re.compile(
        r'export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
        re.MULTILINE,
    )
    lines = source.splitlines()

    for m in exported_func_re.finditer(source):
        fname   = m.group(1)
        params  = m.group(2).strip()
        if not params:
            continue  # no params → nothing to validate

        start_line = source.count("\n", 0, m.start())
        # Collect body lines until matching close brace
        brace_depth = 0
        body_lines  = []
        found_open  = False
        for line in lines[start_line:]:
            brace_depth += line.count("{") - line.count("}")
            if not found_open and "{" in line:
                found_open = True
            body_lines.append(line)
            if found_open and brace_depth <= 0:
                break

        # Extract bare parameter names (strip defaults, types, destructuring brackets)
        param_names = []
        for raw in params.split(","):
            raw = raw.strip()
            # Strip default value: name = default
            raw = raw.split("=")[0].strip()
            # Strip type annotation: name: Type
            raw = raw.split(":")[0].strip()
            # Strip destructuring / rest operator
            raw = re.sub(r'^[{[\.\s]+|[}\]\s]+$', '', raw)
            if re.match(r'^[A-Za-z_]\w*$', raw):
                param_names.append(raw)

        if not param_names:
            continue  # Could not identify param names — skip

        body = "\n".join(body_lines)

        # A guard must appear on a single line that both references a declared
        # parameter AND contains a typical validation operator.  We intentionally
        # avoid re.DOTALL so that `.*` doesn't span lines and create false positives.
        pp = "(?:" + "|".join(re.escape(p) for p in param_names) + ")"
        guard_pattern = (
            r'if\s*\(.*' + pp + r'.*(?:=== undefined|== null|typeof|\.trim\(\)|isNaN)'
            + r'|if\s*\(!\s*' + pp
            + r'|' + pp + r'\s*(?:===|!==|==|!=)\s*(?:null|undefined)'
            + r'|typeof\s+' + pp
        )
        guard_re = re.compile(guard_pattern)
        has_validation = any(guard_re.search(line) for line in body_lines)
        has_io = bool(re.search(
            r'wixData\.|dynamodb\.|fetch\s*\(|axios\.|http\.'
            r'|fs\.(?:readFile|writeFile|appendFile|unlink|mkdir)'
            r'|wixFetch\.|request\s*\('
            r'|pool\.query|client\.query|db\.',
            body,
        ))
        if has_io and not has_validation:
            violations.append(
                f"  exported function '{fname}' performs I/O but has no input validation guard"
            )

    return violations


# ─── Runner ────────────────────────────────────────────────────────────────────

CHECKS = [
    ("Hardcoded Secrets",           check_secrets),
    ("Duplicate Logic",             check_duplicate_logic),
    ("Unnecessary Dependencies",    check_unnecessary_deps),
    ("Frontend Business Logic",     check_frontend_biz_logic),
    ("Missing Input Validation",    check_input_validation),
]

COMPLEXITY_CHECKS = {
    ".py":  check_function_complexity_python,
    ".js":  check_function_complexity_js,
    ".jsw": check_function_complexity_js,
    ".ts":  check_function_complexity_js,
    ".tsx": check_function_complexity_js,
}


def audit_file(path: str) -> dict:
    source = _read(path)
    if source is None:
        return {}

    results = {}

    # Run generic checks
    for name, fn in CHECKS:
        found = fn(path, source)
        if found:
            results[name] = found

    # Run complexity check based on file type
    ext = os.path.splitext(path)[1].lower()
    if ext in COMPLEXITY_CHECKS:
        found = COMPLEXITY_CHECKS[ext](path, source)
        if found:
            results["Function Complexity"] = found

    return results


def main() -> int:
    files = sys.argv[1:]
    if not files:
        print(f"{YELLOW}No files provided — nothing to audit.{RESET}")
        return 0

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  AGT AI-Generated Code Audit{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    total_violations = 0
    summary_lines    = []

    for path in files:
        if not os.path.isfile(path):
            print(f"{YELLOW}[SKIP]{RESET} {path} — not a regular file\n")
            continue

        print(f"{BOLD}Auditing:{RESET} {path}")
        results = audit_file(path)

        if not results:
            print(f"  {GREEN}✓ No violations found{RESET}\n")
            continue

        for rule, violations in results.items():
            count = len(violations)
            total_violations += count
            print(f"  {RED}✗ [{rule}]{RESET} — {count} violation(s):")
            for v in violations:
                print(f"    {v}")
            summary_lines.append(f"  {path}  →  [{rule}] {count} violation(s)")
        print()

    print(f"{BOLD}{'=' * 60}{RESET}")
    if total_violations == 0:
        print(f"{GREEN}{BOLD}  AUDIT PASSED — 0 violations found across {len(files)} file(s){RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}\n")
        return 0
    else:
        print(f"{RED}{BOLD}  AUDIT FAILED — {total_violations} violation(s) found{RESET}")
        print()
        for line in summary_lines:
            print(f"{RED}{line}{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
