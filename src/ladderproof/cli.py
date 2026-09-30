"""Explicit CLI outcomes and atomic export only after complete computation."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from . import __version__, analyze, compare, make_design, verify
from .budget import Budget
from .design import MAX_INPUT_BYTES
from .errors import Invalid, Refused, VerificationError


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise Invalid(f'duplicate JSON key: {key}')
        result[key]=value
    return result


def _constant(value):
    raise Invalid(f'non-finite JSON constant is unsupported: {value}')


def load_json(path):
    try:
        with open(path,'rb') as stream:
            content=stream.read(MAX_INPUT_BYTES+1)
        if len(content)>MAX_INPUT_BYTES: raise Invalid('input exceeds 1 MiB')
        return json.loads(content.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_constant)
    except (UnicodeError,json.JSONDecodeError,RecursionError,ValueError) as exc:
        if isinstance(exc,Invalid): raise
        raise Invalid(f'invalid UTF-8 JSON input: {exc}') from exc


def write_json(value,path=None,force=False):
    data=json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    if path is None:
        sys.stdout.write(data); return
    destination=Path(path)
    if not force and destination.exists(): raise Invalid('output exists; choose another path or use --force')
    fd,temporary=tempfile.mkstemp(prefix='.ladderproof-',dir=destination.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if force: os.replace(temporary,destination)
        else:
            # Atomic non-clobber publication. A concurrent new destination wins.
            os.link(temporary,destination)
    finally:
        try: os.unlink(temporary)
        except FileNotFoundError: pass


def parser():
    p=argparse.ArgumentParser(prog='ladderproof',description='Exact static ideal R-2R tolerance inspection; no physical-device guarantee.')
    p.add_argument('--version',action='version',version=f'LadderProof {__version__}')
    sub=p.add_subparsers(dest='command',required=True)
    create=sub.add_parser('create',help='create an editable design JSON')
    create.add_argument('--bits',type=int,default=6)
    create.add_argument('--tolerance',default='1/100',help='independent fractional resistance interval, e.g. 1/100')
    create.add_argument('--vref',default='1',help='positive exact reference voltage string')
    analysis=sub.add_parser('analyze',help='enumerate every admitted corner and export a complete certificate')
    analysis.add_argument('design',type=Path)
    verification=sub.add_parser('verify',help='independently recompute every bound and validate the complete certificate')
    verification.add_argument('certificate',type=Path)
    comparison=sub.add_parser('compare',help='independently verify two certificates and compare minimum steps')
    comparison.add_argument('before',type=Path); comparison.add_argument('after',type=Path)
    for command in (analysis,verification,comparison):
        command.add_argument('--seconds',type=float,default=60 if command is comparison else 30,help='complete-operation deadline, greater than zero and at most 120')
    for command in (create,analysis,verification,comparison):
        command.add_argument('--output',type=Path); command.add_argument('--force',action='store_true',help='atomically replace the output only after success')
    serve=sub.add_parser('serve',help='open the local browser application')
    serve.add_argument('--port',type=int,default=8766)
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=='serve':
            if not 1024<=args.port<=65535: raise Invalid('port must be from 1024 through 65535')
            from .app import serve
            serve(host='127.0.0.1',port=args.port)
            return 0
        if args.command=='create': result=make_design(args.bits,args.tolerance,args.vref)
        else:
            budget=Budget(seconds=args.seconds)
            if args.command=='analyze': result=analyze(load_json(args.design),budget=budget)
            elif args.command=='verify': result=verify(load_json(args.certificate),budget=budget)
            else: result=compare(load_json(args.before),load_json(args.after),budget=budget)
        write_json(result,args.output,args.force)
        return 0
    except VerificationError as exc: status,code,message='invalid-certificate',1,str(exc)
    except Refused as exc: status,code,message='refused',3,str(exc)
    except (Invalid,OSError) as exc: status,code,message='invalid-input',2,str(exc)
    except KeyboardInterrupt:
        sys.stderr.write(json.dumps({'status':'cancelled','error':'interrupted; check the output destination because atomic publication may already have completed'})+'\n')
        return 130
    sys.stderr.write(json.dumps({'status':status,'error':message})+'\n')
    return code
