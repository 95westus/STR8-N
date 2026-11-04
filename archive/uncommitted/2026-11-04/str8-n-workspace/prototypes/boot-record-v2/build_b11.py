"""b11 recovery help and precise absent-image diagnostics; no new RAM use."""
import argparse
import json
import re
import sys
from pathlib import Path
import build_b10 as previous

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
HELP=b'L=RLP1 R=run D=RAM+CRC V=load+CRC\r\nA/B=MON 0-3=bank C1=USB/2=ACIA/3=both\r\n'
INVERSE=dict(BEQ='BNE',BNE='BEQ',BCS='BCC',BCC='BCS',BMI='BPL',BPL='BMI',BVS='BVC',BVC='BVS')

def b11_source(source):
    source=previous.b10_source(source)
    old=json.loads((ROOT/'BUILD/pr04-b10-wait/symbols.json').read_bytes())['core/str8n-v2-boot']
    def compact(first,last,addition):
        nonlocal source
        start,stop=source.index(first+':'),source.index(last+':')
        text=source[start:stop];count=0
        def short(m):
            nonlocal count
            op,label,dest=m.groups()
            if label!='P_LONG_40' and -127<=old[dest]-(old[label]-3)<=127:
                count+=1
                return '        '+INVERSE[op]+' '+dest+'\n'
            return m[0]
        text=re.sub(r'        (BEQ|BNE|BCS|BCC|BMI|BPL|BVS|BVC) (P_LONG_\d+)\n        JMP (\w+)\n\2:\n',short,text)
        # New instructions/data consume only reclaimed branch-trampoline bytes.
        extra,bytes_added=addition
        padding=count*3-bytes_added
        assert padding>=0,(first,padding)
        pad=('        DB '+','.join(['$EA']*padding)+'\n') if padding else ''
        source=source[:start]+text+extra+pad+source[stop:]
    # This read-only scanner retains all validations. Only branch encodings shrink.
    help_code='''B11_HELP:
        LDX #<B11_HELP_TEXT
        LDY #>B11_HELP_TEXT
        JSR BOOT_PRINT
        LDX #<B11_HELP_TAIL
        LDY #>B11_HELP_TAIL
        JMP BR_MESSAGE
B11_HELP_TEXT: DB '''+','.join(str(x) for x in HELP[:30]+b'\0')+'\n'
    help_tail='B11_HELP_TAIL: DB '+','.join(str(x) for x in HELP[30:]+b'\0')+'\n'
    compact('BOOT_READ_RECORD','BOOT_CHECK_FIELDS',(help_code,14+31))
    compact('BOOT_CHECK_FIELDS','BOOT_META_READ',(help_tail,len(HELP)-30+1))
    diagnostic='''B11_NO_IMAGE:
        LDX #<B11_NO_IMAGE_TEXT
        LDY #>B11_NO_IMAGE_TEXT
        JMP BR_MESSAGE
B11_NO_IMAGE_TEXT: DB "REFUSED: no valid RAM image",13,10,0
'''
    # Compact the menu/loader first, then account for the seven-byte '?' dispatch.
    compact('BOOT_MENU','RL_GET',(diagnostic,7+len(b'REFUSED: no valid RAM image\r\n\0')+7))
    marker="        CMP #'L'"
    assert marker in source
    source=source.replace(marker,"        CMP #'?'\n        BNE B11_NOT_HELP\n        JMP B11_HELP\nB11_NOT_HELP:\n        CMP #'L'",1)
    for label,end in [('RL_RUN','RL_LOAD'),('RL_VERIFY','RL_OUTPUT')]:
        a,b=source.index(label+':'),source.index(end+':')
        part=source[a:b];assert part.count('BR_ERROR')==1
        source=source[:a]+part.replace('BR_ERROR','B11_NO_IMAGE')+source[b:]
    return source

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--base',type=Path,default=ROOT/'BUILD/rc1-r10p2-g0034')
    args=p.parse_args();original=HERE/'build.py';source=original.read_text()
    for before,after in (
        ('generation=0x80000006 if args.startup_drain','generation=0x8000000B if args.startup_drain'),
        ("banner=b'2.0proto b06' if args.startup_drain","banner=b'2.0proto b11' if args.startup_drain"),
        ("    if args.startup_drain:source+=(HERE/'boot-startup.inc').read_text()+'\\n'","    if args.startup_drain:source=b11_source(source+(HERE/'boot-startup.inc').read_text()+'\\n')"),
        ("drain_message='Consuming input'","drain_message='WAIT...'"),
        ("display='3 2 1 0'","display='Boot : 6 5 4 3 2 1 0'"),
        ('countdown_seconds=3','countdown_seconds=6'),('seconds_at_8MHz=3','seconds_at_8MHz=6'),
        ('USB_wait_seconds=3','USB_wait_seconds=2'),
        ('Fixed three seconds; saved target honored','Fixed six seconds; saved target honored'),
    ):
        assert before in source,before
        source=source.replace(before,after)
    namespace=dict(__file__=str(original),__name__='b11_base',b11_source=b11_source)
    exec(compile(source,str(original),'exec'),namespace)
    sys.argv=[str(original),'--base',str(args.base.resolve()),'--out',str(args.out.resolve()),'--bench-core','--startup-drain']
    namespace['main']()
    out=args.out.resolve();path=out/'prototype-report.json';report=json.loads(path.read_bytes())
    report['startup_sequence'].update(drain_message_bytes_hex=b'\r\nWAIT...\r\n'.hex(),choice_labels='S=Recovery  A/B=Monitor  0-3=Bank',countdown_prefix='Boot : ')
    report['b11_recovery_patch']=dict(help=HELP.decode(),no_image_message='REFUSED: no valid RAM image',
        dump_range='$2000-$5FFF',dump_format='16384 raw bytes followed by CRC16 low byte, high byte',
        compacted_regions=['BOOT_MENU..RL_GET','BOOT_READ_RECORD..BOOT_META_READ'],
        previous_build='BUILD/pr04-b10-wait',public_ABI_unchanged=True)
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS b11 build',report['f'],report['monitors'],flush=True)

if __name__=='__main__':main()
