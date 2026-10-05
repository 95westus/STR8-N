"""Explicit owner-authorized autoload installation, exact COM3/2205 only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'output/qualification/b2-2205-2026-10-04'))
import board_session as bs
from v2_b2_config import checksum, decode_header, decode_locator

SHA=lambda data:hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--resume-confirmation',action='store_true',
                        help='Finish the pending K AUTO +X line after verified B/C/E/F installation')
    args=parser.parse_args()
    folder=args.evidence.resolve()
    bs.OUT=folder
    before=[(folder/f'before-b{i}.bin').read_bytes() for i in range(4)]
    old_ram=(folder/'before-app-overlay.bin').read_bytes()
    before_worker=(folder/'before-worker.bin').read_bytes()[:741]
    tests=json.loads((folder/'autoload-updater-host-tests.json').read_text())
    assert len(tests['passed'])==24 and tests['source_full_b3_sha256']==SHA(before[3])
    probe_tests=json.loads((folder/'autoload-service-probe-tests.json').read_text())
    probe=Path(probe_tests['probe'])
    assert probe_tests['passed'] and probe_tests['probe_sha256']==SHA(probe.read_bytes())
    assert probe_tests['candidate_sha256']==SHA((folder/'expected-installed-b3.bin').read_bytes())
    expected=bytearray(before[3])
    board=bs.Board('install')
    sent=(folder/('resume-sent.txt' if args.resume_confirmation else 'sent.txt')).open('x',encoding='ascii')
    original_send=board.send
    def send(data):
        sent.write(data.decode('ascii'));sent.flush();original_send(data)
    board.send=send
    def confirm(command):
        result=board.cmd(command,b' Y?')
        board.send(b'Y\r')
        result+=board.until(b'B3> ')
        print(result.decode('ascii'),flush=True)
        assert b'Done; reset to apply' in result and b'flash fail' not in result
        return result
    try:
        if args.resume_confirmation:
            # V2_CONFIRM reads a complete line; the installer previously sent
            # only Y, leaving the board waiting for Enter before any mutation.
            board.send(b'\r')
            pending=board.until(b'B3> ')
            print(pending.decode('ascii'),flush=True)
            assert b'Done; reset to apply' in pending
            expected[:]=(folder/'expected-installed-b3.bin').read_bytes()
        board.cmd('');board.cmd('B3')
        current=board.dump(0x8000,0xFFFF)
        if args.resume_confirmation:
            assert current[:0x5000]==expected[:0x5000]
            assert current[0x6000:]==expected[0x6000:]
            assert current[0x5050:0x6000]==expected[0x5050:0x6000]
        else:
            assert current==before[3]
            assert board.dump(0x0200,0x60FF)==old_ram
        assert board.dump(0x7900,0x7BE4)==before_worker
        max_end=0x2000
        for phase in ('b','c','e','f'):
            directory=folder/(phase+'-updater')
            artifact=directory/f'str8n-v2-b2-{phase}-update-2000.s19'
            meta=json.loads((directory/'manifest.json').read_text())
            assert SHA(artifact.read_bytes())==tests['artifacts'][phase]==meta['s19_sha256']
            max_end=max(max_end,meta['end'])
            if args.resume_confirmation:
                assert meta['board_installed']
                base=int(phase,16)*4096-0x8000
                assert current[base:base+4096]==(directory/'staged-sector.bin').read_bytes()
                continue
            assert SHA(expected)==meta['source_full_b3_sha256']
            assert board.dump(0x8000,0xFFFF)==expected
            board.load(artifact)
            board.cmd('G 2000',f'B3:{phase.upper()} exact; TYPE Y to install b2> '.encode())
            board.send(b'Y')
            result=board.until(b'B3> ')
            print(result.decode('ascii'),flush=True)
            assert f'B3:{phase.upper()} b2 VERIFIED; RESET'.encode() in result,result
            base=int(phase,16)*4096-0x8000
            expected[base:base+4096]=(directory/'staged-sector.bin').read_bytes()
            actual=board.save_bank(3,'after-'+phase)
            assert actual==expected
            meta.update(board_installed=True,board='2205',port='COM3',
                        readback_sha256=SHA(actual),log=str(board.log.name))
            (directory/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
            print('PASS physical guarded '+phase.upper()+' sector and complete B3 readback',flush=True)
        assert expected==(folder/'expected-installed-b3.bin').read_bytes()
        assert board.dump(0xFFD0,0xFFDF)==before[3][0x7FD0:0x7FE0]
        assert b'C 00 03 V 0A' in board.cmd('C')
        assert b'K 00 B3 D0 00 3F 00 00' in board.cmd('K')
        if not args.resume_confirmation:
            assert b'AUTO legacy' in board.cmd('K AUTO ?')
            confirm('K AUTO +X')
        confirm('K AUTO +H')
        first_config=board.dump(0xD000,0xDFFF)
        assert decode_header(first_config[:16],3,13)==bytes((0,0x3F,0,0))
        assert first_config[10]==0xA1 and first_config[16:20]==b'AL\x01\x3F'
        assert checksum(first_config[16:78])==first_config[78:80]
        assert first_config[80:]==before[3][0x5050:0x6000]
        result=board.cmd('G F004')
        for key in 'KRSTXH':assert (key+' registered').encode() in result
        assert b'C 00 03 V 0A' in board.cmd('C')
        assert b'Registered: K R S T X H ' in board.cmd('H')
        assert b'HELLO FROM X' in board.cmd('X HELLO')
        assert b'AUTO QUIET 00' in board.cmd('K AUTO ?')
        # Prove a disabled provider is not registered, then restore X selection.
        confirm('K AUTO -X')
        result=board.cmd('G F004')
        assert b'X registered' not in result and b'H registered' in result
        assert b'Bad cmd' in board.cmd('X')
        assert b'Registered: K R S T H ' in board.cmd('H')
        confirm('K AUTO +X')
        result=board.cmd('G F004')
        assert b'X registered' in result and b'H registered' in result
        assert board.dump(0xD000,0xDFFF)==first_config
        board.load(probe)
        result=board.cmd('G 2000')
        assert b'SERVICE REGISTER / CALLABLE / DATA / VERSION / DUPLICATE PASS' in result
        assert board.dump(0x7DEB,0x7DEB)==b'\x0C'
        result=board.cmd('G F004')
        assert b'X registered' in result and b'H registered' in result
        assert board.dump(0x7DEB,0x7DEB)==b'\0'
        assert b'TEMP PROVIDER RAM RESTORED' in board.cmd(f"G {probe_tests['restore']:04X}")
        assert board.dump(0x7700,0x7808)==(folder/'before-module-ram.bin').read_bytes()[0x600:0x709]
        # No installation program is left in the user's workspace.
        original=old_ram[0x2000-0x200:max_end-0x200]
        lines=[bs.record('0',0,b'Restore user RAM after autoload installation')]
        lines += [bs.record('1',a,original[a-0x2000:a-0x2000+32])
                  for a in range(0x2000,max_end,32)]
        lines.append(bs.record('9',0x2000))
        restore=folder/'restore-app-2000.s19'
        restore.write_text('\n'.join(lines)+'\n',encoding='ascii')
        board.load(restore)
        assert b'BETA2' in board.cmd('T')
        assert b'RTS error 02' in board.cmd('S 1000 100F BETA2')
        assert b'Done' in board.cmd('R BETA2')
        assert board.dump(0x1000,0x100F)==bytes(range(16))
        bs.write_ram(board,0x1000,old_ram[0x1000-0x200:0x1010-0x200])
        for bank in range(4):
            board.cmd('B'+str(bank))
            assert b'HELLO FROM X' in board.cmd('X HELLO')
            assert b'Registered: K R S T X H ' in board.cmd('H',quiet=True)
        board.cmd('B3')
        assert board.dump(0x0200,0x60FF)==old_ram
        assert board.dump(0x7DEB,0x7DEB)==b'\0'
        assert board.dump(0x7900,0x7BE4)==before_worker
        assert board.dump(0xFFD0,0xFFDF)==before[3][0x7FD0:0x7FE0]
        after=[board.save_bank(i,'after') for i in range(4)]
        board.cmd('B3')
        assert after[:3]==before[:3]
        expected[0x5000:0x6000]=first_config
        assert after[3]==expected
        report=dict(passed=True,board='2205',port='COM3',serial='A10MPUPNA',
            modified_sectors=['B3:B','B3:C','B3:D','B3:E','B3:F'],
            before_sha256=[SHA(b) for b in before],after_sha256=[SHA(b) for b in after],
            B0_B1_B2_unchanged=True,B2_F_original_backup_preserved=True,
            boot_pocket_preserved=True,storage_masks_preserved=True,
            autoload=['R','S','T','X','H'],startup_messages=True,
            C='C 00 03 V 0A',K='K 00 B3 D0 00 3F 00 00',
            software_reset_independent_autoload_passed=True,
            disabled_X_absent_after_reset_passed=True,all_selected_banks_passed=True,
            RTS_list_duplicate_restore_passed=True,application_overlay_ram_restored=True,
            dynamic_service_probe_passed=True,service_reset_and_scratch_restore_passed=True,
            public_worker_unchanged=True,physical_reset_power_cycle_tested=False,
            updater_host_cases=24,source_host_check_groups=37,log=str(board.log.name),
            sent_text=str(folder/'sent.txt'),
            resumed_confirmation=args.resume_confirmation,
            resume_sent_text=str(folder/'resume-sent.txt') if args.resume_confirmation else None)
        (folder/'board-autoload-results.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: autoload installed, C0 retained, H/X reset and deselection verified, RAM restored',flush=True)
    finally:sent.close();board.close()


if __name__=='__main__':main()
