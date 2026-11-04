"""Read-only evidence audit, then finalize the 2512 MON-absent marker/docs."""
import argparse,binascii,json,hashlib
from pathlib import Path
import board_mon_absent_2512 as h
sha=lambda data:hashlib.sha256(data).hexdigest()

def newest(bank):
    rows=[]
    for offset in range(0x4000,0x6000,256):
        row=bank[offset:offset+256]
        if row[:6]==b'SNBT\x01\x20' and row[255]==0 and binascii.crc_hqx(row[:30],65535)==int.from_bytes(row[30:32],'little') and binascii.crc_hqx(row[:252],65535)==int.from_bytes(row[252:254],'little'):rows.append(row)
    assert rows,'No valid journal';return max(rows,key=lambda x:int.from_bytes(x[8:12],'little'))

def main(run):
    run=run.resolve();r=h.r;report=r.read(run/'test-results.json');state=r.read(run/'state.json')
    assert report['passed'] and state['passed'] and state['serial_released'] and not state['application_RAM_restore_pending']
    assert state['RAM_restored'] and state['ZP_preserved'] and state['restore_kit_F_raw_load_verified'] and state['F_unchanged']
    assert r.read(h.b.DEFAULT_COORDINATION/'owner.json')['kind']=='idle'
    expected=[(h.BUILD/f'mon-absent-expected-b{n}.bin').read_bytes() for n in range(4)]
    source=h.pf.expected_banks()
    for phase in ('post-erase-full-flash','after-rescue-probe-full-flash'):
        for repeat in (1,2):
            assert [(run/f'{phase}-r{repeat}-b{n}.bin').read_bytes() for n in range(4)]==expected
    assert expected[3][0x2000:0x4000]==b'\xff'*8192
    assert expected[:3]==source[:3] and expected[3][-8192:]==source[3][-8192:] and expected[3][:8192]==source[3][:8192]
    a,b=newest(source[3]),newest(expected[3]);counts=[]
    for n in range(32):
        old=int.from_bytes(a[64+3*n:67+3*n],'little');new=int.from_bytes(b[64+3*n:67+3*n],'little')
        assert new==old+(n in (26,27));counts.append(dict(bank=n//8,sector=hex(8+n%8),before=old,after=new))
    assert int.from_bytes(b[8:12],'little')==int.from_bytes(a[8:12],'little')+2
    assert a[7:8]+a[12:30]+a[32:64]+a[160:252]==b[7:8]+b[12:30]+b[32:64]+b[160:252]
    for n in ('2604','2609'):assert (h.AUTH/(n+'-marker-before.json')).read_bytes()==(h.pf.MARKER.parent/(n+'.json')).read_bytes()
    tx=[]
    for p in run.glob('serial-*.jsonl'):
        tx.extend(bytes.fromhex(row['hex']) for row in map(json.loads,p.read_text().splitlines()) if row['direction']=='TX')
    assert tx.count(b'X')==1 and b'T' not in tx,'Unexpected erase or restore command'
    h.pf.atomic(run/'F-only-b1-b3.bin',b''.join(expected[1:]))
    report.update(audited=True,failures=0,journal_sequence_increment=2,wear_counter_changes=[x for x in counts if x['before']!=x['after']],
        config_and_history_preserved=True,full_flash_comparisons=4,source_backup=str(h.BACKUP/'capture'),
        restore_kit=str(h.BUILD/'payload/mon-kit.bin'),restore_instructions=str(h.BUILD/'RESTORE-INSTRUCTIONS.txt'),
        host_checks=r.read(h.HERE/'mon-absent-host-tests.json')['checks'],backup_checks=11,normalizer_checks=4,
        source_F_sha256=sha(source[3][-4096:]),final_F_sha256=sha(expected[3][-4096:]),
        final_physical_boot_tested=False,software_reset_vector_boot_tested=True,normal_MON_J3_unavailable_after_erasure=True)
    h.pf.save(run/'test-results.json',report)
    marker=r.read(h.pf.MARKER);assert marker['mon_absent_run']==str(run) and marker['MON_A_present'] is False and marker['MON_B_present'] is False
    marker.update(recorded_utc=state['completed_utc'],firmware_build='pr04-b14-F-only-MON-absent',
        physical_reset_boot_banner_captured=False,software_full_countdown_boot_verified=True,
        physical_boot_status='Not repeated after MON removal; software reset-vector boot captured',
        last_software_timeout_boot_report=str(run/'state.json'),last_recovery_report=str(run/'state.json'),
        last_recovery_scope='MON A/B erased; software F timeout boot; F raw restore-kit launch only; owner RAM/ZP restored; BOTH REC',
        completion_receipt=dict(path=str(run/'state.json'),sha256=sha((run/'state.json').read_bytes())))
    h.pf.save(h.pf.MARKER,marker)
    path=h.HERE/'README.md';body=path.read_bytes().decode('cp1252')
    heading='## Current 2512 MON-absent bench state (October 24)\n'
    if heading not in body:
        note=heading+'\nThe owner subsequently requested removal of both MON slots on 2512. B3:A/B\nare now erased (8192 bytes). F remains exact b14. Software reset-vector timeout\nboot reaches REC, selecting absent A/B stays in recovery, and F raw-loads the\nqualified MON restore kit with both slots absent. The restore T command was not\nsent on hardware. Four full-flash comparisons match the CPU-predicted postimage;\nonly the two MON erase counters increased, with settings/history preserved.\nOriginal full application RAM and owner ZP were restored and verified. The board\nwas left at BOTH REC; 2604/2609 were not opened or changed. A physical reset was\nnot requested or tested after this removal; normal MON J3 is now unavailable.\n\nEvidence: output/qualification/mon-absent-2512-remove/test-results.json.\nBackup: output/qualification/mon-absent-2512-backup-r2/capture.\nRestore kit/instructions: BUILD/pr04-b14-mon-absent-r5/payload/mon-kit.bin\nand BUILD/pr04-b14-mon-absent-r5/RESTORE-INSTRUCTIONS.txt.\nThe following b14 deployment account describes the earlier intact MON state.\n\n'
        first=body.find('\n');body=body[:first+1]+'\n'+note+body[first+1:];path.write_bytes(body.encode('cp1252'))
    print('PASS final evidence audit: exact two MON erases; F/settings/history/RAM preserved; other boards unchanged')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);main(p.parse_args().run)
