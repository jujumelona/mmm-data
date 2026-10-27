import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from inp08 import encode,parse
from test_inp08 import fixture

HERE=Path(__file__).resolve().parent
CFG={'parameter':'Head:: Angle','landmarks':{'face':[5,5],'leftEye':[3,-10],'rightEye':[8,-10],'nose':[5,3],'mouth':[5,9],'chin':[5,30]},'node_roles':{'face':'faceguid'}}
class TestFullFlow(unittest.TestCase):
 def test_plan_apply_and_inspect_real_format_roundtrip(self):
  doc,source=fixture()
  doc['param'][0]['name']='Head:: Angle'
  doc['param'][0]['axis_points']=[[-30,0,30],[-30,0,30]]
  b=doc['param'][0]['bindings'][0]
  b['values']=[[[[0,0],[0,0],[0,0]] for y in range(3)] for x in range(3)]
  b['isSet']=[[False]*3 for _ in range(3)]
  b['isSet'][1][1]=True
  source=encode(doc,parse(source)[2])
  with tempfile.TemporaryDirectory() as td:
   t=Path(td)
   (t/'source.inp').write_bytes(source)
   (t/'config.json').write_text(json.dumps(CFG))
   def call(*args):
    return subprocess.run([sys.executable,str(HERE/'autorig.py'),*map(str,args)],capture_output=True,text=True)
   plan=call('plan',t/'source.inp','--config',t/'config.json','--output',t/'plan.json')
   self.assertEqual(plan.returncode,0,plan.stderr)
   self.assertEqual(len(json.loads((t/'plan.json').read_text())['patches']),8)
   deny=call('apply',t/'source.inp','--plan',t/'plan.json','--output',t/'new.inp')
   self.assertNotEqual(deny.returncode,0)
   apply=call('apply',t/'source.inp','--plan',t/'plan.json','--output',t/'new.inp','--acknowledge-visual-review-required')
   self.assertEqual(apply.returncode,0,apply.stderr)
   new,told,tail=parse((t/'new.inp').read_bytes())
   self.assertEqual(tail,parse(source)[2])
   self.assertTrue(new['param'][0]['bindings'][0]['isSet'][0][0])
   self.assertTrue(new['param'][0]['bindings'][0]['isSet'][1][1])
   qa=subprocess.run([sys.executable,str(HERE/'model_qa.py'),str(t/'new.inp')],capture_output=True,text=True)
   self.assertEqual(qa.returncode,0,qa.stderr)
if __name__=='__main__':unittest.main()
