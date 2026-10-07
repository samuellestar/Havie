"""Paired browser interface for a private LAN; optional TLS support."""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import secrets
import ssl
import threading
import time
from urllib.parse import urlsplit

PERSONAL_EXACT = {'help', 'today', 'notes', 'tasks', 'reminders', 'events', 'memory', 'time'}
PERSONAL_PREFIXES = ('note ', 'task ', 'done ', 'delete note ', 'remind ', 'cancel reminder ',
                     'event ', 'cancel event ', 'remember ', 'forget ', 'calculate ', 'chat ')


class PhoneServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, assistant, token=None, allow_pc=False):
        super().__init__(address, Handler)
        self.assistant = assistant
        self.token = token or secrets.token_urlsafe(32)
        self.allow_pc = allow_pc
        self.pending = {}
        self.pending_lock = threading.Lock()
        self.execution_lock = threading.Lock()

    def prepare(self, request):
        if not isinstance(request, str) or not request.strip() or len(request) > 8000:
            raise ValueError('Enter a request of up to 8000 characters.')
        lower = request.strip().lower()
        if not self.allow_pc and lower not in PERSONAL_EXACT and not lower.startswith(PERSONAL_PREFIXES):
            raise PermissionError('PC controls are disabled in phone mode. Use personal tools, or enable --allow-phone-pc on the PC.')
        action = self.assistant.prepare(request)
        if not action.confirm:
            if not self.execution_lock.acquire(blocking=False):
                raise BlockingIOError('Another action is running. Try again when it completes.')
            try:
                return {'result': str(action.run())}
            finally:
                self.execution_lock.release()
        identity = secrets.token_urlsafe(24)
        with self.pending_lock:
            self.pending = {key: value for key, value in self.pending.items() if value[0] > time.monotonic()}
            if len(self.pending) >= 100:
                raise ValueError('Too many pending actions. Cancel or let them expire.')
            self.pending[identity] = (time.monotonic() + 300, action)
        return {'id': identity, 'preview': action.preview, 'confirmation_required': True}

    def execute(self, identity):
        if not isinstance(identity, str):
            raise ValueError('An action ID is required.')
        if not self.execution_lock.acquire(blocking=False):
            raise BlockingIOError('Another action is running. Try again when it completes.')
        try:
            with self.pending_lock:
                pending = self.pending.pop(identity, None)
            if not pending or pending[0] <= time.monotonic():
                raise ValueError('Action expired or already used. Prepare it again.')
            return {'result': str(pending[1].run())}
        finally:
            self.execution_lock.release()

    def state(self):
        with self.assistant.db() as db:
            items = [dict(zip(('id', 'kind', 'text', 'due', 'done'), row)) for row in
                     db.execute('SELECT id,kind,text,due,done FROM items WHERE done=0 ORDER BY id DESC')]
            memory = [dict(zip(('name', 'value'), row)) for row in db.execute('SELECT name,value FROM memory ORDER BY name')]
        return {'items': items, 'memory': memory, 'pc_controls': self.allow_pc,
                'server_time': datetime.now().isoformat(timespec='seconds'),
                'timezone': str(datetime.now().astimezone().tzinfo)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Do not log request bodies, pairing codes or personal content.
        pass

    def send(self, status, value, content_type='application/json; charset=utf-8'):
        body = json.dumps(value).encode() if content_type.startswith('application/json') else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        expected = 'Bearer ' + self.server.token
        supplied = self.headers.get('Authorization', '')
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            self.send(401, {'error': 'Pair this phone using the code displayed on your PC.'})
            return False
        origin = self.headers.get('Origin')
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in {'http', 'https'} or parsed.netloc != self.headers.get('Host'):
                self.send(403, {'error': 'Cross-origin requests are not allowed.'})
                return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/state':
            if self.authorized():
                self.send(200, self.server.state())
            return
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in assets:
            self.send(404, {'error': 'Not found.'})
            return
        filename, kind = assets[path]
        self.send(200, (Path(__file__).parent / 'web' / filename).read_bytes(), kind)

    def do_POST(self):
        if not self.authorized():
            self.close_connection = True
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 16384:
                self.close_connection = True
                self.send(413, {'error': 'Request size must be between 1 and 16384 bytes.'})
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.send(415, {'error': 'JSON is required.'})
                self.close_connection = True
                return
            self.connection.settimeout(10)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('JSON object required.')
            path = urlsplit(self.path).path
            if path == '/api/prepare':
                value = self.server.prepare(data.get('request'))
            elif path == '/api/execute':
                value = self.server.execute(data.get('id'))
            elif path == '/api/cancel':
                identity = data.get('id')
                if not isinstance(identity, str):
                    raise ValueError('An action ID is required.')
                with self.server.pending_lock:
                    self.server.pending.pop(identity, None)
                value = {'result': 'Cancelled.'}
            else:
                self.send(404, {'error': 'Not found.'})
                return
            self.send(200, value)
        except PermissionError as exc:
            self.send(403, {'error': str(exc)})
        except BlockingIOError as exc:
            self.send(409, {'error': str(exc)})
        except (ValueError, TypeError, OSError) as exc:
            self.send(400, {'error': str(exc)})
        except Exception:
            self.send(500, {'error': 'Action failed on the PC. Check the request and try again.'})


def launch(assistant, host, port, allow_pc=False, cert=None, key=None):
    if bool(cert) != bool(key):
        raise ValueError('Supply both --cert and --key for HTTPS.')
    server = PhoneServer((host, port), assistant, allow_pc=allow_pc)
    if cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f'Havie phone server listening on {host}:{server.server_port}.')
    print('Open your PC’s private LAN address at this port on your phone.')
    print('Pairing code (changes on restart): ' + server.token)
    print('PC controls: ' + ('enabled; every action still requires confirmation' if allow_pc else 'disabled'))
    print('Keep the PC and server running. Use a trusted private network; do not port-forward this server.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
