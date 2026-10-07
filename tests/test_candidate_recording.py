"""Recording adapter contracts; CPU fixtures, no model or Isaac runtime."""
import contextlib,importlib,io,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from visual_lab.core import ProtocolError

class CandidateRecordingTests(unittest.TestCase):
    def setUp(self):
        self.m=importlib.import_module('run_candidate_recording');self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.argv=['--mode','control','--goal-color','blue','--run-dir',str(self.root/'run'),'--isaac-root',str(self.root/'isaac'),
            '--headless','--admission',str(self.root/'admission.json'),'--record-every','3']
    def tearDown(self):self.tmp.cleanup()
    def test_recording_uses_same_gated_model_loop_and_native_scene_recorder(self):
        scene=MagicMock();scene.physics_pose_sync={'update_to_usd':True};scene.scenario._tool_frame='tool0'
        app=MagicMock();second=MagicMock();client=MagicMock();client.health.return_value={'requests_completed':0}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{'OMNI_KIT_ALLOW_ROOT':'1','IVD_ISAAC_PRELAUNCH_LD_LIBRARY_PATH':'','LD_LIBRARY_PATH':''}))
            stack.enter_context(patch.dict(sys.modules,{'isaacsim':types.SimpleNamespace(SimulationApp=MagicMock(return_value=app))}))
            factory=stack.enter_context(patch('visual_lab.sim.IsaacScene',return_value=scene));stack.enter_context(patch('visual_lab.capture.SceneCamera',return_value=second))
            stack.enter_context(patch.object(self.m,'DecisionClient',return_value=client));stack.enter_context(patch.object(self.m,'check_health',side_effect=lambda x:x))
            gate=stack.enter_context(patch.object(self.m,'validate_admission',return_value={'eligible':True}))
            stack.enter_context(patch.object(self.m,'find_tutorial',return_value=self.root/'tutorial.py'));stack.enter_context(patch.object(self.m,'inspect_tutorial',return_value={}))
            loop=stack.enter_context(patch.object(self.m,'run_candidate',return_value={'complete':True,'strict_success':True}))
            with contextlib.redirect_stdout(io.StringIO()):code=self.m.main(self.argv)
        self.assertEqual(code,0);gate.assert_called_once();loop.assert_called_once()
        self.assertEqual(loop.call_args.args[4:6],('blue','control'))
        self.assertEqual(factory.call_args.kwargs['record_every'],3);self.assertEqual(factory.call_args.kwargs['record_directory'],self.root/'run/frames')
        manifest=json.loads((self.root/'run/manifest.json').read_text());self.assertEqual(manifest['record_every'],3)
        self.assertEqual(manifest['source_sha256'],self.m.code_hashes());self.assertTrue(manifest['model_had_control'])
        self.assertIn('recording_entry_sha256',manifest);scene.close.assert_called_once();second.close.assert_called_once();app.close.assert_called_once()
    def test_invalid_interval_or_missing_admission_never_starts_scene(self):
        for argv in [self.argv[:-1]+['0'],self.argv[:-1]+['-1'],self.argv[:self.argv.index('--admission')]+['--record-every','3']]:
            with contextlib.redirect_stderr(io.StringIO()),patch.object(self.m,'DecisionClient') as client:
                with self.assertRaises(SystemExit):self.m.main(argv)
                client.assert_not_called()
    def test_bad_launch_environment_never_calls_model(self):
        with patch.dict(os.environ,{'OMNI_KIT_ALLOW_ROOT':'0'}),patch.object(self.m,'DecisionClient') as client,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):self.m.main(self.argv)
        client.assert_not_called()
    def test_failed_admission_never_creates_run_or_initializes_isaac(self):
        with patch.dict(os.environ,{'OMNI_KIT_ALLOW_ROOT':'1','IVD_ISAAC_PRELAUNCH_LD_LIBRARY_PATH':'','LD_LIBRARY_PATH':''}),\
            patch.object(self.m,'DecisionClient'),patch.object(self.m,'check_health'),patch.object(self.m,'validate_admission',side_effect=ProtocolError('invalid proof')):
            with self.assertRaises(ProtocolError):self.m.main(self.argv)
        self.assertFalse((self.root/'run').exists())
    def test_driver_selects_recording_entry_only_for_positive_interval(self):
        m=importlib.import_module('tools.run_candidate_experiment');plan={'isaac_python':'isaac.sh','isaac_root':'isaac'}
        job={'mode':'control','color':'blue','run_dir':'runs/48_control','record_every':3}
        command=m.episode_command(plan,job,Path('/admission.json'))
        self.assertEqual(Path(command[1]).name,'run_candidate_recording.py');self.assertEqual(command[-2:],['--record-every','3'])
        self.assertIn('/admission.json',command)
        job.pop('record_every');self.assertEqual(Path(m.episode_command(plan,job,Path('/admission.json'))[1]).name,'run_candidate.py')
        for value in [0,-1,True]:
            job['record_every']=value
            with self.assertRaises(ProtocolError):m.episode_command(plan,job,Path('/admission.json'))

if __name__=='__main__':unittest.main()
