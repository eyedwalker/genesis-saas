"""Code Quality MCP Server — real code analysis tools.

Gives Claude's quality assistants actual power:
- Measure cyclomatic/cognitive complexity per function
- Detect code duplication
- Analyze import structure and circular dependencies
- Calculate maintainability index
- Run pattern matching for anti-patterns
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


# ── Complexity Analyzer ───────────────────────────────────────────────────────

@tool(
    "measure_complexity",
    "Measure cyclomatic and cognitive complexity of Python functions/methods. Flags functions exceeding thresholds.",
    {"code": str, "filename": str, "max_cyclomatic": int, "max_cognitive": int},
)
async def measure_complexity(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    filename = args.get("filename", "unknown.py")
    max_cyclo = args.get("max_cyclomatic", 10)
    max_cognitive = args.get("max_cognitive", 15)

    functions = []

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"content": [{"type": "text", "text": json.dumps({
            "error": f"Syntax error: {e}", "file": filename
        })}]}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Cyclomatic complexity: count decision points
            cyclo = 1  # Base complexity
            cognitive = 0
            nesting = 0

            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.IfExp)):
                    cyclo += 1
                    cognitive += 1 + nesting
                elif isinstance(child, (ast.For, ast.While, ast.AsyncFor)):
                    cyclo += 1
                    cognitive += 1 + nesting
                    nesting += 1
                elif isinstance(child, ast.ExceptHandler):
                    cyclo += 1
                    cognitive += 1 + nesting
                elif isinstance(child, (ast.And, ast.Or)):
                    cyclo += 1
                    cognitive += 1
                elif isinstance(child, ast.BoolOp):
                    cyclo += len(child.values) - 1

            # Count lines
            lines = node.end_lineno - node.lineno + 1 if node.end_lineno else 0

            func_data = {
                "name": node.name,
                "line": node.lineno,
                "lines": lines,
                "cyclomatic": cyclo,
                "cognitive": cognitive,
                "params": len(node.args.args),
                "exceeds_cyclomatic": cyclo > max_cyclo,
                "exceeds_cognitive": cognitive > max_cognitive,
                "exceeds_length": lines > 50,
            }

            if cyclo > max_cyclo or cognitive > max_cognitive or lines > 50:
                func_data["severity"] = "high" if cyclo > max_cyclo * 2 else "medium"
                func_data["suggestions"] = []
                if cyclo > max_cyclo:
                    func_data["suggestions"].append(f"Extract methods to reduce cyclomatic complexity ({cyclo} > {max_cyclo})")
                if cognitive > max_cognitive:
                    func_data["suggestions"].append(f"Reduce nesting to lower cognitive complexity ({cognitive} > {max_cognitive})")
                if lines > 50:
                    func_data["suggestions"].append(f"Function is {lines} lines — extract logical sections")

            functions.append(func_data)

    violations = [f for f in functions if f.get("exceeds_cyclomatic") or f.get("exceeds_cognitive") or f.get("exceeds_length")]

    return {
        "content": [{"type": "text", "text": json.dumps({
            "file": filename,
            "functions_analyzed": len(functions),
            "violations": len(violations),
            "functions": sorted(functions, key=lambda f: f["cyclomatic"], reverse=True),
            "summary": {
                "avg_cyclomatic": round(sum(f["cyclomatic"] for f in functions) / max(1, len(functions)), 1),
                "max_cyclomatic": max((f["cyclomatic"] for f in functions), default=0),
                "avg_lines": round(sum(f["lines"] for f in functions) / max(1, len(functions)), 1),
                "total_functions": len(functions),
            },
        }, indent=2)}]
    }


# ── Duplication Detector ──────────────────────────────────────────────────────

@tool(
    "detect_duplication",
    "Detect code duplication across files. Finds repeated blocks of 3+ lines that should be extracted into shared functions.",
    {"files": str},
)
async def detect_duplication(args: dict[str, Any]) -> dict[str, Any]:
    files_input = args["files"]

    # Parse files from JSON or delimited format
    try:
        files = json.loads(files_input)
    except json.JSONDecodeError:
        files = {"input": files_input}

    # Normalize lines and find duplicates
    all_blocks: list[tuple[str, str, int, list[str]]] = []  # (file, content, line, lines)

    for filename, content in files.items():
        lines = content.split("\n")
        for i in range(len(lines) - 2):
            # Create 3-line blocks (minimum duplication unit)
            block = lines[i:i+3]
            normalized = "\n".join(l.strip() for l in block if l.strip())
            if len(normalized) > 30:  # Skip trivial blocks
                all_blocks.append((filename, normalized, i + 1, block))

    # Find duplicates
    from collections import Counter
    block_counter = Counter(b[1] for b in all_blocks)
    duplicates = []

    seen = set()
    for filename, normalized, line, block_lines in all_blocks:
        if block_counter[normalized] > 1 and normalized not in seen:
            locations = [
                {"file": f, "line": l}
                for f, n, l, _ in all_blocks
                if n == normalized
            ]
            if len(locations) > 1:
                duplicates.append({
                    "code": "\n".join(block_lines),
                    "occurrences": len(locations),
                    "locations": locations[:5],
                    "suggestion": "Extract into a shared function/utility",
                })
                seen.add(normalized)

    return {
        "content": [{"type": "text", "text": json.dumps({
            "files_analyzed": len(files),
            "duplicate_blocks": len(duplicates),
            "duplicates": duplicates[:20],
            "recommendation": "Extract duplicated code into shared modules" if duplicates else "No significant duplication detected",
        }, indent=2)}]
    }


# ── Anti-Pattern Detector ─────────────────────────────────────────────────────

@tool(
    "detect_antipatterns",
    "Scan code for common anti-patterns: god objects, feature envy, long parameter lists, primitive obsession, and more.",
    {"code": str, "filename": str, "language": str},
)
async def detect_antipatterns(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    filename = args.get("filename", "unknown")
    language = args.get("language", "python")
    findings = []

    lines = code.split("\n")
    total_lines = len(lines)

    # God object: class with too many methods/attributes
    if language == "python":
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    attrs = [n for n in node.body if isinstance(n, ast.Assign)]
                    class_lines = (node.end_lineno or 0) - node.lineno
                    if len(methods) > 10:
                        findings.append({
                            "pattern": "God Object",
                            "location": f"{filename}:{node.lineno}",
                            "detail": f"Class {node.name} has {len(methods)} methods — extract responsibilities",
                            "severity": "high",
                        })
                    if class_lines > 300:
                        findings.append({
                            "pattern": "Large Class",
                            "location": f"{filename}:{node.lineno}",
                            "detail": f"Class {node.name} is {class_lines} lines — split into focused classes",
                            "severity": "medium",
                        })

                    # Long parameter lists
                    for method in methods:
                        params = len(method.args.args)
                        if params > 5:
                            findings.append({
                                "pattern": "Long Parameter List",
                                "location": f"{filename}:{method.lineno}",
                                "detail": f"{node.name}.{method.name}() has {params} params — use a parameter object",
                                "severity": "medium",
                            })
        except SyntaxError:
            pass

    # Magic numbers
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        numbers = re.findall(r'(?<!["\'\w])(\d{2,})(?!["\'\w])', stripped)
        for num in numbers:
            if num not in ("100", "200", "201", "400", "401", "403", "404", "500"):  # HTTP status codes OK
                findings.append({
                    "pattern": "Magic Number",
                    "location": f"{filename}:{i}",
                    "detail": f"Magic number {num} — extract to named constant",
                    "severity": "low",
                })

    # Deep nesting
    max_indent = 0
    for i, line in enumerate(lines, 1):
        if line.strip():
            indent = len(line) - len(line.lstrip())
            spaces = indent // 4 if language == "python" else indent // 2
            if spaces > 4:
                if spaces > max_indent:
                    max_indent = spaces
                    findings.append({
                        "pattern": "Deep Nesting",
                        "location": f"{filename}:{i}",
                        "detail": f"Nesting depth {spaces} — use guard clauses or extract methods",
                        "severity": "medium",
                    })

    return {
        "content": [{"type": "text", "text": json.dumps({
            "file": filename,
            "total_lines": total_lines,
            "findings": findings[:30],
            "findings_count": len(findings),
            "by_pattern": {p: len([f for f in findings if f["pattern"] == p]) for p in set(f["pattern"] for f in findings)},
        }, indent=2)}]
    }


# ── Maintainability Index ─────────────────────────────────────────────────────

@tool(
    "maintainability_index",
    "Calculate the Maintainability Index (MI) for code. Based on Halstead volume, cyclomatic complexity, and lines of code. Score 0-100, higher is better.",
    {"code": str, "filename": str},
)
async def maintainability_index(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    filename = args.get("filename", "unknown")

    lines = [l for l in code.split("\n") if l.strip() and not l.strip().startswith("#")]
    loc = len(lines)

    # Simplified Halstead volume estimation
    operators = len(re.findall(r'[+\-*/=<>!&|^~%]|and|or|not|in|is', code))
    operands = len(re.findall(r'\b[a-zA-Z_]\w*\b', code))
    volume = (operators + operands) * 1.0  # Simplified

    # Cyclomatic complexity (whole file)
    cyclo = 1 + len(re.findall(
        r'\b(?:if|elif|else|for|while|except|and|or|case)\b', code
    ))

    # Maintainability Index formula (simplified SEI version)
    import math
    mi = max(0, min(100, int(
        171
        - 5.2 * math.log(max(1, volume))
        - 0.23 * cyclo
        - 16.2 * math.log(max(1, loc))
    ) * 100 / 171))

    grade = "A" if mi >= 80 else "B" if mi >= 60 else "C" if mi >= 40 else "D" if mi >= 20 else "F"

    return {
        "content": [{"type": "text", "text": json.dumps({
            "file": filename,
            "maintainability_index": mi,
            "grade": grade,
            "metrics": {
                "lines_of_code": loc,
                "cyclomatic_complexity": cyclo,
                "halstead_volume": round(volume, 1),
            },
            "interpretation": {
                "A (80-100)": "Highly maintainable",
                "B (60-79)": "Moderately maintainable",
                "C (40-59)": "Difficult to maintain",
                "D (20-39)": "Very difficult to maintain",
                "F (0-19)": "Unmaintainable — refactor urgently",
            },
        }, indent=2)}]
    }


# ── Create the MCP Server ────────────────────────────────────────────────────

code_quality_server = create_sdk_mcp_server(
    name="genesis-code-quality",
    version="1.0.0",
    tools=[measure_complexity, detect_duplication, detect_antipatterns, maintainability_index],
)
