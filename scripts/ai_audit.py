#!/usr/bin/env python3
"""
AI-generated code auditor for AGT-2026.

Checks changed files against rules defined in:
  - docs/system-context.md
  - .github/copilot-instructions.md
"""

from __future__ import annotations

import ast
import os
import re
import sys


USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
RED = "\033[31m" if USE_COLOR else ""
YELLOW = "\033[33m" if USE_COLOR else ""
GREEN = "\033[32m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
RESET = "\033[0m" if USE_COLOR else ""

SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']', "hardcoded password"),
    (r'(?i)(secret|api_?key|apikey)\s*=\s*["\'][^"\']{8,}["\']', "hardcoded secret/API key"),
    (r'(?i)aws_access_key_id\s*=\s*["\'][A-Z0-9]{16,}["\']', "hardcoded AWS access key"),
    (r'(?i)aws_secret_access_key\s*=\s*["\'][^"\']{20,}["\']', "hardcoded AWS secret"),
    (r'sk_live_[A-Za-z0-9]{20,}', "Stripe live secret key"),
    (r'sk_test_[A-Za-z0-9]{20,}', "Stripe test secret key"),
    (r'(?i)(token)\s*=\s*["\'][A-Za-z0-9_\-\.]{16,}["\']', "hardcoded token"),
    (r'(?<![#])\b[A-Za-z0-9/+]{40,}={0,2}\b', "possible raw secret value"),
]

FRONTEND_BIZ_LOGIC_PATTERNS = [
    (r'(?i)(price|total|discount|tax|subtotal)\s*[\*\/\+\-]=?\s*\d', "pricing/math logic in frontend code"),
    (r'(?i)stripe\.(charges|paymentIntents)\.create', "Stripe charge creation in frontend"),
    (r'(?i)dynamodb|DocumentClient', "direct DynamoDB access in frontend"),
    (r'(?i)validatePayment|processPayment|calculatePrice|applyDiscount', "payment/pricing function in frontend"),
]

FORBIDDEN_DEP_PATTERNS = [
    (r'<script[^>]+src=["\']https?://', "external CDN script tag (not allowed in index.html)"),
    (r'require\s*\(\s*["\'](?!public/|backend/)', "non-Velo require() - may introduce untracked dependency"),
]

DUPLICATE_LOGIC_MIN_REPEATS = 3
DUPLICATE_LOGIC_MIN_LEN = 40
MAX_FUNCTION_LINES = 60
MAX_FUNCTION_NESTING = 4
IO_PATTERN = re.compile(
    r'wixData\.|dynamodb\.|fetch\s*\(|axios\.|http\.'
    r'|fs\.(?:readFile|writeFile|appendFile|unlink|mkdir)'
    r'|wixFetch\.|request\s*\(|pool\.query|client\.query|db\.'
)


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError as exc:
        print(f"{YELLOW}[SKIP]{RESET} Cannot read {path}: {exc}")
        return None


def _is_frontend_file(path: str) -> bool:
    lowered = path.lower()
    return (
        lowered.endswith("index.html")
        or "/pages/" in lowered
        or lowered.endswith(".html")
        or (lowered.endswith(".js") and "/src/pages/" in lowered)
        or (lowered.endswith(".js") and "/src/public/" in lowered)
    )


def _is_backend_file(path: str) -> bool:
    lowered = path.lower()
    return (
        lowered.endswith(".jsw")
        or "/backend/" in lowered
        or (lowered.endswith(".py") and "/lambda" in lowered)
        or (lowered.endswith(".py") and "handler" in os.path.basename(lowered))
    )


def _line_pattern_violations(
    source: str,
    patterns: list[tuple[str, str]],
    skip_prefixes: tuple[str, ...],
    placeholder_tokens: tuple[str, ...] = (),
) -> list[str]:
    violations = []
    for lineno, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(skip_prefixes):
            continue
        if placeholder_tokens and any(token in line for token in placeholder_tokens):
            continue
        for pattern, label in patterns:
            if re.search(pattern, line):
                violations.append(f"  line {lineno}: {label} - {stripped[:80]}")
    return violations


