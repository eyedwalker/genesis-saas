"""MCP Servers — each assistant domain gets a server with real tools.

Architecture:
- Each MCP server provides domain-specific tools to Claude agents
- Servers are registered with the Claude Agent SDK via mcp_servers config
- During builds, the pipeline agents get access to relevant MCP tools
- Enterprise customers can add their own MCP servers for custom domains
"""
