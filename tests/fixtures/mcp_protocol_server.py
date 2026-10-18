"""Synthetic server for real stdio/HTTP protocol tests; no tourism provider."""
import argparse
from mcp.server import MCPServer
from pydantic import BaseModel

server = MCPServer('synthetic-travel-fixture',version='1',log_level='ERROR')


class Place(BaseModel):
    synthetic: bool
    name: str
    access: str
    source: str


@server.tool(structured_output=True)
def lookup_place(name: str) -> Place:
    """Return synthetic place data for protocol validation only."""
    return Place(synthetic=True,name=name,access='가상 계단 7개',source='test-fixture')


@server.tool()
def fail_lookup(name: str) -> str:
    """Return a deliberate fixture tool error."""
    from mcp.server.mcpserver.exceptions import ToolError
    raise ToolError('Synthetic provider unavailable')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int)
    args=parser.parse_args()
    if args.port:
        server.run(transport='streamable-http',host='127.0.0.1',port=args.port)
    else:
        server.run()
