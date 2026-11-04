"""File-only audit of exact MON install, both USB starts and final REC stop."""
import argparse,json,shutil
from datetime import datetime,timezone
from pathlib import Path
import board_mon_install_2609 as live
p=live.p


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args();run=args.run.resolve();report=p.r.read(run/'report.json');plan=Path(report['plan']).parent
    info=p.r.read(plan/'plan.json');session=plan.parent.parent
    q=p.r.read(session/'step06-MON-ready/qualification.json')
    assert q['passed'] and q['checks']==55 and q['input_plans']['mon-only']['sha256']==p.digest(plan/'plan.json')
    for name,binding in info['inputs'].items():assert p.digest(name)==binding['sha256']
    for name,binding in info['artifacts'].items():assert p.digest(plan/name)==binding['sha256']
    assert report['passed'] and report['closed'] and report['port_released'] and report['post_final_REC_commands']==0
    assert report['MON_device_verified'] and report['all_banks_double_read_verified'] and report['MON_A_boot_verified'] and report['MON_B_boot_verified']
    assert report['final_REC_verified'] and not report['configuration_changed'] and report['stop_before_configuration_honored']
    rb=session/'step05-readback-tools-r1';reader=(rb/'payload/readback-RAM.bin').read_bytes();app=(plan/'payload'/info['BIN']).read_bytes()
    rows=[json.loads(line) for line in (run/'serial.jsonl').read_text().splitlines()]
    tx=[bytes.fromhex(row['hex']) for row in rows if row['direction']=='TX']
    chunks=lambda data:[data[n:n+64] for n in range(0,len(data),64)]
    reads=[b'F'+bytes([n]) for n in range(4)]*2+[b'M',b'J']
    boots=[]
    for target in ('A','B'):boots.extend([b'C1\r',target.encode()+b'\r',b'D 7D30 7D30\r',b'D 7D00 7D02\r',b'J3\r',b'S'])
    expected_tx=[b'\r',b'C1\r',b'L\r']+chunks(reader)+reads+[b'C1\r',b'L\r']+chunks(app)+[
        b'W\r',b'I\r',b'INSTALL MON\r',b'V\r',b'Q\r']+boots+[b'C1\r',b'L\r']+chunks(reader)+reads
    assert tx==expected_tx,'Unexpected payload/command/configuration write or post-REC TX'
    bank_frames=[];ram_frames=[]
    for i,row in enumerate(rows):
        if row['direction']!='TX':continue
        command=bytes.fromhex(row['hex'])
        if command not in [b'F'+bytes([n]) for n in range(4)]+[b'M']:continue
        received=[]
        for nxt in rows[i+1:]:
            if nxt['direction']=='TX':break
            if nxt['direction']=='RX':received.append(bytes.fromhex(nxt['hex']))
        frame=b''.join(received);count=0x6300 if command==b'M' else 32768
        assert len(frame)==count+2+len(live.io.SVC) and frame[count+2:]==live.io.SVC
        assert p.wire.crc(frame[:count])==int.from_bytes(frame[count:count+2],'little')
        if command==b'M':ram_frames.append(frame[:count])
        else:bank_frames.append((command[1],frame[:count]))
    assert len(bank_frames)==16 and len(ram_frames)==2
    for phase in ('before','after'):
        for repeat in (1,2):
            for bank in range(4):
                raw=(run/f'{phase}-r{repeat}-b{bank}.bin').read_bytes()
                desired=(plan/f'{"source" if phase=="before" else "expected"}-b{bank}.bin').read_bytes()
                assert raw==desired
                index=(0 if phase=='before' else 8)+(repeat-1)*4+bank
                assert bank_frames[index]==(bank,raw),'Readback not bound to serial evidence'
        observed=(run/(phase+'-service-RAM.bin')).read_bytes()
        assert observed==ram_frames[0 if phase=='before' else 1] and observed[:len(reader)]==reader
    before=[(run/f'before-r1-b{n}.bin').read_bytes() for n in range(4)]
    after=[(run/f'after-r1-b{n}.bin').read_bytes() for n in range(4)]
    monitors=live.verify_postimages(before,after,info)
    for target,page in (('A',0xa0),('B',0xb0)):
        assert p.wire.slot_valid((run/('MON-'+target+'-device.bin')).read_bytes(),page)
        assert (run/('MON-'+target+'-device.bin')).read_bytes()==after[3][(page-0x80)*256:(page-0x70)*256]
        banner=(run/('MON-'+target+'-banner.txt')).read_bytes()
        assert b'STR8-N 2.0proto' in banner and banner.endswith(live.MON)
        active=live.parse_dump((run/('MON-'+target+'-active.txt')).read_bytes(),0x7d30,0x7d30)
        identity=live.parse_dump((run/('MON-'+target+'-identity.txt')).read_bytes(),0x7d00,0x7d02)
        assert active==bytes([page]) and identity[:2]==b'\x03\x16' and identity[2]&1
        assert (run/('MON-'+target+'-return-REC.txt')).read_bytes().endswith(live.io.REC)
    result=(run/'installer-result.txt').read_bytes()
    assert result.count(b'erase sector; verify blank\r\n')==2
    assert result.count(b'committed; entire action readback VERIFIED\r\n')==4
    positions=[result.find(t) for t in (b'C100\r\n',b'A000\r\n',b'C200\r\n',b'B000\r\n')]
    assert min(positions)>=0 and positions==sorted(positions)
    reservation=p.r.read(run/'wear-reservation.json');wear=p.r.read(run/'host-wear-after.json')
    assert reservation['durable_before_confirmation'] and reservation['reserved_counts']==wear['counts']==info['counts_after']
    assert wear['counts']==[n+(i in (26,27)) for i,n in enumerate(info['counts_before'])]
    assert wear['sequence']==1017 and wear['config']==info['config'] and wear['history_unknown_mask']=='ffffffff'
    assert wear['execution_report_sha256']==p.digest(run/'report.json')
    confirmation_time=next(row['time'] for row in rows if row['direction']=='TX' and bytes.fromhex(row['hex'])==b'INSTALL MON\r')
    assert datetime.fromisoformat(reservation['created_utc']).timestamp()<confirmation_time
    last_tx=max(i for i,row in enumerate(rows) if row['direction']=='TX');assert bytes.fromhex(rows[last_tx]['hex'])==b'J'
    final=(run/'final-REC.txt').read_bytes()
    assert final.endswith(live.io.REC) and b'WAIT...' in final and b'Boot : 6 5 4 3 2 1 0' in final
    assert b''.join(bytes.fromhex(row['hex']) for row in rows[last_tx+1:] if row['direction']=='RX')==final
    marker=p.r.read(p.ROOT/'output/qualification/device-operations/2609.json')
    assert not marker['MON_install_worker_active'] and marker['MON_A_present'] and marker['MON_B_present']
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),p.r.hashes(after)))
    assert p.r.read(p.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    audit=dict(passed=True,hardware=True,board='2609',checked_utc=datetime.now(timezone.utc).isoformat(),
        exact_qualified_RAM_installer=True,MON_A_and_B_CRC_commit_generation_verified=True,MONs=monitors,
        all_four_banks_double_read_before_and_after_boot=True,serial_frames_bound_to_escrow=True,
        B0_backup_sha256=p.WDC_SHA,all_opaque_sectors_and_F_unchanged=True,existing_C000_D000_snapshots_unchanged=True,
        only_MON_A_B_erased=True,only_C100_C200_journal_appends=True,counts_before=info['counts_before'],counts_after=wear['counts'],
        other_30_counts_unchanged=True,configuration_unchanged=True,default='S',MON_A_USB_boot_verified=True,MON_B_USB_boot_verified=True,
        both_slot_and_CPU_identities_verified=True,final_REC_verified=True,no_TX_after_final_REC=True,ACIA_board_tested=False,
        live_source_sha256=p.digest(p.HERE/'board_mon_install_2609.py'),audit_source_sha256=p.digest(__file__),
        report_sha256=p.digest(run/'report.json'),limitation='USB and powered-on software resets; no physical power-cycle or ACIA qualification')
    p.save(run/'audit.json',audit)
    receipt=f'''# 2609 MON-only RAM installation — hardware verified

**PASS: exact MON-only installer ran; both MONs verified and started over USB;
returned to F `REC>` and stopped before saved-configuration changes.**

| Item | Result |
|---|---|
| RAM installer | `2609-MON-AB-RAM.bin`, 11,113 bytes, raw L at $0200 |
| Embedded MONs | `monitor-a0-offline-component.bin`, `monitor-b0-offline-component.bin`; exact b15 PR04 generation 8000000F |
| Erases | A then B only; no C/D or F erase |
| Journals | C100 sequence 1016 reserved A; C200 sequence 1017 reserved B; both committed before their erase |
| Verification | Body/full-image readback, commit-last and all-bank V; independent full-bank reads twice before and twice after MON boot checks |
| Wear | A **49→50**, B **52→53**; C=78, D=47, F=30 and other recorded counts retained |
| B0 | Original WDCMONV2 backup unchanged, repeatedly read before and after |
| Other flash | B0–B2 and B3:8/9/E/F unchanged; existing C000/D000 snapshots unchanged |
| MON A/B start | Both USB banners and B3 active-page/65C816 identities verified; J3/S returned each to REC |
| Configuration | Legacy body, recovery default S, disabled opaque-bank mask and unknown-lifetime mask preserved |
| Stop | Final F restart reached REC>; no later TX; port closed and shared lease idle |

RAM BIN SHA-256: `{info['BIN_sha256']}`.
B0 SHA-256: `{p.WDC_SHA}`.

[Full annotated console log](console-log.txt) · [Raw serial log](serial.jsonl) ·
[Hardware report](report.json) · [Audit](audit.json) · [Updated wear history](host-wear-after.json).

Actual MON readbacks: [MON A](MON-A-device.bin), [MON B](MON-B-device.bin).
Console boot captures: [A](MON-A-banner.txt), [B](MON-B-banner.txt),
[final REC](final-REC.txt).

The initial RAM `W` display shows imported and planned counts; independent final
SNBT readback establishes actual post-install counts. Runtime C1 selected USB
for transfers. No saved configuration writer/selection command was sent; the
entire TX sequence was checked. MON boot tests used A/B, read-only D commands,
J3 and S. The final full-bank comparison includes all those boot checks.

No physical power-cycle or ACIA qualification was performed. Earlier journals,
owner history and all escrow images remain archived. The combined C/D+MON BIN
was not used.
'''
    (run/'receipt.md').write_text(receipt,encoding='utf-8')
    snapshot=run/'source';snapshot.mkdir(exist_ok=True)
    for path in (Path(__file__),p.HERE/'board_mon_install_2609.py'):shutil.copy2(path,snapshot/path.name)
    p.save(run/'manifest.json',{str(path.relative_to(run)):dict(bytes=path.stat().st_size,sha256=p.digest(path))
                               for path in run.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS MON hardware audit: A=50 B=53 C=78 D=47 F=30; both MONs started; B0/config preserved; final REC',flush=True)


if __name__=='__main__':main()
