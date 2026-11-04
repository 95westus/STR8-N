"""File-only audit of the exact VX1 install, both MON queries and REC stop."""
import argparse,json,shutil
from datetime import datetime,timezone
from pathlib import Path
import board_version_caps_2609 as live
p=live.p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    run=parser.parse_args().run.resolve()
    report=p.r.read(run/'report.json');plan=Path(report['plan']).parent;session=plan.parent
    info=p.r.read(plan/'plan.json');ready=session/'step08-VERSION-ready'
    q=p.r.read(ready/'qualification.json')
    assert q['passed'] and q['checks']==52 and q['plan_sha256']==p.digest(plan/'plan.json')
    host=p.r.read(session/'step09-host-qualification.json')
    assert host['passed'] and not host['hardware'] and not host['serial_access']
    assert host['source_sha256']==p.digest(p.HERE/'board_version_caps_2609.py')
    for name,binding in info['inputs'].items():assert p.digest(name)==binding['sha256']
    for name,binding in info['artifacts'].items():assert p.digest(plan/name)==binding['sha256']
    assert report['RAM_BIN_sha256']==p.digest(report['RAM_BIN'])==q['payloads'][info['BIN']]['sha256']
    for key in ('passed','closed','port_released','MON_device_verified','fresh_all_bank_double_read_verified',
                'all_banks_double_read_verified','MON_A_boot_verified','MON_B_boot_verified',
                'MON_A_VERSION_CAPS_verified','MON_B_VERSION_CAPS_verified','final_REC_verified',
                'B0_backup_preserved','saved_configuration_unchanged','stop_before_configuration_honored',
                'other_board_markers_unchanged'):
        assert report[key],key
    assert report['post_final_REC_commands']==0 and not report['configuration_changed']
    reader=(session/'step05-readback-tools-r1/payload/readback-RAM.bin').read_bytes()
    app=(plan/'payload'/info['BIN']).read_bytes()
    rows=[json.loads(line) for line in (run/'serial.jsonl').read_text().splitlines()]
    tx=[bytes.fromhex(row['hex']) for row in rows if row['direction']=='TX']
    chunks=lambda data:[data[n:n+64] for n in range(0,len(data),64)]
    reads=[b'F'+bytes([n]) for n in range(4)]*2+[b'M',b'J']
    boots=[]
    for target in ('A','B'):
        boots.extend([b'C1\r',target.encode()+b'\r',b'D 7D30 7D30\r',b'D 7D00 7D02\r',
                      b'VERSION\r',b'CAPS\r',b'D 6700 67DF\r',b'J3\r',b'S'])
    expected_tx=[b'\r',b'C1\r',b'L\r']+chunks(reader)+reads+[b'C1\r',b'L\r']+chunks(app)+[
        b'W\r',b'I\r',b'INSTALL VERSION\r',b'V\r',b'Q\r']+boots+[b'C1\r',b'L\r']+chunks(reader)+reads
    assert tx==expected_tx,'Unexpected payload, configuration command or post-REC TX'
    exchanges=[]
    for i,row in enumerate(rows):
        if row['direction']!='TX':continue
        received=[]
        for nxt in rows[i+1:]:
            if nxt['direction']=='TX':break
            if nxt['direction']=='RX':received.append(bytes.fromhex(nxt['hex']))
        exchanges.append((bytes.fromhex(row['hex']),b''.join(received)))
    bank_frames=[];ram_frames=[]
    for command,frame in exchanges:
        if command not in [b'F'+bytes([n]) for n in range(4)]+[b'M']:continue
        count=0x6300 if command==b'M' else 32768
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
                assert bank_frames[index]==(bank,raw)
        observed=(run/(phase+'-service-RAM.bin')).read_bytes()
        assert observed==ram_frames[0 if phase=='before' else 1] and observed[:len(reader)]==reader
    before=[(run/f'before-r1-b{n}.bin').read_bytes() for n in range(4)]
    after=[(run/f'after-r1-b{n}.bin').read_bytes() for n in range(4)]
    monitors=live.verify_postimages(before,after,info,plan)
    for index,(target,page) in enumerate((('A',0xa0),('B',0xb0))):
        def capture(suffix):return (run/f'MON-{target}-{suffix}.txt').read_bytes()
        assert (run/f'MON-{target}-device.bin').read_bytes()==after[3][(page-0x80)*256:(page-0x70)*256]
        assert b'STR8-N 2.0proto' in capture('banner') and capture('banner').endswith(live.MON)
        assert live.parse_dump(capture('active'),0x7d30,0x7d30)==bytes([page])
        identity=live.parse_dump(capture('identity'),0x7d00,0x7d02)
        assert identity[:2]==b'\x03\x16' and identity[2]&1
        golden=(ready/'simulated-VERSION.txt').read_bytes().replace(b'Running MON: A',b'Running MON: '+target.encode())
        assert capture('VERSION')==golden
        assert capture('CAPS')==(ready/'simulated-CAPS.txt').read_bytes()
        data=live.parse_dump(capture('INFO-dump'),0x6700,0x67df)
        live.verify_info(data,page,info,plan)
        assert data==(run/f'MON-{target}-INFO.bin').read_bytes()
        for command,suffix in ((b'VERSION\r','VERSION'),(b'CAPS\r','CAPS'),(b'D 6700 67DF\r','INFO-dump')):
            replies=[reply for sent,reply in exchanges if sent==command]
            assert len(replies)==2 and replies[index]==capture(suffix),'Console capture not bound to raw RX'
        assert capture('return-REC').endswith(live.io.REC)
    assert (run/'version-caps-e000-device.bin').read_bytes()==after[3][0x6000:0x7000]
    result=(run/'installer-result.txt').read_bytes()
    assert next(reply for sent,reply in exchanges if sent==b'INSTALL VERSION\r')==result
    assert result.count(b'erase sector; verify blank\r\n')==3
    assert result.count(b'committed; entire action readback VERIFIED\r\n')==6
    positions=[result.find(t) for t in (b'C300\r\n',b'E000\r\n',b'C400\r\n',b'A000\r\n',b'C500\r\n',b'B000\r\n')]
    assert min(positions)>=0 and positions==sorted(positions)
    reservation=p.r.read(run/'wear-reservation.json');wear=p.r.read(run/'host-wear-after.json')
    assert reservation['durable_before_confirmation'] and reservation['reserved_counts']==wear['counts']==info['counts_after']
    assert wear['counts']==[n+(i in (26,27,30)) for i,n in enumerate(info['counts_before'])]
    assert wear['sequence']==1020 and wear['config']==info['config'] and wear['history_unknown_mask']=='ffffffff'
    assert wear['execution_report_sha256']==p.digest(run/'report.json')
    confirmation_time=next(row['time'] for row in rows if row['direction']=='TX' and bytes.fromhex(row['hex'])==b'INSTALL VERSION\r')
    assert datetime.fromisoformat(reservation['created_utc']).timestamp()<confirmation_time
    last_tx=max(i for i,row in enumerate(rows) if row['direction']=='TX')
    assert bytes.fromhex(rows[last_tx]['hex'])==b'J'
    final=(run/'final-REC.txt').read_bytes()
    assert final.endswith(live.io.REC) and b'WAIT...' in final and b'Boot : 6 5 4 3 2 1 0' in final
    assert b''.join(bytes.fromhex(row['hex']) for row in rows[last_tx+1:] if row['direction']=='RX')==final
    marker=p.r.read(p.ROOT/'output/qualification/device-operations/2609.json')
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert marker['VERSION_CAPS_installed'] and marker['current_firmware_profile']=='b15-VX1-F-CD-MON-AB-E'
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),p.r.hashes(after)))
    assert p.r.read(p.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    audit=dict(passed=True,hardware=True,board='2609',checked_utc=datetime.now(timezone.utc).isoformat(),
        exact_qualified_RAM_installer=True,all_components_CRC_commit_build_identity_verified=True,MONs=monitors,
        all_four_banks_double_read_before_and_after_boot=True,serial_frames_and_console_bound_to_escrow=True,
        B0_backup_sha256=p.WDC_SHA,B0_B1_B2_B3_8_9_F_unchanged=True,existing_C_D_snapshots_unchanged=True,
        erase_order=['B3:E','B3:A','B3:B'],only_C300_C400_C500_journal_appends=True,
        counts_before=info['counts_before'],counts_after=wear['counts'],other_29_counts_unchanged=True,
        configuration_unchanged=True,default='S',both_MON_VERSION_CAPS_and_INFO_verified=True,
        final_REC_verified=True,no_TX_after_final_REC=True,ACIA_board_tested=False,
        live_source_sha256=p.digest(p.HERE/'board_version_caps_2609.py'),audit_source_sha256=p.digest(__file__),
        report_sha256=p.digest(run/'report.json'),limitation='USB and powered-on software resets; no physical power-cycle or ACIA qualification')
    p.save(run/'audit.json',audit)
    receipt=f'''# 2609 VERSION/CAPS RAM installation — hardware verified

**PASS: installed VX1 E and matching MON A/B; VERSION, CAPS and the 224-byte
INFO record verified from both MONs. Returned to F `REC>` and stopped before
saved-configuration changes.**

| Item | Result |
|---|---|
| RAM installer | `2609-VERSION-CAPS-RAM.bin`, 15,480 bytes, raw L at $0200 |
| Embedded files | `version-caps-e000.bin`, `monitor-a0-version-caps.bin`, `monitor-b0-version-caps.bin`; each 4096 bytes |
| Erases | E then A then B; no C/D or F erase |
| Journals | C300/1018 reserves E; C400/1019 reserves A; C500/1020 reserves B; committed before each erase |
| Wear | E **42→43**, A **50→51**, B **53→54**; C=78, D=47, F=30 and other 26 counts retained |
| B0 | Original WDCMONV2 backup unchanged; B1/B2 and B3:8/9/F also unchanged |
| Configuration | Legacy body, default S, disabled opaque-bank mask and unknown-lifetime mask preserved |
| Verification | Six commit-last action readbacks; all-bank V; four banks read twice before and twice after both MON queries |
| MON queries | Exact qualified VERSION/CAPS output and 224-byte INFO, active A0/B0, CPU=16, matching builds |
| Stop | Final F restart reached REC>; no later TX; port closed and shared lease idle |

RAM BIN SHA-256: `{report['RAM_BIN_sha256']}`.
B0 SHA-256: `{p.WDC_SHA}`.

[Annotated console](console-log.txt) · [Raw serial](serial.jsonl) ·
[Hardware report](report.json) · [Audit](audit.json) · [Updated wear history](host-wear-after.json).

Actual console captures: [A VERSION](MON-A-VERSION.txt), [A CAPS](MON-A-CAPS.txt),
[B VERSION](MON-B-VERSION.txt), [B CAPS](MON-B-CAPS.txt), [final REC](final-REC.txt).
Actual component readbacks: [E](version-caps-e000-device.bin),
[MON A](MON-A-device.bin), [MON B](MON-B-device.bin).

Runtime C1 selected USB. No saved configuration writer was sent; the complete
TX sequence was audited. Both MONs used VERSION, CAPS and read-only D commands,
then J3/S to recovery. The final full-bank comparison includes those checks.
Original journal snapshots and previous host wear history remain archived.
Counts retain their tracked lower-bound meaning; earlier lifetime wear is unknown.

No physical power-cycle, ACIA qualification, debugger installation or configuration
change was performed. The standalone RAM query client was not run on hardware.
'''
    (run/'receipt.md').write_text(receipt,encoding='utf-8')
    snapshot=run/'source';snapshot.mkdir(exist_ok=True)
    for path in (Path(__file__),p.HERE/'board_version_caps_2609.py'):shutil.copy2(path,snapshot/path.name)
    p.save(run/'manifest.json',{str(path.relative_to(run)):dict(bytes=path.stat().st_size,sha256=p.digest(path))
                               for path in run.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS VX1 hardware audit: E=43 A=51 B=54 C=78 D=47 F=30; both MON VERSION/CAPS; B0/config preserved; final REC',flush=True)


if __name__=='__main__':main()
