"""Old CLI entrypoints must never bypass protections on the MCP/transaction paths."""
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from test_rigging import specimen
ROOT=Path(__file__).resolve().parents[1]
class AlternateWriters(unittest.TestCase):
    def test_legacy_cli_cannot_replace_existing_keyform_using_privileged_flag(self):
        doc,raw,_=specimen()
        plan={'format':'inochi-authoring.keyform-plan.v1','source_sha256':hashlib.sha256(raw).hexdigest(),
              'patches':[{'parameter':'Head:: Angle','node_guid':'face-001','key_index':[1,1],
                          'vertex_offsets':[[0,0] for _ in range(5)],'allow_replace':True}]}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);src=root/'src.inp';src.write_bytes(raw)
            planfile=root/'plan.json';planfile.write_text(json.dumps(plan))
            out=root/'new.inp'
            proc=subprocess.run([sys.executable,str(ROOT/'native/autorig.py'),'apply',str(src),
                   '--plan',str(planfile),'--output',str(out),'--acknowledge-visual-review-required'],
                   text=True,capture_output=True)
            self.assertNotEqual(proc.returncode,0,proc.stdout)
            self.assertFalse(out.exists())
            self.assertEqual(src.read_bytes(),raw)
    def test_cli_propose_keeps_existing_output(self):
        _,raw,manifest=specimen()
        config={'node_guid':'face-001','parameter':'Head:: Angle','key_index':[2,2],
                'targets_local':{'a':[0,0],'b':[10,0],'c':[0,10],'d':[10,11]}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'src.inx';src.write_bytes(raw)
            anchors=root/'anchors.json';anchors.write_text(json.dumps(manifest))
            cfg=root/'cfg.json';cfg.write_text(json.dumps(config))
            out=root/'plan.json';out.write_text('PRESERVE')
            result=subprocess.run([sys.executable,'-m','rigging.cli','propose',str(src),str(anchors),
                                   str(cfg),'--out',str(out)],cwd=ROOT,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertEqual(out.read_text(),'PRESERVE')
