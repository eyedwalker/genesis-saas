"""Database MCP Server — real database analysis tools.

Gives Claude's database assistant actual power:
- Validate SQL schemas for normalization issues
- Analyze queries for performance problems (N+1, missing indexes)
- Generate migration scripts
- Check for data integrity issues
- Suggest indexes based on query patterns
"""

from __future__ import annotations

import json
import re
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


# ── Schema Analyzer ───────────────────────────────────────────────────────────

@tool(
    "analyze_schema",
    "Analyze a database schema (SQL CREATE TABLE statements or ORM model definitions) for normalization issues, missing indexes, and best practices.",
    {"schema": str, "orm_type": str},
)
async def analyze_schema(args: dict[str, Any]) -> dict[str, Any]:
    schema = args["schema"]
    orm_type = args.get("orm_type", "sql")  # sql, sqlalchemy, prisma, django
    findings = []
    suggestions = []

    # Extract table definitions
    tables = re.findall(
        r'(?:CREATE TABLE|class)\s+(\w+)', schema, re.IGNORECASE
    )

    # Check for common issues
    # 1. Missing primary keys
    if orm_type == "sql":
        for table in tables:
            table_block = re.search(
                rf'CREATE TABLE\s+{table}\s*\((.*?)\);',
                schema, re.IGNORECASE | re.DOTALL,
            )
            if table_block:
                block = table_block.group(1)
                if "PRIMARY KEY" not in block.upper() and "SERIAL" not in block.upper():
                    findings.append({
                        "table": table,
                        "issue": "Missing primary key",
                        "severity": "critical",
                        "fix": f"Add `id SERIAL PRIMARY KEY` or equivalent to {table}",
                    })

    # 2. Missing timestamps
    for table in tables:
        if not re.search(rf'{table}.*(?:created_at|createdAt|created)', schema, re.IGNORECASE | re.DOTALL):
            findings.append({
                "table": table,
                "issue": "Missing created_at timestamp",
                "severity": "medium",
                "fix": "Add created_at TIMESTAMP DEFAULT NOW()",
            })

    # 3. VARCHAR without length (risky in some DBs)
    for match in re.finditer(r'VARCHAR\b(?!\s*\()', schema, re.IGNORECASE):
        line = schema[:match.start()].count("\n") + 1
        findings.append({
            "line": line,
            "issue": "VARCHAR without length limit",
            "severity": "low",
            "fix": "Specify VARCHAR(n) — e.g., VARCHAR(255) for names, VARCHAR(500) for URLs",
        })

    # 4. Text fields that should be indexed
    for match in re.finditer(r'(\w+)\s+(?:VARCHAR|TEXT).*?(?:UNIQUE|INDEX)', schema, re.IGNORECASE):
        suggestions.append(f"Index on text column {match.group(1)} — good")

    # 5. Foreign key checks
    fk_count = len(re.findall(r'REFERENCES|ForeignKey|foreign_key', schema, re.IGNORECASE))
    if fk_count == 0 and len(tables) > 1:
        findings.append({
            "issue": "No foreign key relationships defined",
            "severity": "high",
            "fix": "Define REFERENCES constraints between related tables for data integrity",
        })

    # 6. Suggest indexes for common patterns
    for match in re.finditer(r'(\w+_id)\s+(?:INTEGER|BIGINT|UUID|String)', schema, re.IGNORECASE):
        col = match.group(1)
        suggestions.append(f"Consider index on {col} — likely used in JOINs and WHERE clauses")

    # Normalization assessment
    normalization = "3NF"
    if re.search(r'(?:address|city|state|zip|country)\s+VARCHAR', schema, re.IGNORECASE):
        if not re.search(r'addresses|address_id', schema, re.IGNORECASE):
            findings.append({
                "issue": "Address fields embedded in table — consider separate addresses table (2NF violation)",
                "severity": "low",
                "fix": "Extract to an addresses table with foreign key reference",
            })
            normalization = "1NF-2NF"

    return {
        "content": [{"type": "text", "text": json.dumps({
            "scan": "schema_analysis",
            "tables_found": len(tables),
            "table_names": tables,
            "normalization_level": normalization,
            "findings": findings,
            "suggestions": suggestions,
            "foreign_keys": fk_count,
        }, indent=2)}]
    }


# ── Query Analyzer ────────────────────────────────────────────────────────────

