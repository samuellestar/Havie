from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from assistant import Assistant, calculate, path_arguments


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        self.assistant = Assistant(self.workspace, self.root / 'data')

    def run_action(self, text):
        return self.assistant.prepare(text).run()

    def test_personal_data_survives_restart_and_handles_sql_text(self):
        self.run_action("note don't lose this; DROP TABLE items;")
        other = Assistant(self.workspace, self.root / 'data')
        self.assertIn("don't lose this", other.listing('note'))
        self.run_action('task finish project')
        self.assertIn('finish project', self.run_action('tasks'))
        self.run_action('done 2')
        self.assertEqual(self.run_action('tasks'), 'No active tasks.')
        with self.assertRaises(ValueError):
            self.run_action('done 2')

    def test_reminders_due_once_and_future_not_delivered(self):
        past = (datetime.now() - timedelta(minutes=1)).isoformat()
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        self.assistant.add('reminder', 'due', past)
        self.assistant.add('reminder', 'future', future)
        self.assertEqual(self.assistant.due_reminders(), ['Reminder #1: due'])
        self.assertEqual(self.assistant.due_reminders(), [])
        self.assertIn('future', self.run_action('reminders'))

    def test_copy_move_read_and_no_overwrite(self):
        (self.workspace / 'one.txt').write_text('hello')
        self.assertTrue(self.assistant.prepare('copy file one.txt two.txt').confirm)
        self.run_action('copy file one.txt two.txt')
        self.assertEqual(self.run_action('read file two.txt'), 'hello')
        with self.assertRaises(FileExistsError):
            self.run_action('copy file one.txt two.txt')
        self.run_action('move file two.txt three.txt')
        self.assertFalse((self.workspace / 'two.txt').exists())
        self.assertEqual((self.workspace / 'three.txt').read_text(), 'hello')

    def test_file_tools_reject_escape_and_symlink(self):
        with self.assertRaises(ValueError):
            self.assistant.prepare('read file ../secret.txt')
        try:
            (self.workspace / 'escape').symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation is unavailable for this account.')
        with self.assertRaises(ValueError):
            self.assistant.prepare('make folder escape/outside')

    def test_paths_preserve_windows_backslashes(self):
        self.assertEqual(path_arguments('"folder\\my file.txt" "new file.txt"'),
                         ['folder\\my file.txt', 'new file.txt'])

    def test_arithmetic_rejects_code(self):
        self.assertEqual(calculate('(12 + 8) / 4'), '5.0')
        for expression in ["__import__('os').system('echo bad')", '2 ** 99999999', 'True + 1']:
            with self.assertRaises(ValueError):
                calculate(expression)

    def test_browser_requires_confirmation_and_rejects_unsafe_schemes(self):
        with patch('assistant.webbrowser.open', return_value=True) as browser:
            action = self.assistant.prepare('search web Python tutorials')
            browser.assert_not_called()
            self.assertTrue(action.confirm)
            action.run()
            self.assertIn('Python+tutorials', browser.call_args.args[0])
        for url in ['file:///etc/passwd', 'javascript:alert(1)', 'https://user:pass@example.com']:
            with self.assertRaises(ValueError):
                self.assistant.prepare('open url ' + url)

    def test_speech_text_is_input_not_executable_script(self):
        text = "hello'; Remove-Item *; '"
        with patch('assistant.platform.system', return_value='Windows'), patch.object(self.assistant, 'command', return_value='ok') as command:
            action = self.assistant.prepare('speak ' + text)
            self.assertTrue(action.confirm)
            action.run()
            self.assertNotIn(text, command.call_args.args[0][-1])
            self.assertEqual(command.call_args.args[1], text)

    def test_ollama_contract_and_conversation(self):
        import io
        class Response(io.BytesIO):
            pass
        with patch('assistant.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = [Response(json.dumps({'message': {'content': 'hello'}}).encode()), Response(json.dumps({'message': {'content': 'again'}}).encode())]
            self.assertEqual(self.run_action('chat hi'), 'hello')
            self.assertEqual(self.run_action('chat follow up'), 'again')
            request = build.return_value.open.call_args.args[0]
            payload = json.loads(request.data)
            self.assertFalse(payload['stream'])
            self.assertIn('User preferences', payload['messages'][0]['content'])
            self.assertEqual(len(payload['messages']), 4)

    def test_prepare_never_runs_command(self):
        with patch('assistant.subprocess.run') as run:
            action = self.assistant.prepare('run echo hello')
            self.assertTrue(action.confirm)
            run.assert_not_called()

    def test_find_and_folder_creation(self):
        self.run_action('make folder "my folder"')
        (self.workspace / 'my folder' / 'Example.txt').write_text('sample')
        self.assertIn('Example.txt', self.run_action('find files example'))

    def test_routines_saved_without_running_and_reviewed_on_execution(self):
        with patch.object(self.assistant, 'command', return_value='ok') as run:
            action = self.assistant.prepare('save routine check = echo hello')
            self.assertTrue(action.confirm)
            action.run()
            run.assert_not_called()
            self.assertIn('check: echo hello', self.run_action('routines'))
            execute = self.assistant.prepare('routine check')
            self.assertTrue(execute.confirm)
            self.assertIn('echo', execute.preview)
            self.assertEqual(execute.run(), 'ok')
            run.assert_called_once()
            self.run_action('delete routine check')
            with self.assertRaises(ValueError):
                self.assistant.prepare('routine check')

    def test_listing_files_executes_successfully(self):
        (self.workspace / 'expected.txt').write_text('hello')
        output = self.run_action('list files')
        self.assertIn('expected.txt', output)
        self.assertIn('Exit code: 0', output)

    def test_screenshot_review_and_overwrite_protection(self):
        with patch.object(self.assistant, 'powershell', return_value='ok') as ps:
            action = self.assistant.prepare('screenshot output.png')
            self.assertTrue(action.confirm)
            ps.assert_not_called()
            (self.workspace / 'output.png').touch()
            with self.assertRaises(ValueError):
                action.run()
            ps.assert_not_called()

    def test_listen_requires_confirmation(self):
        with patch.object(self.assistant, 'powershell', return_value='recognized words') as ps:
            action = self.assistant.prepare('listen')
            self.assertTrue(action.confirm)
            ps.assert_not_called()
            self.assertEqual(action.run(), 'recognized words')

    def test_today_agenda_and_preference_management(self):
        self.run_action('task Finish my weekly plan')
        self.assertIn('Finish my weekly plan', self.run_action('today'))
        self.run_action('remember my name = Sam')
        self.run_action('remember my name = Alex')
        self.assertIn('Alex', self.run_action('memory'))
        self.assertNotIn('Sam', self.run_action('memory'))
        self.run_action('forget my name')
        self.assertEqual(self.run_action('memory'), 'No personal preferences saved.')
        with self.assertRaises(ValueError):
            self.assistant.prepare('event 2030-99-02 13:30 Invalid date')

    def test_real_command_captures_output_and_failure(self):
        self.assertIn('Exit code: 0', self.run_action('current folder'))
        self.assertIn(str(self.workspace), self.run_action('current folder'))


if __name__ == '__main__':
    unittest.main()
