"""Offline video cadence and reused-shadow timing checks, no GPU or model."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_recording_auditor',ROOT/'test_reports/candidate_control_auditor_20261007.py')
auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)

class RecordingAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.run=self.root/'48_control';(self.run/'frames').mkdir(parents=True)
        self.manifest={'record_every':3,'recording_entry_sha256':'pinned','config':{'physics_dt':1/60,'warmup_frames':120,'camera':{'resolution':[16,12]}}}
        self.summary={'recorded_frames':3,'physics_updates':129};self.plan={'source_sha256':{'run_candidate_recording.py':'pinned'}}
        for i in range(3):Image.new('RGB',(16,12),(i,10,30)).save(self.run/'frames'/f'frame_{i:06d}.png')
    def tearDown(self):self.tmp.cleanup()
    def test_recorded_frames_have_native_simulation_cadence_and_hashes(self):
        result=auditor.audit_recording(self.run,self.manifest,self.summary,self.plan)
        self.assertEqual(result['fps'],20);self.assertEqual(result['frame_count'],3);self.assertEqual(len(result['files_sha256']),3)
        self.assertEqual(result['playback_seconds'],.15);self.assertTrue(result['api_waits_omitted'])
    def test_missing_frame_or_changed_recording_source_rejected(self):
        self.manifest['recording_entry_sha256']='changed'
        with self.assertRaises(AssertionError):auditor.audit_recording(self.run,self.manifest,self.summary,self.plan)
        self.manifest['recording_entry_sha256']='pinned';(self.run/'frames/frame_000001.png').unlink()
        with self.assertRaises(AssertionError):auditor.audit_recording(self.run,self.manifest,self.summary,self.plan)
    def test_two_reused_shadows_can_precede_recording_without_new_shadow_launch(self):
        plan={'reused_shadows':[{'run_dir':'runs/blue'},{'run_dir':'runs/yellow'}]}
        for name in ['blue','yellow']:
            (self.root/name).mkdir();(self.root/name/'events.jsonl').write_text(json.dumps({'utc':'2026-10-07T09:30:00+00:00'})+'\n')
        life={'runs':[{'mode':'control','started_utc':'2026-10-07T09:40:00+00:00'}]}
        auditor.verify_admission_timing(self.root,plan,life)
        life['runs'][0]['started_utc']='2026-10-07T09:20:00+00:00'
        with self.assertRaises(AssertionError):auditor.verify_admission_timing(self.root,plan,life)

if __name__=='__main__':unittest.main()
