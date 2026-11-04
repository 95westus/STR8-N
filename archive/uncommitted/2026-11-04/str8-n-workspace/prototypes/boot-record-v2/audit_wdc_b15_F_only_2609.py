"""File-only audit of the authorized F-only hardware step and REC> stop."""
import argparse,json,shutil
from pathlib import Path
from datetime import datetime,timezone
import wdc_b15_2609 as planning
from installer.common import save
from installer.engine import legacy_transport as wire,runtime as r

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);args=p.parse_args()
    run=args.run.resolve();report=r.read(run/'report.json');plan=Path(report['plan']).parent;info=planning.verify(plan)
    assert report['passed'] and report['REC_verified'] and report['transaction_device_verified'] and report['port_released']
    assert report['transfers_completed']==1 and report['post_REC_commands']==0 and report['stop_after_REC_honored']
    assert not any(report[k] for k in ('C_D_written','MON_written','RTC_written','EEPROM_written','ACIA_board_tested'))
    source=[(plan/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert expected[:3]==source[:3] and expected[3][:-4096]==source[3][:-4096]
    assert len(expected[3][-4096:])==4096 and r.sha(expected[3][-4096:])==report['F_sha256']
    for bank in (0,3):assert (run/f'fresh-B{bank}-0.bin').read_bytes()==(run/f'fresh-B{bank}-1.bin').read_bytes()==source[bank]
    for path in run.glob('RAM-*-before.bin'):assert path.read_bytes()==path.with_name(path.name.replace('-before','-repeat')).read_bytes()
    rows=[json.loads(line) for line in (run/'serial.jsonl').read_text().splitlines()]
    tx=[bytes.fromhex(row['hex']) for row in rows if row['direction']=='TX']
    command=None;mode='WDC';uploaded={};payload=[];go_count=0;confirm_count=0;native_writes=[]
    for raw in tx:
        if mode=='WDC':
            if raw==b'U\xaa':assert command is None;continue
            if command is None:
                assert raw in (b'\x0c',b'\x02',b'\x03',b'\x06'),'Unexpected WDC command'
                command=None if raw==b'\x0c' else raw[0];continue
            if command==3:assert len(raw)==6;command=None;continue
            if command==2:
                address=int.from_bytes(raw[:3],'little');count=int.from_bytes(raw[3:6],'little');body=raw[6:]
                assert len(body)==count
                if address==0x7fec:assert count==1
                else:
                    assert 0x2000<=address and address+count<=0x4000 and count==256
                    for n,value in enumerate(body):assert address+n not in uploaded;uploaded[address+n]=value
                native_writes.append(dict(address=address,bytes=count));command=None;continue
            assert command==6 and raw==bytes.fromhex('003700');go_count+=1;command=None;mode='confirm';continue
        if mode=='confirm':assert raw==b'Y\r';confirm_count+=1;mode='F-payload';continue
        assert mode=='F-payload' and len(raw)==64,'Unexpected command after migrator entry or REC'
        payload.append(raw)
    cells,entry=wire.read_s19(plan/'installer-model-only.s19')
    assert go_count==confirm_count==1 and uploaded==cells and entry==0x3700
    assert len(payload)==64 and b''.join(payload)==(plan/'b15-F-4096.bin').read_bytes()
    boot=(run/'first-F-only-REC.txt').read_bytes()
    assert boot.endswith(b'REC> ') and b'Recovery L A/B 0-3 C1/2/3 ?' in boot
    assert b'Boot : 6 5 4 3 2 1 0' in boot and b'STR8-N 2.0proto' not in boot
    last_tx=max(row['time'] for row in rows if row['direction']=='TX')
    after_tx_rx=b''.join(bytes.fromhex(row['hex']) for row in rows if row['direction']=='RX' and row['time']>last_tx)
    assert b'REC> ' in after_tx_rx
    reservation=r.read(run/'wear-reservation.json');assert reservation['reserved_before_EXEC']
    before=reservation['counts_before'];after=reservation['reserved_counts']
    assert before[31]==29 and after==[n+(i==31) for i,n in enumerate(before)]
    wear=dict(schema=1,board='2609',counts=after,sequence=info['transaction']['sequence_before'],
        config=info['transaction']['source_config'],history_unknown_mask='ffffffff',
        semantics='Verified tracked lower bounds; prior lifetime wear remains unknown',
        source_history=info['source_backup']+'/post-restore-wear-history.json',
        added_erase_attempts=[dict(bank=3,sector='F',count=1)],device_erase_program_verify_passed=True,
        onboard_journal_initialized=False,execution_report=str(run/'report.json'),execution_report_sha256=planning.digest(run/'report.json'))
    save(run/'host-wear-after.json',wear)
    audit=dict(passed=True,hardware=True,board='2609',F_only=True,exact_RAM_installer_uploaded=True,
        one_EXEC=True,one_Y_confirmation=True,one_4096_byte_F_payload=True,device_full_sector_readback_passed=True,
        fresh_B0_B3_double_reads_passed=True,all_four_preimages_checked_by_qualified_device_guard=True,
        only_F_addressed_by_qualified_migrator=True,no_TX_after_F_payload=True,REC_verified=True,
        no_post_REC_commands=True,ACIA_board_tested=False,USB_FT245_REC_board_tested=True,
        wear_F_before=29,wear_F_after=30,other_wear_counts_unchanged=True,onboard_journal_initialized=False,
        verification_limit='No post-REC RAM reader or MON was loaded. Non-F preservation is supported by fresh B0/B3 capture, four-bank device preflight and the exact qualified single-F write path; no independent post-flash full-bank host readback is claimed.',
        checked_utc=datetime.now(timezone.utc).isoformat())
    save(run/'audit.json',audit)
    markerpath=planning.ROOT/'output/qualification/device-operations/2609.json';marker=r.read(markerpath)
    assert marker['current_firmware_profile']=='b15-F-only' and marker['F_only_REC_verified'] and not marker['physical_reset_pending']
    marker.update(last_tracked_wear_host_record=str(run/'host-wear-after.json'),ACIA_board_tested=False)
    save(markerpath,marker)
    assert r.read(planning.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    sessionpath=Path(info['source_session'])/'session.json';session=r.read(sessionpath)
    save(run/'session-before-closeout.json',session)
    session.update(step03='F-only flash and USB REC verified; stopped',last_completed_step=3,b15_installed=True,
        b15_installation_scope='B3:F000-FFFF only',b15_F_installed=True,MON_installed=False,journals_initialized=False,
        ACIA_board_tested=False,current_stage='F alone; stopped at first USB REC>',step03_report=str(run/'report.json'),
        step03_audit=str(run/'audit.json'),wear_history=str(run/'host-wear-after.json'),
        next_step='Wait for the next user-directed step; no commands after REC>')
    save(sessionpath,session)
    lines=['# 2609 F-only hardware installation — October 27, 2026','',
        '**PASS: b15 F installed and `REC>` verified through USB. Stopped immediately at that prompt.**','',
        '| Item | Result |','|---|---|',
        '| Flash payload | Exactly 4096 bytes at B3:$F000–$FFFF |',
        '| RAM migrator | Exact qualified image, read back before one EXEC at $3700 |',
        '| B0 WDC backup | Fresh double read matched its saved original image; no B0 write |',
        '| Other sectors | No other flash destination in the admitted transaction; MON and C/D untouched |',
        '| F verification | Device erase/program/full-sector readback passed |',
        '| Reset | Owner pressed physical S2/RESB; startup countdown and recovery prompt captured |',
        '| Stop | No command after REC>; no help, CONFIG, MON or RAM tool loaded afterward |',
        '| Console evidence | USB/FT245 only; ACIA is not board-tested by this operation |',
        '| Wear history | Existing tracked F count 29 → 30 in host history; all other recorded counts retained |',
        '| Journals | Not initialized; factory C/D bytes left unchanged |',
        '| Port | Closed and shared lease released |','',
        audit['verification_limit'],'',
        'For a factory WDC board with unknown prior wear, record unknown lifetime history and count observed erase attempts. Do not replace 2609’s retained history with a guessed starting value. Zero/one can describe tracked attempts, not a claim of zero/one lifetime erases.','',
        '[Device report](report.json) · [Independent audit](audit.json) · [Captured first REC>](first-F-only-REC.txt) · [Preserved host wear history](host-wear-after.json).']
    (run/'receipt.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    src=run/'source';src.mkdir(exist_ok=True)
    for path in (Path(__file__),planning.HERE/'board_wdc_b15_F_only_2609.py'):shutil.copyfile(path,src/path.name)
    save(run/'manifest.json',{str(path.relative_to(run)):dict(bytes=path.stat().st_size,sha256=planning.digest(path)) for path in run.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS F-only live audit: 4096 bytes, one EXEC, one F transfer, no post-REC TX, F wear 29 -> 30; USB only',flush=True)

if __name__=='__main__':main()
