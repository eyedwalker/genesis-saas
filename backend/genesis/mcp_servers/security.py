"""Security MCP Server — real security analysis tools.

Gives Claude's security assistant actual power:
- Scan code for OWASP Top 10 vulnerabilities
- Audit dependencies for known CVEs
- Check for secrets/credentials in code
- Analyze authentication patterns
- Generate security headers config
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


# ── Secret Detection ──────────────────────────────────────────────────────────

SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', "API Key"),
    (r'(?i)(secret|password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']', "Password/Secret"),
    (r'(?i)(aws_access_key_id)\s*[=:]\s*["\']?(AKIA[A-Z0-9]{16})["\']?', "AWS Access Key"),
    (r'(?i)(aws_secret_access_key)\s*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', "AWS Secret Key"),
    (r'sk-[a-zA-Z0-9]{48,}', "OpenAI/Anthropic API Key"),
    (r'ghp_[a-zA-Z0-9]{36,}', "GitHub Personal Access Token"),
    (r'(?i)(private[_-]?key)\s*[=:]\s*["\']([^"\']{20,})["\']', "Private Key"),
    (r'(?i)Bearer\s+[a-zA-Z0-9\-._~+/]+=*', "Bearer Token"),
    (r'(?i)(database_url|db_url|connection_string)\s*[=:]\s*["\']([^"\']+)["\']', "Database URL"),
    (r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----', "PEM Private Key"),
]


@tool(
    "scan_secrets",
    "Scan code for hardcoded secrets, API keys, passwords, and credentials. Returns findings with file locations and severity.",
    {"code": str, "filename": str},
)
async def scan_secrets(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    filename = args.get("filename", "unknown")
    findings = []

    for pattern, secret_type in SECRET_PATTERNS:
        for match in re.finditer(pattern, code):
            line_num = code[:match.start()].count("\n") + 1
            # Redact the actual secret
            context = match.group(0)
            if len(context) > 20:
                context = context[:10] + "..." + context[-5:]
            findings.append({
                "type": secret_type,
                "file": filename,
                "line": line_num,
                "severity": "critical",
                "context": context,
                "recommendation": f"Remove hardcoded {secret_type}. Use environment variables or a secrets manager.",
            })

    return {
        "content": [{"type": "text", "text": json.dumps({
            "scan": "secrets",
            "file": filename,
            "findings_count": len(findings),
            "findings": findings,
            "clean": len(findings) == 0,
        }, indent=2)}]
    }


# ── OWASP Vulnerability Scanner ───────────────────────────────────────────────

OWASP_PATTERNS = {
    "A01_Broken_Access_Control": [
        (r'\.role\s*===?\s*["\']admin["\']', "Hardcoded role check — use RBAC middleware"),
        (r'req\.user\.id\s*(!==?|===?)\s*', "Direct user ID comparison — verify ownership in data layer"),
        (r'(?i)@public|no.?auth|skip.?auth', "Public endpoint marker — verify intentional"),
    ],
    "A02_Cryptographic_Failures": [
        (r'(?i)md5|sha1(?![\w])', "Weak hash algorithm — use bcrypt/argon2 for passwords, SHA-256+ for data"),
        (r'(?i)aes.?ecb|DES|RC4', "Weak encryption — use AES-GCM or ChaCha20"),
        (r'(?i)http://', "Insecure HTTP — use HTTPS"),
    ],
    "A03_Injection": [
        (r'f["\'].*\{.*\}.*(?:SELECT|INSERT|UPDATE|DELETE|WHERE)', "SQL injection risk — use parameterized queries"),
        (r'\.format\(.*\).*(?:SELECT|INSERT|UPDATE|DELETE)', "SQL injection via format string"),
        (r'eval\(|exec\(|subprocess\.call\(.*shell\s*=\s*True', "Command injection risk — avoid eval/exec, use subprocess with shell=False"),
        (r'innerHTML\s*=|dangerouslySetInnerHTML|v-html', "XSS risk — sanitize HTML input"),
        (r'\.raw\(|\.rawQuery\(|\.execute\(.*%s', "Raw query — use ORM or parameterized queries"),
    ],
    "A04_Insecure_Design": [
        (r'(?i)rate.?limit|throttl', None),  # Positive check — presence is good
        (r'(?i)(?<!re)try:\s*\n\s*(?:.*\n){0,3}\s*except\s*:', "Bare except — catch specific exceptions"),
    ],
    "A05_Security_Misconfiguration": [
        (r'(?i)debug\s*=\s*True|DEBUG\s*=\s*1|FLASK_DEBUG', "Debug mode enabled — disable in production"),
        (r'(?i)cors.*\*|allow_all|Access-Control-Allow-Origin:\s*\*', "CORS wildcard — restrict to specific origins"),
        (r'(?i)stacktrace|stack_trace|traceback', "Stack traces exposed — hide in production"),
    ],
    "A07_Auth_Failures": [
        (r'(?i)password.*=\s*["\'][^"\']{0,7}["\']', "Weak password — enforce minimum 8 characters"),
        (r'(?i)jwt\.decode.*verify\s*=\s*False', "JWT verification disabled — always verify"),
        (r'(?i)session.*expire|timeout.*=\s*0', "No session expiry — set reasonable timeout"),
    ],
}


@tool(
    "scan_owasp",
    "Scan code for OWASP Top 10 (2021) vulnerabilities. Checks for injection, broken auth, XSS, misconfig, and more.",
    {"code": str, "filename": str},
)
async def scan_owasp(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    filename = args.get("filename", "unknown")
    findings = []

    for category, patterns in OWASP_PATTERNS.items():
        for pattern, recommendation in patterns:
            if recommendation is None:
                continue
            for match in re.finditer(pattern, code):
                line_num = code[:match.start()].count("\n") + 1
                severity = "critical" if "injection" in category.lower() or "crypto" in category.lower() else "high"
                findings.append({
                    "category": category.replace("_", " "),
                    "file": filename,
                    "line": line_num,
                    "match": match.group(0)[:80],
                    "severity": severity,
                    "recommendation": recommendation,
                })

    return {
        "content": [{"type": "text", "text": json.dumps({
            "scan": "owasp_top_10",
            "file": filename,
            "findings_count": len(findings),
            "findings": findings,
            "categories_checked": list(OWASP_PATTERNS.keys()),
        }, indent=2)}]
    }


# ── Dependency Audit ──────────────────────────────────────────────────────────

@tool(
    "audit_dependencies",
    "Audit project dependencies for known CVEs. Analyzes requirements.txt, package.json, or pyproject.toml.",
    {"manifest_content": str, "manifest_type": str},
)
async def audit_dependencies(args: dict[str, Any]) -> dict[str, Any]:
    content = args["manifest_content"]
    manifest_type = args.get("manifest_type", "requirements.txt")

    # Parse dependencies
    deps = []
    if manifest_type in ("requirements.txt", "pyproject.toml"):
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("["):
                # Extract package name and version
                match = re.match(r'[\s"]*([a-zA-Z0-9_-]+)\s*([><=!~]+\s*[\d.]+)?', line)
                if match:
                    deps.append({"name": match.group(1), "version": match.group(2) or "latest"})
    elif manifest_type == "package.json":
        try:
            pkg = json.loads(content)
            for section in ("dependencies", "devDependencies"):
                for name, version in pkg.get(section, {}).items():
                    deps.append({"name": name, "version": version})
        except json.JSONDecodeError:
            pass

    # Known vulnerable packages (subset — in production, use OSV/Snyk API)
    KNOWN_VULNS = {
        "lodash": {"below": "4.17.21", "cve": "CVE-2021-23337", "severity": "critical", "desc": "Command injection in template"},
        "minimist": {"below": "1.2.6", "cve": "CVE-2021-44906", "severity": "critical", "desc": "Prototype pollution"},
        "jsonwebtoken": {"below": "9.0.0", "cve": "CVE-2022-23529", "severity": "high", "desc": "JWT secret confusion"},
        "axios": {"below": "1.6.0", "cve": "CVE-2023-45857", "severity": "medium", "desc": "CSRF token exposure"},
        "express": {"below": "4.19.2", "cve": "CVE-2024-29041", "severity": "medium", "desc": "Open redirect"},
        "django": {"below": "4.2.11", "cve": "CVE-2024-24680", "severity": "high", "desc": "DoS via intcomma"},
        "flask": {"below": "2.3.2", "cve": "CVE-2023-30861", "severity": "high", "desc": "Session cookie vulnerability"},
        "pyyaml": {"below": "6.0.1", "cve": "CVE-2022-42004", "severity": "high", "desc": "Arbitrary code execution via yaml.load"},
        "pillow": {"below": "10.2.0", "cve": "CVE-2024-28219", "severity": "high", "desc": "Buffer overflow in image processing"},
        "requests": {"below": "2.31.0", "cve": "CVE-2023-32681", "severity": "medium", "desc": "Information disclosure"},
    }

    vuln_findings = []
    for dep in deps:
        name_lower = dep["name"].lower()
        if name_lower in KNOWN_VULNS:
            vuln = KNOWN_VULNS[name_lower]
            vuln_findings.append({
                "package": dep["name"],
                "installed_version": dep["version"],
                "vulnerable_below": vuln["below"],
                "cve": vuln["cve"],
                "severity": vuln["severity"],
                "description": vuln["desc"],
                "fix": f"Upgrade {dep['name']} to >= {vuln['below']}",
            })

    return {
        "content": [{"type": "text", "text": json.dumps({
            "scan": "dependency_audit",
            "total_dependencies": len(deps),
            "vulnerabilities_found": len(vuln_findings),
            "findings": vuln_findings,
            "recommendation": "Use `pip-audit` (Python) or `npm audit` (Node) for comprehensive CVE scanning" if not vuln_findings else None,
        }, indent=2)}]
    }


# ── Security Headers Generator ────────────────────────────────────────────────

@tool(
    "generate_security_headers",
    "Generate recommended security headers configuration for a web application. Returns headers for nginx, Express, or FastAPI.",
    {"framework": str, "features": str},
)
async def generate_security_headers(args: dict[str, Any]) -> dict[str, Any]:
    framework = args.get("framework", "nginx").lower()
    features = args.get("features", "standard")

    headers = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "0",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'",
    }

    if "api" in features.lower():
        headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

    configs = {}

    if framework == "nginx":
        lines = [f'add_header {k} "{v}" always;' for k, v in headers.items()]
        configs["nginx"] = "\n".join(lines)

    elif framework in ("express", "node"):
        configs["express"] = f"""const helmet = require('helmet');
