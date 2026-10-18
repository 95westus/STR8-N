"""Build isolated beta24 / MAINT 2.0 board-name candidate; never open ports."""
import hashlib
import json
import shutil
from pathlib import Path

import build_v2_status as status
from build_v2_local_time import main as local_time
from build_bank_maint_v2 import long_branches
from beta4_migration import s19

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-board-name'


def name_writer():
    # Reuse the qualified OFFSET append protocol, including readback before
    # committing, saved worker ZP/bank/LED, and refusing erase/sequence wrap.
    text = (ROOT/'tools/v2-rtc/clock-offset.inc').read_text()
    text = text[text.index('OFFSET_SAVE:\n'):text.index('OFFSET_WORD DB')]
    text = text.replace('OFFSET_', 'BN_').replace('TZ_READ', 'BN_READ')
    text = text.replace('BN_HEADER', 'BN_RECORD_HEADER')
    text = text.replace('TZ_FREE', 'BN_FREE').replace('TZ_SEQ', 'BN_SEQ').replace('TZ_MAGIC', 'BN_MAGIC')
    first = text.index('        LDA BN_PENDING\n')
    last = text.index('        LDA #<BN_RECORD_BYTES\n', first)
    text = text[:first]+'''        LDA BN_PENDING_LENGTH
        STA BN_RECORD_BYTES+8
        LDX #7
BN_PAYLOAD:
        LDA BN_PENDING,X
        STA BN_RECORD_BYTES+9,X
        DEX
        BPL BN_PAYLOAD
'''+text[last:]
    first = text.index('        LDA TZ_OFFSET\n')
    last = text.index('        SEC\n        RTS\n', first)
    text = text[:first]+'''        LDA BN_LENGTH
        CMP BN_PENDING_LENGTH
        BNE BN_REFUSE
        LDX #7
BN_READBACK:
        LDA BN_TEXT,X
        CMP BN_PENDING,X
        BNE BN_REFUSE
        DEX
        BPL BN_READBACK
'''+text[last:]
    return text+'''BN_JOURNAL_MAGIC DB "PJ",6,1
BN_BANK DB 0
BN_LED DB 0
BN_INDEX DB 0
BN_ERROR DB 0
BN_RECORD_BYTES DS 32
BN_ZP DS 32
'''


def maint():
    folder=OUT/'maint';stage=folder/'asm'
    meta=json.loads((OUT/'build.json').read_text())
    path=folder/'bank-maint.asm'
    # Build from the existing qualified storage MAINT source copied by firmware.
    sources=list(folder.glob('*2000.asm'))
    if not sources:
        sources=[folder/'str8n-bank-maint-2000.asm']
    source=next(p for p in sources if p.exists())
    text=source.read_text().replace('1.8','2.0')
    marker='                        STZ INDEX\n'
    assert text.count(marker)==1
    text=text.replace(marker,'                        JSR BN_TRY\n'+marker,1)
    text=text.replace('HELP:                   DB','HELP:                   DB "NAME [1-8 characters | CLEAR] (YES required)",13,10\n                        DB',1)
    local=(ROOT/'tools/v2-rtc/local-time.inc').read_text()
    crc=local[local.index('TZ_CRC:\n'):local.index('TZ_ABS:\n')]
    extra=f"BN_FLASH_BYTE EQU ${meta['worker']['V2W_BYTE']:04X}\nTZ_PTR EQU $D6\nTZ_SUM DS 2\n"
    extra+=crc+(ROOT/'tools/v2-rtc/board-name.inc').read_text()
    extra+=(ROOT/'tools/v2-rtc/maint-board-name.inc').read_text()+name_writer()
    text=text.replace('BM_END:',extra+'\nBM_END:',1)
    path.write_text(long_branches(text).replace('BM_LONG_','BN_LONG_'))
    link=status.spi.compiler;link.OUT=folder;link.SOURCE=stage
    def compile():return link.assemble('bank-maint',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=path)
    cells,s=compile();cells,s=status.spi.relax_branches(path,cells,s,compile)
    body=link.dense_image(cells,0x2000,s['BM_END'])
    assert s['BM_END']<=0x5000
    record=b'SR\x01\x3F\0\x20'+len(body).to_bytes(2,'little')+b'MAINT'.ljust(16,b'\0')+body
    size=(len(record)+4095)//4096*4096
    assert size<=12288
    record+=b'\xff'*(size-len(record))
    name=f'str8n-maint-2.0-b1-8000-{0x8000+size-1:04x}.bin'
    (OUT/name).write_bytes(record)
    (folder/'str8n-bank-maint-2.0-2000.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    (folder/'board-name.bin').write_bytes(body)
    manifest=dict(version='2.0',entry=0x2000,bytes=len(body),end=s['BM_END'],symbols=s,program_sha256=hashlib.sha256(body).hexdigest(),storage_sha256=hashlib.sha256(record).hexdigest(),storage_bytes=size,storage_file=name,hardware_tested=False)
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    old=meta['maintenance_storage_file'];meta['artifacts'].pop(old,None)
    meta.update(maintenance_version='2.0',maintenance_storage_file=name)
    meta['artifacts'][name]=manifest['storage_sha256']
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('UNFLASHED MAINT 2.0:',len(body),'bytes; NAME limit 8; no automatic erase')


def main():
    status.SPI_STARTUP_ACK=True
    status.COMPACT_BOOT_LOCAL=True
    status.BOARD_NAME=True
    local_time(build='BUILD/v2-board-name',version='2.0b24',generation=33)
    maint()


if __name__=='__main__':main()
