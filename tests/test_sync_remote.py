"""Real local Git repositories stand in for the source and deployment checkout."""
import importlib
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SyncRemoteTests(unittest.TestCase):
    def setUp(self):
        self.sync = importlib.import_module("tools.sync_remote")
        self.temp = tempfile.TemporaryDirectory(prefix="isaac sync test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.remote = self.root / "remote checkout"
        self.source.mkdir()
        self.git(self.source, "init", "-b", "main")
        self.configure(self.source)
        (self.source / ".gitignore").write_text("runs/\nmodels/\n.env\n")
        (self.source / "code.py").write_text("version = 1\n")
        self.git(self.source, "add", ".")
        self.git(self.source, "commit", "-m", "baseline")
        self.git(self.root, "clone", str(self.source), str(self.remote))
        self.configure(self.remote)
        self.old_head = self.git(self.remote, "rev-parse", "HEAD")
        (self.source / "code.py").write_text("version = 2\n")
        self.git(self.source, "commit", "-am", "update")
        self.new_head = self.git(self.source, "rev-parse", "HEAD")
        self.bundle = self.root / "update.bundle"
        self.git(self.source, "bundle", "create", str(self.bundle), "refs/heads/main")

    def git(self, directory, *args):
        return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(directory), *args],
                              check=True, text=True, capture_output=True).stdout.strip()

    def configure(self, directory):
        self.git(directory, "config", "user.name", "Sync Test")
        self.git(directory, "config", "user.email", "sync-test@example.invalid")

    def remote_call(self, action, *args, directory=None):
        return subprocess.run([sys.executable, "-c", self.sync.REMOTE_SCRIPT,
                               str(directory or self.remote), action, *args],
                              text=True, capture_output=True)

    def remote_json(self, action, *args):
        result = self.remote_call(action, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def stage_bundle(self):
        stage = self.remote_json("prepare", self.old_head)["staging"]
        Path(stage, "update.bundle").write_bytes(self.bundle.read_bytes())
        return stage

    def test_fast_forward_preserves_results_models_and_origin(self):
        for folder in ("runs", "models"):
            (self.remote / folder).mkdir()
            (self.remote / folder / "keep.txt").write_text("do not delete")
        origin = self.git(self.remote, "remote", "get-url", "origin")
        stage = self.stage_bundle()
        result = self.remote_json("apply", stage, self.new_head, self.old_head)
        self.assertEqual(result["head"], self.new_head)
        self.assertEqual(self.git(self.remote, "rev-parse", "HEAD"), self.new_head)
        self.assertEqual(self.git(self.remote, "remote", "get-url", "origin"), origin)
        for folder in ("runs", "models"):
            self.assertEqual((self.remote / folder / "keep.txt").read_text(), "do not delete")
        self.remote_json("cleanup", stage)
        self.assertFalse(Path(stage).exists())

    def test_dirty_remote_refuses_update(self):
        (self.remote / "code.py").write_text("remote work\n")
        result = self.remote_call("prepare", self.old_head)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uncommitted", result.stderr)
        self.assertEqual((self.remote / "code.py").read_text(), "remote work\n")
        self.assertEqual(self.git(self.remote, "rev-parse", "HEAD"), self.old_head)

    def test_untracked_remote_file_is_not_discarded(self):
        (self.remote / "notes.txt").write_text("user notes")
        self.assertNotEqual(self.remote_call("inspect").returncode, 0)
        self.assertEqual((self.remote / "notes.txt").read_text(), "user notes")

    def test_diverged_history_refuses_merge(self):
        (self.remote / "local.py").write_text("local work\n")
        self.git(self.remote, "add", "local.py")
        self.git(self.remote, "commit", "-m", "remote commit")
        remote_head = self.git(self.remote, "rev-parse", "HEAD")
        stage = self.remote_json("prepare", remote_head)["staging"]
        Path(stage, "update.bundle").write_bytes(self.bundle.read_bytes())
        result = self.remote_call("apply", stage, self.new_head, remote_head)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fast-forward", result.stderr)
        self.assertEqual(self.git(self.remote, "rev-parse", "HEAD"), remote_head)

    def test_wrong_branch_and_nested_directory_are_rejected(self):
        nested = self.remote / "nested"
        nested.mkdir()
        self.assertNotEqual(self.remote_call("inspect", directory=nested).returncode, 0)
        nested.rmdir()
        self.git(self.remote, "checkout", "-b", "other")
        self.assertNotEqual(self.remote_call("inspect").returncode, 0)

    def test_remote_change_after_prepare_is_not_overwritten(self):
        stage = self.stage_bundle()
        (self.remote / "code.py").write_text("changed during upload\n")
        self.assertNotEqual(self.remote_call("apply", stage, self.new_head, self.old_head).returncode, 0)
        self.assertEqual((self.remote / "code.py").read_text(), "changed during upload\n")

    def test_ignored_file_collision_is_not_overwritten(self):
        (self.remote / "runs").mkdir()
        (self.remote / "runs" / "keep.txt").write_text("experiment")
        (self.source / "runs").mkdir()
        (self.source / "runs" / "keep.txt").write_text("incoming tracked file")
        self.git(self.source, "add", "-f", "runs/keep.txt")
        self.git(self.source, "commit", "-m", "collision")
        incoming = self.git(self.source, "rev-parse", "HEAD")
        self.bundle.unlink()
        self.git(self.source, "bundle", "create", str(self.bundle), "refs/heads/main")
        stage = self.stage_bundle()
        self.assertNotEqual(self.remote_call("apply", stage, incoming, self.old_head).returncode, 0)
        self.assertEqual((self.remote / "runs" / "keep.txt").read_text(), "experiment")
        self.assertEqual(self.git(self.remote, "rev-parse", "HEAD"), self.old_head)

    def test_cleanup_cannot_target_user_directory(self):
        result = self.remote_call("cleanup", str(self.remote))
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.remote / "code.py").exists())

    def test_host_options_and_unsafe_paths_are_rejected(self):
        for host in ("-oProxyCommand=bad", "root@host;bad", "root@host\nbad"):
            with self.assertRaises(self.sync.SyncError):
                self.sync.validate_target(host, 22, "/data/project")
        for port in (0, 65536):
            with self.assertRaises(self.sync.SyncError):
                self.sync.validate_target("root@example.invalid", port, "/data/project")
        for directory in ("relative", "/", "/data\nproject"):
            with self.assertRaises(self.sync.SyncError):
                self.sync.validate_target("root@example.invalid", 22, directory)

    def test_remote_path_is_shell_quoted(self):
        directory = "/data/a project';echo bad"
        command = self.sync.remote_command(directory, "inspect")
        self.assertEqual(shlex.split(command), ["python3", "-c", self.sync.REMOTE_SCRIPT, directory, "inspect"])

    def test_local_dirty_checkout_never_connects(self):
        (self.source / "code.py").write_text("uncommitted work\n")
        with patch.object(self.sync, "remote_call") as transport:
            with self.assertRaises(self.sync.SyncError):
                self.sync.sync(self.source, "root@example.invalid", 22, str(self.remote))
            transport.assert_not_called()

    def test_check_only_does_not_prepare_or_transfer(self):
        status = {"head": self.old_head, "branch": "main"}
        with patch.object(self.sync, "remote_call", return_value=status) as transport:
            with patch.object(self.sync, "copy_bundle") as transfer:
                self.sync.sync(self.source, "root@example.invalid", 22, str(self.remote), check_only=True)
                self.assertEqual(transport.call_count, 1)
                self.assertEqual(transport.call_args.args[3], "inspect")
                transfer.assert_not_called()

    def local_transport(self, host, port, directory, action, *args):
        result = self.remote_call(action, *args, directory=Path(directory))
        if result.returncode:
            raise self.sync.SyncError(result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_complete_sync_with_local_transport(self):
        def transfer(host, port, bundle, staging):
            Path(staging, "update.bundle").write_bytes(Path(bundle).read_bytes())

        with patch.object(self.sync, "remote_call", side_effect=self.local_transport):
            with patch.object(self.sync, "copy_bundle", side_effect=transfer):
                self.sync.sync(self.source, "root@example.invalid", 22, str(self.remote))
        self.assertEqual(self.git(self.remote, "rev-parse", "HEAD"), self.new_head)
        self.assertEqual(self.git(self.remote, "status", "--porcelain"), "")
        for repo in (self.source, self.remote):
            self.assertEqual(list((repo / ".git").glob("isaac-sync-*")), [])

    def test_failed_transfer_cleans_staging_without_changing_checkout(self):
        with patch.object(self.sync, "remote_call", side_effect=self.local_transport):
            with patch.object(self.sync, "copy_bundle", side_effect=self.sync.SyncError("transfer failed")):
                with self.assertRaisesRegex(self.sync.SyncError, "transfer failed"):
                    self.sync.sync(self.source, "root@example.invalid", 22, str(self.remote))
        self.assertEqual(self.git(self.remote, "rev-parse", "HEAD"), self.old_head)
        for repo in (self.source, self.remote):
            self.assertEqual(list((repo / ".git").glob("isaac-sync-*")), [])

    def test_already_current_does_not_transfer(self):
        with patch.object(self.sync, "remote_call", return_value={"head": self.new_head}) as transport:
            with patch.object(self.sync, "copy_bundle") as transfer:
                self.sync.sync(self.source, "root@example.invalid", 22, str(self.remote))
                self.assertEqual(transport.call_count, 1)
                transfer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
