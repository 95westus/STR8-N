"""File-only acceptance of CONFIG A then S, exact flash and retained SRAM."""
import argparse,json,hashlib,re,shutil
from pathlib import Path
import board_config_save_restore_seq1021_2609 as b
import edu_sram_backup as backup
p,io=b.p,b.io
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);args=parser.parse_args();run=args.run.resolve()
    r=p.r.read(run/'report.json');plan=p.r.read(b.PLAN/'plan.json');q=p.r.read(b.READY/'qualification.json')
    assert r['passed'] and r['final_REC_verified'] and r['closed'] and r['port_released'] and r['post_final_REC_commands']==0
    assert r['saved_setting_writes']==2 and r['sequence_after']==1023 and r['default_after']=='S' and r['enabled_banks']==0
    assert r['erase_count']==r['SRAM_writes']==r['SRAM_mode_writes']==0 and r['wear_counts_preserved'] and r['B0_preserved']
    assert r['plan_sha256']==sha(b.PLAN/'plan.json')==q['plan_sha256'] and q['passed'] and q['checks']==25
    assert r['RAM_BIN_sha256']==q['BIN_sha256']==sha(b.READY/'2609-CONFIG-RAM.bin')
    source=[(b.PLAN/f'source-b{n}.bin').read_bytes() for n in range(4)];final=[(b.PLAN/f'restored-S-b{n}.bin').read_bytes() for n in range(4)]
    for prefix,want in (('before',source),('final',final)):
        for repeat in (1,2):
            banks=[(run/f'{prefix}-r{repeat}-b{n}.bin').read_bytes() for n in range(4)]
            assert banks==want and all(len(bank)==32768 for bank in banks)
    assert source[:3]==final[:3] and p.r.sha(final[0])==p.WDC_SHA
    changed=[i+0x8000 for i,(x,y) in enumerate(zip(source[3],final[3])) if x!=y]
    assert changed and all(0xc700<=address<0xc900 for address in changed)
    for stage,address,seq,target in (('MON-A',0xc700,1022,'A'),('restored-S',0xc800,1023,'S')):
        row=(b.PLAN/(stage+'-journal-row.bin')).read_bytes();assert final[3][address-0x8000:address-0x8000+256]==row
        assert row[7]==ord(target) and int.from_bytes(row[8:12],'little')==seq and row[13]==0 and row[14:18]==b'\x08'*4
        assert [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==plan['counts_before'] and row[160:164]==b'\xff'*4
    assert (run/'saved-A-device-journal.bin').read_bytes()==(b.PLAN/'MON-A-journal-row.bin').read_bytes()
    io.atomic(run/'restored-S-device-journal.bin',final[3][0x4800:0x4900])
    records=p.snbt_records(final);seq,off,row=max(records);assert len(records)==10 and seq==1023 and off==0x4800
    original_row=max(p.snbt_records(source))[2]
    assert row[:8]+row[12:30]+row[32:252]+row[254:]==original_row[:8]+original_row[12:30]+original_row[32:252]+original_row[254:]
    image=(b.READY/'2609-CONFIG-RAM.bin').read_bytes();symbols=p.r.read(b.BUILD/'symbols.json')['core/ram-config'];expected=bytearray(image);expected[symbols['CONFIG_ROW']-0x200]=4
    for prefix in ('CONFIG-before-A','CONFIG-before-S'):assert (run/(prefix+'-device-RAM.bin')).read_bytes()==expected
    originals=[(b.SESSION/f'step16-EDU-SRAM-preflight-live/SRAM-pass{n}-131072.bin').read_bytes() for n in (1,2)]
    for prefix in ('SRAM-before','SRAM-after-pass1','SRAM-after-pass2'):
        raw=(run/(prefix+'-131072.bin')).read_bytes();parsed,mode=backup.parse((run/(prefix+'-console.txt')).read_bytes())
        assert raw==parsed==originals[0]==originals[1] and len(raw)==131072 and mode==0x40 and p.r.sha(raw)==r['SRAM_sha256']==plan['baseline']['SRAM_sha256']
    for name,target in (('saved-A-autoboot.txt','A'),('restored-S-autoboot.txt','S')):
        raw=(run/name).read_bytes();assert raw.startswith(b'Q\r\n') and b'Boot : 6 5 4 3 2 1 0' in raw
        assert raw.endswith(b.common.MON if target=='A' else io.REC)
    assert (run/'final-REC.txt').read_bytes().endswith(io.REC)
    tx=[bytes.fromhex(e['hex']) for e in map(json.loads,(run/'serial.jsonl').read_text().splitlines()) if e['direction']=='TX']
    assert tx.count(b'C A\r')==tx.count(b'C S\r')==1 and tx.count(b'G 0200\r')==2
    assert len([v for v in tx if re.fullmatch(rb'R [0-9A-F]{5} 40\r',v)])==3*2048
    assert not any(re.fullmatch(rb'B [0-3] [0-9A-F]{4}\r',v) for v in tx) and b'I\r' not in tx
    prior=p.r.read(run/'host-wear-before.json');wear=p.r.read(run/'host-wear-after.json')
    assert prior['sequence']==1021 and wear['sequence']==1023 and wear['counts']==prior['counts']==plan['counts_before']
    assert wear['execution_report_sha256']==sha(run/'report.json') and Path(wear['source_history']).read_bytes()==(run/'host-wear-before.json').read_bytes()
    assert p.r.read(b.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    marker=p.r.read(b.ROOT/'output/qualification/device-operations/2609.json')
    assert marker['CONFIG_save_restore_verified'] and not marker['CONFIG_exercise_worker_active'] and marker['journal_sequence']==1023
    assert marker['default_boot']=='S' and marker['enabled_banks']==0 and marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),map(p.r.sha,final)))
    audit=dict(passed=True,report_sha256=sha(run/'report.json'),saved_setting_writes=2,erase_count=0,
        exact_C700_seq1022_A_and_C800_seq1023_S=True,all_other_flash_bytes_preserved=True,changed_flash_bytes=len(changed),all_32_counts_unchanged=True,
        B0_preserved=True,SRAM_full_reads=3,SRAM_matches_both_originals=True,SRAM_sha256=r['SRAM_sha256'],SRAM_mode='40',
        bank_mask_throughout=0,final_default='S',final_sequence=1023,saved_A_and_restored_S_booted_without_override=True,
        CONFIG_RAM_independently_verified_twice=True,final_REC_verified=True,port_released=True)
    io.save(run/'audit.json',audit)
    sessionpath=b.SESSION/'session.json';session=p.r.read(sessionpath)
    session.update(step19_audit=str(run/'audit.json'),step19_audit_sha256=sha(run/'audit.json'),step19_receipt=str(run/'receipt.md'))
    io.save(sessionpath,session)
    marker.update(last_CONFIG_exercise_audit=str(run/'audit.json'),last_CONFIG_exercise_audit_sha256=sha(run/'audit.json'))
    io.save(b.ROOT/'output/qualification/device-operations/2609.json',marker)
    campaign_path=b.ROOT/'output/qualification/rtc-drift-3hour-campaign.json'
    if campaign_path.exists():
        campaign=p.r.read(campaign_path);before_marker=p.r.read(run/'marker-before.json')
        keys=tuple(campaign['board_admission']['2609'])
        current_admission={key:marker.get(key) for key in keys}
        assert campaign['board_admission']['2609'] in ({key:before_marker.get(key) for key in keys},current_admission)
        campaign['board_admission']['2609']=current_admission
        event=dict(board='2609',type='CONFIG temporary A then restored S',finished_utc=r['finished_utc'],
            audit=str(run/'audit.json'),audit_sha256=sha(run/'audit.json'),sequence=1023,default='S',banks=0,
            clock_set=False,trim_changed=False,power_cycle=False,NTP_baseline_retained=True,bank3_sha256=p.r.sha(final[3]))
        maintenance=campaign.setdefault('verified_maintenance',[])
        if not any(item.get('audit_sha256')==event['audit_sha256'] for item in maintenance):maintenance.append(event)
        io.save(campaign_path,campaign)
        io.save(run/'RTC-campaign-readmission.json',dict(passed=True,baseline_unchanged=True,interval_hours=campaign['interval_hours'],maintenance=event))
    transcript=(run/'console-log.txt').read_text(encoding='ascii')
    first=next(line for line in transcript.splitlines() if '[HOST] FILE 2609-CONFIG-RAM.bin:' in line)
    first=first[first.index('[HOST]'):]
    names=['CONFIG-before-A-RAM-reentry.txt','CONFIG-save-A.txt','CONFIG-saved-A-B.txt','saved-A-autoboot.txt','saved-A-active-slot.txt',
           'CONFIG-before-S-RAM-reentry.txt','CONFIG-restore-S.txt','CONFIG-restored-S-B.txt','restored-S-autoboot.txt']
    excerpt=first+'\n\nSelected captures; gaps between labeled files omit intervening commands.\n'
    excerpt+=''.join('\n[CAPTURE '+name+']\n'+(run/name).read_text(encoding='ascii')+'\n' for name in names)
    (run/'console-excerpt.txt').write_text(excerpt,encoding='ascii')
    receipt=f'''# 2609 CONFIG save/restore — hardware verified

PASS. Executed `2609-CONFIG-RAM.bin` (2728 bytes, SHA-256 `{r['RAM_BIN_sha256']}`).

| Stage | Command | Journal | Default | Bank mask | Erases |
|---|---|---|---|---|---:|
| Before | Inspection | C600 seq1021 | S | 00 | 0 |
| Temporary MON A | C A | C700 seq1022 | A | 00 | 0 |
| Restore recovery | C S | C800 seq1023 | S | 00 | 0 |

Both saves returned OK. Saved A started MON A0 on countdown expiry without an A key; restored S returned to REC without an S override. Each raw CONFIG upload was independently read back through MON before the save. The two complete flash reads before and two after match the planned source/result; only the two journal pages changed. All 32 wear counts and unknown-history mask remain unchanged. No erase was performed. B0 SHA-256 `{p.WDC_SHA}`.

Fresh complete SRAM reads before and twice after match both original 131072-byte backups, byte for byte, in mode40. SRAM SHA-256 `{r['SRAM_sha256']}`. No SRAM data/mode write, time reset, trim change or bank enable was part of this exercise. Final REC verified, port released.

[Console excerpt](console-excerpt.txt) · [Complete console log](console-log.txt) · [Audit](audit.json) · [Report](report.json) · [New wear record](host-wear-after.json)
'''
    (run/'receipt.md').write_text(receipt,encoding='utf-8')
    src=run/'source';src.mkdir(exist_ok=True)
    for path in (Path(__file__),Path(b.__file__),b.HERE/'test_config_save_restore_seq1021_2609.py',b.HERE/'prepare_config_save_restore_seq1021_2609.py'):shutil.copyfile(path,src/path.name)
    io.save(run/'manifest.json',{str(path.relative_to(run)):dict(bytes=path.stat().st_size,sha256=sha(path)) for path in run.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS INDEPENDENT CONFIG AUDIT',run/'receipt.md',flush=True)
    print(excerpt,flush=True)


if __name__=='__main__':main()