def check_secrets(path: str, source: str) -> list[str]:
    del path
    return _line_pattern_violations(
        source,
        SECRET_PATTERNS,
        ("#", "//", "*", "<!--"),
        ("YOUR_", "YOURHANDLE", "<YOUR", "example", "placeholder"),
    )


def check_duplicate_logic(path: str, source: str) -> list[str]:
    del path
    freq: dict[str, list[int]] = {}
    for lineno, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith(("#", "//", "import ", "from ", "<!--", "*"))
            or len(stripped) < DUPLICATE_LOGIC_MIN_LEN
        ):
            continue
        freq.setdefault(stripped, []).append(lineno)

    violations = []
    for expr, occurrences in freq.items():
        if len(occurrences) >= DUPLICATE_LOGIC_MIN_REPEATS:
            violations.append(f"  Repeated {len(occurrences)}x (lines {occurrences}): {expr[:80]}")
    return violations


def check_function_complexity_python(path: str, source: str) -> list[str]:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        length = end - start + 1
        if length > MAX_FUNCTION_LINES:
            violations.append(f"  function '{node.name}' at line {start} is {length} lines (max {MAX_FUNCTION_LINES})")
        depth = _max_nesting(node)
        if depth > MAX_FUNCTION_NESTING:
            violations.append(f"  function '{node.name}' at line {start} has nesting depth {depth} (max {MAX_FUNCTION_NESTING})")
    return violations


def _max_nesting(node: ast.AST, current: int = 0) -> int:
    block_nodes = (
        ast.If,
        ast.For,
        ast.While,
        ast.With,
        ast.Try,
        ast.ExceptHandler,
        ast.AsyncFor,
        ast.AsyncWith,
    )
    max_depth = current
    for child in ast.iter_child_nodes(node):
        next_depth = current + 1 if isinstance(child, block_nodes) else current
        max_depth = max(max_depth, _max_nesting(child, next_depth))
    return max_depth


def check_function_complexity_js(path: str, source: str) -> list[str]:
    del path
    func_re = re.compile(
        r'(?:^|\s)(?:async\s+)?(?:function\s+(\w+)'
        r'|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>|\w+\s*=>))',
        re.MULTILINE,
    )
    lines = source.splitlines()
    violations = []
    for match in func_re.finditer(source):
        name = match.group(1) or match.group(2) or "<anonymous>"
        start_line = source.count("\n", 0, match.start())
        end_line = _matching_brace_line(lines, start_line)
        length = end_line - start_line + 1
        if length > MAX_FUNCTION_LINES:
            violations.append(f"  function '{name}' at line {start_line + 1} is ~{length} lines (max {MAX_FUNCTION_LINES})")
    return violations


def _matching_brace_line(lines: list[str], start_line: int) -> int:
    brace_depth = 0
    end_line = start_line
    found_open = False
    for lineno, line in enumerate(lines[start_line:], start_line):
        brace_depth += line.count("{") - line.count("}")
        if not found_open and "{" in line:
            found_open = True
        if found_open and brace_depth <= 0:
            end_line = lineno
            break
    return end_line


def check_frontend_biz_logic(path: str, source: str) -> list[str]:
    if not _is_frontend_file(path):
        return []
    return _line_pattern_violations(source, FRONTEND_BIZ_LOGIC_PATTERNS, ("#", "//", "<!--", "*"))


def check_unnecessary_deps(path: str, source: str) -> list[str]:
    del path
    return _line_pattern_violations(source, FORBIDDEN_DEP_PATTERNS, ("#", "//", "<!--"))


def _js_body_lines(source: str, lines: list[str], match: re.Match) -> list[str]:
    start_line = source.count("\n", 0, match.start())
    brace_depth = 0
    found_open = False
    body_lines = []
    for line in lines[start_line:]:
        brace_depth += line.count("{") - line.count("}")
        if not found_open and "{" in line:
            found_open = True
        body_lines.append(line)
        if found_open and brace_depth <= 0:
            break
    return body_lines


