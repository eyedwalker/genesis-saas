"""Infrastructure MCP Server — DevOps analysis and generation tools.

Gives Claude's infrastructure assistants actual power:
- Analyze Dockerfiles for security and efficiency
- Estimate cloud costs from architecture descriptions
- Generate CI/CD pipeline configs
- Check environment variable hygiene
- Generate health check endpoints
"""

from __future__ import annotations

import json
import re
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


# ── Dockerfile Analyzer ───────────────────────────────────────────────────────

@tool(
    "analyze_dockerfile",
    "Analyze a Dockerfile for security issues, size optimization opportunities, layer ordering, and best practices.",
    {"dockerfile": str},
)
async def analyze_dockerfile(args: dict[str, Any]) -> dict[str, Any]:
    content = args["dockerfile"]
    findings = []
    good_practices = []
    lines = content.split("\n")

    # Check base image
    from_match = re.search(r'^FROM\s+(.+?)(?:\s+AS\s+\w+)?$', content, re.MULTILINE)
    if from_match:
        base = from_match.group(1)
        if ":latest" in base or ":" not in base:
            findings.append({
                "issue": "Unpinned base image",
                "severity": "high",
                "line": 1,
                "fix": f"Pin version: {base}:<specific-version> (e.g., python:3.11-slim)",
            })
        if "slim" in base or "alpine" in base or "distroless" in base:
            good_practices.append(f"Using minimal base image: {base}")
        elif not re.search(r'slim|alpine|distroless|scratch', base):
            findings.append({
                "issue": f"Using full base image: {base}",
                "severity": "medium",
                "fix": "Use -slim or -alpine variant to reduce image size by 50-80%",
            })

    # Check for multi-stage build
    from_count = len(re.findall(r'^FROM\s+', content, re.MULTILINE))
    if from_count > 1:
        good_practices.append(f"Multi-stage build ({from_count} stages)")
    elif len(lines) > 15:
        findings.append({
            "issue": "No multi-stage build",
            "severity": "medium",
            "fix": "Use multi-stage build to separate build deps from runtime (reduces image size)",
        })

    # Check for root user
    if not re.search(r'^USER\s+(?!root)', content, re.MULTILINE):
        findings.append({
            "issue": "Running as root",
            "severity": "high",
            "fix": "Add USER directive: RUN adduser --disabled-password appuser && USER appuser",
        })
    else:
        good_practices.append("Non-root user configured")

    # Check COPY ordering (deps before code for cache efficiency)
    copy_indices = [i for i, l in enumerate(lines) if l.strip().startswith("COPY")]
    run_install_idx = next(
        (i for i, l in enumerate(lines) if re.search(r'(pip install|npm install|yarn install|go mod)', l)),
        None,
    )
    if copy_indices and run_install_idx:
        # Check if package manifest is copied before full source
        first_copy = copy_indices[0] if copy_indices else 999
        if first_copy > run_install_idx:
            findings.append({
                "issue": "Poor layer ordering — deps installed before COPY",
                "severity": "medium",
                "fix": "COPY package files first, install deps, then COPY source code for better cache hits",
            })

    # Check for .dockerignore hints
    if re.search(r'COPY\s+\.\s+', content):
        findings.append({
            "issue": "COPY . copies everything — ensure .dockerignore exists",
            "severity": "low",
            "fix": "Add .dockerignore with: .git, node_modules, __pycache__, .env, *.md",
        })

    # Check for HEALTHCHECK
    if re.search(r'HEALTHCHECK', content):
        good_practices.append("HEALTHCHECK defined")
    else:
        findings.append({
            "issue": "No HEALTHCHECK instruction",
            "severity": "low",
            "fix": "Add HEALTHCHECK CMD curl -f http://localhost:PORT/health || exit 1",
        })

    # Check for secrets in build
    if re.search(r'ENV.*(?:PASSWORD|SECRET|KEY|TOKEN)\s*=\s*\S+', content, re.IGNORECASE):
        findings.append({
            "issue": "Secrets hardcoded in Dockerfile ENV",
            "severity": "critical",
            "fix": "Pass secrets at runtime via -e flag or Docker secrets, not in Dockerfile",
        })

    # Estimate image size category
    size_category = "large"
    if "alpine" in content.lower() or "slim" in content.lower():
        size_category = "medium"
    if "distroless" in content.lower() or "scratch" in content.lower():
        size_category = "small"
    if from_count > 1 and size_category != "large":
        size_category = "optimized"

    return {
        "content": [{"type": "text", "text": json.dumps({
            "analysis": "dockerfile",
            "stages": from_count,
            "estimated_size": size_category,
            "findings": findings,
            "good_practices": good_practices,
            "score": max(0, 100 - sum(
                25 if f["severity"] == "critical" else 15 if f["severity"] == "high" else 5
                for f in findings
            )),
        }, indent=2)}]
    }


