import json
import struct
import unittest

from rigging.inspect import InochiFormatError, inspect_bytes


def puppet(nodes=None, textures=()):
    payload = json.dumps({"nodes": nodes or {"type": "Node", "children": []}, "param": []}).encode()
    raw = b"TRNSRTS\x00" + struct.pack(">I", len(payload)) + payload + b"TEX_SECT" + struct.pack(">I", len(textures))
    for encoding, data in textures:
        raw += struct.pack(">I", len(data)) + bytes([encoding]) + data
    return raw


class TestInochiInspector(unittest.TestCase):
    def test_empty(self):
        result = inspect_bytes(puppet())
        self.assertEqual(result["nodes"], 1)
        self.assertEqual(result["texture_count"], 0)
        self.assertEqual(result["parameters"], 0)

    def test_geometry(self):
        node = {"type": "Part", "mesh": {"verts": [[0,0],[1,0],[0,1]], "indices":[0,1,2]}, "children":[]}
        result = inspect_bytes(puppet(node, [(0, b"abc")]))
        self.assertEqual((result["vertices"], result["triangles"], result["texture_count"]), (3,1,1))

    def test_reject_trailing_bytes(self):
        with self.assertRaises(InochiFormatError):
            inspect_bytes(puppet() + b"garbage")

    def test_reject_truncated_textures(self):
        with self.assertRaises(InochiFormatError):
            inspect_bytes(puppet(textures=[(1,b"abcd")])[:-1])

    def test_reject_wrong_magic(self):
        with self.assertRaises(InochiFormatError):
            inspect_bytes(b"NOTINP!!" + b"\x00" * 30)


if __name__ == "__main__":
    unittest.main()
