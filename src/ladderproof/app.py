"""Loopback workbench with one bounded, disposable computation process.

The HTTP surface has no filesystem paths, shell calls, or external requests.
"""
from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path
import queue
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 1_048_576
MAX_SECONDS = 30
ASSETS = Path(__file__).with_name('assets')


def _work(output, cancelled, operation, payload):
    try:
        from . import analyze, verify, compare, Budget
        budget = Budget(seconds=MAX_SECONDS, cancel=cancelled.is_set)
        if operation == 'analyze':
            result = analyze(payload['design'], budget=budget)
        elif operation == 'verify':
            result = verify(payload['certificate'], budget=budget)
        else:
            result = compare(payload['before'], payload['after'], budget=budget)
        output.put({'state': 'complete', 'result': result})
    except Exception as exc:
        from .errors import Refused
        output.put({'state': 'refused' if isinstance(exc, Refused) else 'failed',
                    'error': str(exc)[:1000] or type(exc).__name__})


class Jobs:
    """One running process. Cancelled jobs can never become complete."""
    def __init__(self, seconds=MAX_SECONDS):
        self.lock = threading.RLock()
        self.context = mp.get_context('spawn')
        self.jobs = {}
        self.current = None
        self.seconds = min(MAX_SECONDS, max(.01, seconds))
        self.closed = False

    def start(self, operation, payload):
        with self.lock:
            if self.closed:
                raise ValueError('Service is closing.')
            if self.current is not None:
                raise ValueError('A computation is already running. Cancel it or wait for completion.')
            identifier = uuid.uuid4().hex
            output = self.context.Queue(maxsize=1)
            cancelled = self.context.Event()
            process = self.context.Process(target=_work, args=(output, cancelled, operation, payload), daemon=True)
            job = {'id': identifier, 'operation': operation, 'state': 'running',
                   'process': process, 'output': output, 'cancelled': cancelled,
                   'started': time.monotonic()}
            self.jobs[identifier] = job
            self.current = identifier
            try:
                process.start()
            except Exception:
                self.current = None
                del self.jobs[identifier]
                output.close()
                raise
            threading.Thread(target=self._monitor, args=(identifier,), daemon=True).start()
            for old in list(self.jobs)[:-8]:
                if old != self.current:
                    del self.jobs[old]
            return self._public(job)

    def _monitor(self, identifier):
        job = self.jobs[identifier]
        process = job['process']
        response = None
        while True:
            try:
                response = job['output'].get(timeout=.05)
                break
            except queue.Empty:
                with self.lock:
                    if job['state'] != 'running':
                        break
                    if time.monotonic() - job['started'] >= self.seconds:
                        job.update(state='refused', error='Computation exceeded the 30-second service limit. No certificate was produced.')
                        job['cancelled'].set()
                        break
                if not process.is_alive():
                    response = {'state': 'failed', 'error': 'Computation stopped without a complete result.'}
                    break
        if process.is_alive():
            # A complete result has been drained before join; cancelled/deadline
            # paths are terminated so HTTP stays responsive.
            if response is None:
                process.terminate()
            process.join(timeout=.5)
            if process.is_alive():
                process.kill()
                process.join(timeout=.5)
        else:
            process.join(timeout=.1)
        with self.lock:
            if job['state'] == 'running' and response is not None:
                job.update(response)
            if self.current == identifier:
                self.current = None
        job['output'].close()

    def _public(self, job):
        return {key: value for key, value in job.items()
                if key in {'id', 'operation', 'state', 'result', 'error'}}

    def get(self, identifier):
        with self.lock:
            return self._public(self.jobs[identifier])

    def cancel(self, identifier):
        with self.lock:
            job = self.jobs[identifier]
            if job['state'] == 'running':
                job.update(state='cancelled', error='Cancelled. No certificate was produced.')
                job['cancelled'].set()
            return self._public(job)

    def close(self):
        with self.lock:
            self.closed = True
            processes = []
            for job in self.jobs.values():
                if job['state'] == 'running':
                    job.update(state='cancelled', error='Service closed.')
                    job['cancelled'].set()
                processes.append(job['process'])
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=.5)


