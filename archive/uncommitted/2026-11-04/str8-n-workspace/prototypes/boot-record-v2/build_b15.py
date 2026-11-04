"""Offline b15: Ctrl-C cancels SEND BIN before the first payload byte only."""
import argparse
import json
import re
import sys
from pathlib import Path
import build_b14 as frozen

HERE, ROOT = frozen.HERE, frozen.ROOT
BASE = frozen.BASE
FT_POLLS, AC_POLLS = frozen.FT_POLLS, frozen.AC_POLLS
HELP = b'L=0200 ^C=cancel idle3s\r\nA/B 0-3 C1USB/2ACIA/3both\r\n'
SPARES = frozen.SPARES


def replace_once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


def b15_source(source):
    assert len(HELP) <= 53
    old_help = frozen.HELP
    try:
        frozen.HELP = HELP
        source = frozen.b14_source(source)
    finally:
        frozen.HELP = old_help
    # Both normal first-byte input and a byte caught by the optional command-LF
    # probe must pass the same check. After one payload byte, RL_LOAD_BYTE is
    # reached directly and every value, including 03, remains literal data.
    source = replace_once(source, '        LDA B14_PENDING_BYTE\n        JMP RL_LOAD_BYTE\n',
                          '        LDA B14_PENDING_BYTE\n        JMP B14_FIRST_GOT\n')
    source = replace_once(source, 'B14_FIRST_GOT:\n        JMP RL_LOAD_BYTE\n',
                          'B14_FIRST_GOT:\n        CMP #3\n        BEQ B15_CANCEL\n        JMP RL_LOAD_BYTE\n')
    cancel = '''B15_CANCEL:
        LDA V2_RX_BAD
        BEQ B15_CANCEL_OK
        JMP B14_RX_BAD
B15_CANCEL_OK:
        STZ DC_BINARY
        JMP BOOT_RECOVERY
'''
    # Four check bytes fit the existing init reservation. The 13-byte cancel
    # path uses an existing 17-byte gap; all shared entry addresses stay fixed.
    gap = 'B14_FREE_FIRST:\n        DB '+','.join(['$FF']*17)+'\n'
    source = replace_once(source, gap, cancel+frozen.pad('B14_FREE_FIRST',4))
    return source


def main():
    source = Path(frozen.__file__).read_text()
    source = source[source.index('\ndef main():')+1:source.rindex('\nif __name__')]
    source = source.replace('0x8000000E','0x8000000F').replace('2.0proto b14','2.0proto b15')
    source = source.replace('b14_source','b15_source').replace('PASS b14 offline','PASS b15 offline')
    namespace = dict(__file__=__file__,HERE=HERE,ROOT=ROOT,BASE=BASE,Path=Path,
                     argparse=argparse,json=json,sys=sys,HELP=HELP,SPARES=SPARES,
                     previous=frozen.previous,b15_source=b15_source,
                     FT_POLLS=FT_POLLS,AC_POLLS=AC_POLLS)
    exec(compile(source,__file__,'exec'),namespace)
    namespace['main']()
    out=Path(sys.argv[sys.argv.index('--out')+1])
    path=out/'prototype-report.json';report=json.loads(path.read_text())
    report['raw_loader'].update(
        first_byte_wait='indefinite; Ctrl-C (03) cancels before the first payload byte',
        first_byte_cancel=True,
        cancellation='03 as first input returns to text recovery without RAM writes; later 03 is literal payload',
        hardware_flashed=False)
    report['new_f_features'].append('Ctrl-C cancellation while SEND BIN waits for its first payload byte')
    report['console']['binary']+='; first input 03 cancels before reception starts'
    report['b15_first_byte_cancel']=dict(implemented=True,hardware_qualified=False,
        pending_command_LF_probe_also_checked=True,receive_errors_take_precedence=True,
        shared_addresses_preserved=True,base_build='BUILD/pr04-b14-raw-r4')
    path.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__': main()
