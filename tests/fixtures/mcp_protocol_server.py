"""Synthetic server for real stdio/HTTP protocol tests; no tourism provider."""
import argparse
from mcp.server import MCPServer
from pydantic import BaseModel

server = MCPServer('synthetic-travel-fixture',version='1',log_level='ERROR')


@server.tool()
def brave_web_search(query: str) -> str:
    """Synthetic Brave-shaped result; no real web request."""
    import json
    return json.dumps({'title': '합성 공식 안내', 'url': 'https://example.com/visit',
        'description': '합성 검색 요약.', 'extra_snippets': ['추가 근거가 완전한 문장으로 유지됩니다.']}, ensure_ascii=False)


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
