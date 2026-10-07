import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from assistant import Assistant
from phone import PhoneServer


class PhoneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.assistant = Assistant(root, root / 'data')
        self.server = PhoneServer(('127.0.0.1', 0), self.assistant, token='test-pairing-code')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, data=None, token='test-pairing-code', origin=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        self.addCleanup(connection.close)
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if origin:
            headers['Origin'] = origin
        connection.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = connection.getresponse()
        body = response.read()
        value = json.loads(body) if response.getheader('Content-Type').startswith('application/json') else body
        return response.status, value

    def test_pairing_required_and_static_page_public(self):
        self.assertEqual(self.request('GET', '/', token=None)[0], 200)
        self.assertEqual(self.request('GET', '/api/state', token=None)[0], 401)
        self.assertEqual(self.request('GET', '/api/state', token='wrong')[0], 401)
        self.assertEqual(self.request('GET', '/api/state')[0], 200)

    def test_confirmation_cancel_execution_and_replay(self):
        status, prepared = self.request('POST', '/api/prepare', {'request': 'note hello phone'})
        self.assertEqual(status, 200)
        self.assertTrue(prepared['confirmation_required'])
        self.assertEqual(self.request('GET', '/api/state')[1]['items'], [])
        self.request('POST', '/api/cancel', {'id': prepared['id']})
        self.assertEqual(self.request('POST', '/api/execute', {'id': prepared['id']})[0], 400)
        prepared = self.request('POST', '/api/prepare', {'request': 'note hello phone'})[1]
        self.assertEqual(self.request('POST', '/api/execute', {'id': prepared['id']})[0], 200)
        self.assertEqual(self.request('POST', '/api/execute', {'id': prepared['id']})[0], 400)
        self.assertEqual(self.request('GET', '/api/state')[1]['items'][0]['text'], 'hello phone')

    def test_pc_commands_blocked_by_default_even_routines_and_files(self):
        for request in ['run echo hello', 'routine saved', 'open app notepad', 'read file secret.txt', 'clipboard']:
            self.assertEqual(self.request('POST', '/api/prepare', {'request': request})[0], 403)

    def test_optional_pc_control_still_requires_confirmation(self):
        self.server.allow_pc = True
        with patch.object(self.assistant, 'command', return_value='executed') as run:
            prepared = self.request('POST', '/api/prepare', {'request': 'run echo hello'})[1]
            self.assertTrue(prepared['confirmation_required'])
            run.assert_not_called()
            status, output = self.request('POST', '/api/execute', {'id': prepared['id']})
            self.assertEqual(status, 200)
            self.assertEqual(output['result'], 'executed')
            run.assert_called_once()

    def test_expired_confirmation_is_rejected(self):
        prepared = self.server.prepare('task do something')
        _, action = self.server.pending[prepared['id']]
        self.server.pending[prepared['id']] = (time.monotonic() - 1, action)
        self.assertEqual(self.request('POST', '/api/execute', {'id': prepared['id']})[0], 400)
        self.assertEqual(self.assistant.listing('task'), 'No active tasks.')

    def test_cross_origin_request_rejected(self):
        self.assertEqual(self.request('POST', '/api/prepare', {'request': 'notes'}, origin='https://untrusted.example')[0], 403)

    def test_invalid_json_shape_and_unknown_endpoint(self):
        self.assertEqual(self.request('POST', '/api/prepare', ['not', 'object'])[0], 400)
        self.assertEqual(self.request('POST', '/api/prepare', {'request': None})[0], 400)
        self.assertEqual(self.request('POST', '/api/unknown', {})[0], 404)

    def test_personal_calendar_memory_and_shared_database(self):
        self.assistant.prepare('event 2030-01-02 13:30 Lunch with Alex').run()
        self.assistant.prepare('remember my name = Sam').run()
        state = self.request('GET', '/api/state')[1]
        self.assertEqual(state['items'][0]['kind'], 'event')
        self.assertEqual(state['memory'], [{'name': 'my name', 'value': 'Sam'}])
        other = Assistant(self.assistant.workspace, self.assistant.data_dir)
        self.assertIn('Lunch with Alex', other.listing('event'))
        self.assertIn('Sam', other.prepare('memory').run())


if __name__ == '__main__':
    unittest.main()