def _declared_param_names(params: str) -> list[str]:
    names = []
    for raw in params.split(","):
        cleaned = raw.strip().split("=")[0].strip().split(":")[0].strip()
        cleaned = re.sub(r'^[{[\.\s]+|[}\]\s]+$', '', cleaned)
        if re.match(r'^[A-Za-z_]\w*$', cleaned):
            names.append(cleaned)
    return names


def _guard_regex(param_names: list[str]) -> re.Pattern[str]:
    param_pattern = "(?:" + "|".join(re.escape(name) for name in param_names) + ")"
    guard_pattern = (
        r'if\s*\(.*' + param_pattern + r'.*(?:=== undefined|== null|typeof|\.trim\(\)|isNaN)'
        + r'|if\s*\(!\s*' + param_pattern
        + r'|' + param_pattern + r'\s*(?:===|!==|==|!=)\s*(?:null|undefined)'
        + r'|typeof\s+' + param_pattern
    )
    return re.compile(guard_pattern)


def check_input_validation(path: str, source: str) -> list[str]:
    if not _is_backend_file(path):
        return []

    exported_func_re = re.compile(r'export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', re.MULTILINE)
    lines = source.splitlines()
    violations = []
    for match in exported_func_re.finditer(source):
        fname = match.group(1)
        params = match.group(2).strip()
        if not params:
            continue
        param_names = _declared_param_names(params)
        if not param_names:
            continue
        body_lines = _js_body_lines(source, lines, match)
        body = "\n".join(body_lines)
        has_validation = any(_guard_regex(param_names).search(line) for line in body_lines)
        if _has_io_call(body) and not has_validation:
            violations.append(f"  exported function '{fname}' performs I/O but has no input validation guard")
    return violations


def _has_io_call(body: str) -> bool:
    return bool(IO_PATTERN.search(body))


CHECKS = [
    ("Hardcoded Secrets", check_secrets),
    ("Duplicate Logic", check_duplicate_logic),
    ("Unnecessary Dependencies", check_unnecessary_deps),
    ("Frontend Business Logic", check_frontend_biz_logic),
    ("Missing Input Validation", check_input_validation),
]

COMPLEXITY_CHECKS = {
    ".py": check_function_complexity_python,
    ".js": check_function_complexity_js,
    ".jsw": check_function_complexity_js,
    ".ts": check_function_complexity_js,
    ".tsx": check_function_complexity_js,
}


def audit_file(path: str) -> dict[str, list[str]]:
    source = _read(path)
    if source is None:
        return {}

    results: dict[str, list[str]] = {}
    for name, check in CHECKS:
        found = check(path, source)
        if found:
            results[name] = found

    extension = os.path.splitext(path)[1].lower()
    if extension in COMPLEXITY_CHECKS:
        found = COMPLEXITY_CHECKS[extension](path, source)
        if found:
            results["Function Complexity"] = found

    return results


def main() -> int:
    files = sys.argv[1:]
    if not files:
        print(f"{YELLOW}No files provided - nothing to audit.{RESET}")
        return 0

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  AGT AI-Generated Code Audit{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    total_violations = 0
    summary_lines = []
    for path in files:
        if not os.path.isfile(path):
            print(f"{YELLOW}[SKIP]{RESET} {path} - not a regular file\n")
            continue

        print(f"{BOLD}Auditing:{RESET} {path}")
        results = audit_file(path)
        if not results:
            print(f"  {GREEN}[OK] No violations found{RESET}\n")
            continue

        for rule, violations in results.items():
            total_violations += len(violations)
            print(f"  {RED}[FAIL] [{rule}]{RESET} - {len(violations)} violation(s):")
            for violation in violations:
                print(f"    {violation}")
            summary_lines.append(f"  {path}  ->  [{rule}] {len(violations)} violation(s)")
        print()

    print(f"{BOLD}{'=' * 60}{RESET}")
    if total_violations == 0:
        print(f"{GREEN}{BOLD}  AUDIT PASSED - 0 violations found across {len(files)} file(s){RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}\n")
        return 0

    print(f"{RED}{BOLD}  AUDIT FAILED - {total_violations} violation(s) found{RESET}")
    print()
    for line in summary_lines:
        print(f"{RED}{line}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
