"""File-only audit of the non-writing F user demo and unchanged flash."""
import argparse,json,shutil
from datetime import datetime,timezone
from pathlib import Path
import board_f_user_demo_2609 as live
p,io=live.p,live.io


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    run=parser.parse_args().run.resolve();report=p.r.read(run/'report.json')
    build,ready,readback=(Path(report[n]) for n in ('build','ready','readback'))
    info,q,base,image_path=live.admit(build,ready,readback)
    hostpath=build.parent/'step13-host-qualification.json';host=p.r.read(hostpath)
    assert host['passed'] and not host['hardware'] and not host['serial_access']
    assert host['source_sha256']==p.digest(p.HERE/'board_f_user_demo_2609.py')
    for key in ('passed','closed','port_released','before_double_read_verified','all_banks_double_read_verified',
                'F_help_verified','F_cancel_verified','F_disabled_bank_verified','F_RAM_program_verified',
                'loaded_RAM_independently_verified','B0_backup_preserved','wear_counts_preserved',
                'journal_sequence_unchanged','default_S_and_banks_disabled','final_REC_verified',
                'stop_before_saved_setting_writes_honored','host_wear_history_unchanged','other_board_markers_unchanged'):
        assert report[key],key
    assert report['saved_setting_writes']==report['post_final_REC_commands']==0
    assert not report['configuration_changed'] and not report['flash_written']
    reader=(readback/'payload/readback-RAM.bin').read_bytes();image=image_path.read_bytes()
    chunks=lambda data:[data[n:n+64] for n in range(0,len(data),64)]
    reads=[b'F'+bytes([n]) for n in range(4)]*2+[b'M',b'J']
    expected=[b'\r',b'C1\r',b'L\r']+chunks(reader)+reads+[
        b'?\r',b'C1\r',b'0\r',b'L\r',b'\x03',b'L\r']+chunks(image)+[
        b'!',b'C1\r',b'A\r',b'D 0200 03E4\r',b'J3\r',b'S',b'C1\r',b'L\r']+chunks(reader)+reads
    rows=[json.loads(line) for line in (run/'serial.jsonl').read_text().splitlines()]
    assert [bytes.fromhex(row['hex']) for row in rows if row['direction']=='TX']==expected,'TX differs from inspection-only sequence'
    exchanges=[]
    for index,row in enumerate(rows):
        if row['direction']!='TX':continue
        received=[]
        for nxt in rows[index+1:]:
            if nxt['direction']=='TX':break
            if nxt['direction']=='RX':received.append(bytes.fromhex(nxt['hex']))
        exchanges.append((bytes.fromhex(row['hex']),b''.join(received)))
    banks=[];memory=[]
    for command,frame in exchanges:
        if command not in [b'F'+bytes([n]) for n in range(4)]+[b'M']:continue
        count=0x6300 if command==b'M' else 32768
        assert len(frame)==count+2+len(io.SVC) and frame[count+2:]==io.SVC
        assert p.wire.crc(frame[:count])==int.from_bytes(frame[count:count+2],'little')
        if command==b'M':memory.append(frame[:count])
        else:banks.append((command[1],frame[:count]))
    assert len(banks)==16 and len(memory)==2
    for phase in ('before','after'):
        for repeat in (1,2):
            observed=[]
            for bank in range(4):
                raw=(run/f'{phase}-r{repeat}-b{bank}.bin').read_bytes()
                assert raw==(build/f'source-b{bank}.bin').read_bytes()
                index=(0 if phase=='before' else 8)+(repeat-1)*4+bank
                assert banks[index]==(bank,raw),'Bank capture differs from serial RX'
                observed.append(raw)
            live.verify_banks(observed,base)
        raw=(run/(phase+'-service-RAM.bin')).read_bytes()
        assert raw==memory[0 if phase=='before' else 1] and raw[:len(reader)]==reader
    console=bytearray()
    for command,name in ((b'?\r','F-help.txt'),(b'C1\r','F-C1.txt'),(b'0\r','F-disabled-bank.txt'),(b'L\r','F-cancel-L.txt'),(b'\x03','F-cancel-result.txt'),(b'L\r','F-demo-L.txt')):
        raw=(run/name).read_bytes();console.extend(raw)
        if command!=b'L\r' and command!=b'C1\r':
            replies=[reply for sent,reply in exchanges if sent==command]
            assert len(replies)==1 and replies[0]==raw
    startup=(run/'F-demo-startup.txt').read_bytes();result=(run/'F-demo-result.txt').read_bytes()
    assert startup==(ready/'golden-startup-65c816-e.txt').read_bytes()
    assert result==(ready/'golden-result-65c816-e.txt').read_bytes()
    assert [reply for sent,reply in exchanges if sent==chunks(image)[-1]]==[startup]
    assert [reply for sent,reply in exchanges if sent==b'!']==[result]
    console.extend(startup);console.extend(result);io.atomic(run/'F-demo-console.txt',console)
    dump=(run/'F-demo-RAM-dump.txt').read_bytes()
    assert next(reply for sent,reply in exchanges if sent==b'D 0200 03E4\r')==dump
    ram=live.common.parse_dump(dump,0x200,0x3e4)
    live.verify_loaded(ram,build,ready);assert ram==(run/'F-demo-device-RAM.bin').read_bytes()
    before=p.r.read(run/'session-before.json');wearpath=Path(before['wear_history'])
    assert wearpath.read_bytes()==(run/'host-wear-before.json').read_bytes()
    wear=p.r.read(wearpath);assert wear['counts']==base['counts'] and wear['sequence']==1020
    assert wear['config']==base['config'] and wear['history_unknown_mask']=='ffffffff'
    for board in ('2205','2512','2604'):
        escrow=run/(board+'-marker-before.json')
        if escrow.exists():assert escrow.read_bytes()==(p.ROOT/f'output/qualification/device-operations/{board}.json').read_bytes()
    last=max(index for index,row in enumerate(rows) if row['direction']=='TX')
    assert bytes.fromhex(rows[last]['hex'])==b'J'
    final=(run/'final-REC.txt').read_bytes()
    assert b'Boot : 6 5 4 3 2 1 0' in final and final.endswith(io.REC)
    assert b''.join(bytes.fromhex(row['hex']) for row in rows[last+1:] if row['direction']=='RX')==final
    marker=p.r.read(p.ROOT/'output/qualification/device-operations/2609.json')
    assert not any(value for key,value in marker.items() if key.endswith('_worker_active'))
    assert marker['current_firmware_profile']=='b15-VX1-F-CD-MON-AB-E'
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),base['bank_sha256']))
    assert p.r.read(p.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    audit=dict(passed=True,board='2609',hardware=True,checked_utc=datetime.now(timezone.utc).isoformat(),
        exact_qualified_F_DEMO_BIN=True,F_demo_commands=['?','C1','0 (disabled)','L/Ctrl-C','L/demo/key'],entire_TX_sequence_inspection_only=True,
        F_demo_bound_to_raw_RX=True,loaded_F_demo_RAM_verified=True,
        all_four_banks_double_read_before_and_after=True,serial_CRC_frames_bound_to_escrow=True,
        all_128KiB_flash_unchanged=True,all_journal_bytes_and_sequence_unchanged=True,sequence=1020,
        counts=base['counts'],host_wear_history_unchanged=True,B0_sha256=p.WDC_SHA,default='S',enabled_banks=0,
        configuration_changed=False,saved_setting_writes=0,flash_erases=0,final_REC_verified=True,no_TX_after_final_REC=True,
        report_sha256=p.digest(run/'report.json'),live_source_sha256=p.digest(p.HERE/'board_f_user_demo_2609.py'),
        audit_source_sha256=p.digest(__file__),ACIA_board_tested=False)
    io.save(run/'audit.json',audit)
    receipt=f'''# 2609 F user demo — USB hardware verified

**PASS: F help, USB selection, disabled-bank refusal, pre-payload Ctrl-C cancellation,
raw RAM loading, public CPU/capability queries, RAM calculation, key input and return
to the saved recovery default were demonstrated. No flash/settings write occurred.**

File: `b15-F-DEMO-RAM.bin`, 485 bytes, load/entry `$0200`, last byte `$03E4`.
SHA-256: `{report['RAM_BIN_sha256']}`.

[User demo console](F-demo-console.txt) · [Full annotated console](console-log.txt) ·
[Raw serial](serial.jsonl) · [Audit](audit.json) · [Report](report.json).

The RAM app calls only b15 F-supplied services. Eight model checks exercised
both CPUs with MON A/B, C/D and E absent, and with the current 2609 contents.
The live board retains its existing components; no sector was removed for the demo.
An independent MON A dump checked the exact executed 485 RAM bytes and expected
private result variables. That MON read was verification outside the F demo.

All four banks were read twice before and twice after the demonstration and RAM
check. Every flash byte matched. B0 WDCMONV2, all 32 counts, every journal page,
sequence 1020, default S and bank mask 00 are unchanged. Existing host wear history
is byte-identical. Counts remain A=51, B=54, C=78, D=47, E=43, F=30.

The complete serial TX sequence was audited. No CONFIG save/restore, initializer,
flash installer, RTC or EEPROM write was sent. Final REC verified; no later TX;
port closed and shared lease idle. The CONFIG A/S exercise remains prepared only.

ACIA and electrical power-cycle behavior were not qualified by this USB demo.
'''
    (run/'receipt.md').write_text(receipt,encoding='utf-8')
    snapshot=run/'source';snapshot.mkdir(exist_ok=True)
    for path in (Path(__file__),p.HERE/'board_f_user_demo_2609.py',hostpath):shutil.copy2(path,snapshot/path.name)
    io.save(run/'manifest.json',{str(path.relative_to(run)):dict(bytes=path.stat().st_size,sha256=p.digest(path))
                               for path in run.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS F user hardware demo audit; all flash/counts/B0 unchanged; S/mask00/seq1020; final REC',flush=True)


if __name__=='__main__':main()
