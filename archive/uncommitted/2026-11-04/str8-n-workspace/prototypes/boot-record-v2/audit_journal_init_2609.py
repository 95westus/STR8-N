"""File-only independent audit of the C/D hardware initializer and REC stop."""
import argparse,json,shutil
from pathlib import Path
from datetime import datetime,timezone
import wdc_b15_2609 as p
from board_journal_init_2609 import verify_records,SVC


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args();run=args.run.resolve();report=p.r.read(run/'report.json');plan=Path(report['plan']).parent
    info=p.r.read(plan/'plan.json');session=plan.parent
    rb=session/'step05-readback-tools-r1';reader=(rb/'payload/readback-RAM.bin').read_bytes()
    app=(plan/'payload/2609-journal-init-RAM.bin').read_bytes()
    assert report['passed'] and report['closed'] and report['port_released']
    assert report['device_journals_verified'] and report['independent_readback_verified'] and report['final_REC_verified']
    assert report['post_final_REC_commands']==0 and report['stop_before_MON_honored'] and not report['MON_installed']
    rows=[json.loads(line) for line in (run/'serial.jsonl').read_text().splitlines()]
    tx=[bytes.fromhex(row['hex']) for row in rows if row['direction']=='TX']
    chunks=lambda body:[body[n:n+64] for n in range(0,len(body),64)]
    reads=[b'F'+bytes([n]) for n in range(4)]*2+[b'M',b'J']
    expected_tx=[b'\r',b'C1\r',b'L\r']+chunks(reader)+reads+[b'C1\r',b'L\r']+chunks(app)+[
        b'W\r',b'I\r',b'INIT C/D\r',b'V\r',b'Q\r',b'C1\r',b'L\r']+chunks(reader)+reads
    assert tx==expected_tx,'Unexpected command, payload, repetition or post-REC TX'
    bank_frames=[];RAM_frames=[]
    for i,row in enumerate(rows):
        if row['direction']!='TX':continue
        command=bytes.fromhex(row['hex'])
        if command not in [b'F'+bytes([n]) for n in range(4)]+[b'M']:continue
        following=[]
        for nxt in rows[i+1:]:
            if nxt['direction']=='TX':break
            if nxt['direction']=='RX':following.append(bytes.fromhex(nxt['hex']))
        frame=b''.join(following);count=0x6300 if command==b'M' else 32768
        assert len(frame)==count+2+len(SVC) and frame[count+2:]==SVC
        assert p.wire.crc(frame[:count])==int.from_bytes(frame[count:count+2],'little')
        if command==b'M':RAM_frames.append(frame[:count])
        else:bank_frames.append((command[1],frame[:count]))
    assert len(bank_frames)==16 and len(RAM_frames)==2
    for phase in ('before','after'):
        wanted=[(plan/f'{"source" if phase=="before" else "expected"}-b{n}.bin').read_bytes() for n in range(4)]
        for repeat in (1,2):
            for bank in range(4):
                raw=(run/f'{phase}-r{repeat}-b{bank}.bin').read_bytes()
                assert raw==wanted[bank]
                index=(0 if phase=='before' else 8)+(repeat-1)*4+bank
                assert bank_frames[index]==(bank,raw),'Archived readback disconnected from serial evidence'
        memory=(run/f'{phase}-service-RAM.bin').read_bytes()
        assert memory==RAM_frames[0 if phase=='before' else 1] and memory[:len(reader)]==reader
    before=[(run/f'before-r1-b{n}.bin').read_bytes() for n in range(4)]
    after=[(run/f'after-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert before[:3]==after[:3] and before[3][:0x4000]==after[3][:0x4000] and before[3][0x6000:]==after[3][0x6000:]
    assert p.r.sha(before[0])==p.WDC_SHA==p.r.sha(after[0])
    records=verify_records(after,info)
    assert not p.snbt_records(before)
    result=(run/'initializer-result.txt').read_bytes()
    assert result.count(b'D0: erase and verify blank\r\n')==result.count(b'C0: erase and verify blank\r\n')==1
    assert result.find(b'D0:')<result.find(b'C0:') and result.count(b'committed; all 4096 bytes verified\r\n')==2
    assert (run/'initializer-V.txt').read_bytes()==b'V\r\nC/D postimages VERIFIED\r\nRAM JINIT ? V W I Q> '
    reservation=p.r.read(run/'wear-reservation.json');wear=p.r.read(run/'host-wear-after.json')
    assert reservation['durable_before_confirmation'] and reservation['counts_before']==info['counts_before']
    assert reservation['reserved_counts']==wear['counts']==info['counts_reserved']
    assert wear['counts']==[n+(i in (28,29)) for i,n in enumerate(info['counts_before'])]
    assert wear['execution_report_sha256']==p.digest(run/'report.json') and wear['onboard_journal_initialized']
    assert wear['history_unknown_mask']=='ffffffff' and wear['sequence']==1015
    final=(run/'final-REC.txt').read_bytes();assert final.endswith(b'REC> ') and b'WAIT...' in final and b'Boot : 6 5 4 3 2 1 0' in final
    last_tx=max(i for i,row in enumerate(rows) if row['direction']=='TX')
    assert bytes.fromhex(rows[last_tx]['hex'])==b'J'
    assert b''.join(bytes.fromhex(row['hex']) for row in rows[last_tx+1:] if row['direction']=='RX')==final
    confirm_time=next(row['time'] for row in rows if row['direction']=='TX' and bytes.fromhex(row['hex'])==b'INIT C/D\r')
    assert datetime.fromisoformat(reservation['created_utc']).timestamp()<confirm_time
    marker=p.r.read(p.ROOT/'output/qualification/device-operations/2609.json')
    assert marker['journals_initialized'] and not marker['journal_init_worker_active']
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),p.r.hashes(after)))
    assert not marker['MON_A_present'] and not marker['MON_B_present']
    assert p.r.read(p.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    audit=dict(passed=True,hardware=True,board='2609',checked_utc=datetime.now(timezone.utc).isoformat(),
        exact_qualified_RAM_payloads=True,only_one_I_and_confirmation=True,only_CD_mutated=True,
        all_four_banks_independently_double_read_before_and_after=True,serial_CRC_frames_bound_to_escrow=True,
        B0_backup_sha256=p.WDC_SHA,all_nonCD_bytes_unchanged=True,F_sha256=p.r.sha(after[3][-4096:]),
        counts_before=info['counts_before'],counts_after=wear['counts'],other_30_counts_unchanged=True,
        journal_records=records,final_REC_verified=True,no_TX_after_final_REC=True,
        MON_installed=False,ACIA_board_tested=False,port_closed=True,
        actual_erase_order=['D','C'],source_plan_sha256=p.digest(plan/'plan.json'),
        hardware_report_sha256=p.digest(run/'report.json'),live_source_sha256=p.digest(p.HERE/'board_journal_init_2609.py'),
        audit_source_sha256=p.digest(__file__),
        limitation='Powered-on software restart verified; no physical power interruption or ACIA qualification')
    p.save(run/'audit.json',audit)
    receipt='''# 2609 C/D journal initialization — hardware verified

**PASS: RAM initializer completed; both journals independently verified; returned
to USB `REC>` and stopped. MON A/B were not installed.**

| Check | Result |
|---|---|
| Starting state | Exact b15 F only; all four banks read twice before initialization |
| Journal operation | B3:D erased/programmed/committed/verified, then B3:C; commit bytes last |
| Device verification | Every byte of both 4096-byte sectors verified; additional `V` passed |
| Independent readback | All four banks read twice afterward; every byte matched the planned image; serial CRCs checked |
| Journal format | Header/body CRCs and commit markers valid; D sequence 1014, C sequence 1015 |
| Tracked wear | C **77→78**, D **46→47**, F **30 unchanged**; other 30 counts retained |
| History | Unknown prior lifetime `FFFFFFFF` retained; original configuration body preserved |
| B0 backup | Exact WDCMONV2 SHA-256 retained before and after |
| Other sectors | Every non-C/D byte unchanged, including MON regions and F |
| Boot settings | Recovery default S; no enabled opaque banks; generation 8000000F |
| Return/stop | F software restart and countdown reached REC>; no later TX |
| Console | USB FT245 only; ACIA remains unqualified |
| Connection | Port closed; shared serial lease idle |

The host wear reservation was flushed before `INIT C/D` was sent. Both snapshots
contain the preserved history plus these two tracked erase attempts. The new
host history was published only after device verification, independent repeated
readback and final REC. The previous host history remains intact.

B0 SHA-256: `1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`.

[Hardware report](report.json) · [Independent audit](audit.json) ·
[Final REC capture](final-REC.txt) · [Updated wear history](host-wear-after.json).

Keystrokes used: synchronize with Enter; `C1`, `L`, read-only RAM service BIN;
`F` plus bank byte 0–3 twice, `M`, `J`; `C1`, `L`, exact initializer BIN; `W`,
`I`, `INIT C/D`, `V`, `Q`; `C1`, `L`, read-only service again; repeat full-bank
reads and `M`; final `J` restarts F. Text commands use Enter; service commands
and bank bytes are binary. Raw BIN payloads were sent unchanged in 64-byte
chunks. No MON installation command or payload was transmitted.

This proves the powered-on software restart. A physical power-cycle test was
not performed. SRAM-journal relocation is a logged future idea; this operation
uses the installed C/D map.
'''
    (run/'receipt.md').write_text(receipt,encoding='utf-8')
    store=run/'source';store.mkdir(exist_ok=True)
    for source in (Path(__file__),p.HERE/'board_journal_init_2609.py',p.HERE/'prepare_journal_readback_2609.py'):
        shutil.copy2(source,store/source.name)
    p.save(run/'manifest.json',{str(path.relative_to(run)):dict(bytes=path.stat().st_size,sha256=p.digest(path))
             for path in run.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS hardware audit: only C/D changed; C=78 D=47 F=30; B0 exact; all banks double read; final REC; no MON',flush=True)


if __name__=='__main__':main()
