"""MCP stdio entry point. Run with: python -m issuedeck.mcp"""
from __future__ import annotations

from fastmcp import FastMCP

from issuedeck.mcp import tools

mcp_server = FastMCP("issuedeck")

for fn in (
    tools.list_projects,
    tools.get_project_config,
    tools.create_item,
    tools.update_item,
    tools.ship_item,
    tools.append_item_event,
    tools.delete_item,
    tools.get_item,
    tools.list_items,
    tools.search_items,
    tools.add_relationship,
    tools.remove_relationship,
):
    mcp_server.tool()(fn)


def run() -> int:
    mcp_server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
