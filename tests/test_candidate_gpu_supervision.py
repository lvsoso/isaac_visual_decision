"""CPU namespace-accounting contracts, no CUDA allocation or model inference."""
import importlib,unittest
from visual_lab.core import ProtocolError

class GPUSupervisionTests(unittest.TestCase):
    def setUp(self):self.m=importlib.import_module('tools.run_candidate_experiment')
    def test_gpu_host_pid_need_not_equal_container_service_pid(self):
        baseline=self.m.gpu_baseline('1491493, [Not Found], 428 MiB',container_service_pid=114184)
        self.assertEqual(baseline['host_gpu_pids'],[1491493]);self.assertEqual(baseline['container_service_pid'],114184)
        record=self.m.verify_gpu_after_episode(baseline,'1491493, [Not Found], 8000 MiB')
        self.assertTrue(record['only_pinned_model_gpu_process_remains'])
        self.assertEqual(record['observed_host_gpu_pids'],[1491493])
    def test_same_namespace_also_passes_without_special_case(self):
        baseline=self.m.gpu_baseline('114184, /env/bin/python, 8000 MiB',container_service_pid=114184)
        self.assertTrue(self.m.verify_gpu_after_episode(baseline,'114184, /env/bin/python, 9000 MiB')['only_pinned_model_gpu_process_remains'])
    def test_any_extra_host_gpu_pid_remains_terminal(self):
        baseline=self.m.gpu_baseline('1491493, [Not Found], 8000 MiB',container_service_pid=114184)
        with self.assertRaises(ProtocolError) as raised:self.m.verify_gpu_after_episode(baseline,'1491493, [Not Found], 8000 MiB\n1491494, [Not Found], 4000 MiB')
        self.assertIn('1491494',str(raised.exception))
    def test_lost_or_replaced_model_gpu_process_is_rejected(self):
        baseline=self.m.gpu_baseline('1491493, [Not Found], 8000 MiB',container_service_pid=114184)
        for report in ['', '1491494, [Not Found], 8000 MiB']:
            with self.assertRaises(ProtocolError):self.m.verify_gpu_after_episode(baseline,report)
    def test_baseline_requires_exactly_one_gpu_process_after_idle_precheck(self):
        for report in ['', '1, python, 100 MiB\n2, other, 100 MiB', 'not-a-pid, python, 100 MiB']:
            with self.assertRaises(ProtocolError):self.m.gpu_baseline(report,container_service_pid=114184)
    def test_whitespace_order_and_container_pid_are_recorded_separately(self):
        baseline=self.m.gpu_baseline(' 1491493 , [Not Found], 8000 MiB\n',container_service_pid=114184)
        record=self.m.verify_gpu_after_episode(baseline,'1491493, [Not Found], 8000 MiB\n')
        self.assertEqual(record['container_service_pid'],114184);self.assertIn('[Not Found]',record['observed_compute_report'])

if __name__=='__main__':unittest.main()
