"""`docs/client/session-groups.md`: every claim the page makes, proved against the real SDK.

`connect_to_server` opens a real transport (a subprocess or a socket), so these tests drive the
exact same aggregation path through `connect_with_session` with in-memory sessions instead.
"""

import traceback

import pytest
from mcp_types import INVALID_PARAMS, Implementation, TextContent, TextResourceContents

from docs_src.session_groups import tutorial001, tutorial002, tutorial004, tutorial005, tutorial006
from mcp import Client, ClientSessionGroup, MCPError

# See test_index.py for why this is a per-module mark and not a conftest hook.
pytestmark = [pytest.mark.anyio, pytest.mark.filterwarnings("error::mcp.MCPDeprecationWarning")]


def _server_info(client: Client) -> Implementation:
    """Narrow `client.server_info` for `connect_with_session`: these servers all identify themselves."""
    assert client.server_info is not None
    return client.server_info


async def test_both_servers_call_their_tool_search() -> None:
    """tutorial001 + tutorial002: two unrelated servers, one colliding tool name."""
    async with Client(tutorial001.mcp) as library, Client(tutorial002.mcp) as web:
        (library_tool,) = (await library.list_tools()).tools
        (web_tool,) = (await web.list_tools()).tools
        assert library_tool.name == "search"
        assert web_tool.name == "search"


async def test_a_connected_server_is_aggregated_into_the_group() -> None:
    """tutorial003: the group exposes every component of every connected server as a dict."""
    async with Client(tutorial001.mcp) as library:
        group = ClientSessionGroup()
        await group.connect_with_session(_server_info(library), library.session)
        assert sorted(group.tools) == ["search"]
        assert sorted(group.resources) == ["hours"]
        assert group.prompts == {}
        assert group.tools["search"].description == "Search the library catalog."


async def test_colliding_names_are_rejected() -> None:
    """tutorial003: without a hook the second `search` raises, and nothing from `Web` is kept."""
    async with Client(tutorial001.mcp) as library, Client(tutorial002.mcp) as web:
        group = ClientSessionGroup()
        await group.connect_with_session(_server_info(library), library.session)
        with pytest.raises(MCPError) as exc_info:
            await group.connect_with_session(_server_info(web), web.session)
        assert str(exc_info.value) == "{'search'} already exist in group tools."
        assert exc_info.value.error.code == INVALID_PARAMS
        assert sorted(group.tools) == ["search"]
        # The page's `!!! check` fence is the last line of the traceback, verbatim.
        assert traceback.format_exception_only(exc_info.value) == [
            "mcp.shared.exceptions.MCPError: {'search'} already exist in group tools.\n"
        ]


async def test_component_name_hook_prefixes_every_name() -> None:
    """tutorial004: the hook rewrites every registered name, so both servers coexist."""
    async with Client(tutorial001.mcp) as library, Client(tutorial002.mcp) as web:
        group = ClientSessionGroup(component_name_hook=tutorial004.by_server)
        await group.connect_with_session(_server_info(library), library.session)
        await group.connect_with_session(_server_info(web), web.session)
        assert sorted(group.tools) == ["Library.search", "Web.search"]
        assert sorted(group.resources) == ["Library.hours"]


def test_the_hook_is_a_plain_function_of_name_and_server_info() -> None:
    """tutorial004: `by_server` builds the key from `server_info.name`."""
    assert tutorial004.by_server("search", Implementation(name="Web", version="1.0.0")) == "Web.search"


async def test_the_key_is_prefixed_but_the_wire_name_is_not() -> None:
    """tutorial004: the dict key is yours; the `Tool` inside keeps the name the server declared."""
    async with Client(tutorial002.mcp) as web:
        group = ClientSessionGroup(component_name_hook=tutorial004.by_server)
        await group.connect_with_session(_server_info(web), web.session)
        assert group.tools["Web.search"].name == "search"


async def test_call_tool_routes_to_the_owning_server() -> None:
    """tutorial004: `group.call_tool` resolves the prefixed name to the session that owns it."""
    async with Client(tutorial001.mcp) as library, Client(tutorial002.mcp) as web:
        group = ClientSessionGroup(component_name_hook=tutorial004.by_server)
        await group.connect_with_session(_server_info(library), library.session)
        await group.connect_with_session(_server_info(web), web.session)
        web_result = await group.call_tool("Web.search", {"query": "model context protocol"})
        assert web_result.structured_content == {"result": "12 pages match 'model context protocol'."}
        library_result = await group.call_tool("Library.search", {"query": "dune"})
        assert library_result.structured_content == {"result": "3 books match 'dune'."}


async def test_disconnect_removes_every_component_of_that_server() -> None:
    """tutorial004: `disconnect_from_server` takes the session back out of all three dicts."""
    async with Client(tutorial001.mcp) as library, Client(tutorial002.mcp) as web:
        group = ClientSessionGroup(component_name_hook=tutorial004.by_server)
        await group.connect_with_session(_server_info(library), library.session)
        web_session = await group.connect_with_session(_server_info(web), web.session)
        await group.disconnect_from_server(web_session)
        assert sorted(group.tools) == ["Library.search"]
        assert sorted(group.resources) == ["Library.hours"]


async def test_read_resource_and_get_prompt_route_to_the_owning_server() -> None:
    """tutorial006: the group finds the owning server for a resource and for a prompt."""
    async with Client(tutorial001.mcp) as library, Client(tutorial005.mcp) as greeter:
        group = ClientSessionGroup(component_name_hook=tutorial006.by_server)
        await group.connect_with_session(_server_info(library), library.session)
        await group.connect_with_session(_server_info(greeter), greeter.session)

        hours = await group.read_resource("Library.hours")
        (content,) = hours.contents
        assert isinstance(content, TextResourceContents)
        assert content.text == "Mon-Fri 09:00-17:00"

        prompt = await group.get_prompt("Greeter.greet", {"name": "Ada"})
        (message,) = prompt.messages
        assert isinstance(message.content, TextContent)
        assert message.content.text == "Please write a warm greeting for Ada."


async def test_an_unknown_key_raises_key_error() -> None:
    """tutorial006: only keys the group aggregated can be read or fetched."""
    group = ClientSessionGroup()
    with pytest.raises(KeyError):
        await group.read_resource("Library.hours")
    with pytest.raises(KeyError):
        await group.get_prompt("Greeter.greet")
