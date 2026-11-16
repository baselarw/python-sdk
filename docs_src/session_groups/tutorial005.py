from mcp.server import MCPServer

mcp = MCPServer("Greeter")


@mcp.prompt()
def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Please write a warm greeting for {name}."
