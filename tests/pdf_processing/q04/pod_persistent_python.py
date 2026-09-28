"""One prestarted Python process per independent read-only Pod command lane.

Avoid repeated container-runtime exec processes inside the measured cgroup.
EOF, timeout and malformed responses fail the lane closed; never reconnect.
"""
import json
import os
import select
import subprocess
import time

SERVER = """import contextlib,io,json,sys
for line in sys.stdin:
 output=io.StringIO()
 try:
  request=json.loads(line)
  with contextlib.redirect_stdout(output):
   exec(request['program'],{'__name__':'__main__'})
  response={'output':output.getvalue()}
 except BaseException as error:
  response={'error':type(error).__name__+': '+str(error)}
 print(json.dumps(response),flush=True)
"""

class PersistentPython:
    def __init__(self, command):
        self.process = subprocess.Popen(
            [*command, '-u', '-c', SERVER], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        )
        try:
            self.run("print('ready')")
        except BaseException:
            self.close()
            raise

    def run(self, program, timeout=30):
        if self.process.poll() is not None:
            raise RuntimeError('persistent Python channel stopped; no retry')
        deadline = time.monotonic() + timeout
        request = json.dumps({'program': program}).encode() + b'\n'
        response = bytearray()
        try:
            while request:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([], [self.process.stdin], [], remaining)[1]:
                    raise TimeoutError('persistent Python request timeout')
                written = os.write(self.process.stdin.fileno(), request[:4096])
                request = request[written:]
            while not response.endswith(b'\n'):
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                    raise TimeoutError('persistent Python response timeout')
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError('persistent Python channel EOF; no retry')
                response.extend(chunk)
            value = json.loads(response)
            if set(value) not in ({'output'}, {'error'}):
                raise ValueError('invalid persistent Python response')
        except BaseException:
            self.close()
            raise
        if 'error' in value:
            raise RuntimeError(value['error'])
        return value['output']

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                stream.close()
