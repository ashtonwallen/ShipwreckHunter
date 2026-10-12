"""One-command local startup. No cloud account or LLM key required."""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
import json

ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
PY=ROOT/('.venv/Scripts/python.exe' if os.name=='nt' else '.venv/bin/python')

def run(args,**kwargs):
    subprocess.run([str(a) for a in args],check=True,**kwargs)

def main():
    parser=argparse.ArgumentParser(description='Start Shipwreck Hunter on loopback')
    parser.add_argument('--port',type=int,default=8787)
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('--port must be between 1 and 65535')
    url=f'http://127.0.0.1:{args.port}'
    try:
        with urllib.request.urlopen(url+'/api/health',timeout=2) as r:
            health=json.load(r)
        if health.get('application')=='GHOSTFLEET':
            print('Shipwreck Hunting Tool is already running: '+url);return
    except Exception:pass
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',args.port))==0:
            raise SystemExit(f'Port {args.port} is occupied by another process. Choose a free port with --port, for example: python start.py --port 8788')
    if not PY.exists():
        if sys.version_info<(3,12):raise SystemExit('Python 3.12+ is required; 3.13 was tested.')
        run([sys.executable,'-m','venv',ROOT/'.venv'])
    deps=ROOT/'requirements.txt';digest=hashlib.sha256(deps.read_bytes()).hexdigest()
    stamp=ROOT/'.venv/ghostfleet-dependencies'
    if not stamp.exists() or stamp.read_text()!=digest:
        run([PY,'-m','pip','install','-r',deps]);stamp.write_text(digest)
    frontend=ROOT/'frontend';build=frontend/'dist/index.html'
    inputs=[*frontend.glob('src/**/*'),frontend/'package-lock.json',frontend/'vite.config.ts']
    if not build.exists() or any(p.is_file() and p.stat().st_mtime>build.stat().st_mtime for p in inputs):
        npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
        if not npm:raise SystemExit('Node.js 22+ and npm are required to build the frontend.')
        run([npm,'ci'],cwd=frontend);run([npm,'run','build'],cwd=frontend)
    if not (ROOT/'data/ghostfleet.sqlite').exists():run([PY,'-m','scripts.seed'])
    print('Shipwreck Hunting Tool: '+url+'\nCtrl+C stops the local server.',flush=True)
    run([PY,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',str(args.port)])

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except subprocess.CalledProcessError as exc:raise SystemExit(exc.returncode)
