"""Prepare reviewable2609 postimages from captures; no ports or execution."""
import binascii
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(KIT/'tools'))
from native_journal_room import inspect
from nf_migrate import valid_snapshot

sha=lambda b:hashlib.sha256(b).hexdigest()
crc=lambda b:binascii.crc_hqx(b,65535)


def main():
    source=ROOT/'output/qualification/2609-mon-features-ram-20261030-r3'
    out=ROOT/'output/qualification/2609-mon-feature-install-scope-20261030'
    out.mkdir(exist_ok=False)
    banks=[(source/f'before-1-b{n}.bin').read_bytes() for n in range(4)]
    assert all(b==(source/f'before-2-b{n}.bin').read_bytes() for n,b in enumerate(banks))
    room=inspect(banks[3]);assert room['sequence']==1024 and room['ordinary_blank_pages']==['CA00','CB00','CC00','CD00','CE00']
    service=KIT/'monitors/candidates/services-g00000003-r5'
    mon=KIT/'monitors/candidates/g00000008-r2'
    sm=json.loads((service/'manifest.json').read_text())['artifacts']
    mm=json.loads((mon/'manifest.json').read_text())['artifacts']
    def image(root,items,variant):
        name,meta=next((n,m) for n,m in items.items() if m['variant']==variant)
        data=(root/name).read_bytes();assert sha(data)==meta['sha256'] and len(data)==meta['bytes']
        return data
    bundle=image(service,sm,'B2 bundle')
    e=image(service,sm,'E')
    b=image(mon,mm,'B')
    targets=[(2,0x8000,bundle[:4096]),(2,0x9000,bundle[4096:8192]),
             (2,0xa000,bundle[8192:]),(3,0xe000,e),(3,0xb000,b)]
    expected=list(map(bytearray,banks));row=bytearray(banks[3][0x4900:0x4a00])
    assert valid_snapshot(row)
    oldcounts=[int.from_bytes(row[64+3*i:67+3*i],'little') for i in range(32)]
    steps=[]
    for index,(bank,address,body) in enumerate(targets):
        count_index=bank*8+(address//4096-8)
        offset=64+3*count_index
        before=int.from_bytes(row[offset:offset+3],'little')
        row[offset:offset+3]=(before+1).to_bytes(3,'little')
        row[8:12]=(1025+index).to_bytes(4,'little')
        row[30:32]=crc(row[:30]).to_bytes(2,'little')
        row[252:254]=crc(row[:252]).to_bytes(2,'little')
        row[255]=0;assert valid_snapshot(row)
        dest=0xca00+index*256
        assert expected[3][dest-0x8000:dest-0x7f00]==b'\xff'*256
        expected[3][dest-0x8000:dest-0x7f00]=row
        original=banks[bank][address-0x8000:address-0x7000]
        expected[bank][address-0x8000:address-0x7000]=body
        (out/f'original-B{bank}-{address:04X}.bin').write_bytes(original)
        (out/f'target-B{bank}-{address:04X}.bin').write_bytes(body)
        (out/f'journal-{dest:04X}.bin').write_bytes(row)
        steps.append(dict(target=f'B{bank}:{address:04X}',bytes=4096,original_sha256=sha(original),
                          target_sha256=sha(body),journal_page=f'{dest:04X}',sequence=1025+index,
                          counter_before=before,counter_after=before+1))
    for n,data in enumerate(expected):(out/f'expected-B{n}.bin').write_bytes(data)
    for off in range(0x4000,0x6000,256):
        if valid_snapshot(banks[3][off:off+256]):assert expected[3][off:off+256]==banks[3][off:off+256]
    assert expected[3][0x7000:]==banks[3][0x7000:]
    assert expected[0]==banks[0] and expected[1]==banks[1]
    result=dict(status='REVIEW_ONLY_NOT_AUTHORIZED_OR_EXECUTED',board='2609',CPU='65C816 emulation',
                source_capture=str(source),source_bank_sha256=list(map(sha,banks)),
                expected_bank_sha256=list(map(sha,expected)),scope='MON B first; keep A and every old raw journal row',
                sector_erases=5,journal_appends=5,C_D_erases=0,F_writes=0,
                boot_settings='Default S, mask00, entries8000 and all policy bytes preserved',
                sequence_after=1029,valid_records_after=16,steps=steps,
                original_A_retained_execution_unqualified=True,SRAM_data_writes=0,
                RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,
                all_old_journal_rows_preserved=True,
                journal_room_after='No ordinary slots remain; CF00 is reserved, next write requires reviewed D rotation',
                full_AB_alternative=dict(component_erases=6,journal_D_erases=1,total_erases=7,
                    journal_records_written=7,sequence_after=1031,valid_records_after=17,
                    oldest_D_record_sequence_1014='Must be archived on host before D erase; all C records retained',
                    default='S unchanged',F_writes=0))
    (out/'plan.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
