#!/usr/bin/env python3
"""Offline process tests: fake SSH/SCP/Slurm operate only in temporary folders.

These tests establish command construction, transfer ordering, recovery receipts,
and failure handling. They do not establish Alpha access, real SCP behavior,
Slurm availability, GPU allocation, MFA, or model inference.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("alpha_submit.sh")
MOCK = r'''#!/usr/bin/env python3
import json, os, shutil, subprocess, sys
from pathlib import Path

name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['MOCK_LOG'], 'a') as log:
    log.write(json.dumps({'name': name, 'args': args, 'cwd': os.getcwd()}) + '\n')
remote = Path(os.environ['MOCK_REMOTE'])

if name in ('ssh', 'scp'):
    while args[:1] == ['-o']:
        assert len(args) >= 2, args
        args = args[2:]

if name == 'ssh':
    assert args[0] == '--' and args[1] == 'tester@alpha.invalid', args
    command = args[2]
    if os.environ.get('FAIL_SSH_CREATE') and 'mkdir' in command:
        sys.exit(255)
    result = subprocess.run(['bash', '-c', command], cwd=remote)
    if os.environ.get('DROP_AFTER_SUBMIT') and 'sbatch' in command:
        sys.exit(255)
    sys.exit(result.returncode)

if name == 'scp':
    if os.environ.get('FAIL_SCP'):
        sys.exit(1)
    paths = [arg for arg in args if arg not in ('-r', '--')]
    sources, destination = paths[:-1], paths[-1]
    def resolve(path):
        if path.startswith('tester@alpha.invalid:'):
            return remote / path.split(':', 1)[1]
        return Path(path)
    destination = resolve(destination)
    for source in sources:
        source_path = resolve(source)
        if source_path.is_dir():
            # A remote directory ending in '/.' copies its contents.
            target = destination if source.endswith('/.') else destination / source_path.name
            shutil.copytree(source_path, target, dirs_exist_ok=True)
        else:
            target = destination / source_path.name if destination.is_dir() else destination
            shutil.copy2(source_path, target)
    sys.exit(0)

if name == 'sbatch':
    assert args == ['--parsable', 'job.sbatch'], args
    if os.environ.get('FAIL_SBATCH'):
        print('submission rejected', file=sys.stderr)
        sys.exit(1)
    Path('fake-job.out').write_text('fake GPU output\n')
    print(os.environ.get('RECEIPT', '12345'))
elif name == 'squeue':
    if os.environ.get('FAIL_SQUEUE'):
        sys.exit(1)
    print(os.environ.get('QUEUE', 'JOBID STATE\n12345 RUNNING'))
elif name == 'sacct':
    if os.environ.get('FAIL_SACCT'):
        sys.exit(1)
    print(os.environ.get('ACCOUNTING', 'JobID State ExitCode\n12345 COMPLETED 0:0'))
else:
    raise AssertionError(name)
'''


class AlphaSubmitTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix="lantern-alpha-test-")
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.local = self.root / "local files"
        self.remote = self.root / "fake remote"
        self.bin = self.root / "bin"
        for path in (self.local, self.remote, self.bin):
            path.mkdir()
        self.log = self.root / "calls.jsonl"
        for name in ("ssh", "scp", "sbatch", "squeue", "sacct"):
            executable = self.bin / name
            executable.write_text(MOCK)
            executable.chmod(0o755)
        self.job = self.local / "my job.sbatch"
        self.job.write_text("#!/bin/bash\nprintf 'fixture only\\n'\n")
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "ALPHA_HOST": "tester@alpha.invalid",
            "ALPHA_CONTROL_PATH": "",
            "MOCK_REMOTE": str(self.remote),
            "MOCK_LOG": str(self.log),
        })

    def run_helper(self, *args, **env):
        return subprocess.run(
            ["bash", str(SCRIPT), *map(str, args)], cwd=self.local,
            env=self.env | env, text=True, capture_output=True, timeout=10,
        )

    def calls(self, name=None):
        rows = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return rows if name is None else [row for row in rows if row["name"] == name]

    def run_id(self, result):
        match = re.search(r"^Run ID: ([A-Za-z0-9_-]+)$", result.stdout, re.M)
        self.assertIsNotNone(match, result.stdout + result.stderr)
        return match[1]

    def test_help_needs_no_host_or_network(self):
        result = self.run_helper("--help", ALPHA_HOST="")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        self.assertEqual(self.calls(), [])

    def assert_original_connection_arguments(self, control_path):
        # Freeze the SSH/SCP argv from pre-multiplexing helper eae89e8.
        # Only the generated run ID and fixture paths are filled at runtime;
        # no arguments are stripped or normalized before comparison.
        if control_path is None:
            self.env.pop("ALPHA_CONTROL_PATH", None)
            self.assertNotIn("ALPHA_CONTROL_PATH", self.env)
        else:
            self.env["ALPHA_CONTROL_PATH"] = control_path
        package = self.local / "runner"
        package.mkdir()
        (package / "example.py").write_text("# fixture only\n")
        submitted = self.run_helper("submit", self.job, "runner")
        self.assertEqual(submitted.returncode, 0, submitted.stderr)
        remote_dir = "lantern/runs/" + self.run_id(submitted)
        for job in ("12345", "12345;alpha"):
            status = self.run_helper("status", job)
            self.assertEqual(status.returncode, 0, status.stderr)
        fetched = self.run_helper("fetch", self.run_id(submitted), "snapshot")
        self.assertEqual(fetched.returncode, 0, fetched.stderr)

        def original_status(cluster_option):
            return (
                "query_status=0\n"
                f"squeue --jobs='12345' {cluster_option} || query_status=1\n"
                "sacct --allocations --jobs='12345' --format=JobID,State,ExitCode "
                f"{cluster_option} || query_status=1\n"
                "exit $query_status"
            )

        host = "tester@alpha.invalid"
        expected = [
            ("ssh", ["--", host, f"mkdir -p lantern/runs && mkdir '{remote_dir}'"]),
            ("scp", ["--", str(self.job), f"{host}:{remote_dir}/job.sbatch"]),
            ("scp", ["-r", "--", "./runner", f"{host}:{remote_dir}/"]),
            ("ssh", ["--", host, f"cd '{remote_dir}' && sbatch --parsable job.sbatch > submission.txt && cat submission.txt"]),
            ("ssh", ["--", host, original_status("")]),
            ("ssh", ["--", host, original_status("--clusters='alpha'")]),
            ("scp", ["-r", "--", f"{host}:{remote_dir}/.", "./snapshot/"]),
        ]
        actual = [(row["name"], row["args"]) for row in self.calls()
                  if row["name"] in ("ssh", "scp")]
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.calls("sbatch")), 1)
        self.assertEqual((self.local / "snapshot/submission.txt").read_text(), "12345\n")

    def test_unset_control_path_preserves_original_connection_arguments(self):
        self.assert_original_connection_arguments(None)

    def test_empty_control_path_preserves_original_connection_arguments(self):
        self.assert_original_connection_arguments("")

    def test_shared_connection_used_for_submit_status_and_fetch(self):
        # Spaces and shell metacharacters must remain inside one option value.
        socket_path = str(self.root / "control socket;literal")
        settings = {"ALPHA_CONTROL_PATH": socket_path}
        package = self.local / "runner"
        package.mkdir()
        (package / "example.py").write_text("# fixture only\n")
        submitted = self.run_helper("submit", self.job, package, **settings)
        self.assertEqual(submitted.returncode, 0, submitted.stderr)
        self.assertIn("Job ID: 12345", submitted.stdout)
        status = self.run_helper("status", "12345;alpha", **settings)
        self.assertEqual(status.returncode, 0, status.stderr)
        fetched = self.run_helper("fetch", self.run_id(submitted), "snapshot", **settings)
        self.assertEqual(fetched.returncode, 0, fetched.stderr)
        self.assertEqual((self.local / "snapshot/submission.txt").read_text(), "12345\n")
        expected = ["-o", f'ControlPath="{socket_path}"', "-o", "ControlMaster=no",
                    "-o", "BatchMode=yes"]
        connections = [row for row in self.calls() if row["name"] in ("ssh", "scp")]
        self.assertEqual(len(connections), 6)
        for row in connections:
            self.assertEqual(row["args"][:len(expected)], expected)
            self.assertNotIn("-t", row["args"])
            self.assertNotIn("-tt", row["args"])
        self.assertEqual(len(self.calls("sbatch")), 1)

    def test_shared_connection_options_parse_in_openssh_without_connecting(self):
        ssh = shutil.which("ssh")
        if ssh is None:
            self.skipTest("OpenSSH client unavailable for offline config parsing")
        socket_path = str(self.root / "control socket;literal")
        result = self.run_helper("status", "12345", ALPHA_CONTROL_PATH=socket_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        options = self.calls("ssh")[0]["args"][:6]
        config = subprocess.run(
            [ssh, "-F", "/dev/null", "-G", *options, "tester@alpha.invalid"],
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(config.returncode, 0, config.stderr)
        self.assertIn(f"controlpath {socket_path}\n", config.stdout)
        self.assertIn("batchmode yes\n", config.stdout)
        self.assertIn("controlmaster false\n", config.stdout)

    def test_invalid_shared_connection_paths_make_no_remote_calls(self):
        for path in ('/tmp/a"b', '/tmp/a\\b', '/tmp/a\nb', '/tmp/a\rb'):
            with self.subTest(path=path):
                result = self.run_helper("submit", self.job, ALPHA_CONTROL_PATH=path)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ALPHA_CONTROL_PATH", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_shared_connection_failure_before_upload_never_submits(self):
        result = self.run_helper("submit", self.job, ALPHA_CONTROL_PATH="/tmp/socket",
                                 FAIL_SSH_CREATE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls("scp"), [])
        self.assertEqual(self.calls("sbatch"), [])

    def test_shared_connection_disconnect_retains_receipt_without_retry(self):
        result = self.run_helper("submit", self.job, ALPHA_CONTROL_PATH="/tmp/socket",
                                 DROP_AFTER_SUBMIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown", result.stderr)
        run = self.remote / "lantern/runs" / self.run_id(result)
        self.assertEqual((run / "submission.txt").read_text(), "12345\n")
        self.assertEqual(len(self.calls("sbatch")), 1)

    def test_invalid_arguments_make_no_remote_calls(self):
        for args, env in (
            (("submit",), {}),
            (("submit", "missing.sbatch"), {}),
            (("submit", self.job), {"ALPHA_HOST": ""}),
            (("submit", self.job), {"ALPHA_HOST": "x;touch injected"}),
            (("status", "123;cluster;touch injected"), {}),
            (("fetch", "../escape", "output"), {}),
        ):
            with self.subTest(args=args, env=env):
                self.assertNotEqual(self.run_helper(*args, **env).returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.local / "injected").exists())

    def test_payload_validation_happens_before_connection(self):
        reserved = self.local / "submission.txt"
        reserved.write_text("existing input")
        for extra in ("missing", reserved, self.local):
            with self.subTest(extra=extra):
                self.assertNotEqual(self.run_helper("submit", self.job, extra).returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_duplicate_payload_basenames_refused(self):
        for parent in ("a", "b"):
            (self.local / parent).mkdir()
            (self.local / parent / "same.txt").write_text(parent)
        result = self.run_helper("submit", self.job, "a/same.txt", "b/same.txt")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_submit_preserves_inputs_and_remote_receipt(self):
        payload = self.local / "evidence:packet.txt"
        payload.write_text("reviewed evidence")
        package = self.local / "runner"
        package.mkdir()
        (package / "example.py").write_text("# fixture only\n")
        # Colon in the basename is deliberately refused before any upload.
        bad = self.run_helper("submit", self.job, payload)
        self.assertNotEqual(bad.returncode, 0)
        self.assertEqual(self.calls(), [])
        payload.rename(self.local / "evidence.txt")
        result = self.run_helper("submit", self.job, "evidence.txt", "runner")
        self.assertEqual(result.returncode, 0, result.stderr)
        run = self.remote / "lantern/runs" / self.run_id(result)
        self.assertEqual((run / "job.sbatch").read_text(), self.job.read_text())
        self.assertEqual((run / "evidence.txt").read_text(), "reviewed evidence")
        self.assertEqual((run / "runner/example.py").read_text(), "# fixture only\n")
        self.assertEqual((run / "submission.txt").read_text(), "12345\n")
        self.assertIn("Job ID: 12345", result.stdout)
        self.assertEqual(len(self.calls("sbatch")), 1)
        self.assertEqual(self.job.read_text(), "#!/bin/bash\nprintf 'fixture only\\n'\n")

    def test_repeated_submissions_have_separate_directories(self):
        first = self.run_helper("submit", self.job)
        second = self.run_helper("submit", self.job)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(self.run_id(first), self.run_id(second))

    def test_failed_directory_creation_never_uploads_or_submits(self):
        result = self.run_helper("submit", self.job, FAIL_SSH_CREATE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls("scp"), [])
        self.assertEqual(self.calls("sbatch"), [])

    def test_failed_upload_never_submits(self):
        result = self.run_helper("submit", self.job, FAIL_SCP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls("sbatch"), [])

    def test_rejection_does_not_retry(self):
        result = self.run_helper("submit", self.job, FAIL_SBATCH="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("before retrying", result.stderr)
        self.assertEqual(len(self.calls("sbatch")), 1)

    def test_disconnect_after_acceptance_retains_receipt_and_never_retries(self):
        result = self.run_helper("submit", self.job, DROP_AFTER_SUBMIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown", result.stderr)
        self.assertNotIn("Job ID:", result.stdout)
        run = self.remote / "lantern/runs" / self.run_id(result)
        self.assertEqual((run / "submission.txt").read_text(), "12345\n")
        self.assertEqual(len(self.calls("sbatch")), 1)

    def test_unexpected_receipt_does_not_report_a_job_id(self):
        result = self.run_helper("submit", self.job, RECEIPT="unexpected banner")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Job ID:", result.stdout)
        self.assertEqual(len(self.calls("sbatch")), 1)

    def test_cluster_receipt_and_status(self):
        result = self.run_helper("submit", self.job, RECEIPT="12345;alpha")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_helper("status", "12345;alpha")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("squeue", "sacct"):
            self.assertIn("--clusters=alpha", self.calls(command)[0]["args"])

    def test_empty_queue_still_queries_accounting(self):
        result = self.run_helper("status", "12345", QUEUE="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("COMPLETED", result.stdout)
        self.assertEqual(len(self.calls("sacct")), 1)

    def test_queue_failure_still_queries_accounting(self):
        result = self.run_helper("status", "12345", FAIL_SQUEUE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls("sacct")), 1)

    def test_missing_accounting_never_reports_completion(self):
        result = self.run_helper("status", "12345", QUEUE="", ACCOUNTING="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("empty records do not establish completion", result.stdout)
        result = self.run_helper("status", "12345", FAIL_SACCT="1")
        self.assertNotEqual(result.returncode, 0)

    def test_fetch_copies_snapshot_without_submitting(self):
        run = self.remote / "lantern/runs/example-run"
        run.mkdir(parents=True)
        (run / "output.txt").write_text("fixture output")
        result = self.run_helper("fetch", "example-run", "results with spaces")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.local / "results with spaces/output.txt").read_text(), "fixture output")
        self.assertEqual(self.calls("sbatch"), [])

    def test_fetch_refuses_existing_destination(self):
        destination = self.local / "results"
        destination.mkdir()
        (destination / "keep.txt").write_text("keep")
        result = self.run_helper("fetch", "example-run", destination)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((destination / "keep.txt").read_text(), "keep")
        self.assertEqual(self.calls(), [])

    def test_failed_fetch_never_reports_success(self):
        result = self.run_helper("fetch", "example-run", "results", FAIL_SCP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("partial files may remain", result.stderr)
        self.assertNotIn("Copied run snapshot", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
