"""Physical 2604 F-only acceptance stages; fixed F and other banks stay intact."""
import argparse,json,time
from pathlib import Path
import migrate_v2 as u
from beta4_migration import Link,crc,metadata,default_config
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial.tools.list_ports import comports
from serial_test_coordination import serial_lease
from qualify_v2_rtc_board import load

BUILD=u.ROOT/'BUILD/v2-beta25-b24g34';REC=b'REC> ';MON=b'\r\nB3> '

def capture(root,label,monitor=False):
    out=root/label;out.mkdir(exist_ok=False)
    with serial_lease('2604-recovery-reset'),(out/'serial.jsonl').open('x') as log:
        l=Link(port(),log)
        try:
            print('ARMED: 2604 receive-only physical RESET capture, 15 minutes',flush=True)
            text=l.until(MON if monitor else REC,900);(out/'boot.txt').write_bytes(text)
            assert (b'STR8-N 2.0b25' in text and b'gen 00000022 VALID' in text and b'gen 00000025 VALID' in text) if monitor else b'FIXED F RECOVERY' in text,text
            (out/'report.json').write_text(json.dumps(dict(passed=True,board='2604',physical_reset=True,tx_bytes=0),indent=2)+'\n')
            p=root/'upgrade/install/reset-pending.json'
            if p.exists():
                r=u.read(p);r.update(physical_reset_pending=False,physical_reset_verified=True);p.write_text(json.dumps(r,indent=2)+'\n')
            print('PASS 2604 physical '+('restored beta25 monitor' if monitor else 'F-only recovery prompt'),flush=True)
        finally:l.serial.close()

def port():return next(p.device for p in comports() if p.serial_number==SERIALS['2604'])

def begin(l,slot,prompt):
    text=l.command('U '+slot,b'Y then Enter> ');text+=l.command('Y',b'SEND 4096 BIN\r\n');return text

def transfer(l,data):
    for i in range(0,len(data),64):l.send(data[i:i+64]);time.sleep(.01)

def truncate(root):
    out=root/'refusals-and-truncate';out.mkdir(exist_ok=False)
    with serial_lease('2604-recovery-refusals'),(out/'serial.jsonl').open('x') as log:
        l=Link(port(),log)
        try:
            assert b'JOURNAL INVALID' in l.command('W',REC)
            for slot in ('A','B'):
                text=l.command(slot,REC);assert text.endswith(REC) and b'COMMITTED' not in text
            text=l.command('U A',b'Y then Enter> ')+l.command('N',REC);assert b'REFUSED' in text
            image=(BUILD/'str8n-v2-recovery-slot-a0.bin').read_bytes()
            for mode in ('crc','cookie','wrong-slot'):
                bad=bytearray(image)
                if mode=='crc':bad[500]^=1
                elif mode=='cookie':bad[20]^=1;bad[18:20]=crc(bad[:18]+bad[32:]).to_bytes(2,'little')
                else:bad=bytearray((BUILD/'str8n-v2-recovery-slot-b0.bin').read_bytes())
                begin(l,'A',REC);transfer(l,bad);reply=l.until(REC);assert b'REFUSED' in reply,reply
                (out/(mode+'.txt')).write_bytes(reply)
            begin(l,'A',REC);transfer(l,image[:1024]);time.sleep(.15)
            text=l.read(max(1,l.serial.in_waiting));assert not text,text
            (out/'report.json').write_text(json.dumps(dict(board='2604',refusals_passed=True,truncated_bytes=1024,physical_reset_required=True),indent=2)+'\n')
            print('PASS absent slots, canceled/CRC/cookie/wrong-slot uploads refused; 1024/4096 bytes staged; physical RESET required',flush=True)
        finally:l.serial.close()

