"""Non-blocking, lease-authenticated publication of stdout and trusted diagnostics."""
from __future__ import annotations
import codecs
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import tempfile
import threading
import time
import traceback
import subprocess
import urllib.error
import urllib.request

from evaluation_log_safety import MAX_LOG_CHUNK, redact_evaluation_details, redact_log


class RunLogs:
    def __init__(self, base, job, directory=''):
        self.base, self.job = base, job
        self.temporary = None if directory else tempfile.TemporaryDirectory(prefix='evaluation-logs-')
        self.root = Path(directory or self.temporary.name)
        if directory and job.get('attempt', 1) > 1:
            self.root = self.root / f"attempt-{job['attempt']}"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.enabled = bool(job.get('logs_url'))
        self.secrets = [job.get('lease_token'), job.get('api_token')]
        self.secrets += [value for name, value in os.environ.items() if any(key in name.upper() for key in ('TOKEN', 'PASSWORD', 'API_KEY'))]
        self.files, self.offsets = [], {}
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.watch('worker', self.root/'worker.log')
        self.watch('diagnostics', self.root/'diagnostics.log')
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def watch(self, source, path):
        path = Path(path)
        with self.lock:
            if not any(item['path'] == path and item['source'] == source for item in self.files):
                self.files.append({'path':path,'source':source,'read':0,'pending':'',
                    'decoder':codecs.getincrementaldecoder('utf-8')('replace'),'in_key':False,
                    'redacting_value':False,'queue':b''})

    def replace(self, previous, current):
        with self.lock:
            for item in self.files:
                if item['path'] == Path(previous): item['path'] = Path(current)

    def event(self, text):
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with (self.root/'worker.log').open('a', encoding='utf-8') as output:
            output.write(f'{stamp} {redact_log(text, self.secrets)}\n')

    def exception(self):
        with (self.root/'diagnostics.log').open('a', encoding='utf-8') as output:
            output.write(redact_log(traceback.format_exc(), self.secrets)+'\n')

    def _redact_lines(self, item, final):
        pending = item['pending']
        if item['redacting_value']:
            end=re.search(r'''[\s,'"}\]]''',pending)
            if not end:
                item['pending']=''
                return b''
            pending=pending[end.start():]
            item['redacting_value']=False
        if final:
            lines, remaining = pending.splitlines(keepends=True), ''
        else:
            split = pending.rfind('\n')
            lines, remaining = (pending[:split+1].splitlines(keepends=True), pending[split+1:]) if split >= 0 else ([],pending)
        safe = []
        for line in lines:
            if '-----BEGIN ' in line and 'PRIVATE KEY-----' in line:
                item['in_key'] = True
                safe.append('[PRIVATE KEY REDACTED]\n')
            if item['in_key']:
                if '-----END ' in line and 'PRIVATE KEY-----' in line: item['in_key'] = False
                continue
            value=redact_log(line,self.secrets)
            value=redact_evaluation_details(value)
            safe.append(value)
        # Bound incomplete lines while retaining token-sized overlap.
        if len(remaining) > MAX_LOG_CHUNK:
            value=re.search(r'''(?i)(?:token|password|passwd|secret|api[_-]?key|seed|ground_truth)['"]?\s*[:=]\s*['"]?[^\s,'"}\]]*$''',remaining)
            if value:
                if not item['in_key']:
                    safe.append(redact_evaluation_details(redact_log(remaining,self.secrets)))
                item['redacting_value']=True
                item['pending']=''
                return ''.join(safe).encode('utf-8')
            cut = len(remaining)-4096
            # Never cut through a known credential or a keyed sensitive value.
            for secret in self.secrets:
                if isinstance(secret,str) and secret:
                    start=remaining.rfind(secret,0,cut+len(secret))
                    if start >= 0 and start < cut < start+len(secret): cut=min(cut,start)
            start=re.search(r'-----BEGIN [^\n]*PRIVATE KEY-----',remaining[:cut])
            if start:
                cut=min(cut,start.start())
                safe.append(redact_evaluation_details(redact_log(remaining[:cut],self.secrets)))
                safe.append('[PRIVATE KEY REDACTED]\n')
                item['in_key']=True
                item['pending']=remaining[-4096:]
                return ''.join(safe).encode('utf-8')
            prefix=remaining[:cut]
            if not item['in_key']:
                safe.append(redact_evaluation_details(redact_log(prefix,self.secrets)))
            remaining=remaining[cut:]
        item['pending'] = remaining
        return ''.join(safe).encode('utf-8')

    def flush(self, final=False, deadline=None):
        if not self.enabled: return True
        wait=max(0,deadline-time.monotonic()) if deadline else 0
        if not self.lock.acquire(timeout=wait): return False
        try:
            for item in self.files:
                if deadline is not None and time.monotonic() >= deadline: return
                source = item['source']
                if not item['queue']:
                    try:
                        with item['path'].open('rb') as stream:
                            stream.seek(item['read']); raw=stream.read(MAX_LOG_CHUNK)
                        item['read'] += len(raw)
                        item['pending'] += item['decoder'].decode(raw, final=False)
                    except FileNotFoundError:
                        raw=b''
                    is_end = final and (not item['path'].exists() or item['read'] >= item['path'].stat().st_size)
                    if is_end: item['pending'] += item['decoder'].decode(b'',final=True)
                    item['queue'] += self._redact_lines(item,is_end)
                while item['queue']:
                    if deadline is not None and time.monotonic() >= deadline: return
                    payload=item['queue'][:MAX_LOG_CHUNK].decode('utf-8','ignore').encode('utf-8')
                    offset=self.offsets.get(source,0)
                    request=urllib.request.Request(self.base + f"/evaluation-worker/runs/{self.job['id']}/logs/{source}",
                        data=json.dumps({'offset':offset,'text':payload.decode('utf-8')}).encode(),method='POST',
                        headers={'Content-Type':'application/json','X-Evaluation-Lease':self.job['lease_token'],
                                 'User-Agent':'Mozilla/5.0 UESTC-EvaluationCheck'})
                    timeout=min(3,max(.1,deadline-time.monotonic())) if deadline else 3
                    try:
                        with urllib.request.urlopen(request,timeout=timeout) as response: result=json.load(response)
                    except (OSError, ValueError):
                        # Retry from the acknowledged offset; evaluation must continue.
                        return False
                    self.offsets[source]=result['offset']
                    item['queue']=item['queue'][len(payload):]
            return True
        finally:
            self.lock.release()

    def _loop(self):
        while not self.stop.wait(1):
            try:self.flush()
            except (OSError, ValueError):pass

    def __enter__(self):
        self.event(f"领取测评任务；运行上限 {self.job['config']['resources']['time_seconds']} 秒")
        if self.enabled:self.thread.start()
        return self

    def __exit__(self, kind, error, tb):
        if error is not None:
            self.exception()
            self.event('运行失败：'+('evaluation time limit exceeded' if kind.__name__ in {'TimeoutExpired','TimeoutError'} else str(error)))
        else:self.event('运行与清理完成，准备回写结果')
        self.stop.set()
        if self.thread.ident:self.thread.join(timeout=4)
        if not self.enabled:
            if self.temporary:self.temporary.cleanup()
            return
        try:
            # Containers are stopped; final log transfer does not extend execution.
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                ok=self.flush(final=True,deadline=deadline)
                if all(not item['queue'] and (not item['path'].exists() or item['read']>=item['path'].stat().st_size) for item in self.files):break
                if not ok:self.stop.wait(min(.25,max(0,deadline-time.monotonic())))
        except (OSError, ValueError):pass
        finally:
            if self.temporary:self.temporary.cleanup()


@contextmanager
def capture_inference_logs(logs, output_root):
    """Observe native inference stdout without modifying the sealed GPU judge."""
    original = subprocess.Popen
    captured = []

    def launch(command, *args, **kwargs):
        if (isinstance(command, (tuple, list))
                and any(Path(str(part)).name == 'classification_inference.py' for part in command)):
            output = kwargs.get('stdout')
            if output and isinstance(getattr(output, 'name', None), str):
                captured.append(Path(output.name))
                logs.watch('agent', output.name)
                logs.event(f'开始分类推理场景 {len(captured)}')
        return original(command, *args, **kwargs)

    subprocess.Popen = launch
    try:
        yield
    finally:
        subprocess.Popen = original
        for index, previous in enumerate(captured, 1):
            retained = Path(output_root) / str(index) / 'inference.log'
            if retained.exists():
                logs.replace(previous, retained)
