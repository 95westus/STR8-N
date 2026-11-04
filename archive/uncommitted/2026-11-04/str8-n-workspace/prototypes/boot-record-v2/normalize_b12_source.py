"""Normalize exact idle b11 REC/MON B for backup, without RAM/flash writes."""
import argparse
from pathlib import Path
import capture_b12_preflight as pf

def normalize(link):
    link.send(b'\r');raw=link.until(b'> ',10)
    if raw==b'\r\nREC> ':
        reply=link.command('B',pf.board.MON_PROMPT)
        pf.board.r.require(b'STR8-N 2.0proto b11 B3 65C02' in reply,'Exact validated b11 MON B required')
        raw+=reply
    else:
        pf.board.r.require(raw in (b'\r\nB3> ',b'\r\n\r\nB3> '),'Unknown command boundary; no handoff sent')
    pf.identity(link)
    return raw

def self_test():
    for prefix in (b'\r\nREC> ',b'\r\nB3> ',b'\r\n\r\nB3> ',b'unknown REC> '):
        class Link:
            commands=[]
            def send(self,data):assert data==b'\r'
            def until(self,token,seconds):assert token==b'> ';return prefix
            def command(self,text,prompt=pf.board.MON_PROMPT):
                self.commands.append(text)
                return b'STR8-N 2.0proto b11 B3 65C02'+prompt if text=='B' else prompt
            def dump(self,a,b):return {(0x7d01,0x7d02):b'\x02\x03',(0x7d30,0x7d30):b'\xb0'}[(a,b)]
        peer=Link()
        try:normalize(peer)
        except ValueError:assert prefix.startswith(b'unknown') and not peer.commands
        else:assert not prefix.startswith(b'unknown') and peer.commands==(['B',''] if prefix.endswith(b'REC> ') else [''])
    print('PASS exact REC/MON normalization:4 buffered cases, no hardware',flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--run',type=Path);p.add_argument('--authorization',type=Path)
    args=p.parse_args()
    if args.self_test:self_test();return
    import capture_b12_backup as backup
    backup.auth_check(pf.board.r.read(args.authorization));args.run=args.run.resolve()
    pf.board.r.require(not args.run.exists(),'Fresh normalization run required');args.run.mkdir(parents=True)
    args.marker=pf.MARKER;args.coordination=pf.board.DEFAULT_COORDINATION;args.stage='normalize-b11-source'
    before=args.marker.read_bytes()
    with pf.link_for(args,raw_watch=True) as (link,marker):pf.atomic(args.run/'stream.bin',normalize(link))
    pf.board.r.require(args.marker.read_bytes()==before,'Marker changed externally')
    pf.save(args.run/'normalization.json',dict(passed=True,source='2.0proto b11',RAM_written=False,flash_written=False,physical_reset=False,serial_released=True))

if __name__=='__main__':main()
