"""Actual CLI effects: distribution command tested separately at installation gate."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def run(*args):
    env=os.environ.copy(); env['PYTHONPATH']=str(ROOT/'src')
    return subprocess.run([sys.executable,'-m','ladderproof',*map(str,args)],env=env,text=True,capture_output=True)

class CLITests(unittest.TestCase):
    def test_complete_json_edit_analyze_verify_compare_journey(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); design=p/'design.json'; c1=p/'c1.json'; c2=p/'c2.json'
            result=run('create','--bits','2','--tolerance','1/100','--output',design)
            self.assertEqual(result.returncode,0,result.stderr)
            document=json.loads(design.read_text()); document['resistors'][0]['nominal']='2050'
            document['resistors'][0]['max']='2100'; design.write_text(json.dumps(document))
            result=run('analyze',design,'--output',c1)
            self.assertEqual(result.returncode,0,result.stderr)
            result=run('verify',c1)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'verified')
            result=run('create','--bits','2','--tolerance','0','--output',design,'--force')
            self.assertEqual(result.returncode,0,result.stderr)
            result=run('analyze',design,'--output',c2)
            self.assertEqual(result.returncode,0,result.stderr)
            result=run('compare',c1,c2)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'verified-comparison')

    def test_invalid_input_and_deadline_preserve_existing_output_even_with_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); d=p/'design.json'; out=p/'saved.json'; out.write_text('valuable existing result')
            self.assertEqual(run('create','--bits','6','--output',d).returncode,0)
            refused=run('analyze',d,'--seconds','0.000000001','--output',out,'--force')
            self.assertEqual(refused.returncode,3,refused.stderr)
            self.assertEqual(out.read_text(),'valuable existing result')
            d.write_text('{"bits":6,"bits":2}')
            invalid=run('analyze',d,'--output',out,'--force')
            self.assertEqual(invalid.returncode,2,invalid.stderr)
            self.assertEqual(out.read_text(),'valuable existing result')
            self.assertEqual(list(p.glob('.ladderproof-*')),[])

    def test_no_clobber_and_invalid_certificate_exit_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); d=p/'d.json'; c=p/'c.json'
            self.assertEqual(run('create','--bits','2','--output',d).returncode,0)
            self.assertEqual(run('analyze',d,'--output',c).returncode,0)
            saved=c.read_bytes()
            self.assertEqual(run('analyze',d,'--output',c).returncode,2)
            self.assertEqual(c.read_bytes(),saved)
            cert=json.loads(c.read_text()); cert['results']['steps'][0]['min']='0'; c.write_text(json.dumps(cert))
            mismatch=run('verify',c)
            self.assertEqual(mismatch.returncode,1,mismatch.stderr)
            self.assertEqual(json.loads(mismatch.stderr)['status'],'invalid-certificate')

    def test_bounded_files_and_deep_json_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.json'
            for raw in [' '*1_048_577, '['*1100+']'*1100, '{"bits":NaN}']:
                p.write_text(raw)
                response=run('analyze',p)
                self.assertEqual(response.returncode,2,response.stderr)
                self.assertNotIn('Traceback',response.stderr)


class PublicationInterruptionTests(unittest.TestCase):
    def test_interrupt_after_atomic_replace_reports_destination_uncertainty(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from unittest.mock import patch
        from ladderproof.cli import main
        real_replace=os.replace
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'design.json'; out.write_text('old user result')
            def replace_then_interrupt(source,destination):
                real_replace(source,destination)
                raise KeyboardInterrupt()
            stderr=StringIO()
            with patch('ladderproof.cli.os.replace',replace_then_interrupt),redirect_stderr(stderr):
                code=main(['create','--bits','2','--output',str(out),'--force'])
            self.assertEqual(code,130)
            self.assertEqual(json.loads(out.read_text())['format'],'ladderproof.design.v1')
            report=json.loads(stderr.getvalue())
            self.assertNotIn('not replaced',report['error'])
            self.assertIn('check',report['error'].lower())
            self.assertEqual(list(Path(tmp).glob('.ladderproof-*')),[])

if __name__=='__main__': unittest.main()
