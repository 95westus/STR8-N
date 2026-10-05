"""Explicit guarded B/E/F startup-order update on owner-authorized board 2205."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/qualification/b2-2205-2026-10-04'
PREVIOUS=BASE/'autoload-install-1791128505967075700'
sys.path.insert(0,str(BASE))
import board_session as bs
import build_v2_b2_autoload_update as updater

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('backup','install'))
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--named',action='store_true',help='Install the qualified named-command B/C/E/F follow-up')
    args=parser.parse_args()
    previous_folder=BASE/'startup-order-install-4013' if args.named else PREVIOUS
    phases=('b','c','e','f') if args.named else ('b','e','f')
    groups,core_bytes=(41,4039) if args.named else (37,4013)
    folder=args.evidence.resolve()
    if args.mode=='backup':folder.mkdir(parents=True,exist_ok=False)
    bs.OUT=folder
    board=bs.Board('startup-order-'+args.mode)
    sent=(folder/(args.mode+'-sent.txt')).open('x',encoding='ascii')
    original_send=board.send
    def send(data):
        sent.write(data.decode('ascii'));sent.flush();original_send(data)
    board.send=send
    try:
        board.cmd('');board.cmd('B3')
        if args.mode=='backup':
            previous=json.loads((previous_folder/('board-startup-order-results.json' if args.named else 'board-autoload-results.json')).read_text())
            assert previous['passed']
            for bank in range(4):
                data=board.save_bank(bank,'before')
                assert sha(data)==previous['after_sha256'][bank]
            board.cmd('B3')
            for name,start,end in [('app-overlay',0x0200,0x60FF),('worker',0x7900,0x7BFF)]:
                (folder/('before-'+name+'.bin')).write_bytes(board.dump(start,end))
            assert b'C 00 03 V 0A' in board.cmd('C')
            assert b'K 00 B3 D0 00 3F 00 00' in board.cmd('K')
            assert b'X ON B3 C70A' in board.cmd('K AUTO ?')
            print('PASS: fresh complete bank and user RAM backups; known installed revision',flush=True)
            return
        before=[(folder/f'before-b{i}.bin').read_bytes() for i in range(4)]
        old_ram=(folder/'before-app-overlay.bin').read_bytes()
        worker=(folder/'before-worker.bin').read_bytes()[:741]
        qualification=json.loads((ROOT/'BUILD/v2-b2/autoload-qualification.json').read_text())
        assert qualification['host_check_groups']==groups and qualification['core_bytes']==core_bytes
        for path,digest in qualification['images'].items():assert sha((ROOT/path).read_bytes())==digest
        tests=json.loads((folder/'autoload-updater-host-tests.json').read_text())
        assert len(tests['passed'])==len(phases)*6 and tests['source_full_b3_sha256']==sha(before[3])
        assert board.dump(0x8000,0xFFFF)==before[3]
        assert board.dump(0x0200,0x60FF)==old_ram
        assert board.dump(0x7900,0x7BE4)==worker
        expected=bytearray(before[3]);max_end=0x2000
        for phase in phases:
            directory=folder/(phase+'-updater')
            meta=json.loads((directory/'manifest.json').read_text())
            artifact=directory/f'str8n-v2-b2-{phase}-update-2000.s19'
            assert sha(artifact.read_bytes())==tests['artifacts'][phase]==meta['s19_sha256']
            assert sha(expected)==meta['source_full_b3_sha256']
            assert board.dump(0x8000,0xFFFF)==expected
            board.load(artifact);max_end=max(max_end,meta['end'])
            board.cmd('G 2000',f'B3:{phase.upper()} exact; TYPE Y to install b2> '.encode())
            board.send(b'Y')
            result=board.until(b'B3> ')
            print(result.decode('ascii'),flush=True)
            assert f'B3:{phase.upper()} b2 VERIFIED; RESET'.encode() in result
            base=int(phase,16)*4096-0x8000
            expected[base:base+4096]=(directory/'staged-sector.bin').read_bytes()
            actual=board.save_bank(3,'after-'+phase)
            assert actual==expected
            meta.update(board_installed=True,board='2205',readback_sha256=sha(actual),log=str(board.log.name))
            (directory/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
        assert expected==(folder/'expected-installed-b3.bin').read_bytes()
        result=board.cmd('G F004')
        (folder/'startup-output.txt').write_bytes(result)
        result=result.replace(b'\r\r\n',b'\r\n')
        dots=result.index(b'.'*160)
        assert result.index(b'K registered')>dots+159
        assert result[dots:].startswith(b'.'*160+b'\r\nK registered')
        for key in 'KRSTXH':assert (key+' registered').encode() in result
        assert result.index(b'H registered')<result.index(b'STR8-N')
        assert b'C 00 03 V 0A' in board.cmd('C')
        assert b'K 00 B3 D0 00 3F 00 00' in board.cmd('K')
        assert b'H ON B3 C00A' in board.cmd('K AUTO ?')
        assert b'Registered: K R S T X H ' in board.cmd('H')
        assert b'HELLO FROM X' in board.cmd('X HELLO')
        if args.named:
            assert b'Named: HELLO ECHO ' in board.cmd('H')
            assert board.dump(0x76B0,0x76B0)==b'\x08'
            assert b'HELLO FROM X' in board.cmd('HELLO')
            assert b'SOME TEXT' in board.cmd('ECHO SOME TEXT')
            assert b'SOME TEXT' in board.cmd('X ECHO SOME TEXT')
            assert b'Bad cmd' in board.cmd('HELLOX')
            assert b'Bad cmd' in board.cmd('ECHOX SOME TEXT')
            assert b'conflict' not in board.cmd('G C700')
            assert board.dump(0x76B0,0x76B0)==b'\x08'
            for bank in range(4):
                board.cmd('B'+str(bank))
                assert b'HELLO FROM X' in board.cmd('HELLO')
                assert b'TEXT' in board.cmd('ECHO TEXT')
            board.cmd('B3')
        assert b'BETA2' in board.cmd('T')
        original=old_ram[0x2000-0x0200:max_end-0x0200]
        lines=[bs.record('0',0,b'Restore user RAM after startup order update')]
        lines += [bs.record('1',a,original[a-0x2000:a-0x2000+32]) for a in range(0x2000,max_end,32)]
        lines.append(bs.record('9',0x2000))
        restore=folder/'restore-app-2000.s19'
        restore.write_text('\n'.join(lines)+'\n',encoding='ascii');board.load(restore)
        assert board.dump(0x0200,0x60FF)==old_ram
        assert board.dump(0x7900,0x7BE4)==worker
        after=[board.save_bank(i,'after') for i in range(4)];board.cmd('B3')
        assert after[:3]==before[:3] and after[3]==expected
        assert after[3][:0x3000]==before[3][:0x3000]
        assert after[3][0x5000:0x6000]==before[3][0x5000:0x6000]
        if not args.named:assert after[3][0x4000:0x5000]==before[3][0x4000:0x5000]
        assert after[3][0x7FD0:0x7FE0]==before[3][0x7FD0:0x7FE0]
        report=dict(passed=True,board='2205',port='COM3',serial='A10MPUPNA',
            modified_sectors=['B3:'+p.upper() for p in phases],before_sha256=[sha(b) for b in before],
            after_sha256=[sha(b) for b in after],startup_dots_first=True,
            registration_before_banner=True,autoload=['R','S','T','X','H'],
            C='C 00 03 V 0A',K='K 00 B3 D0 00 3F 00 00',
            config_and_boot_pocket_preserved=True,B0_B1_B2_unchanged=True,
            application_overlay_ram_restored=True,public_worker_unchanged=True,
            named_commands_passed=args.named,
            host_groups=groups,updater_host_cases=len(phases)*6,physical_reset_power_cycle_tested=False,
            log=str(board.log.name),sent_text=str(folder/'install-sent.txt'))
        (folder/('board-named-results.json' if args.named else 'board-startup-order-results.json')).write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: startup dots first, registrations next, banner last; user RAM and settings preserved',flush=True)
    finally:sent.close();board.close()

if __name__=='__main__':main()
