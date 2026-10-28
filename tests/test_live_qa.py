from __future__ import annotations
import base64
import struct
import unittest
from unittest.mock import patch
from rigging.live_qa import capture_pose_sweep,LiveQAError
from rigging.creator_bridge import CreatorBridgeError

# Synthetic PNG header is sufficient for the metadata-only capture test. It
# cannot be passed off as a rendered scene or perceptual-quality check.
PNG=b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',1,1)+b'\x08\x06\x00\x00\x00'

class TestLiveQA(unittest.TestCase):
    def fake(self,fail_capture=False):
        value=[0,0]
        calls=[]
        def call(method,params=None):
            calls.append((method,params))
            if method=='get_status':return {'project_path':'/project/test.inx','armed_parameter':None}
            if method=='list_parameters':return {'parameters':[{'uuid':123,'name':'Head X','is_group':False,
                'is_vec2':False,'value':value[:],'min':[-30,0],'max':[30,0]}]}
            if method=='set_parameter':
                value[0]=params['x'];value[1]=params['y'];return {'ok':True}
            if method=='capture_viewport':
                if fail_capture:raise CreatorBridgeError('simulated real capture failure')
                return {'png_base64':base64.b64encode(PNG).decode(),'width':1,'height':1}
            raise AssertionError(method)
        return call,value,calls

    def test_captures_restores_and_never_returns_images(self):
        call,value,calls=self.fake()
        with patch('rigging.live_qa.call_creator',side_effect=call):
            report=capture_pose_sweep('123',[[-30,0],[30,0]])
        self.assertEqual(report['actual_viewports_captured'],2)
        self.assertEqual(value,[0,0])
        self.assertIsNone(report['aesthetic_score'])
        self.assertTrue(all('png_base64' not in frame for frame in report['poses']))
        self.assertEqual(calls[-2][0],'set_parameter')
        self.assertEqual(calls[-2][1]['x'],0)

    def test_capture_failure_always_restores(self):
        call,value,calls=self.fake(fail_capture=True)
        with patch('rigging.live_qa.call_creator',side_effect=call):
            with self.assertRaisesRegex(CreatorBridgeError,'capture failure'):
                capture_pose_sweep('123',[[30,0]])
        self.assertEqual(value,[0,0])

    def test_reject_invalid_pose_before_changing_editor(self):
        call,value,calls=self.fake()
        with patch('rigging.live_qa.call_creator',side_effect=call):
            for poses in ([[90,0]],[[0,1]],[[float('nan'),0]]):
                with self.assertRaises(LiveQAError):capture_pose_sweep('123',poses)
        self.assertFalse(any(name=='set_parameter' for name,_ in calls))

if __name__=='__main__':unittest.main()
