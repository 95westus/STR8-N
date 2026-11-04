"""Independent file-only ES1 install, wear, SRAM preservation and TX audit."""
import argparse,binascii,hashlib,json
from datetime import datetime
from pathlib import Path
import edu_sram_backup as backup

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda data:hashlib.sha256(data).hexdigest()
digest=lambda p:sha(Path(p).read_bytes())
crc=lambda data:binascii.crc_hqx(bytes(data),65535)


def records(bank):
    result=[]
    for off in range(0x4000,0x6000,256):
        row=bank[off:off+256]
        if row[:6]!=b'SNBT\x01\x20':continue
        assert row[254:]==b'\xff\0' and crc(row[:30])==int.from_bytes(row[30:32],'little') and crc(row[:252])==int.from_bytes(row[252:254],'little')
        result.append((int.from_bytes(row[8:12],'little'),off,row))
    return result


def audit(run):
    run=Path(run).resolve();r=read(run/'report.json');assert r['passed'] and r['hardware'] and r['final_REC_verified'] and r['port_released']
    assert r['post_final_REC_commands']==0 and not r['configuration_changed'] and r['saved_setting_writes']==r['SRAM_writes']==r['SRAM_mode_writes']==0
    ready,build,prior,readback=(Path(r[n]) for n in ('ready','build','prior','readback'));plan=read(build/'plan.json')
    oldwear=read(run/'host-wear-before.json');newwear=read(run/'host-wear-after.json')
    oldrecord=Path(read(run/'session-before.json')['wear_history']);assert oldrecord.read_bytes()==(run/'host-wear-before.json').read_bytes()
    before=[(run/f'before-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert list(map(sha,before))==plan['source_sha256']
    assert sha(before[0])=='1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94'
    # Derive the sole reservation from the observed newest record, independently
    # of the plan's expected banks. No counter seeding or boot-policy change.
    seq,off,previous=max(records(before[3]));assert seq==1020 and len(records(before[3]))==7
    counts=[int.from_bytes(previous[64+3*n:67+3*n],'little') for n in range(32)]
    assert counts==oldwear['counts'] and oldwear['sequence']==1020 and counts[24]==26
    counts[24]+=1;row=bytearray(previous);row[8:12]=(1021).to_bytes(4,'little');row[136:139]=(27).to_bytes(3,'little')
    row[30:32]=crc(row[:30]).to_bytes(2,'little');row[252:254]=crc(row[:252]).to_bytes(2,'little')
    provider=(ready/'2609-EDU-SRAM-B3-8.bin').read_bytes();assert len(provider)==4096 and provider[:4]==b'ES\x01\x40' and provider[31]==0 and crc(provider)==0
    assert sha(provider)==plan['provider_sha256']
    expected=list(map(bytearray,before));assert expected[3][0x4600:0x4700]==b'\xff'*256
    expected[3][0x4600:0x4700]=row;expected[3][:4096]=provider;expected=list(map(bytes,expected))
    assert list(map(sha,expected))==plan['expected_sha256'] and expected[:3]==before[:3]
    evidence=[]
    for phase,want in (('before',before),('after-install',expected),('final',expected)):
        for repeat in (1,2):
            for bank in range(4):
                path=run/f'{phase}-r{repeat}-b{bank}.bin';assert path.read_bytes()==want[bank];evidence.append(path)
    finalrecords=records(expected[3]);assert len(finalrecords)==8 and max(finalrecords)==(1021,0x4600,bytes(row))
    assert row[7]==ord('S') and row[13]==0 and row[32:48]==previous[32:48] and row[160:164]==b'\xff'*4
    assert newwear['counts']==counts==plan['counts_after'] and newwear['sequence']==1021
    assert newwear['execution_report_sha256']==digest(run/'report.json') and newwear['added_erase_attempts']==[dict(bank=3,sector='8',count=1)]
    reserve=read(run/'wear-reservation.json');assert reserve['durable_before_confirmation'] and reserve['reserved_counts']==counts and reserve['erase_order']==['B3:8']
    device=(run/'2609-EDU-SRAM-B3-8-device.bin').read_bytes();assert device==expected[3][:4096]==provider
    (run/'B3-8-before-device.bin').write_bytes(before[3][:4096]);(run/'SNBT-C600-device.bin').write_bytes(row)
    originals=[(prior/f'SRAM-pass{n}-131072.bin').read_bytes() for n in (1,2)]
    assert len(originals[0])==131072 and originals[0]==originals[1] and sha(originals[0])==r['original_SRAM_sha256']
    for name in ('SRAM-before-install','SRAM-after-pass1','SRAM-after-pass2'):
        path=run/(name+'-console.txt');raw,mode=backup.parse(path.read_bytes());assert raw==originals[0]==originals[1] and mode==0x40
        assert raw==(run/(name+'-131072.bin')).read_bytes();evidence.extend((path,run/(name+'-131072.bin')))
    client=(ready/'2609-EDU-SRAM-RAM.bin').read_bytes();loaded=(run/'client-device-RAM.bin').read_bytes();sy=read(build/'symbols.json')['core/edu-client']
    immutable=sy['EC_IMM_END']-0x200;assert loaded[:immutable]==client[:immutable] and len(loaded)==len(client) and loaded[sy['EC_ERROR']-0x200]==0
    # Exact typed commands and exact raw RAM uploads; refuse any additional
    # installer/settings/SRAM write request in the complete captured transport.
    tx=[bytes.fromhex(v['hex']) for line in (run/'serial.jsonl').read_text().splitlines() if (v:=json.loads(line))['direction']=='TX']
    confirmation_times=[v['time'] for line in (run/'serial.jsonl').read_text().splitlines() if (v:=json.loads(line))['direction']=='TX' and bytes.fromhex(v['hex'])==b'INSTALL EDU\r']
    assert len(confirmation_times)==1 and datetime.fromisoformat(reserve['created_utc']).timestamp()<confirmation_times[0]
    def upload(body):return [b'L\r']+[body[n:n+64] for n in range(0,len(body),64)]
    reader=(readback/'payload/readback-RAM.bin').read_bytes()
    def flash_read():return [b'C1\r']+upload(reader)+[b'F'+bytes([n]) for _ in (1,2) for n in range(4)]+[b'M']
    def setup(prefix):return [b'?\r',b'S\r',b'V\r']+([b'A\r',b'V\r'] if r[prefix+'_disabled_CB_ack'] else [])
    onepass=[f'R {a:05X} 40\r'.encode() for a in range(0,131072,64)]
    preflight=(ready/'2609-EDU-SRAM-PREFLIGHT-RAM.bin').read_bytes();installer=(ready/'2609-EDU-SRAM-INSTALL-RAM.bin').read_bytes()
    wanted=[b'\r']+flash_read()+[b'J',b'C1\r']+upload(preflight)+setup('preflight')+onepass+[b'V\r',b'Q\r',b'C1\r']
    wanted+=upload(installer)+[b'W\r',b'I\r',b'INSTALL EDU\r',b'V\r',b'Q\r']
    wanted+=flash_read()+[b'J',b'C1\r']+upload(client)+setup('client')+onepass+onepass
    wanted+=[b'V\r',b'Q\r',b'C1\r',b'A\r',f'D 0200 {0x200+len(client)-1:04X}\r'.encode(),b'J3\r',b'S']+flash_read()+[b'J']
    assert tx==wanted,'Unexpected command, payload or extra operation'
    result=(run/'installer-result.txt').read_bytes()
    assert result.find(b'C600\r\n')>=0 and result.find(b'8000\r\n')>result.find(b'C600\r\n')
    assert result.count(b'erase sector; verify blank\r\n')==1 and result.count(b'committed; entire action readback VERIFIED\r\n')==2
    assert (run/'final-REC.txt').read_bytes().endswith(b'REC> ') and read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    for name in ('2205','2512','2604'):
        path=run/(name+'-marker-before.json')
        if path.exists():assert path.read_bytes()==(ROOT/f'output/qualification/device-operations/{name}.json').read_bytes()
    info=dict(passed=True,hardware_evidence=True,report_sha256=digest(run/'report.json'),provider_sha256=sha(device),provider_CRC_valid=True,
        independently_derived_flash_postimage=True,B0_B1_B2_preserved=True,only_B3_8_and_C600_changed=True,C_D_erases=0,F_writes=0,
        prior_wear_counts_retained=True,single_recorded_erase=dict(bank=3,sector='8',before=26,after=27),sequence=1021,
        configuration_body_unchanged=True,default='S',enabled_banks=0,SRAM_bytes_each=131072,SRAM_sha256=sha(originals[0]),SRAM_mode='40',
        fresh_pre_install_and_two_post_install_arrays_match_both_originals=True,SRAM_read_replies_verified=6144,SRAM_writes=0,SRAM_mode_writes=0,
        client_immutable_RAM_verified=True,client_immutable_bytes=immutable,client_mutable_tail_bytes=len(client)-immutable,
        exact_serial_TX_sequence_verified=True,TX_records=len(tx),saved_setting_writes=0,final_REC=True,post_final_REC_commands=0,port_lease_idle=True,
        audit_source_sha256=digest(__file__),live_wrapper_sha256=digest(HERE/'board_edu_sram_install_2609.py'),host_wear_after_sha256=digest(run/'host-wear-after.json'),
        evidence={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in evidence})
    (run/'audit.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    text=f'''# 2609 ES1 EDU/SRAM provider — installed and verified

**PASS:** `2609-EDU-SRAM-INSTALL-RAM.bin` ran over USB COM8 / A10MPQXCA.
It appended the C600 wear reservation (commit last), erased/programmed B3:8,
verified the complete provider and committed $801F last. Exactly one sector
erase: **B3:8 count 26 → 27**. Every other count and unknown prior-lifetime mask
FFFFFFFF are retained. Journal sequence is **1021**, default **S**, banks **00**.
The saved configuration body is unchanged; no CONFIG command was sent.

| File | Bytes | SHA-256 |
|---|---:|---|
| `2609-EDU-SRAM-INSTALL-RAM.bin` | {len(installer)} | `{sha(installer)}` |
| `2609-EDU-SRAM-B3-8-device.bin` | 4096 | `{sha(provider)}` |
| `2609-EDU-SRAM-RAM.bin` | {len(client)} | `{sha(client)}` |
| `SRAM-before-install-131072.bin` | 131072 | `{sha(originals[0])}` |
| `SRAM-after-pass1-131072.bin` | 131072 | `{sha(originals[0])}` |
| `SRAM-after-pass2-131072.bin` | 131072 | `{sha(originals[0])}` |

Both original backups from step16 remain intact. One fresh pre-install array
and two complete reads through the installed provider match **both** originals
byte for byte. All 6144 ordered 64-byte replies pass address/status/count/mode
checks; mode stays **40**. No SRAM data/mode write, presence/alias probe, format,
repartition, RTC/EEPROM or saved-setting operation was requested. These reads
do not separately qualify battery retention or non-aliasing physical capacity.

All four flash banks were independently read twice before, twice immediately
after installation, and twice after the provider/SRAM exercise. The audit
derives the final image from the observed old journal and the qualified provider:
only B3:8000–8FFF and C600–C6FF differ. B0 (original WDCMONV2), B1/B2,
B3:9, MON A/B, the old journals, VX1 E and F are retained. Provider readback
matches the 4096-byte payload, full CRC residue zero and committed header.

The installed-provider client passed its startup/header/CRC guards and its
immutable {immutable}-byte prefix matched an independent MON dump. Its
{len(client)-immutable}-byte mutable tail is recorded separately. The complete
sequence of {len(tx)} serial TX records matches the permitted commands and RAM
payloads. The durable host erase reservation precedes confirmation; the new
verified host wear record is linked to the final execution report.

Finished at **REC>**, port closed and lease idle, no commands after final REC.
Stop before configuration changes. ES1 remains an explicitly invoked read-only
service; named storage/WORK and saved EDU ON/OFF remain future ports. The old
seq1020/C600 CONFIG exercise and old exact-state installers are now stale and
must be regenerated before any later use.

[Complete console](console-log.txt) · [Installer console](installer-result.txt)
· [Report](report.json) · [Independent audit](audit.json)
· [Provider readback](2609-EDU-SRAM-B3-8-device.bin)
· [Before SRAM](SRAM-before-install-131072.bin)
· [After SRAM 1](SRAM-after-pass1-131072.bin) · [After SRAM 2](SRAM-after-pass2-131072.bin)
· [Wear before](host-wear-before.json) · [Wear after](host-wear-after.json)
· [Reservation](wear-reservation.json) · [Final REC](final-REC.txt).
'''
    (run/'receipt.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:info[k] for k in ('passed','provider_CRC_valid','only_B3_8_and_C600_changed','single_recorded_erase','sequence','SRAM_sha256','fresh_pre_install_and_two_post_install_arrays_match_both_originals','final_REC')},indent=2))
    return info


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);audit(parser.parse_args().run)
