"""Check the installed distribution outside the source tree, including real HTTP.

Run with the fresh environment's python -I, never through PYTHONPATH=src.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    source=args.source.resolve()
    import ladderproof
    installed=Path(ladderproof.__file__).resolve()
    if source in installed.parents:
        raise AssertionError('smoke must import an installed distribution outside the source checkout')
    if importlib.metadata.requires('ladderproof'):
        raise AssertionError('runtime distribution unexpectedly requires dependencies')
    env=os.environ.copy()
    env.pop('PYTHONPATH',None); env.pop('PYTHONHOME',None)
    report={'version':importlib.metadata.version('ladderproof'),'python':sys.version.split()[0],
            'installed_module':str(installed),'outside_checkout':True,'runtime_dependencies':[],
            'cli':{},'served_assets':{},'http':{}}
    with tempfile.TemporaryDirectory(prefix='ladderproof-installed-') as temporary:
        cwd=Path(temporary)
        def cli(*arguments):
            result=subprocess.run([sys.executable,'-I','-m','ladderproof',*arguments],cwd=cwd,
                                  env=env,text=True,capture_output=True,timeout=40)
            if result.returncode:
                raise AssertionError(f'installed CLI failed ({result.returncode}): {result.stderr}')
            return json.loads(result.stdout) if result.stdout.strip() else None
        cli('create','--bits','6','--tolerance','1/20','--output','loose.json')
        # Genuine input edit, including finite individual component intervals.
        design=json.loads((cwd/'loose.json').read_text())
        design['title']='Installed six-bit individual-interval inspection'
        (cwd/'loose.json').write_text(json.dumps(design))
        cli('analyze','loose.json','--output','loose.certificate.json')
        loose=cli('verify','loose.certificate.json')
        assert loose['status']=='verified' and loose['corner_count']==4096
        assert loose['worst_transition']['step']=='-269227/7660721'
        assert (loose['worst_transition']['from'],loose['worst_transition']['to'])==(31,32)
        cli('create','--bits','6','--tolerance','1/100','--output','tight.json')
        cli('analyze','tight.json','--output','tight.certificate.json')
        tight=cli('verify','tight.certificate.json')
        assert tight['status']=='verified' and tight['nondecreasing']
        assert tight['worst_transition']['step']=='186147971/34016602567'
        comparison=cli('compare','loose.certificate.json','tight.certificate.json')
        assert comparison['status']=='verified-comparison'
        assert not comparison['before']['nondecreasing'] and comparison['after']['nondecreasing']
        report['cli']={'create_edit_analyze_reopen_verify_compare':'passed',
                       'loose_step':loose['worst_transition']['step'],
                       'tight_step':tight['worst_transition']['step'],
                       'same_assignment_witness':loose['worst_transition'],
                       'comparison_status':comparison['status']}
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        with (cwd/'server.log').open('w+') as log:
            process=subprocess.Popen([sys.executable,'-I','-m','ladderproof','serve','--port',str(port)],
                                     cwd=cwd,env=env,stdout=log,stderr=log,text=True)
            try:
                deadline=time.monotonic()+8
                while True:
                    if process.poll() is not None:
                        log.seek(0); raise AssertionError('installed server failed: '+log.read())
                    try:
                        with urlopen(base+'/',timeout=1) as response:
                            assert response.status==200
                            break
                    except (URLError,TimeoutError):
                        if time.monotonic()>=deadline: raise AssertionError('installed server never became ready')
                        time.sleep(.05)
                for route,filename in [('/','index.html'),('/app.js','app.js'),('/style.css','style.css')]:
                    with urlopen(base+route,timeout=3) as response:
                        observed=response.read()
                        assert response.status==200
                        assert response.headers['X-Content-Type-Options']=='nosniff'
                    expected=(source/'src'/'ladderproof'/'assets'/filename).read_bytes()
                    assert observed==expected, f'installed served asset differs: {filename}'
                    report['served_assets'][filename]={'bytes':len(observed),'sha256':hashlib.sha256(observed).hexdigest(),'source_identity':True}
                def request(route,data=None):
                    body=None if data is None else json.dumps(data).encode()
                    headers={'Origin':base,'Content-Type':'application/json'} if body is not None else {}
                    with urlopen(Request(base+route,data=body,headers=headers),timeout=3) as response:
                        return json.loads(response.read())
                def finish(job):
                    limit=time.monotonic()+35
                    while job['state']=='running':
                        if time.monotonic()>limit: raise AssertionError('installed job exceeded smoke limit')
                        time.sleep(.04)
                        job=request('/api/jobs/'+job['id'])
                    assert job['state']=='complete',job
                    return job['result']
                d=request('/api/design',{'bits':3,'tolerance':'1/100','vref':'1'})
                certificate=finish(request('/api/jobs',{'operation':'analyze','design':d}))
                verified=finish(request('/api/jobs',{'operation':'verify','certificate':certificate}))
                assert verified['status']=='verified' and verified['corner_count']==64
                report['http']={'cli_serve_outside_checkout':'passed','spawned_installed_analysis':'passed',
                                'independent_installed_verification':'passed','corner_count':64}
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try: process.wait(timeout=3)
                        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
                report['http']['owned_server_stopped']=process.poll() is not None
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