# ── Cloud Cost Estimator ──────────────────────────────────────────────────────

@tool(
    "estimate_cloud_cost",
    "Estimate monthly cloud costs for an architecture. Covers compute, database, storage, CDN, and managed services.",
    {"architecture": str, "cloud": str, "scale": str},
)
async def estimate_cloud_cost(args: dict[str, Any]) -> dict[str, Any]:
    arch = args["architecture"]
    cloud = args.get("cloud", "aws").lower()
    scale = args.get("scale", "startup")  # startup, growth, enterprise

    # Cost reference table (approximate monthly USD)
    costs = {
        "startup": {
            "compute": {"service": "t3.small or Fargate 0.5vCPU", "monthly": 30},
            "database": {"service": "RDS db.t3.micro or Free Tier", "monthly": 15},
            "cache": {"service": "ElastiCache t3.micro", "monthly": 13},
            "storage": {"service": "S3 Standard 50GB", "monthly": 2},
            "cdn": {"service": "CloudFront 100GB/mo", "monthly": 10},
            "dns": {"service": "Route53 hosted zone", "monthly": 1},
            "monitoring": {"service": "CloudWatch basic", "monthly": 0},
            "ci_cd": {"service": "GitHub Actions free tier", "monthly": 0},
        },
        "growth": {
            "compute": {"service": "t3.medium x2 + ALB", "monthly": 120},
            "database": {"service": "RDS db.t3.medium Multi-AZ", "monthly": 140},
            "cache": {"service": "ElastiCache r6g.large", "monthly": 130},
            "storage": {"service": "S3 Standard 500GB", "monthly": 12},
            "cdn": {"service": "CloudFront 1TB/mo", "monthly": 85},
            "dns": {"service": "Route53 + health checks", "monthly": 5},
            "monitoring": {"service": "CloudWatch + alarms", "monthly": 30},
            "ci_cd": {"service": "GitHub Actions Team", "monthly": 20},
        },
        "enterprise": {
            "compute": {"service": "m6i.xlarge x4 + ALB + Auto Scaling", "monthly": 600},
            "database": {"service": "RDS r6g.xlarge Multi-AZ + read replicas", "monthly": 800},
            "cache": {"service": "ElastiCache r6g.xlarge cluster", "monthly": 400},
            "storage": {"service": "S3 Standard 5TB + Glacier", "monthly": 120},
            "cdn": {"service": "CloudFront 10TB/mo + WAF", "monthly": 500},
            "dns": {"service": "Route53 + DNSSEC", "monthly": 10},
            "monitoring": {"service": "CloudWatch + X-Ray + Datadog", "monthly": 200},
            "ci_cd": {"service": "GitHub Actions Enterprise", "monthly": 100},
        },
    }

    tier_costs = costs.get(scale, costs["startup"])
    total = sum(item["monthly"] for item in tier_costs.values())

    # Detect specific services mentioned
    detected_services = []
    service_keywords = {
        "redis": "cache", "postgres": "database", "mysql": "database",
        "s3": "storage", "cdn": "cdn", "cloudfront": "cdn",
        "lambda": "serverless", "ecs": "compute", "kubernetes": "compute",
    }
    for keyword, category in service_keywords.items():
        if keyword in arch.lower():
            detected_services.append({"keyword": keyword, "category": category})

    return {
        "content": [{"type": "text", "text": json.dumps({
            "estimate": {
                "scale": scale,
                "cloud": cloud,
                "monthly_total_usd": total,
                "annual_total_usd": total * 12,
                "breakdown": tier_costs,
            },
            "detected_services": detected_services,
            "cost_optimization_tips": [
                "Use Spot/Preemptible instances for dev/staging (60-90% savings)",
                "Reserved instances for production (30-40% savings on 1-year commit)",
                "S3 Intelligent-Tiering for variable access patterns",
                "Right-size instances — monitor CPU/memory utilization",
                "Use Graviton/ARM instances (20% cheaper, 40% better perf)",
            ],
            "free_tier_eligible": scale == "startup",
        }, indent=2)}]
    }


# ── CI/CD Pipeline Generator ─────────────────────────────────────────────────

