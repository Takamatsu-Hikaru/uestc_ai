import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_independent_evaluation_trials import IndependentTrialTests
from platform_api.extensions import db
from platform_api.models import EvaluationRun, utcnow
from evaluation_logs import RunLogs, capture_inference_logs
from evaluation_log_safety import redact_evaluation_details, redact_log


class LogApiTests(unittest.TestCase):
    setUp = IndependentTrialTests.setUp
    tearDown = IndependentTrialTests.tearDown
    register = IndependentTrialTests.register
    login = IndependentTrialTests.login
    fixture = IndependentTrialTests.fixture
    claim = IndependentTrialTests.claim
    stage = IndependentTrialTests.stage
    start = IndependentTrialTests.start
    complete = IndependentTrialTests.complete
    formal = IndependentTrialTests.formal

    def prepare(self):
        self.fixture()
        self.asset = self.stage()
        self.run = self.start(self.asset).get_json()
        self.job = self.claim()
        self.headers = {'X-Evaluation-Lease': self.job['lease_token']}
        self.url = self.job['logs_url']

    def append(self, source, text, offset=0):
        return self.worker.post(self.url + '/' + source, headers=self.headers,
                                json={'text': text, 'offset': offset})

    def test_all_sources_visible_to_team_and_formal_judges_only(self):
        self.prepare()
        for source in ['agent', 'controller', 'worker', 'diagnostics', 'environment']:
            response = self.append(source, f'{source} 输出\n')
            self.assertEqual(response.status_code, 200, response.get_json())
        endpoint = f"/api/evaluation-runs/{self.run['id']}/logs"
        listed = self.member.get(endpoint)
        self.assertEqual(listed.headers['Cache-Control'], 'private, no-store')
        streams = listed.get_json()['items']
        self.assertEqual(len(streams), 5)
        self.assertEqual(self.member.get(f"/api/evaluation-runs/{self.run['id']}").get_json()['artifacts'], [])
        self.login(self.reviewer, 'reviewer@uestc.ai')
        self.assertEqual(self.reviewer.get(endpoint).status_code, 404)
        other = self.app.test_client()
        self.register(other, 'log-other@std.uestc.edu.cn', 'Other')
        self.assertEqual(other.get(endpoint).status_code, 404)
        self.assertEqual(self.app.test_client().get(endpoint).status_code, 401)
        self.complete(self.job)
        self.assertEqual(self.formal(self.asset, self.run['id']).status_code, 201)
        self.assertEqual(len(self.reviewer.get(endpoint).get_json()['items']), 5)
        for stream in streams:
            read = f"/api/evaluation-logs/{stream['id']}"
            self.assertIn('输出', self.reviewer.get(read).get_json()['text'])
            self.assertEqual(other.get(read).status_code, 404)
            download = self.reviewer.get(stream['url'], buffered=True)
            self.assertEqual(download.status_code, 200)
            self.assertIn('输出'.encode(), download.data)
            download.close()
        self.assertEqual(self.member.get(self.budget_url).get_json()['used_runs'], 1)
        self.assertEqual(self.append('agent', 'late', 0).status_code, 403)

    def test_utf8_resume_lost_ack_redaction_and_offset_validation(self):
        self.prepare()
        text = f'第一行 api_key="sk-{"x"*25}" lease={self.job["lease_token"]} world_seed=12345\n'
        response = self.append('agent', text)
        self.assertEqual(response.status_code, 200)
        ack = response.get_json()['offset']
        self.assertEqual(self.append('agent', text).get_json()['offset'], ack)
        self.assertEqual(self.append('agent', 'other').status_code, 409)
        self.assertEqual(self.append('agent', '结束\n', ack).status_code, 200)
        stream = self.member.get(f"/api/evaluation-runs/{self.run['id']}/logs").get_json()['items'][0]
        url = f"/api/evaluation-logs/{stream['id']}"
        first = self.member.get(url + '?limit=4').get_json()
        self.assertEqual(first['text'], '第')
        self.assertEqual(first['offset'], 3)
        rest = self.member.get(url + '?offset=3').get_json()
        entire = first['text'] + rest['text']
        self.assertNotIn('12345', entire)
        self.assertNotIn(self.job['lease_token'], entire)
        self.assertNotIn('x'*25, entire)
        self.assertIn('第一行', entire)
        self.assertIn('结束', entire)
        self.assertEqual(self.member.get(url + '?offset=-1').status_code, 400)
        self.assertEqual(self.append('agent', 'x'*65537).status_code, 413)
        self.assertEqual(self.append('unknown', 'text').status_code, 400)
        self.assertEqual(self.append('agent', 'text', True).status_code, 400)

    def test_expired_or_reclaimed_lease_cannot_append_and_attempts_are_separate(self):
        self.prepare()
        self.assertEqual(self.append('controller', 'first attempt\n').status_code, 200)
        with self.app.app_context():
            run = db.session.get(EvaluationRun, self.run['id'])
            run.lease_expires_at = utcnow() - timedelta(seconds=1)
            db.session.commit()
        self.assertEqual(self.append('controller', 'expired').status_code, 403)
        replacement = self.claim()
        self.assertEqual(replacement['attempt'], 2)
        self.assertEqual(self.append('controller', 'stale').status_code, 403)
        self.headers = {'X-Evaluation-Lease': replacement['lease_token']}
        self.assertEqual(self.append('controller', 'second attempt\n').status_code, 200)
        streams = self.member.get(f"/api/evaluation-runs/{self.run['id']}/logs").get_json()['items']
        self.assertEqual([item['attempt'] for item in streams], [1, 2])

    def test_large_log_is_not_truncated_at_evidence_or_screen_limit(self):
        from platform_api.progress_models import EvaluationArtifact
        self.prepare()
        with self.app.app_context():
            run=db.session.get(EvaluationRun,self.run['id'])
            size=25*1024*1024
            root=Path(self.app.config['UPLOAD_FOLDER'])
            path=root/'large.log'
            with path.open('wb') as output:
                output.seek(size-1);output.write(b'\n')
            db.session.add(EvaluationArtifact(run=run,name='attempt-1-agent.log',storage_name=path.name,size=size))
            db.session.commit()
        result=self.append('agent','after 25 MiB\n',size)
        self.assertEqual(result.status_code,200)
        self.assertGreater(result.get_json()['offset'],size)
        stream=self.member.get(f"/api/evaluation-runs/{self.run['id']}/logs").get_json()['items'][0]
        tail=self.member.get(f"/api/evaluation-logs/{stream['id']}?offset={size}").get_json()
        self.assertEqual(tail['text'],'after 25 MiB\n')


