"""Real loopback requests and disposable-worker lifecycle checks."""
import copy
import http.client
import json
import threading
import time
import tempfile
import unittest
from pathlib import Path

from ladderproof import make_design, analyze
from ladderproof.app import Jobs, Server, MAX_BODY
from ladderproof.cli import load_json
from ladderproof.errors import Invalid


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server(('127.0.0.1', 0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        supplied = {'Content-Type': 'application/json'}
        supplied.update(headers or {})
        if isinstance(body, dict):
            body = json.dumps(body)
        conn.request(method, path, body=body, headers=supplied)
        response = conn.getresponse()
        payload = response.read()
        status = response.status
        content = response.getheader('Content-Type')
        conn.close()
        return status, json.loads(payload) if content.startswith('application/json') else payload

    def finished(self, identifier):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            status, job = self.request('GET', '/api/jobs/' + identifier)
            self.assertEqual(status, 200)
            if job['state'] != 'running':
                return job
            time.sleep(.03)
        self.fail('Worker did not finish within the test deadline')

    def ready(self):
        deadline = time.monotonic() + 2
        while self.server.jobs.current is not None and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertIsNone(self.server.jobs.current)

    def test_real_design_analyze_verify_compare_journey_and_tamper_failure(self):
        status, design = self.request('POST', '/api/design', {'bits': 2, 'tolerance': '1/100', 'vref': '1'})
        self.assertEqual(status, 200)
        status, job = self.request('POST', '/api/jobs', {'operation': 'analyze', 'design': design})
        self.assertEqual(status, 202)
        complete = self.finished(job['id'])
        self.assertEqual(complete['state'], 'complete')
        certificate = complete['result']
        self.assertEqual(certificate['corner_count'], 16)
        self.ready()
        status, job = self.request('POST', '/api/jobs', {'operation': 'verify', 'certificate': certificate})
        self.assertEqual(status, 202)
        self.assertEqual(self.finished(job['id'])['result']['status'], 'verified')
        self.ready()
        changed = analyze(make_design(2, '0', '1'))
        status, job = self.request('POST', '/api/jobs', {'operation': 'compare', 'before': certificate, 'after': changed})
        self.assertEqual(status, 202)
        self.assertEqual(self.finished(job['id'])['result']['status'], 'verified-comparison')
        self.ready()
        altered = copy.deepcopy(certificate)
        altered['results']['steps'][0]['min'] = '0'
        status, job = self.request('POST', '/api/jobs', {'operation': 'verify', 'certificate': altered})
        self.assertEqual(status, 202)
        rejected = self.finished(job['id'])
        self.assertEqual(rejected['state'], 'failed')
        self.assertNotIn('result', rejected)
        self.ready()

    def test_one_worker_cancellation_is_terminal_and_server_stays_responsive(self):
        status, job = self.request('POST', '/api/jobs', {'operation': 'analyze', 'design': make_design(6, '1/20', '1')})
        self.assertEqual(status, 202)
        status, _ = self.request('POST', '/api/jobs', {'operation': 'analyze', 'design': make_design(2)})
        self.assertEqual(status, 409)
        start = time.monotonic()
        status, page = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'<title>LadderProof', page)
        self.assertIn(b'id="analyze"', page)
        self.assertIn(b'id="cancel"', page)
        status, cancelled = self.request('POST', '/api/jobs/' + job['id'] + '/cancel', {})
        self.assertEqual(status, 200)
        self.assertEqual(cancelled['state'], 'cancelled')
        self.assertLess(time.monotonic() - start, 1)
        self.ready()
        final = self.finished(job['id'])
        self.assertEqual(final['state'], 'cancelled')
        self.assertNotIn('result', final)
        self.assertFalse(self.server.jobs.jobs[job['id']]['process'].is_alive())

    def test_exact_validation_and_http_boundaries(self):
        design = make_design(2, '0', '1')
        design['resistors'][0]['nominal'] = '2000.0'
        status, canonical = self.request('POST', '/api/validate', {'design': design})
        self.assertEqual(status, 200)
        self.assertEqual(canonical['resistors'][0]['nominal'], '2000')
        for method, path, body, headers, expected in [
            ('GET', '/', None, {'Host': 'attacker.example'}, 403),
            ('GET', '/', None, {'Origin': 'https://attacker.example'}, 403),
            ('POST', '/api/validate', {'design': design}, {'Content-Type': 'text/plain'}, 415),
            ('POST', '/api/validate', '{"design":{},"design":{}}', {}, 400),
            ('POST', '/api/validate', '{"design":NaN}', {}, 400),
            ('POST', '/api/validate', '{}', {'Content-Length': str(MAX_BODY + 1)}, 413),
            ('POST', '/api/validate', {'design': {**design, 'correlation': 'same'}}, {}, 400),
            ('GET', '/../../etc/passwd', None, {}, 404),
            ('GET', '/api/jobs/missing', None, {}, 404),
            ('OPTIONS', '/api/jobs', None, {}, 405),
        ]:
            with self.subTest(path=path, headers=headers, body=body):
                self.assertEqual(self.request(method, path, body, headers)[0], expected)

    def test_deadline_refuses_without_certificate_and_nonloopback_bind_refused(self):
        with self.assertRaises(ValueError):
            Server(('0.0.0.0', 0))
        jobs = Jobs(seconds=.01)
        try:
            job = jobs.start('analyze', {'design': make_design(6)})
            deadline = time.monotonic() + 2
            while jobs.current is not None and time.monotonic() < deadline:
                time.sleep(.02)
            result = jobs.get(job['id'])
            self.assertEqual(result['state'], 'refused')
            self.assertNotIn('result', result)
            self.assertFalse(jobs.jobs[job['id']]['process'].is_alive())
        finally:
            jobs.close()

    def test_raw_imports_preserve_strict_json_and_cli_parity(self):
        design = make_design(2, '0', '1')
        certificate = analyze(design)
        status, reopened = self.request('POST', '/api/import-design', json.dumps(design))
        self.assertEqual(status, 200)
        self.assertEqual(reopened, design)
        status, parsed_unverified = self.request('POST', '/api/import-certificate', json.dumps(certificate))
        self.assertEqual(status, 200)
        self.assertEqual(parsed_unverified, certificate)
        self.assertNotEqual(parsed_unverified['status'], 'verified')
        for endpoint, data in [('/api/import-design', design), ('/api/import-certificate', certificate)]:
            raw = json.dumps(data).replace('"vref": "1"', '"vref": "2", "vref": "1"')
            with self.subTest(endpoint=endpoint):
                status, rejected = self.request('POST', endpoint, raw)
                self.assertEqual(status, 400)
                self.assertIn('Duplicate JSON field', rejected['error'])
                self.assertNotIn('result', rejected)
                with tempfile.TemporaryDirectory() as directory:
                    file = Path(directory) / 'duplicate.json'
                    file.write_text(raw)
                    with self.assertRaises(Invalid):
                        load_json(file)
                self.assertEqual(self.request('POST', endpoint, '{"x": NaN}')[0], 400)
                self.assertEqual(self.request('POST', endpoint, '{}', {'Content-Length': str(MAX_BODY+1)})[0], 413)


if __name__ == '__main__':
    unittest.main()
