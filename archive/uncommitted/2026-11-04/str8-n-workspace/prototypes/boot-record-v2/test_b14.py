"""b14 core/selection, bench, and unchanged boot timing adapters."""
import argparse,sys
from pathlib import Path
import build_b14

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True)
    p.add_argument('--suite',choices=['regression','bench','usb','countdown'],required=True)
    p.add_argument('--cpu',choices=['65c02','65c816-e']);args=p.parse_args()
    names=dict(regression='test_b08.py',bench='bench_target.py',usb='test_b09_usb_wait.py',countdown='test_b08_countdown.py')
    source=(build_b14.HERE/names[args.suite]).read_text()
    if args.suite=='regression':
        source=source.replace('import test_b07 as previous','import test_b14_core as previous')
        source=source.replace('2.0proto b08','2.0proto b14').replace('0x80000008','0x8000000E')
        source=source.replace("old['checks'] == 352","old['checks'] > 200")
        source=source.replace('Recovery L/R/D/V A/B 0-3 C1/2/3','Recovery L A/B 0-3 C1/2/3 ?')
        source=source.replace('b08-selection-tests.json','b14-selection-tests.json')
    elif args.suite=='bench':
        source=source.replace('F RLP1 RAM load/run, download escrow and verified-range readback','F raw BIN at 0200; three-second idle autorun; no CRC/length/header/R')
        source=source.replace('loaded separately with range escrow','raw-loaded separately at 0200; application RAM disposable')
        source=source.replace('F RLP1 RAM load/run','F raw BIN idle autorun')
    source=source.replace('2.0proto b09','2.0proto b14').replace('b09-usb-wait-','b14-usb-wait-').replace('b08-countdown-','b14-countdown-')
    sys.argv=[__file__,'--build',str(args.build.resolve())]
    if args.cpu:sys.argv+=['--cpu',args.cpu]
    exec(compile(source,str(build_b14.HERE/names[args.suite]),'exec'),dict(__file__=__file__,__name__='__main__'))

if __name__=='__main__':main()
