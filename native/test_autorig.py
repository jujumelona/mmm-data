import copy
import hashlib
import json
import unittest
from pathlib import Path
from inp08 import parse,encode,FormatError
from test_inp08 import fixture
from autorig import compile_plan

class TestAuto(unittest.TestCase):
 def test_candidate_plan_3x3(self):
  doc,src=fixture()
  doc['param'][0]['name']='Head:: Angle'
  doc['param'][0]['axis_points']=[[-30,0,30],[-30,0,30]]
  b=doc['param'][0]['bindings'][0]
  b['isSet']=[[False]*3 for _ in range(3)]
  b['isSet'][1][1]=True
  b['values']=[[[[0,0],[0,0],[0,0]] for y in range(3)] for x in range(3)]
  src=encode(doc,parse(src)[2])
  cfg={'parameter':'Head:: Angle','landmarks':{'face':[5,5],'leftEye':[3,-10],'rightEye':[8,-10],'nose':[5,3],'mouth':[5,9],'chin':[5,30]},'node_roles':{'face':'faceguid'}}
  plan=compile_plan(doc,src,cfg)
  self.assertEqual(len(plan['patches']),8)
  self.assertEqual(plan['status'],'CANDIDATE_ONLY')
  self.assertEqual(len(plan['skipped']),0)
 def test_already_authored_is_skipped(self):
  doc,src=fixture()
  doc['param'][0]['name']='Head:: Angle'
  doc['param'][0]['axis_points']=[[-30,0,30],[-30,0,30]]
  b=doc['param'][0]['bindings'][0]
  b['isSet']=[[False]*3 for _ in range(3)]
  b['isSet'][1][1]=True
  b['isSet'][0][0]=True
  b['values']=[[[[0,0],[0,0],[0,0]] for y in range(3)] for x in range(3)]
  cfg={'landmarks':{'face':[5,5],'leftEye':[3,-10],'rightEye':[8,-10],'nose':[5,3],'mouth':[5,9],'chin':[5,30]},'node_roles':{'face':'faceguid'}}
  plan=compile_plan(doc,src,cfg)
  self.assertEqual(len(plan['patches']),7)
  self.assertTrue(any(x['reason']=='already user-authored' for x in plan['skipped']))

if __name__=='__main__':unittest.main()
