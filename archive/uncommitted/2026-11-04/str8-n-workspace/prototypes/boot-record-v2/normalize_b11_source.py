"""2512 b10 REC -> validated MON B, without RAM loading or flash/settings writes."""
import argparse
from pathlib import Path
from types import SimpleNamespace
import capture_b11_preflight as pf


def normalize(link):
    link.send(b'\r')
    raw=link.until(b'REC> ',10)
    pf.board.r.require(raw==b'\r\nREC> ', 'Exact idle REC command boundary required; no bank handoff sent')
    reply=link.command('B',pf.board.MON_PROMPT)
    pf.board.r.require(b'STR8-N 2.0proto b10 B3 65C02' in reply,
                       'Validated resident b10 MON B banner required')
    pf.identity(link)
    return raw+reply


def self_test():
    for valid in (True,False):
        class Link:
            commands=[]
            def send(self,data):assert data==b'\r'
            def until(self,token,seconds):return b'\r\nREC> ' if valid else b'unknown REC> '
            def command(self,text,prompt=pf.board.MON_PROMPT):
                self.commands.append(text)
                if text=='B':return b'STR8-N 2.0proto b10 B3 65C02'+prompt
                assert text=='';return prompt
            def dump(self,first,last):return {(0x7d01,0x7d02):b'\x02\x03',(0x7d30,0x7d30):b'\xb0'}[(first,last)]
        peer=Link()
        try:normalize(peer)
        except ValueError:assert not valid and not peer.commands
        else:assert valid and peer.commands==['B','']
    print('PASS REC normalization exact prompt/unknown refusal; no serial imports',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--self-test',action='store_true')
    p.add_argument('--authorization',type=Path);p.add_argument('--run',type=Path)
    args=p.parse_args()
    if args.self_test:self_test();return
    import capture_b11_backup as backup
    pf.board.r.require(args.authorization and args.run,'Explicit source-backup authorization/run required')
    backup.auth_check(pf.board.r.read(args.authorization))
    args.run=args.run.resolve();pf.board.r.require(not args.run.exists(),'Fresh normalization run required')
    args.run.mkdir(parents=True)
    args.marker=pf.MARKER;args.coordination=pf.board.DEFAULT_COORDINATION;args.stage='normalize-REC-to-MON-B'
    before=args.marker.read_bytes()
    with pf.link_for(args,raw_watch=True) as (link,marker):
        pf.atomic(args.run/'stream.bin',normalize(link))
    pf.board.r.require(args.marker.read_bytes()==before,'Preservation marker changed externally')
    pf.save(args.run/'normalization.json',dict(passed=True,board='2512',source='2.0proto b10',
        commands=['CR','B','CR','D 7D01 7D02','D 7D30 7D30'],flash_written=False,
        application_RAM_loaded=False,physical_reset_requested=False,serial_released=True))
    print('PASS b10 recovery to validated MON B; serial released',flush=True)


if __name__=='__main__':main()
