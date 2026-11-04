"""Offline b13 regression adapters; frozen earlier checkers remain unchanged."""
import argparse,sys
from pathlib import Path
import build_b13

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True)
    p.add_argument('--suite',choices=['regression','commands','wait','usb','countdown','installer','bench'],required=True)
    p.add_argument('--cpu',choices=['65c02','65c816-e'])
    args=p.parse_args();suite=args.suite
    names=dict(regression='test_b08.py',commands='test_b12_commands.py',wait='test_b12_wait.py',
               usb='test_b09_usb_wait.py',countdown='test_b08_countdown.py',
               installer='test_b12_deployment_cpu.py',bench='bench_b12.py')
    source=(build_b13.HERE/names[suite]).read_text()
    if suite=='regression':
        source=source.replace('import test_b07 as previous','import test_b12_core as previous')
        source=source.replace('2.0proto b08','2.0proto b13').replace('0x80000008','0x8000000D')
        source=source.replace('Recovery L/R/D/V A/B 0-3 C1/2/3',build_b13.previous.RECOVERY)
        source=source.replace('b08-selection-tests.json','b13-selection-tests.json')
    source=source.replace('0x8000000c','0x8000000d').replace('2.0proto b09','2.0proto b13')
    for old,new in [('b12-command-tests','b13-command-tests'),('b12-wait-tests','b13-wait-tests'),
                    ('b09-usb-wait-','b13-usb-wait-'),('b08-countdown-','b13-countdown-'),
                    ('b12-deployment-cpu-tests','b13-installer-cpu-tests')]:source=source.replace(old,new)
    sys.argv=[__file__,'--build',str(args.build.resolve())]
    if args.cpu:sys.argv+=['--cpu',args.cpu]
    exec(compile(source,str(build_b13.HERE/names[suite]),'exec'),dict(__file__=__file__,__name__='__main__'))

if __name__=='__main__':main()