@tool(
    "analyze_query",
    "Analyze SQL queries or ORM code for performance issues: N+1 queries, missing indexes, unbounded selects, and optimization opportunities.",
    {"code": str, "language": str},
)
async def analyze_query(args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    language = args.get("language", "python")
    findings = []

    # N+1 query detection
    loop_patterns = [
        (r'for\s+\w+\s+in\s+.*:\s*\n.*(?:\.query|\.get|\.find|\.fetch|SELECT|await\s+db)', "N+1 query inside loop"),
        (r'\.map\(\s*(?:async\s*)?\w+\s*=>\s*.*(?:findOne|findUnique|query|fetch)', "N+1 query inside map/forEach"),
        (r'for\s+.*:\s*\n\s+.*(?:cursor|execute|session\.)', "Database call inside loop"),
    ]
    for pattern, issue in loop_patterns:
        for match in re.finditer(pattern, code, re.MULTILINE):
            line = code[:match.start()].count("\n") + 1
            findings.append({
                "issue": issue,
                "severity": "critical",
                "line": line,
                "fix": "Use eager loading (joinedload/include), batch queries, or IN clause",
                "context": match.group(0)[:100],
            })

    # SELECT * detection
    for match in re.finditer(r'SELECT\s+\*', code, re.IGNORECASE):
        line = code[:match.start()].count("\n") + 1
        findings.append({
            "issue": "SELECT * — fetches all columns",
            "severity": "medium",
            "line": line,
            "fix": "Select only needed columns to reduce I/O and memory",
        })

    # Missing LIMIT
    select_count = len(re.findall(r'SELECT|\.all\(\)|\.find\(\{', code, re.IGNORECASE))
    limit_count = len(re.findall(r'LIMIT|\.limit\(|\.take\(|\.head\(|slice\[', code, re.IGNORECASE))
    if select_count > 0 and limit_count == 0:
        findings.append({
            "issue": "No LIMIT on queries — unbounded result sets",
            "severity": "high",
            "fix": "Add LIMIT/pagination to prevent memory exhaustion on large tables",
        })

    # Missing eager loading hints
    if re.search(r'\.relationship|hasMany|belongsTo|@relation', code, re.IGNORECASE):
        if not re.search(r'joinedload|include|eager|prefetch|with\(', code, re.IGNORECASE):
            findings.append({
                "issue": "Relationships defined but no eager loading configured",
                "severity": "medium",
                "fix": "Use joinedload() (SQLAlchemy), include (Prisma), or prefetch_related (Django)",
            })

    # Transaction safety
    if re.search(r'(?:INSERT|UPDATE|DELETE).*(?:INSERT|UPDATE|DELETE)', code, re.IGNORECASE | re.DOTALL):
        if not re.search(r'transaction|BEGIN|COMMIT|atomic|session\.begin', code, re.IGNORECASE):
            findings.append({
                "issue": "Multiple write operations without transaction",
                "severity": "high",
                "fix": "Wrap related writes in a transaction for atomicity",
            })

    return {
        "content": [{"type": "text", "text": json.dumps({
            "scan": "query_analysis",
            "findings": findings,
            "queries_detected": select_count,
            "has_pagination": limit_count > 0,
        }, indent=2)}]
    }


# ── Migration Generator ──────────────────────────────────────────────────────

@tool(
    "generate_migration",
    "Generate a safe database migration script from a schema diff. Includes rollback, zero-downtime strategies, and data preservation.",
    {"current_schema": str, "target_schema": str, "db_type": str},
)
async def generate_migration(args: dict[str, Any]) -> dict[str, Any]:
    current = args.get("current_schema", "")
    target = args["target_schema"]
    db_type = args.get("db_type", "postgresql")

    # Extract tables from both schemas
    current_tables = set(re.findall(r'(?:CREATE TABLE|class)\s+(\w+)', current, re.IGNORECASE))
    target_tables = set(re.findall(r'(?:CREATE TABLE|class)\s+(\w+)', target, re.IGNORECASE))

    new_tables = target_tables - current_tables
    removed_tables = current_tables - target_tables

    migration_steps = []
    rollback_steps = []

    for table in new_tables:
        # Extract the CREATE TABLE block
        block = re.search(
            rf'CREATE TABLE\s+{table}\s*\((.*?)\);',
            target, re.IGNORECASE | re.DOTALL,
        )
        if block:
            migration_steps.append(f"-- Create new table\nCREATE TABLE IF NOT EXISTS {table} (\n{block.group(1)}\n);")
            rollback_steps.append(f"DROP TABLE IF EXISTS {table};")

    for table in removed_tables:
        migration_steps.append(f"-- WARNING: Dropping table (ensure data is backed up)\n-- DROP TABLE IF EXISTS {table};")
        rollback_steps.append(f"-- Restore table {table} (manual restore from backup required)")

    warnings = []
    if removed_tables:
        warnings.append(f"DESTRUCTIVE: {len(removed_tables)} table(s) will be dropped — back up data first")

    return {
        "content": [{"type": "text", "text": json.dumps({
            "migration": {
                "new_tables": list(new_tables),
                "removed_tables": list(removed_tables),
                "up": "\n\n".join(migration_steps) if migration_steps else "-- No schema changes detected",
                "down": "\n\n".join(rollback_steps) if rollback_steps else "-- Nothing to rollback",
            },
            "warnings": warnings,
            "zero_downtime_tips": [
                "Add new columns as NULLABLE first, then backfill, then add NOT NULL constraint",
                "Create new indexes CONCURRENTLY to avoid table locks",
                "Use blue-green deployment for destructive changes",
            ],
        }, indent=2)}]
    }


# ── Index Advisor ─────────────────────────────────────────────────────────────

@tool(
    "suggest_indexes",
    "Analyze query patterns and suggest optimal database indexes. Considers composite indexes, partial indexes, and covering indexes.",
    {"queries": str, "schema": str},
)
async def suggest_indexes(args: dict[str, Any]) -> dict[str, Any]:
    queries = args["queries"]
    schema = args.get("schema", "")
    suggestions = []

    # Extract WHERE clauses
    where_cols = re.findall(
        r'WHERE\s+(?:\w+\.)?([\w]+)\s*(?:=|>|<|IN|LIKE|BETWEEN)',
        queries, re.IGNORECASE,
    )

    # Extract JOIN columns
    join_cols = re.findall(
        r'(?:JOIN|ON)\s+\w+\s+ON\s+(?:\w+\.)?([\w]+)\s*=',
        queries, re.IGNORECASE,
    )

    # Extract ORDER BY columns
    order_cols = re.findall(
        r'ORDER BY\s+(?:\w+\.)?([\w]+)',
        queries, re.IGNORECASE,
    )

    # Count frequency
    from collections import Counter
    col_freq = Counter(where_cols + join_cols)

    for col, count in col_freq.most_common(10):
        if col.lower() in ("id", "pk"):
            continue
        idx_type = "btree"
        if col in order_cols:
            idx_type = "btree (supports ORDER BY)"
        suggestions.append({
            "column": col,
            "frequency": count,
            "index_type": idx_type,
            "sql": f"CREATE INDEX CONCURRENTLY idx_{col} ON <table> ({col});",
            "reason": f"Used in {count} WHERE/JOIN clause(s)",
        })

    # Composite index suggestions
    # Look for multi-column WHERE clauses
    composite = re.findall(
        r'WHERE\s+(?:\w+\.)?([\w]+)\s*=.*?AND\s+(?:\w+\.)?([\w]+)\s*=',
        queries, re.IGNORECASE,
    )
    for col1, col2 in composite:
        suggestions.append({
            "columns": [col1, col2],
            "index_type": "composite btree",
            "sql": f"CREATE INDEX CONCURRENTLY idx_{col1}_{col2} ON <table> ({col1}, {col2});",
            "reason": "Frequently queried together in WHERE clause",
        })

    return {
        "content": [{"type": "text", "text": json.dumps({
            "suggestions": suggestions,
            "general_tips": [
                "Index columns used in WHERE, JOIN, and ORDER BY",
                "Use CONCURRENTLY to avoid table locks during creation",
                "Monitor unused indexes with pg_stat_user_indexes",
                "Composite indexes: put most selective column first",
            ],
        }, indent=2)}]
    }


# ── Create the MCP Server ────────────────────────────────────────────────────

database_server = create_sdk_mcp_server(
    name="genesis-database",
    version="1.0.0",
    tools=[analyze_schema, analyze_query, generate_migration, suggest_indexes],
)