class LogPublisherTests(unittest.TestCase):
    def job(self):
        return {'id': 'test-log', 'attempt': 1, 'lease_token': 'long-private-lease-value',
                'api_token': 'long-private-model-value', 'logs_url': '/api/evaluation-worker/runs/test-log/logs',
                'config': {'resources': {'time_seconds': 30}}}

    def test_incremental_upload_redacts_split_credentials_and_private_key(self):
        with tempfile.TemporaryDirectory() as directory:
            publisher = RunLogs('https://example.test/api', self.job(), directory)
            path = Path(directory)/'agent.log'
            publisher.watch('agent', path)
            received = bytearray()
            def post(request, **kwargs):
                data = json.loads(request.data)
                self.assertEqual(data['offset'], len(received))
                received.extend(data['text'].encode())
                return io.BytesIO(json.dumps({'offset': len(received)}).encode())
            with patch('evaluation_logs.urllib.request.urlopen', side_effect=post):
                path.write_bytes(b'normal stdout\napi_key=long-private-')
                publisher.flush()
                self.assertIn(b'normal stdout', received)
                self.assertNotIn(b'private-', received)
                with path.open('ab') as file:
                    file.write(b'model-value\n-----BEGIN RSA PRIVATE KEY-----\nprivate-body\n')
                publisher.flush()
                with path.open('ab') as file:
                    file.write(b'-----END RSA PRIVATE KEY-----\nstderr traceback\nworld_seed=99999\nlast without newline')
                publisher.flush(final=True)
            output = received.decode()
            self.assertIn('stderr traceback', output)
            self.assertIn('last without newline', output)
            self.assertNotIn('model-value', output)
            self.assertNotIn('private-body', output)
            self.assertNotIn('99999', output)

    def test_http_failure_retains_chunk_and_retry_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            publisher = RunLogs('https://example.test/api', self.job(), directory)
            path = Path(directory)/'agent.log'
            path.write_text('stdout\nstderr\n')
            publisher.watch('agent', path)
            with patch('evaluation_logs.urllib.request.urlopen', side_effect=OSError('network down')):
                self.assertFalse(publisher.flush())
            self.assertTrue(publisher.files[-1]['queue'])
            def ack(request, **kwargs):
                data = json.loads(request.data)
                return io.BytesIO(json.dumps({'offset': len(data['text'].encode())}).encode())
            with patch('evaluation_logs.urllib.request.urlopen', side_effect=ack):
                self.assertTrue(publisher.flush(final=True))
            self.assertFalse(publisher.files[-1]['queue'])
            self.assertEqual(publisher.offsets['agent'], len(path.read_bytes()))

    def test_redaction_is_idempotent_and_preserves_diagnostic_text(self):
        text = 'api_token="abc" Bearer private-token world_seed=777 <Seed>888</Seed> accuracy=90 error=bad-action'
        once = redact_evaluation_details(redact_log(text))
        self.assertEqual(once, redact_evaluation_details(redact_log(once)))
        self.assertIn('accuracy=90 error=bad-action', once)
        self.assertNotIn('777', once)

    def test_upload_lock_has_bounded_final_wait(self):
        import threading
        with tempfile.TemporaryDirectory() as directory:
            publisher = RunLogs('https://example.test/api', self.job(), directory)
            locked, release = threading.Event(), threading.Event()
            def hold():
                with publisher.lock:
                    locked.set(); release.wait(2)
            thread = threading.Thread(target=hold)
            thread.start(); locked.wait(1)
            before = time.monotonic()
            self.assertFalse(publisher.flush(final=True, deadline=before + .1))
            self.assertLess(time.monotonic()-before, .3)
            release.set(); thread.join()

    def test_long_unterminated_secret_has_bounded_buffer_and_preserves_following_output(self):
        with tempfile.TemporaryDirectory() as directory:
            publisher=RunLogs('',self.job(),directory)
            item=publisher.files[0]
            item['pending']='stdout api_key='+'x'*70000
            first=publisher._redact_lines(item,False).decode()
            self.assertIn('stdout api_key=[REDACTED]',first)
            self.assertEqual(item['pending'],'')
            item['pending']='x'*65000
            self.assertEqual(publisher._redact_lines(item,False),b'')
            item['pending']='x'*100+'\nnext stdout\n'
            last=publisher._redact_lines(item,True).decode()
            self.assertIn('next stdout',last)
            self.assertNotIn('x',last.split('next')[0])

    def test_native_inference_capture_survives_temporary_file_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            temporary = root/'inference.log'
            temporary.write_text('GPU inference output\n')
            retained = root/'1'/'inference.log'
            publisher = RunLogs('https://example.test/api', self.job(), str(root))
            original = subprocess.Popen
            with patch('evaluation_logs.subprocess.Popen') as launch:
                with capture_inference_logs(publisher, root):
                    with temporary.open('ab') as output:
                        subprocess.Popen([sys.executable, '-I', '/sealed/classification_inference.py'], stdout=output)
                    retained.parent.mkdir(); retained.write_bytes(temporary.read_bytes())
                    temporary.unlink()
                self.assertIs(subprocess.Popen, launch)
            self.assertIs(subprocess.Popen, original)
            self.assertEqual(publisher.files[-1]['path'], retained)
            self.assertEqual(publisher.files[-1]['read'], 0)


if __name__ == '__main__':
    unittest.main()
