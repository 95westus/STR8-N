"""Inspect the permanent 2604 double capture; no serial access or image writes."""
import binascii,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from installer.engine.runtime import clean_journal,sha
from installer.engine.legacy_transport import config_sum,slot_valid
from inventory_boards_readonly import durable

ARCHIVE=ROOT/'local-archives/STR8-N-rc1-g0034-2604-20261102'
CAPTURE=ARCHIVE/'live-board'
F_HASH='78ee949e20545cbe0e10030185dd5629b65c584af526c16e2c75c9fa103ceaec'


def inspect(capture):
    receipt=json.loads((capture/'report.json').read_text())
    assert receipt['passed'] and receipt['owner_RAM_unchanged'] and receipt['owner_ZP_unchanged']
    assert receipt['provider_cache_unchanged'] and receipt['vectors_unchanged'] and receipt['port_released']
    banks=[]
    for n in range(4):
        a=(capture/f'b{n}.bin').read_bytes();b=(capture/f'b{n}-repeat.bin').read_bytes()
        assert len(a)==32768 and a==b and sha(a)==receipt['bank_sha256'][f'B{n}']
        banks.append(a)
    assert sha(banks[3][-4096:])==F_HASH
    for n,page in ((0x2000,0xa0),(0x3000,0xb0)):
        slot=banks[3][n:n+4096]
        assert slot_valid(slot,page) and int.from_bytes(slot[8:12],'little')==0x34
    seq,offset,row,valid=clean_journal(banks)
    for _,_,r in valid:assert r[22:24]==config_sum(r[8:24]),'Invalid historical config checksum'
    counts=[max(int.from_bytes(r[24+i*3:27+i*3],'little') for _,_,r in valid) for i in range(32)]
    cfg=row[8:24]
    assert cfg[0]==1 and cfg[1]<2 and cfg[2]<4 and cfg[5]>=10 and cfg[6]<2
    assert cfg[7:9] in (b'P\xa0',b'P\xb0')
    generation=int.from_bytes(cfg[9:13],'little')
    assert generation==0x34
    records=[]
    for s,o,r in sorted(valid):
        records.append(dict(address=f'B3:{o+0x8000:04X}',sequence=s,sha256=sha(r),config=r[8:24].hex()))
    metadata=[];latest={}
    for off in range(0x1c00,0x2000,32):
        r=banks[3][off:off+32]
        if r==b'\xff'*32:continue
        assert r[:4] in (b'TZ\1\0',b'BN\1\0',b'BA\1\0',b'EI\1\0',b'ED\1\0'),'Unrecognized metadata row; inspect before conversion'
        assert r[30:]==b'\xff\0' and binascii.crc_hqx(r[:28],65535)==int.from_bytes(r[28:30],'little')
        kind=r[:2].decode('ascii');s=int.from_bytes(r[4:8],'little')
        item=dict(address=f'B3:{off+0x8000:04X}',kind=kind,sequence=s,sha256=sha(r),raw=r.hex())
        metadata.append(item)
        if kind in latest and s==latest[kind]['sequence']:assert r.hex()==latest[kind]['raw'],'Conflicting metadata'
        if kind not in latest or s>latest[kind]['sequence']:latest[kind]=item
    decoded={}
    if 'TZ' in latest:decoded['offset_minutes']=int.from_bytes(bytes.fromhex(latest['TZ']['raw'])[8:10],'little',signed=True)
    if 'BN' in latest:
        r=bytes.fromhex(latest['BN']['raw']);assert r[8]<=8
        decoded['board_name']=r[9:9+r[8]].decode('ascii')
    return dict(board='2604',status='INSPECTED_HOST_ONLY_NOT_WRITE_AUTHORIZATION',source_F_sha256=F_HASH,
        bank_sha256={f'B{n}':sha(b) for n,b in enumerate(banks)},source_journal_format='WC v1 / 128 bytes',
        original_records=records,sequence=seq,latest_address=f'B3:{offset+0x8000:04X}',counts=counts,
        counts_semantics='tracked lower bounds; prior/direct lifetime unknown',prior_unknown_mask='ffffffff',
        config_hex=cfg.hex(),config_decoded=dict(version=cfg[0],application_autostart_enabled=bool(cfg[1]),
            application_bank=cfg[2],application_address=f'{int.from_bytes(cfg[3:5],"little"):04X}',
            application_delay_tenths=cfg[5],application_vector_mode=bool(cfg[6]),
            preferred_monitor='A' if cfg[8]==0xa0 else 'B',preferred_generation=generation,
            application_reserved_byte=cfg[13]),
        metadata_records=metadata,latest_metadata=latest,metadata_decoded=decoded,
        metadata_preservation='Retain every raw byte of B3:9C00-9FFF in the new provider sector',
        raw_L_supported=False,legacy_load='MON L: load-only S0/S1/S9; read back RAM, then explicit G',
        migration_requirement='Separate inspected WC-to-SNBT conversion; existing public upgrader must still refuse this source',
        flash_writes=0,board_access=False)


def run():
    result=inspect(CAPTURE)
    out=ARCHIVE/'legacy-inspection';out.mkdir()
    durable(out/'inspection.json',(json.dumps(result,indent=2)+'\n').encode())
    for item in result['original_records']:
        address=int(item['address'].split(':')[1],16)
        body=(CAPTURE/'b3.bin').read_bytes()[address-0x8000:address-0x8000+128]
        durable(out/f'WC-{address:04X}-seq{item["sequence"]}.bin',body)
    durable(out/'original-CD-8192.bin',(CAPTURE/'b3.bin').read_bytes()[0x4000:0x6000])
    durable(out/'original-metadata-1024.bin',(CAPTURE/'b3.bin').read_bytes()[0x1c00:0x2000])
    print(json.dumps({k:result[k] for k in ('board','sequence','latest_address','counts','config_decoded','metadata_decoded')},indent=2))


if __name__=='__main__':run()
