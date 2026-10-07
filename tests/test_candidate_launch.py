"""CPU regression for the observed prelaunch/postlaunch Isaac library distinction."""
import contextlib,importlib,io,json,unittest
from pathlib import Path
from unittest.mock import patch
from visual_lab.core import ProtocolError

class LaunchTests(unittest.TestCase):
    def setUp(self):self.m=importlib.import_module('run_candidate');self.root=Path('/fixture/isaac')
    def env(self,ld=''):
        return {'OMNI_KIT_ALLOW_ROOT':'1','IVD_ISAAC_PRELAUNCH_LD_LIBRARY_PATH':'','LD_LIBRARY_PATH':ld}
    def test_isaac_launcher_can_add_its_own_libraries_after_empty_prelaunch(self):
        env=self.env(':/fixture/isaac/.:/fixture/isaac/kit:/fixture/isaac/exts/plugin/lib')
        record=self.m.launch_environment(self.root,env)
        self.assertEqual(record['before_python_sh'],{'OMNI_KIT_ALLOW_ROOT':'1','LD_LIBRARY_PATH':''})
        self.assertEqual(record['inside_isaac_ld_library_path'],env['LD_LIBRARY_PATH'])
    def test_system_python_library_cannot_precede_isaac(self):
        with self.assertRaises(ProtocolError):self.m.launch_environment(self.root,self.env('/usr/local/lib:/fixture/isaac/kit'))
    def test_prelaunch_declaration_must_be_present_and_empty(self):
        env=self.env();env.pop('IVD_ISAAC_PRELAUNCH_LD_LIBRARY_PATH')
        with self.assertRaises(ProtocolError):self.m.launch_environment(self.root,env)
        env=self.env();env['IVD_ISAAC_PRELAUNCH_LD_LIBRARY_PATH']='/usr/local/lib'
        with self.assertRaises(ProtocolError):self.m.launch_environment(self.root,env)
    def test_root_opt_in_still_required_and_direct_empty_is_allowed(self):
        self.assertEqual(self.m.launch_environment(self.root,self.env())['inside_isaac_ld_library_path'],'')
        env=self.env();env['OMNI_KIT_ALLOW_ROOT']='0'
        with self.assertRaises(ProtocolError):self.m.launch_environment(self.root,env)
    def test_relative_and_sibling_prefix_paths_are_rejected(self):
        for ld in ['kit','/fixture/isaac-other/lib','/fixture/isaac/../system/lib']:
            with self.assertRaises(ProtocolError):self.m.launch_environment(self.root,self.env(ld))
    def test_launch_only_never_constructs_client_or_creates_run_directory(self):
        argv=['run_candidate.py','--mode','shadow','--goal-color','blue','--isaac-root',str(self.root),'--run-dir','unused','--check-launch-only']
        output=io.StringIO()
        with patch('sys.argv',argv),patch.dict(self.m.os.environ,self.env(':/fixture/isaac/kit'),clear=True),patch.object(self.m,'DecisionClient') as client,patch.object(self.m,'AuditLog') as log,contextlib.redirect_stdout(output):
            self.assertEqual(self.m.main(),0)
        client.assert_not_called();log.assert_not_called();record=json.loads(output.getvalue());self.assertEqual(record['model_calls'],0);self.assertFalse(record['simulation_app_started'])

if __name__=='__main__':unittest.main()