def run_slot(root,slot):
    out=root/'slot-test';out.mkdir(exist_ok=False);page=0xA0 if slot=='A' else 0xB0;other='B' if slot=='A' else 'A';opage=page^0x10
    with serial_lease('2604-recovery-slot'),(out/'serial.jsonl').open('x') as log:
        l=Link(port(),log)
        try:
            image=(BUILD/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes();begin(l,slot,REC);transfer(l,image)
            text=l.until(MON);(out/'upload.txt').write_bytes(text);assert b'COMMITTED' in text and b'STR8-N 2.0b25' in text,text
            assert l.dump(0x7D30,0x7D30)==bytes((page,))
            assert b'JOURNAL INVALID' in l.command('W')
            # Verify every byte, including no writes from the rejected/truncated transfers.
            banks=[]
            for bank in range(4):
                p=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',p);b=b''.join(l.dump(a,a+4095,p) for a in range(0x8000,0x10000,4096));banks.append(b)
                expected=(root/f'upgrade/expected-b{bank}.bin').read_bytes()
                if bank==3:
                    expected=bytearray(expected);i=(page-0x80)*256;expected[i:i+4096]=image
                assert b==expected,bank
            l.command('B3');load(l,BUILD/'bootstrap/bootstrap-journal.s19')
            text=l.command('G 2000',b'Y then Enter> ')+l.command('N');assert b'Canceled' in text
            text=l.command('G 2000',b'Y then Enter> ')+l.command('Y');assert b'Journal initialized' in text,text
            assert l.dump(0xC000,0xC07F)==metadata(default_config(),[0]*32,1)
            reply=l.command('W');(out/'initial-wear.txt').write_bytes(reply)
            assert reply.count(b' 000000')==32,reply
            assert b'Journal initialized' in l.command('G 2000',b'Y then Enter> ')+l.command('Y')
            # A newer test-only header exercises the ordinary accounted erase path.
            newer=bytearray((BUILD/f'str8n-v2-recovery-slot-{opage:02x}.bin').read_bytes());newer[8:12]=(38).to_bytes(4,'little');newer[18:20]=crc(newer[:18]+newer[32:]).to_bytes(2,'little')
            begin(l,other,MON);transfer(l,newer);text=l.until(MON);assert b'COMMITTED' in text and l.dump(0x7D30,0x7D30)==bytes((opage,)),text
            w=l.command('W');assert (f'B3:{opage>>4:X} 000001').encode() in w,w;(out/'normal-update-wear.txt').write_bytes(w)
            assert l.dump(opage<<8,(opage<<8)+4095)==newer
            assert l.dump(page<<8,(page<<8)+4095)==image
            assert l.dump(0xF000,0xFFFF)==(BUILD/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
            text=l.command('J3');(out/'journalled-j3.txt').write_bytes(text)
            assert b'STR8-N 2.0b25' in text and l.dump(0x7D30,0x7D30)==bytes((opage,))
            # Full fresh source, twice, for the next blank fixture or restoration.
            prior=root/'post-test';prior.mkdir();entries=[]
            for bank in range(4):
                p=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',p)
                def readbank():return b''.join(l.dump(a,a+4095,p) for a in range(0x8000,0x10000,4096))
                b=readbank();assert b==readbank();(prior/f'b{bank}.bin').write_bytes(b);(prior/f'b{bank}-repeat.bin').write_bytes(b)
                entries.append(dict(bank=bank,sha256=u.sha(b),bytes=len(b),repeat_verified=True))
            l.command('B3');(prior/'manifest.json').write_text(json.dumps(dict(board='2604',repeat_verified=True,banks=entries),indent=2)+'\n')
            report=dict(passed=True,board='2604',f_only_destination=slot,bootstrap_generation=37,test_only_newer_generation=38,
                explicit_journal_sequence=1,initial_counts_zero=True,normal_accounted_erase_sector=opage>>4,
                fixed_f_preserved=True,other_banks_preserved=True,refusal_and_truncated_transfer_left_no_flash_writes=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS 2604 F-only',slot,'boot, actual L/G journal provision, retry, W, and normal accounted update',other,flush=True)
        finally:l.serial.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('capture','truncate','slot'));p.add_argument('--root',required=True,type=Path);p.add_argument('--label',default='physical-reset');p.add_argument('--slot',choices=('A','B'));p.add_argument('--monitor',action='store_true');a=p.parse_args()
    if a.stage=='capture':capture(a.root,a.label,a.monitor)
    elif a.stage=='truncate':truncate(a.root)
    else:run_slot(a.root,a.slot)
