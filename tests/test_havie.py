import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from havie import execute, plan


class AssistantTests(unittest.TestCase):
    def test_windows_command_uses_explicit_interpreter(self):
        self.assertEqual(plan('run dir', 'Windows'), ['cmd.exe', '/d', '/s', '/c', 'dir'])

    def test_quoted_arguments_preserved_without_shell(self):
        self.assertEqual(plan('run echo "hello world"', 'Linux'), ['echo', 'hello world'])

    def test_unknown_request_rejected(self):
        with self.assertRaises(ValueError):
            plan('delete everything')

    def test_execution_returns_failure(self):
        with tempfile.TemporaryDirectory() as cwd, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute([sys.executable, '-c', 'raise SystemExit(7)'], cwd), 7)

    def test_cancel_does_not_execute(self):
        with tempfile.TemporaryDirectory() as cwd:
            marker = Path(cwd) / 'marker'
            command = f'run {sys.executable} -c "from pathlib import Path; Path(\'marker\').touch()"'
            result = subprocess.run([sys.executable, 'havie.py', '--workspace', cwd],
                                    input=command + '\nno\nexit\n', text=True,
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Cancelled.', result.stdout)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
