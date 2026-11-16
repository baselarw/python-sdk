import asyncio

from mcp import ClientSessionGroup, StdioServerParameters
from mcp.types import Implementation


def by_server(name: str, server_info: Implementation) -> str:
    return f"{server_info.name}.{name}"


async def main() -> None:
    library = StdioServerParameters(command="uv", args=["run", "mcp", "run", "library_server.py"])
    greeter = StdioServerParameters(command="uv", args=["run", "mcp", "run", "greeter_server.py"])

    async with ClientSessionGroup(component_name_hook=by_server) as group:
        await group.connect_to_server(library)
        await group.connect_to_server(greeter)

        # `Library.hours` is the group key; `library://hours` goes on the wire.
        hours = await group.read_resource("Library.hours")
        print(hours.contents[0])

        # `arguments` are forwarded to the owning server unchanged.
        prompt = await group.get_prompt("Greeter.greet", {"name": "Ada"})
        print(prompt.messages[0].content)


if __name__ == "__main__":
    asyncio.run(main())
