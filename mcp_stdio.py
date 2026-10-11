"""Stdio MCP bridge. Run with the project venv; start the web app first.

This process deliberately imports no backend modules: only the web app owns
the database, job recovery and worker pool, even with multiple MCP clients.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from mcp import Client
from mcp.server import Server
from mcp.server.stdio import stdio_server


def local_url(value):
    try:
        parsed = urlparse(value)
        port = parsed.port
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or port == 0 or parsed.path.rstrip('/') != '/mcp'):
            raise ValueError()
    except ValueError:
        raise argparse.ArgumentTypeError('Use a loopback HTTP MCP URL, such as http://127.0.0.1:8787/mcp') from None
    return value


async def serve(url):
    async with Client(url, read_timeout_seconds=300) as client:
        async def list_tools(ctx, params):
            return await client.list_tools(cursor=params.cursor if params else None)

        async def call_tool(ctx, params):
            return await client.call_tool(params.name, params.arguments)

        bridge = Server('shipwreck-hunter', version='0.1.0',
                        instructions=client.instructions,
                        on_list_tools=list_tools, on_call_tool=call_tool)
        async with stdio_server() as (reader, writer):
            await bridge.run(reader, writer, bridge.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', type=local_url, default='http://127.0.0.1:8787/mcp')
    parser.add_argument('--print-config', action='store_true', help='Print a desktop MCP configuration using absolute paths, then exit')
    args = parser.parse_args()
    if args.print_config:
        print(json.dumps({'mcpServers': {'shipwreck-hunter': {
            'command': sys.executable,
            'args': [str(Path(__file__).resolve()), '--url', args.url],
        }}}, indent=2))
        return
    try:
        asyncio.run(serve(args.url))
    except KeyboardInterrupt:
        pass
    except Exception:
        print('Cannot communicate with Shipwreck Hunter. Start/restart python start.py, '
              'then reconnect this MCP client. Check --url if using another port.', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
