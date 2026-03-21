"""MCP Server Registry — maps assistant domains to MCP servers.

When a build starts, the pipeline looks up which MCP servers to attach
to the Claude Agent SDK based on the selected assistants.
"""

from __future__ import annotations

import logging
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions

logger = logging.getLogger(__name__)


def get_mcp_servers_for_assistants(
    assistant_ids: list[str],
) -> dict[str, Any]:
    """Get MCP server configs for the selected assistants.

    Returns a dict of {server_name: McpSdkServerConfig} suitable for
    passing to ClaudeAgentOptions(mcp_servers=...).
    """
    servers = {}

    # Map assistant domains to MCP servers
    domain_servers = {
        "compliance": "genesis-security",
        "quality": "genesis-code-quality",
        "architecture": "genesis-database",  # DB is part of architecture
        "infrastructure": "genesis-infrastructure",
        "project": "genesis-discovery",
        "ba": "genesis-discovery",
    }

    # Figure out which domains are active
    try:
        from genesis.assistants.catalog import ALL_ASSISTANTS
        active_domains = set()
        for a in ALL_ASSISTANTS:
            if a.id in assistant_ids:
                active_domains.add(a.domain)
    except ImportError:
        active_domains = set(domain_servers.keys())

    # Load the corresponding MCP servers
    server_loaders = {
        "genesis-security": lambda: _load_security_server(),
        "genesis-code-quality": lambda: _load_code_quality_server(),
        "genesis-database": lambda: _load_database_server(),
        "genesis-infrastructure": lambda: _load_infrastructure_server(),
        "genesis-discovery": lambda: _load_discovery_server(),
    }

    needed_servers = set()
    for domain in active_domains:
        server_name = domain_servers.get(domain)
        if server_name:
            needed_servers.add(server_name)

    for server_name in needed_servers:
        loader = server_loaders.get(server_name)
        if loader:
            try:
                servers[server_name] = loader()
                logger.info("Loaded MCP server: %s", server_name)
            except Exception as e:
                logger.warning("Failed to load MCP server %s: %s", server_name, e)

    return servers


def _load_security_server():
    from genesis.mcp_servers.security import security_server
    return security_server


def _load_code_quality_server():
    from genesis.mcp_servers.code_quality import code_quality_server
    return code_quality_server


def _load_database_server():
    from genesis.mcp_servers.database import database_server
    return database_server


def _load_infrastructure_server():
    from genesis.mcp_servers.infrastructure import infrastructure_server
    return infrastructure_server


def _load_discovery_server():
    from genesis.mcp_servers.discovery import discovery_server
    return discovery_server


def get_mcp_tool_names(servers: dict[str, Any]) -> list[str]:
    """Get the tool permission strings for MCP server tools.

    Claude Agent SDK uses mcp__<server_name>__<tool_name> format.
    """
    tool_names = []
    server_tools = {
        "genesis-security": [
            "scan_secrets", "scan_owasp", "audit_dependencies",
            "generate_security_headers", "analyze_auth_patterns",
        ],
        "genesis-code-quality": [
            "measure_complexity", "detect_duplication",
            "detect_antipatterns", "maintainability_index",
        ],
        "genesis-database": [
            "analyze_schema", "analyze_query",
            "generate_migration", "suggest_indexes",
        ],
        "genesis-infrastructure": [
            "analyze_dockerfile", "estimate_cloud_cost",
            "generate_cicd", "audit_env_vars",
        ],
        "genesis-discovery": [
            "analyze_competitor", "generate_persona",
            "build_journey_map", "validate_hypothesis", "shape_scope",
        ],
    }

    for server_name in servers:
        for tool in server_tools.get(server_name, []):
            tool_names.append(f"mcp__{server_name}__{tool}")

    return tool_names


def get_all_servers() -> dict[str, Any]:
    """Load all MCP servers (for admin/debug)."""
    all_ids = []
    try:
        from genesis.assistants.catalog import ALL_ASSISTANTS
        all_ids = [a.id for a in ALL_ASSISTANTS]
    except ImportError:
        pass
    return get_mcp_servers_for_assistants(all_ids)
