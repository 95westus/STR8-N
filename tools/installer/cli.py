"""Shared installer command line. Offline operations never import serial."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path

from . import capture, package, plan, workflow
from .common import REGISTRY, board_profile
from .engine import runtime as r


@contextmanager
def live_link(args, marker, auth):
    # Called only by explicit preflight/execute/recover commands, after all
    # applicable offline/owner checks. Tests never invoke this adapter.
    from . import serial_lease
    from .engine.legacy_transport import Link
    from serial.tools.list_ports import comports
    serial_lease.ROOT=args.coordination.resolve()
    with serial_lease.serial_lease('current-installer-'+args.board,timeout=30):
        current=r.read(args.marker)
        r.require(current==marker, 'Operation marker changed while acquiring lease')
        workflow.marker_identity(current,args.board)
        if args.operation!='recover':workflow.idle(current)
        profile=board_profile(args.board)
        ports=[p.device for p in comports() if p.serial_number==profile['usb_serial']]
        r.require(len(ports)==1, 'USB identity not uniquely present')
        logs=args.run.parent/(args.run.name+'-serial')
        logs.mkdir(parents=True,exist_ok=True);(logs/'.gitignore').write_text('*\n')
        with (logs/(args.operation+'.jsonl')).open('x',encoding='utf-8') as log:
            link=Link(ports[0],log)
            try:yield link
            finally:link.serial.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='operation',required=True)
    commands.add_parser('profiles')
    create=commands.add_parser('package')
    create.add_argument('--candidate',required=True,choices=[*REGISTRY['candidates'],REGISTRY['cleanup']['candidate']])
    create.add_argument('--image',action='append',required=True,metavar='CANDIDATE=FILE')
    create.add_argument('--out',type=Path,required=True);create.add_argument('--board',choices=REGISTRY['boards'])
    create.add_argument('--cleanup-capture',type=Path)
    for operation in ('plan','verify','restore','qualify','preflight','execute','recover'):
        sub=commands.add_parser(operation);sub.add_argument('--kit',type=Path,required=True)
        if operation in ('plan','restore'):
            sub.add_argument('--capture',type=Path,required=True);sub.add_argument('--out',type=Path,required=True)
        if operation=='restore':sub.add_argument('--original-plan',type=Path,required=True)
        if operation in ('verify','qualify','execute','recover'):sub.add_argument('--plan',type=Path,required=True)
        if operation=='qualify':
            sub.add_argument('--out',type=Path,required=True)
            sub.add_argument('--deps-02',type=Path,required=True);sub.add_argument('--deps-816',type=Path,required=True)
        if operation in ('preflight','execute','recover'):
            sub.add_argument('--board',choices=REGISTRY['boards'],required=True)
            sub.add_argument('--run',type=Path,required=True);sub.add_argument('--marker',type=Path,required=True)
            sub.add_argument('--authorization',type=Path,required=True)
            sub.add_argument('--coordination',type=Path,required=True,help='Existing shared serial-coordination directory used by all board workers')
        if operation=='execute':sub.add_argument('--proof',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.operation=='profiles':result=REGISTRY
        elif args.operation=='package':
            images={}
            for value in args.image:
                key,sep,path=value.partition('=');r.require(sep and key not in images, 'Unique CANDIDATE=FILE images required');images[key]=Path(path)
            result=package.create(args.out,args.candidate,images,board=args.board,cleanup_capture=args.cleanup_capture)
        elif args.operation=='plan':result=plan.prepare(args.kit,args.capture,args.out)
        elif args.operation=='verify':result=plan.verify(args.kit,args.plan)
        elif args.operation=='restore':result=plan.restore(args.kit,args.original_plan,args.capture,args.out)
        elif args.operation=='qualify':
            from .model import qualify
            result=qualify(args.kit,args.plan,args.out,deps02=args.deps_02,deps816=args.deps_816)
        else:
            manifest=package.validate(args.kit);marker=r.read(args.marker);auth=r.read(args.authorization)
            r.require(manifest['board'] is None or manifest['board']==args.board, 'Candidate board differs')
            workflow.marker_identity(marker,args.board)
            action='capture' if args.operation=='preflight' else args.operation
            workflow.authorization(auth,args.board,action,root=args.kit,folder=None if args.operation=='preflight' else args.plan)
            if args.operation!='recover':workflow.idle(marker)
            if args.operation=='preflight':r.require(not args.run.exists(), 'Fresh run directory required')
            if args.operation=='execute':
                info=plan.verify(args.kit,args.plan);r.require(info['board']==args.board, 'Plan board differs')
                escrow,_=capture.validate(args.plan/'capture',args.board)
                r.require(not escrow.get('synthetic_model_fixture',False), 'Synthetic capture cannot access a live board')
                receipt=r.read(args.proof);workflow.proof(args.kit,args.plan,receipt)
                r.require(not (args.run/'flash-report.json').exists(), 'Fresh execution receipt required')
            if args.operation=='recover':
                plan.verify(args.kit,args.plan)
                escrow,_=capture.validate(args.plan/'capture',args.board)
                r.require(not escrow.get('synthetic_model_fixture',False), 'Synthetic capture cannot access a live board')
                workflow.recovery_ready(marker,args.board,args.plan,args.run)
                r.require(not (args.run/'RAM-recovery.json').exists(), 'Fresh recovery receipt required')
            with live_link(args,marker,auth) as link:
                if args.operation=='preflight':result=workflow.preflight(args.kit,link,args.board,args.run,marker,auth)
                elif args.operation=='execute':result=workflow.execute(args.kit,args.plan,args.run,link,args.board,marker,auth,receipt,marker_path=args.marker)
                else:result=workflow.recover_ram(args.kit,args.plan,args.run,link,args.board,marker,auth,marker_path=args.marker)
        print(json.dumps(result,indent=2))
    except (ValueError,KeyError,OSError) as error:
        raise SystemExit('REFUSED: '+str(error))
