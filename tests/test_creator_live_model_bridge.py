"""Integration tests use real INP bytes and a fake Creator RPC; no live GUI claims."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native.inp08 import parse, encode
from rigging.contracts import mesh_fingerprint
from rigging.live_model_bridge import prepare_session, preview_batch, apply_batch, CreatorSessionError
from rigging.transactions import FORMAT
from test_rigging import specimen


class RpcDouble:
    def __init__(self, model):
        self.model = model
        self.project = "/models/source.inx"
        self.imports = 0
        self.corrupt_once = False

    def __call__(self, method, params=None):
        if method == "get_status":
            return {"project_path": self.project, "edit_mode": "model", "armed_parameter": None}
        if method == "export_inp":
            Path(params["path"]).write_bytes(self.model)
            return {"path": params["path"]}
        if method == "import_inp":
            self.imports += 1
            self.model = Path(params["path"]).read_bytes()
            if self.corrupt_once and self.imports == 1:
                doc, _, tail = parse(self.model)
                doc["meta"]["name"] = "unexpected-editor-change"
                self.model = encode(doc, tail)
            self.project = ""
            return True
        raise AssertionError(method)


class LiveBridgeTests(unittest.TestCase):
    def setUp(self):
        self.doc, self.raw, _ = specimen()
        self.rpc = RpcDouble(self.raw)
        self.batch = {
            "format": FORMAT,
            "source_sha256": hashlib.sha256(self.raw).hexdigest(),
            "request_id": "live-001",
            "edits": [{
                "op": "subdivide_mesh",
                "node_guid": "face-001",
                "expected_mesh_sha256": mesh_fingerprint(
                    self.doc["nodes"]["children"][0]["mesh"]
                )
            }]
        }

    def test_prepare_and_preview_are_non_destructive(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("rigging.live_model_bridge.call_creator", side_effect=self.rpc):
            info = prepare_session(directory, expected_project_path="/models/source.inx")
            report = preview_batch(info["session_path"], self.batch)
            self.assertFalse(report["committed"])
            self.assertEqual(self.rpc.model, self.raw)
            self.assertEqual(self.rpc.imports, 0)
            self.assertEqual((Path(info["session_path"]) / "source.inp").read_bytes(), self.raw)

    def test_apply_imports_and_verifies_readback(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("rigging.live_model_bridge.call_creator", side_effect=self.rpc), \
             patch.dict("os.environ", {"INOCHI_CREATOR_MUTATIONS": "1"}):
            info = prepare_session(directory, expected_project_path="/models/source.inx")
            result = apply_batch(info["session_path"], self.batch,
                                 expected_project_path="/models/source.inx",
                                 acknowledge_project_replacement=True)
            self.assertTrue(result["creator_import_verified"])
            self.assertFalse(result["editor_undo_history_preserved"])
            self.assertEqual(self.rpc.imports, 1)
            self.assertEqual(len(parse(self.rpc.model)[0]["nodes"]["children"][0]["mesh"]["verts"]), 13)
            self.assertEqual((Path(info["session_path"]) / "source.inp").read_bytes(), self.raw)

    def test_prevent_unacknowledged_import(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("rigging.live_model_bridge.call_creator", side_effect=self.rpc):
            info = prepare_session(directory, expected_project_path="/models/source.inx")
            with self.assertRaisesRegex(CreatorSessionError, "acknowledge"):
                apply_batch(info["session_path"], self.batch,
                            expected_project_path="/models/source.inx")
            self.assertEqual(self.rpc.imports, 0)

    def test_recheck_blocks_concurrent_editor_change(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("rigging.live_model_bridge.call_creator", side_effect=self.rpc), \
             patch.dict("os.environ", {"INOCHI_CREATOR_MUTATIONS": "1"}):
            info = prepare_session(directory, expected_project_path="/models/source.inx")
            doc, _, tail = parse(self.raw)
            doc["meta"]["name"] = "changed"
            self.rpc.model = encode(doc, tail)
            with self.assertRaisesRegex(CreatorSessionError, "changed"):
                apply_batch(info["session_path"], self.batch,
                            expected_project_path="/models/source.inx",
                            acknowledge_project_replacement=True)
            self.assertEqual(self.rpc.imports, 0)

    def test_failed_readback_rolls_back_source_model(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("rigging.live_model_bridge.call_creator", side_effect=self.rpc), \
             patch.dict("os.environ", {"INOCHI_CREATOR_MUTATIONS": "1"}):
            info = prepare_session(directory, expected_project_path="/models/source.inx")
            self.rpc.corrupt_once = True
            with self.assertRaises(CreatorSessionError):
                apply_batch(info["session_path"], self.batch,
                            expected_project_path="/models/source.inx",
                            acknowledge_project_replacement=True)
            self.assertEqual(parse(self.rpc.model)[0], self.doc)
            self.assertEqual(self.rpc.imports, 2)
            self.assertEqual(json.loads((Path(info["session_path"]) / "manifest.json").read_text())["state"], "rolled_back")


if __name__ == "__main__":
    unittest.main()
