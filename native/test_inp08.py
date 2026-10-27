import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from inp08 import MAGIC,parse,encode,inspect,extract_samples,apply_keyform,FormatError,atomic_write

HERE=Path(__file__).resolve().parent

def fixture():
  doc={"meta":{"name":"SYNTHETIC QA MODEL"},"nodes":{"name":"Root","uuid":"root","children":[{"name":"face","uuid":"faceguid","mesh":{"verts":[[0,0],[10,0],[0,10]],"uvs":[[0,0],[1,0],[0,1]],"indices":[0,1,2]}}]},"param":[{"name":"Angle X","guid":"paramguid","axis_points":[[-30,0,30],[0]],"bindings":[{"node":"faceguid","param_name":"deform","values":[[[[0,0],[0,0],[0,0]]],[[[0,0],[0,0],[0,0]]],[[[0,0],[0,0],[0,0]]]],"isSet":[[False],[True],[False]]}]}],"animations":{}}
  png=b'\x89PNG\r\n\x1a\nsynthetic' # opaque tail preservation, not visual asset
  tex=b'TEX_SECT'+struct.pack('>I',1)+struct.pack('>I',len(png))+b'\x00'+png
  ext=b'EXT_SECT'+struct.pack('>I',1)+struct.pack('>I',6)+b'vendor'+struct.pack('>I',4)+b'data'
  return doc,encode(doc,tex+ext)

class TestINP(unittest.TestCase):
 def test_roundtrip_and_preserved_sections(self):
  doc,original=fixture();parsed,raw,tail=parse(original)
  self.assertEqual(parsed,doc)
  self.assertEqual(original,MAGIC+struct.pack('>I',len(raw))+raw+tail)
  self.assertEqual(parse(encode(parsed,tail))[2],tail)
 def test_inspect_extract(self):
  doc,data=fixture();self.assertEqual(inspect(doc)['mesh_nodes'][0]['vertices'],3)
  result=extract_samples(doc);self.assertEqual(len(result['samples']),4)
 def test_apply_existing_empty_binding_and_texture_preserve(self):
  doc,data=fixture();patch={"parameter":"Angle X","node_guid":"faceguid","key_index":[0,0],"vertex_offsets":[[0,0],[1,0],[0,0]]}
  got=apply_keyform(doc,patch);self.assertEqual(got['changed_vertices'],3)
  self.assertTrue(doc['param'][0]['bindings'][0]['isSet'][0][0])
  out=encode(doc,parse(data)[2]);self.assertEqual(parse(out)[2],parse(data)[2])
 def test_cannot_overwrite_existing_key(self):
  doc,_=fixture()
  with self.assertRaises(FormatError):apply_keyform(doc,{"parameter":"Angle X","node_guid":"faceguid","key_index":[1,0],"vertex_offsets":[[0,0],[0,0],[0,0]]})
 def test_reject_bad_mesh(self):
  doc,_=fixture()
  with self.assertRaises(FormatError):apply_keyform(doc,{"parameter":"Angle X","node_guid":"faceguid","key_index":[0,0],"vertex_offsets":[[0,0],[-30,0],[0,0]]})
 def test_reject_inp2_and_invalid_sections(self):
  _,data=fixture()
  for d in [b'TRNSRTS2bad',data[:20],data.replace(b'TEX_SECT',b'BAD_SECT')]:
   with self.assertRaises(FormatError):parse(d)
 def test_source_checksum_and_cli(self):
  doc,data=fixture()
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);src=base/'m.inp';src.write_bytes(data)
   cp=subprocess.run([sys.executable,str(HERE/'inp08.py'),'inspect',str(src)],capture_output=True,text=True)
   self.assertEqual(cp.returncode,0,cp.stderr)
   self.assertIn('faceguid',cp.stdout)
   cp=subprocess.run([sys.executable,str(HERE/'inp08.py'),'roundtrip',str(src),'--output',str(base/'copy.inp')],capture_output=True,text=True)
   self.assertEqual(cp.returncode,0,cp.stderr)
   self.assertEqual((base/'copy.inp').read_bytes(),data)
   patch={"source_sha256":hashlib.sha256(data).hexdigest(),"parameter":"Angle X","node_guid":"faceguid","key_index":[0,0],"vertex_offsets":[[0,0],[1,0],[0,0]]}
   (base/'patch.json').write_text(json.dumps(patch))
   cp=subprocess.run([sys.executable,str(HERE/'inp08.py'),'patch-keyform',str(src),'--patch',str(base/'patch.json'),'--output',str(base/'patched.inp')],capture_output=True,text=True)
   self.assertEqual(cp.returncode,0,cp.stderr)
   self.assertEqual(parse((base/'patched.inp').read_bytes())[0]['param'][0]['bindings'][0]['values'][0][0][1],[1,0])
   cp=subprocess.run([sys.executable,str(HERE/'inp08.py'),'patch-keyform',str(src),'--patch',str(base/'patch.json'),'--output',str(base/'patched.inp')],capture_output=True,text=True)
   self.assertNotEqual(cp.returncode,0)
 def test_refuse_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'foo';path.write_text('original')
   with self.assertRaises(FormatError):atomic_write(path,b'overwrite')
   self.assertEqual(path.read_text(),'original')

if __name__=='__main__':unittest.main()