def _object(body):
    """Reject ambiguous duplicate keys and non-finite JSON numbers."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Non-finite JSON numbers are not accepted.')
    value = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError('A JSON object is required.')
    return value


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self, address=('127.0.0.1', 8766), jobs=None):
        if address[0] != '127.0.0.1':
            raise ValueError('LadderProof only binds to 127.0.0.1.')
        self.jobs = jobs or Jobs()
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, Handler)
    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise
    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()
    def server_close(self):
        self.jobs.close()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
    def log_message(self, *_args):
        pass
    def _send(self, status, data, content='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if content.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True
    def _boundary(self):
        port = self.server.server_address[1]
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        host = self.headers.get_all('Host', [])
        if len(host) != 1 or host[0] not in hosts:
            self._send(403, {'error': 'Loopback Host required.'})
            return False
        origins = self.headers.get_all('Origin', [])
        if len(origins) > 1 or (origins and origins[0] != 'http://' + host[0]):
            self._send(403, {'error': 'Same-origin request required.'})
            return False
        return True
    def do_GET(self):
        if not self._boundary():
            return
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.path in assets:
            filename, mime = assets[self.path]
            self._send(200, (ASSETS / filename).read_bytes(), mime)
        elif self.path.startswith('/api/jobs/') and len(self.path.split('/')) == 4:
            identifier = self.path.split('/')[-1]
            try:
                self._send(200, self.server.jobs.get(identifier))
            except KeyError:
                self._send(404, {'error': 'Job not found.'})
        else:
            self._send(404, {'error': 'Resource not found.'})
    def do_POST(self):
        if not self._boundary():
            return
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) != 1:
            self._send(411, {'error': 'One bounded Content-Length is required.'})
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            self._send(415, {'error': 'Content-Type must be application/json.'})
            return
        try:
            length = int(lengths[0])
            if length < 0 or length > MAX_BODY:
                self._send(413, {'error': 'JSON input exceeds the 1 MiB limit.'})
                return
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError('Incomplete request body.')
            data = _object(body)
            if self.path == '/api/design':
                from . import make_design
                if set(data) != {'bits', 'tolerance', 'vref'}:
                    raise ValueError('Expected bits, tolerance and vref.')
                self._send(200, make_design(**data))
            elif self.path == '/api/validate':
                from . import parse_design
                if set(data) != {'design'}:
                    raise ValueError('Expected one design object.')
                self._send(200, parse_design(data['design']).to_dict())
            elif self.path == '/api/import-design':
                from . import parse_design
                self._send(200, parse_design(data).to_dict())
            elif self.path == '/api/import-certificate':
                # Only strict JSON parsing happens here. This object is still
                # unverified and must go through the independent worker.
                self._send(200, data)
            elif self.path == '/api/jobs':
                operation = data.get('operation')
                keys = {'analyze': {'operation', 'design'}, 'verify': {'operation', 'certificate'},
                        'compare': {'operation', 'before', 'after'}}
                if operation not in keys or set(data) != keys[operation]:
                    raise ValueError('Expected an analyze, verify or compare payload.')
                # Bound cheap validation before allocating the worker.
                from . import parse_design
                if operation == 'analyze':
                    parse_design(data['design'])
                elif operation == 'verify' and not isinstance(data['certificate'], dict):
                    raise ValueError('Certificate must be a JSON object.')
                elif operation == 'compare' and not all(isinstance(data[k], dict) for k in ('before', 'after')):
                    raise ValueError('Comparison requires two certificate objects.')
                try:
                    job = self.server.jobs.start(operation, data)
                except ValueError as exc:
                    self._send(409, {'error': str(exc)})
                    return
                self._send(202, job)
            elif self.path.startswith('/api/jobs/') and self.path.endswith('/cancel') and len(self.path.split('/')) == 5:
                if data:
                    raise ValueError('Cancellation body must be empty.')
                try:
                    self._send(200, self.server.jobs.cancel(self.path.split('/')[3]))
                except KeyError:
                    self._send(404, {'error': 'Job not found.'})
            else:
                self._send(404, {'error': 'Resource not found.'})
        except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
            self._send(400, {'error': str(exc)[:1000]})
        except Exception as exc:
            from .errors import Invalid
            self._send(400 if isinstance(exc, Invalid) else 500, {'error': str(exc)[:1000]})
    def do_OPTIONS(self):
        self._send(405, {'error': 'Cross-origin preflight is not supported.'})


def serve(host='127.0.0.1', port=8766):
    server = Server((host, port))
    print(f'LadderProof workbench: http://127.0.0.1:{server.server_address[1]}', flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
