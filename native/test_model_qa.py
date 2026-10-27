import copy
import unittest
from test_inp08 import fixture
from model_qa import run

class TestModelQA(unittest.TestCase):
 def test_valid_poses(self):
  doc,_=fixture()
  report=run(doc)
  self.assertTrue(report['geometryPass'])
  self.assertEqual(report['samplesChecked'],4)
 def test_invalid_fold(self):
  doc,_=fixture()
  doc['param'][0]['bindings'][0]['values'][0][0][1]=[-30,0]
  report=run(doc)
  self.assertFalse(report['geometryPass'])
  self.assertGreater(report['failedTriangles'],0)
if __name__=='__main__':unittest.main()
