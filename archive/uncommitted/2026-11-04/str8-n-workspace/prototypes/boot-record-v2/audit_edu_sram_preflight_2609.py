"""Independently audit live read-only ES1 exports, flash and exact TX sequence."""
import argparse,binascii,hashlib,json
from pathlib import Path
import edu_sram_backup as backup

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
read=lambda path:json.loads(Path(path).read_text())
sha=lambda raw:hashlib.sha256(raw).hexdigest()
digest=lambda path:sha(Path(path).read_bytes())


def audit(run):
    run=Path(run).resolve();report=read(run/'report.json');assert report['passed'] and report['hardware']
    assert report['final_REC_verified'] and report['post_final_REC_commands']==0 and report['port_released']
    assert not report['flash_written'] and report['saved_setting_writes']==report['SRAM_writes']==report['SRAM_mode_writes']==0
    ready=Path(report['ready']);q=read(ready/'qualification.json');build=Path(q['preflight_build']);image=(ready/'2609-EDU-SRAM-PREFLIGHT-RAM.bin').read_bytes()
    assert len(image)==2264 and sha(image)==report['RAM_BIN_sha256']==q['artifacts']['2609-EDU-SRAM-PREFLIGHT-RAM.bin']['sha256']
    assert (run/'EDU-device-RAM.bin').read_bytes()==image
    banks=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)]
    files=[]
    for phase in ('before','after'):
        for repeat in (1,2):
            for bank in range(4):
                path=run/f'{phase}-r{repeat}-b{bank}.bin';assert path.read_bytes()==banks[bank];files.append(path)
    assert list(map(sha,banks))==report['baseline']['bank_sha256']
    assert sha(banks[0])=='1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94'
    history=read(run/'host-wear-before.json');rows=[]
    for off in range(0x4000,0x6000,256):
        row=banks[3][off:off+256]
        if row[:6]!=b'SNBT\x01\x20':continue
        assert row[255]==0 and binascii.crc_hqx(row[:30],65535)==int.from_bytes(row[30:32],'little')
        assert binascii.crc_hqx(row[:252],65535)==int.from_bytes(row[252:254],'little')
        rows.append((int.from_bytes(row[8:12],'little'),row))
    seq,row=max(rows);assert len(rows)==7 and seq==history['sequence']==1020
    assert [int.from_bytes(row[64+n*3:67+n*3],'little') for n in range(32)]==history['counts']
    assert row[7]==ord('S') and row[13]==0 and row[32:48].hex()==history['config'] and row[160:164]==b'\xff'*4
    session=read(run/'session-before.json');wearpath=Path(session['wear_history']);assert wearpath.read_bytes()==(run/'host-wear-before.json').read_bytes()
    arrays=[];modes=[]
    for n in (1,2):
        path=run/f'SRAM-pass{n}-console.txt';raw,mode=backup.parse(path.read_bytes());files.append(path)
        file=run/f'SRAM-pass{n}-131072.bin';assert raw==file.read_bytes();files.append(file)
        assert raw==(run/f'backup-verified/SRAM-pass{n}-131072.bin').read_bytes()
        arrays.append(raw);modes.append(mode)
    assert len(arrays[0])==len(arrays[1])==131072 and arrays[0]==arrays[1] and modes[0]==modes[1]
    assert sha(arrays[0])==report['SRAM_sha256'] and f'{modes[0]:02X}'==report['SRAM_mode']
    # Every board-directed serial write must be a known raw RAM payload or an
    # exact read/inspection/reset command. No installer/settings path exists.
    tx=[bytes.fromhex(row['hex']) for line in (run/'serial.jsonl').read_text().splitlines() if (row:=json.loads(line))['direction']=='TX']
    reader=(Path(report['readback'])/'payload/readback-RAM.bin').read_bytes()
    def upload(body):return [b'L\r']+[body[n:n+64] for n in range(0,len(body),64)]
    def full_read():return [b'C1\r']+upload(reader)+[b'F'+bytes([n]) for _ in (1,2) for n in range(4)]+[b'M']
    expected=[b'\r']+full_read()+[b'J',b'C1\r']+upload(image)+[b'?\r',b'S\r',b'V\r']
    if report['disabled_CB_ack_performed']:expected.extend((b'A\r',b'V\r'))
    expected.extend(f'R {a:05X} 40\r'.encode() for _ in (1,2) for a in range(0,131072,64))
    expected.extend((b'V\r',b'Q\r',b'C1\r',b'A\r',f'D 0200 {0x200+len(image)-1:04X}\r'.encode(),b'J3\r',b'S'))
    expected+=full_read()+[b'J'];assert tx==expected,'Unexpected board command or payload'
    assert (run/'final-REC.txt').read_bytes().endswith(b'REC> ')
    assert read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    for name in ('2205','2512','2604'):
        prior=run/(name+'-marker-before.json')
        if prior.exists():assert prior.read_bytes()==(ROOT/f'output/qualification/device-operations/{name}.json').read_bytes()
    info=dict(passed=True,hardware_evidence=True,report_sha256=digest(run/'report.json'),two_full_arrays_identical=True,
        bytes_each=131072,SRAM_sha256=sha(arrays[0]),SRAM_mode=f'{modes[0]:02X}',SRAM_read_replies_verified=4096,
        exact_serial_TX_sequence_verified=True,TX_records=len(tx),all_128KiB_flash_unchanged=True,independent_loaded_RAM_match=True,
        B0_backup_preserved=True,wear_counts_preserved=True,host_wear_sha256=digest(wearpath),sequence=1020,default='S',enabled_banks=0,
        flash_writes=0,saved_setting_writes=0,SRAM_writes=0,SRAM_mode_writes=0,final_REC=True,post_final_REC_commands=0,port_lease_idle=True,
        current_board_physical_bank_sha256=list(map(sha,banks)),presence_or_capacity_probe=False,
        audit_source_sha256=digest(__file__),live_wrapper_sha256=digest(HERE/'board_edu_sram_preflight_2609.py'),
        evidence={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in files})
    (run/'audit.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    text=f'''# 2609 RAM EDU/SRAM preflight — hardware complete, no flash

**PASS:** `2609-EDU-SRAM-PREFLIGHT-RAM.bin` ran over USB COM8 / A10MPQXCA.
Two complete 131072-byte SRAM arrays match byte for byte. All 4096 ordered
64-byte read replies passed address, status, completed-count and mode checks.

| File | Bytes | SHA-256 |
|---|---:|---|
| `SRAM-pass1-131072.bin` | 131072 | `{sha(arrays[0])}` |
| `SRAM-pass2-131072.bin` | 131072 | `{sha(arrays[1])}` |
| `2609-EDU-SRAM-PREFLIGHT-RAM.bin` | {len(image)} | `{sha(image)}` |

SRAM mode remained **{modes[0]:02X}**. Disabled-CB acknowledgment performed:
**{report['disabled_CB_ack_performed']}**. VIA snapshot before:
`{report['VIA_before']}`, after: `{report['VIA_after']}` (DDR/PCR/ACR/IFR/IER).
No SRAM write, WRMR, presence/alias probe, format, repartition, RTC/EEPROM
operation, saved setting or flash write was requested. These reads and matching
backups do not separately qualify physical capacity or battery retention.

All four flash banks were read twice before and twice after, with serial CRC,
and match the exact admitted source. The original B0 WDC backup, every C/D
journal byte and all 32 wear counts are unchanged. Actual journal sequence is
**1020**, default **S**, enabled banks **00**, unknown lifetime mask FFFFFFFF.
The executed 2264-byte RAM image was independently dumped through MON A and
matched the qualified BIN. The exact sequence of {len(tx)} serial TX records
was independently checked; no unexpected command/payload was sent.

Finished at **REC>**, port closed and lease idle; no commands after the final
REC verification. The ROM EDU/SRAM installer has **not** been run. Stop before
flashing. The existing prepared ROM plan remains for a separately directed step.

[Complete console log](console-log.txt) · [Report](report.json) · [Audit](audit.json)
· [Pass 1 BIN](SRAM-pass1-131072.bin) · [Pass 2 BIN](SRAM-pass2-131072.bin)
· [Pass 1 console](SRAM-pass1-console.txt) · [Pass 2 console](SRAM-pass2-console.txt)
· [Independent backup assembly](backup-verified/backup.json)
· [Final REC](final-REC.txt).
'''
    (run/'receipt.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:info[k] for k in ('passed','bytes_each','SRAM_sha256','SRAM_mode','all_128KiB_flash_unchanged','wear_counts_preserved','sequence','final_REC')},indent=2))
    return info


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    audit(parser.parse_args().run)
