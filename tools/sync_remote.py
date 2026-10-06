#!/usr/bin/env python3
"""Transfer committed main through SSH, without the remote contacting GitHub.

Requires Git, OpenSSH and Python 3 on both machines. Passwords are handled by
SSH's terminal prompt, never by this script or a command-line password option.
"""
from __future__ import annotations
import argparse
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

# Sent through SSH as a quoted Python command; no helper installation is needed.
REMOTE_SCRIPT = r'''
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

def fail(message):
    raise RuntimeError(message)

def git(*args):
    result = subprocess.run(["git", "-C", str(directory), *args], text=True, capture_output=True)
    if result.returncode:
        fail(result.stderr.strip() or result.stdout.strip() or "Git command failed")
    return result.stdout.strip()

def clean_main():
    if git("symbolic-ref", "--short", "HEAD") != "main":
        fail("Remote checkout must be on main")
    if git("status", "--porcelain"):
        fail("Remote checkout has uncommitted or untracked files; nothing will be overwritten")
    return git("rev-parse", "HEAD")

def staging_path(value):
    path = Path(value)
    if path.is_symlink() or path.parent.resolve() != git_dir or not path.name.startswith("isaac-sync-"):
        fail("Refusing a staging path outside the repository Git metadata")
    return path

try:
    directory = Path(sys.argv[1]).resolve()
    action = sys.argv[2]
    if Path(git("rev-parse", "--show-toplevel")).resolve() != directory:
        fail("Target directory must be the Git checkout root, not a nested directory")
    git_dir = Path(git("rev-parse", "--absolute-git-dir")).resolve()
    if action == "inspect":
        output = {"head": clean_main(), "branch": "main"}
    elif action == "prepare":
        if clean_main() != sys.argv[3]:
            fail("Remote HEAD changed since inspection; retry after reviewing it")
        output = {"staging": tempfile.mkdtemp(prefix="isaac-sync-", dir=git_dir)}
    elif action == "apply":
        stage = staging_path(sys.argv[3])
        expected, original = sys.argv[4:6]
        if not re.fullmatch(r"[0-9a-f]{40,64}", expected):
            fail("Invalid expected commit")
        if clean_main() != original:
            fail("Remote HEAD changed during transfer; nothing will be overwritten")
        bundle = stage / "update.bundle"
        if not bundle.is_file() or bundle.is_symlink():
            fail("Uploaded bundle is missing or is a symlink")
        git("bundle", "verify", str(bundle))
        git("fetch", "--no-tags", str(bundle), "refs/heads/main")
        incoming = git("rev-parse", "FETCH_HEAD")
        if incoming != expected:
            fail("Bundle commit does not match the source commit")
        ancestor = subprocess.run(["git", "-C", str(directory), "merge-base", "--is-ancestor", "HEAD", incoming])
        if ancestor.returncode:
            fail("Remote history cannot fast-forward; review it manually, no reset was performed")
        git("merge", "--ff-only", "--no-overwrite-ignore", incoming)
        head = git("rev-parse", "HEAD")
        if head != expected:
            fail("Remote commit verification failed")
        output = {"head": head, "branch": "main"}
    elif action == "cleanup":
        stage = staging_path(sys.argv[3])
        if stage.exists():
            (stage / "update.bundle").unlink(missing_ok=True)
            stage.rmdir()
        output = {"cleaned": True}
    else:
        fail("Unknown sync action")
    print(json.dumps(output), flush=True)
except (RuntimeError, OSError, IndexError, ValueError) as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(2)
'''


class SyncError(RuntimeError):
    pass


def run(command, *, cwd=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise SyncError(result.stderr.strip() or result.stdout.strip() or "Command failed")
    return result.stdout.strip()


def validate_target(host, port, directory):
    if not re.fullmatch(r"(?:[A-Za-z0-9_][A-Za-z0-9_.-]*@)?[A-Za-z0-9][A-Za-z0-9_.-]*", host):
        raise SyncError("Use an SSH hostname or user@hostname, not options or shell commands")
    if not 1 <= port <= 65535:
        raise SyncError("SSH port must be between 1 and 65535")
    path = PurePosixPath(directory)
    if not path.is_absolute() or str(path) == "/" or any(c in directory for c in "\0\n\r"):
        raise SyncError("Remote directory must be an absolute project path, not /")


def ssh_options():
    # Reuse one authenticated connection, instead of asking for every SSH/SCP call.
    return ["-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
            "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=2", "-o", "ControlMaster=auto",
            "-o", "ControlPersist=10m", "-o", f"ControlPath={Path.home() / '.ssh' / 'isaac-sync-%C'}"]


def remote_command(directory, action, *args):
    return shlex.join(["python3", "-c", REMOTE_SCRIPT, directory, action, *args])


def remote_call(host, port, directory, action, *args):
    output = run(["ssh", "-p", str(port), *ssh_options(), host, remote_command(directory, action, *args)])
    try:
        return json.loads(output.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise SyncError("SSH returned no valid sync status") from exc


def copy_bundle(host, port, bundle, staging):
    run(["scp", "-P", str(port), *ssh_options(), str(bundle), f"{host}:{staging}/update.bundle"])


def sync(repo, host, port, directory, *, check_only=False):
    validate_target(host, port, directory)
    repo = Path(repo).resolve()

    def git(*args):
        return run(["git", "-C", str(repo), *args])

    if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
        raise SyncError("Local path must be the Git checkout root")
    if git("symbolic-ref", "--short", "HEAD") != "main":
        raise SyncError("Local checkout must be on main")
    if git("status", "--porcelain"):
        raise SyncError("Commit and push local changes before syncing; local checkout is not clean")
    head = git("rev-parse", "HEAD")
    status = remote_call(host, port, directory, "inspect")
    print(f"Local main:  {head}\nRemote main: {status['head']}", flush=True)
    if check_only:
        print("Check only: no bundle transferred and no remote files updated.")
        return
    if status["head"] == head:
        print("Remote main is already up to date.")
        return
    git_dir = Path(git("rev-parse", "--absolute-git-dir"))
    with tempfile.TemporaryDirectory(prefix="isaac-sync-", dir=git_dir) as temporary:
        bundle = Path(temporary) / "update.bundle"
        git("bundle", "create", str(bundle), "refs/heads/main")
        if git("bundle", "list-heads", str(bundle), "refs/heads/main").split()[0] != head:
            raise SyncError("Local main changed while packing the bundle; retry")
        staging = remote_call(host, port, directory, "prepare", status["head"])["staging"]
        try:
            copy_bundle(host, port, bundle, staging)
            updated = remote_call(host, port, directory, "apply", staging, head, status["head"])
            if updated.get("head") != head:
                raise SyncError("Remote commit verification failed")
            print(f"Synced and verified remote main: {head}", flush=True)
        finally:
            try:
                remote_call(host, port, directory, "cleanup", staging)
            except (SyncError, OSError) as exc:
                print(f"Warning: staging cleanup failed: {exc}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="SSH hostname or user@hostname; no password")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--remote-dir", required=True, help="Existing Git checkout root on main")
    parser.add_argument("--check", action="store_true", help="Inspect only; do not transfer or update")
    args = parser.parse_args()
    try:
        sync(ROOT, args.host, args.port, args.remote_dir, check_only=args.check)
        return 0
    except (SyncError, OSError) as exc:
        print(f"Sync stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