@tool(
    "generate_cicd",
    "Generate a CI/CD pipeline configuration. Supports GitHub Actions, GitLab CI, and generic Docker-based pipelines.",
    {"tech_stack": str, "platform": str, "features": str},
)
async def generate_cicd(args: dict[str, Any]) -> dict[str, Any]:
    tech = args["tech_stack"]
    platform = args.get("platform", "github_actions")
    features = args.get("features", "lint,test,build,deploy")

    is_python = any(t in tech.lower() for t in ["python", "fastapi", "django", "flask"])
    is_node = any(t in tech.lower() for t in ["node", "next", "react", "express"])

    if platform == "github_actions":
        steps = []
        if is_python:
            steps = [
                "- uses: actions/checkout@v4",
                "- uses: actions/setup-python@v5\n  with:\n    python-version: '3.11'",
                "- run: pip install -e '.[dev]'",
                "- run: ruff check ." if "lint" in features else None,
                "- run: mypy ." if "lint" in features else None,
                "- run: pytest --cov -q" if "test" in features else None,
                "- run: docker build -t app ." if "build" in features else None,
            ]
        elif is_node:
            steps = [
                "- uses: actions/checkout@v4",
                "- uses: actions/setup-node@v4\n  with:\n    node-version: 20\n    cache: npm",
                "- run: npm ci",
                "- run: npm run lint" if "lint" in features else None,
                "- run: npm test" if "test" in features else None,
                "- run: npm run build" if "build" in features else None,
            ]

        steps = [s for s in steps if s]

        pipeline = f"""name: CI/CD
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
{chr(10).join('      ' + s for s in steps)}

  deploy:
    needs: ci
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        run: echo "Add deployment steps here"
"""
    else:
        pipeline = "# Generic pipeline — adapt to your CI/CD platform"

    return {
        "content": [{"type": "text", "text": json.dumps({
            "platform": platform,
            "tech_stack": tech,
            "pipeline": pipeline,
            "features_included": features.split(","),
        }, indent=2)}]
    }


# ── Environment Variable Auditor ──────────────────────────────────────────────

@tool(
    "audit_env_vars",
    "Audit environment variable usage across code. Checks for missing .env.example, hardcoded values, and security issues.",
    {"code": str, "env_example": str},
)
async def audit_env_vars(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    env_example = args.get("env_example", "")
    findings = []

    # Find all env var references
    env_refs = set()
    for pattern in [
        r'os\.environ\[[\'"]([\w]+)[\'"]\]',
        r'os\.getenv\([\'"]([\w]+)[\'"]',
        r'process\.env\.([\w]+)',
        r'env\([\'"]([\w]+)[\'"]',
        r'\$\{([\w]+)\}',
    ]:
        env_refs.update(re.findall(pattern, code))

    # Find documented vars
    documented = set()
    for line in env_example.split("\n"):
        match = re.match(r'^([\w]+)\s*=', line)
        if match:
            documented.add(match.group(1))

    # Undocumented vars
    undocumented = env_refs - documented
    if undocumented:
        for var in undocumented:
            severity = "high" if any(s in var.upper() for s in ["SECRET", "KEY", "PASSWORD", "TOKEN"]) else "medium"
            findings.append({
                "issue": f"Env var {var} used in code but not in .env.example",
                "severity": severity,
                "fix": f"Add {var}= to .env.example with a placeholder value",
            })

    # Hardcoded values that should be env vars
    hardcoded_patterns = [
        (r'(?:host|hostname)\s*[=:]\s*["\'](?:localhost|127\.0\.0\.1|0\.0\.0\.0)', "Hardcoded host — use env var"),
        (r'(?:port)\s*[=:]\s*(?:\d{4,5})\b', "Hardcoded port — use env var"),
        (r'(?:https?://)[a-z]+\.[a-z]+\.[a-z]+', "Hardcoded URL — use env var for configurability"),
    ]
    for pattern, issue in hardcoded_patterns:
        for match in re.finditer(pattern, code, re.IGNORECASE):
            findings.append({
                "issue": issue,
                "severity": "low",
                "location": f"line {code[:match.start()].count(chr(10)) + 1}",
                "context": match.group(0)[:50],
            })

    return {
        "content": [{"type": "text", "text": json.dumps({
            "env_vars_used": sorted(env_refs),
            "documented_vars": sorted(documented),
            "undocumented_vars": sorted(undocumented),
            "findings": findings,
            "recommendation": "All env vars should be documented in .env.example with descriptions",
        }, indent=2)}]
    }


# ── Create the MCP Server ────────────────────────────────────────────────────

infrastructure_server = create_sdk_mcp_server(
    name="genesis-infrastructure",
    version="1.0.0",
    tools=[analyze_dockerfile, estimate_cloud_cost, generate_cicd, audit_env_vars],
)