app.use(helmet({{
  contentSecurityPolicy: {{
    directives: {{
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", "data:", "https:"],
    }},
  }},
  hsts: {{ maxAge: 31536000, includeSubDomains: true, preload: true }},
  frameguard: {{ action: 'deny' }},
}}));"""

    elif framework in ("fastapi", "python"):
        middleware_code = """from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
"""
        for k, v in headers.items():
            middleware_code += f'        response.headers["{k}"] = "{v}"\n'
        middleware_code += "        return response\n\napp.add_middleware(SecurityHeadersMiddleware)"
        configs["fastapi"] = middleware_code

    return {
        "content": [{"type": "text", "text": json.dumps({
            "headers": headers,
            "framework": framework,
            "config": configs,
        }, indent=2)}]
    }


# ── Auth Pattern Analyzer ─────────────────────────────────────────────────────

@tool(
    "analyze_auth_patterns",
    "Analyze authentication and authorization patterns in code. Checks JWT config, session management, password handling, RBAC implementation.",
    {"code": str, "filename": str},
)
async def analyze_auth_patterns(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    filename = args.get("filename", "unknown")
    findings = []
    good_practices = []

    # JWT checks
    if "jwt" in code.lower() or "jsonwebtoken" in code.lower():
        if re.search(r'expiresIn.*["\'](\d+d|\d+y)', code) or re.search(r'exp.*timedelta\(days=(\d+)\)', code):
            match = re.search(r'(\d+)', code)
            if match and int(match.group(1)) > 1:
                findings.append({"issue": "Long JWT expiry", "severity": "medium", "fix": "Use 15-60 min access tokens with refresh token rotation"})
        if re.search(r'HS256|HS384', code):
            findings.append({"issue": "Symmetric JWT signing (HS256)", "severity": "low", "fix": "Consider RS256/ES256 for production (asymmetric keys)"})
        if re.search(r'RS256|ES256|EdDSA', code):
            good_practices.append("Using asymmetric JWT signing")
        if re.search(r'httpOnly|http_only', code):
            good_practices.append("JWT stored in httpOnly cookie")

    # Password handling
    if re.search(r'bcrypt|argon2|scrypt', code, re.IGNORECASE):
        good_practices.append("Using strong password hashing")
    if re.search(r'(?i)md5|sha1.*password|sha256.*password', code):
        findings.append({"issue": "Weak password hashing", "severity": "critical", "fix": "Use bcrypt (cost 12+) or argon2id"})

    # Rate limiting
    if re.search(r'(?i)rate.?limit|throttle|RateLimiter', code):
        good_practices.append("Rate limiting implemented")
    elif re.search(r'(?i)login|authenticate|sign.?in', code):
        findings.append({"issue": "No rate limiting on auth endpoint", "severity": "high", "fix": "Add rate limiting (e.g., 5 attempts/minute per IP)"})

    # RBAC
    if re.search(r'(?i)role|permission|authorize|@require|@admin', code):
        good_practices.append("Role-based access control present")

    return {
        "content": [{"type": "text", "text": json.dumps({
            "scan": "auth_patterns",
            "file": filename,
            "findings": findings,
            "good_practices": good_practices,
            "score": max(0, 100 - sum(30 if f["severity"] == "critical" else 15 if f["severity"] == "high" else 5 for f in findings)),
        }, indent=2)}]
    }


# ── Create the MCP Server ────────────────────────────────────────────────────

security_server = create_sdk_mcp_server(
    name="genesis-security",
    version="1.0.0",
    tools=[scan_secrets, scan_owasp, audit_dependencies, generate_security_headers, analyze_auth_patterns],
)
