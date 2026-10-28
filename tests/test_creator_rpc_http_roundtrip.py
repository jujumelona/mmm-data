"""Real localhost HTTP transport smoke test with simulated Creator RPC.

NOT a test of the patched Inochi Creator binary or its viewport renderer.
"""
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from native.inp08 import parse
from rigging.contracts import mesh_fingerprint
from rigging.live_model_bridge import prepare_session, preview_batch, apply_batch
from rigging.transactions import FORMAT
from test_rigging import specimen


class CreatorHttpRoundtripTests(unittest.TestCase):
    def test_http_export_edit_import_readback(self):
        doc, source, _ = specimen()
        state = {"model": source, "project": "/projects/example.inx", "calls": []}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *unused):
                return

            def do_POST(self):
                if self.path != "/rpc":
                    self.send_error(404)
                    return
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                method = request["method"]
                params = request.get("params", {})
                state["calls"].append(method)
                if method == "get_status":
                    result = {"project_path": state["project"], "edit_mode": "model",
                              "armed_parameter": None}
                elif method == "export_inp":
                    Path(params["path"]).write_bytes(state["model"])
                    result = {"path": params["path"]}
                elif method == "import_inp":
                    state["model"] = Path(params["path"]).read_bytes()
                    state["project"] = ""
                    result = True
                else:
                    self.send_error(400)
                    return
                data = json.dumps({"ok": True, "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as td, patch.dict(
                "os.environ",
                {"INOCHI_MCP_PORT": str(server.server_address[1]),
                 "INOCHI_CREATOR_MUTATIONS": "1"},
            ):
                session = prepare_session(td, expected_project_path=state["project"])
                batch = {
                    "format": FORMAT,
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "request_id": "http-smoke-1",
                    "edits": [{
                        "op": "subdivide_mesh",
                        "node_guid": "face-001",
                        "expected_mesh_sha256": mesh_fingerprint(
                            doc["nodes"]["children"][0]["mesh"])
                    }],
                }
                self.assertFalse(preview_batch(session["session_path"], batch)["committed"])
                result = apply_batch(
                    session["session_path"], batch,
                    expected_project_path="/projects/example.inx",
                    acknowledge_project_replacement=True)
                self.assertTrue(result["creator_import_verified"])
                self.assertIn("import_inp", state["calls"])
                self.assertEqual(
                    len(parse(state["model"])[0]["nodes"]["children"][0]["mesh"]["verts"]),
                    13)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=4)


if __name__ == "__main__":
    unittest.main()
