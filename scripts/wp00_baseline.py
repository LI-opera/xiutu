"""Run unchanged legacy pytest with isolated paths, no network, and evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def inventory(root):
    command = ['rg','--files','--hidden','-g','!.git/**','-g','!.venv/**','-g','!.test-runs/**','-g','!.pytest_cache/**','-g','!**/__pycache__/**','-g','!logs/**','-g','!backups/**','-g','!data/**','-g','!.env','-g','!.env.*','-g','!.agents/**','-g','!.codex/**']
    found = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8', check=True).stdout.splitlines()
    if (root/'.env.example').is_file():
        found.append('.env.example')
    return {Path(p).as_posix(): {'sha256':sha(root/p),'size':(root/p).stat().st_size} for p in sorted(set(found))}


def child(old, run):
    sys.path.insert(0, str(old))
    os.chdir(old)
    # Override possible default-app initialization; explicit fixtures still use pytest tmp_path.
    os.environ.update(DATABASE_PATH=str(run/'fallback.db'),DOCUMENTS_PATH=str(run/'docs'),ATTACHMENTS_PATH=str(run/'attachments'),LOG_PATH=str(run/'logs'),DEEPSEEK_API_KEY='',WEB_SEARCH_ENABLED='false',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
    def guard(event, args):
        # Windows asyncio uses a loopback socketpair for its internal wakeup pipe.
        if event == 'socket.connect' and args[1][0] in ('127.0.0.1', '::1'):
            frame = sys._getframe(1)
            if frame.f_code.co_name == '_fallback_socketpair' and frame.f_globals.get('__name__') == 'socket':
                return
        if event in ('socket.connect','socket.getaddrinfo'):
            raise RuntimeError('WP-00 baseline forbids network access')
        if event == 'sqlite3.connect':
            path = str(args[0])
            if path != ':memory:' and run not in Path(path).resolve().parents:
                raise RuntimeError('WP-00 baseline forbids SQLite outside test directory')
    sys.addaudithook(guard)
    import pytest
    return pytest.main([str(old/'tests'),'-q','-p','no:cacheprovider','--basetemp='+str(run/'pytest'),'--tb=short','--junitxml='+str(run/'junit.xml')])

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--old',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--evidence',type=Path)
    p.add_argument('--child',action='store_true')
    args=p.parse_args()
    old=args.old.resolve(); run=args.run.resolve()
    if args.child:
        sys.exit(child(old,run))
    run.mkdir(parents=True,exist_ok=False)
    evidence=args.evidence.resolve()
    before=inventory(old)
    (evidence/'legacy-hashes-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
    command=[sys.executable,'-B',str(Path(__file__).resolve()),'--child','--old',str(old),'--run',str(run)]
    start=datetime.now(timezone.utc).isoformat()
    result=subprocess.run(command,cwd=old,capture_output=True,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'})
    (evidence/'legacy-pytest.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
    after=inventory(old)
    (evidence/'legacy-hashes-after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'started_at':start,'finished_at':datetime.now(timezone.utc).isoformat(),'command':command,'exit_code':result.returncode,'old':str(old),'run':str(run),'python':sys.executable,'python_version':sys.version,'source_file_count':len(before),'hashes_identical':before==after,'network':'blocked by Python audit hook','sqlite':'restricted to run directory','pytest_cache':'disabled','bytecode':'disabled'}
    if (run/'junit.xml').exists():
        import shutil
        import xml.etree.ElementTree as ET
        shutil.copyfile(run/'junit.xml',evidence/'legacy-junit.xml')
        summary['junit']=[suite.attrib for suite in ET.parse(run/'junit.xml').getroot()]
    (evidence/'legacy-test-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(result.stdout[-3500:])
    sys.exit(result.returncode if before==after else 90)

