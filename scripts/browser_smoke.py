"""Destructive UI smoke runs exclusively against a disposable, seeded database."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory(prefix='shoppilot-ui-') as temp:
        env={**os.environ,'SHOP_DB':str(Path(temp)/'test.sqlite3')}
        seed='''
from scripts.manage import seed
from backend.app import db,hash_password
seed()
with db() as c:
    for uid,name,role in [('ui-admin','ui_admin','admin'),('ui-user','ui_user','user')]:
        c.execute('INSERT INTO users(id,username,password,role) VALUES(?,?,?,?)',(uid,name,hash_password('UI-test-password-123'),role))
        c.execute('INSERT INTO profiles VALUES(?,?,?,?)',(uid+'-profile',uid,'我','{}'))
'''
        subprocess.run([sys.executable,'-c',seed],env=env,cwd=ROOT,check=True)
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        env['SHOP_SMOKE_URL']=f'http://127.0.0.1:{port}'
        server=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(port)],env=env,cwd=ROOT,stdout=subprocess.DEVNULL)
        try:
            ready=False
            for _ in range(60):
                try:
                    urllib.request.urlopen(env['SHOP_SMOKE_URL']+'/api/health',timeout=1).close();ready=True;break
                except OSError:
                    if server.poll() is not None: raise RuntimeError('Test server failed to start')
                    time.sleep(.1)
            if not ready: raise RuntimeError('Test server startup timed out')
            subprocess.run(['node',str(ROOT/'scripts/browser-check.mjs')],env=env,cwd=ROOT,check=True,timeout=150)
        finally:
            server.terminate();server.wait(timeout=10)
if __name__=='__main__':main()
