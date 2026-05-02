def test_mcp_entry_imports_and_registers_tools():
    from issuedeck.mcp import __main__ as entry
    assert entry.mcp_server is not None
