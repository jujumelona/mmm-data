"""Real MCP stdio subprocess handshake. CI installs the optional MCP SDK."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import unittest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    HAVE_MCP = False
else:
    HAVE_MCP = True


@unittest.skipUnless(HAVE_MCP, 'Install pip install -e ".[mcp]" for real MCP smoke test')
class RealMCPStdioTest(unittest.TestCase):
    def test_real_mcp_initialize_list_and_invoke(self):
        async def verify():
            repo = Path(__file__).resolve().parents[1]
            env = dict(os.environ)
            env['PYTHONPATH'] = str(repo)
            env['INOCHI_CREATOR_MUTATIONS'] = '0'
            params = StdioServerParameters(
                command=sys.executable,
                args=['-m', 'rigging.mcp_server'],
                env=env,
            )
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()
                    available = await client.list_tools()
                    names = {item.name for item in available.tools}
                    for needed in ('rig_status', 'rig_inspect', 'creator_probe_connection',
                                   'creator_manual_edit_snapshot'):
                        self.assertIn(needed, names)
                    response = await client.call_tool('rig_status', {})
                    self.assertFalse(getattr(response, 'is_error', getattr(response, 'isError', False)))
                    content = next(item.text for item in response.content if item.type == 'text')
                    value = json.loads(content)
                    self.assertEqual(value['psd_to_full_rig'], 'NOT implemented')
                    self.assertEqual(value['creator_live_mesh_and_binding_edit'], 'NOT implemented')
        asyncio.run(verify())


if __name__ == '__main__':
    unittest.main()
