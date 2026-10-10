"""Build the standalone named SRAM utility. No serial ports or board writes."""
import argparse,hashlib,json
from pathlib import Path
from build_bank_maint_v2 import long_branches
from beta4_migration import s19
from build_v2_spi_resident import assemble
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-spi-resident/store'

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--build',type=Path,default=ROOT/'BUILD/v2-spi-resident');parser.add_argument('--streams',action='store_true');args=parser.parse_args();OUT=args.build.resolve()/'store'
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    src=ROOT/'tools/v2-spi/sram-store.asm'
    text=src.read_text()
    if args.streams:
        text=text.replace('TITLE DB "SRAM 1.1"','TITLE DB "SRAM 1.2"')
        text=text.replace('APP_END:\n','SOURCE_BYTE_HOOK DS 2\nSAVE_TRANSFER_HOOK DS 2\nRESTORE_TRANSFER_HOOK DS 2\nAPP_END:\n')
    cut=text.index('SV_MAGIC DB')
    (stage/'sram-data.asm').write_text('        MODULE SRAM_DATA\n        XDEF DATA_END\n        CODE\n'+text[cut:].replace('APP_END:','DATA_END:'))
    data,ds,_=assemble(stage,'sram-data',0x6700,'DATA_END',0x6700)
    assert len(data)<=256,len(data)
    (stage/'store-data-eq.inc').write_text(''.join(f'{n} EQU ${a:04X}\n' for n,a in ds.items() if 0x6700<=a<ds['DATA_END']))
    ext=b'';es={}
    if args.streams:
        (stage/'sram-stream.asm').write_text(long_branches((ROOT/'tools/v2-spi/sram-stream.asm').read_text()))
        (stage/'stream-core-eq.inc').write_text('TRANSFER EQU $6C00\n')
        ext,es,_=assemble(stage,'sram-stream',0x7B90,'EXT_END',0x7B90);assert len(ext)<=112
        (stage/'stream-eq.inc').write_text(''.join(f'{n} EQU ${es[n]:04X}\n' for n in ('SOURCE_BYTE','SAVE_TRANSFER','RESTORE_TRANSFER','COPY_BEGIN')))
        text=text.replace('SAVE_CRC_LOOP:\n        LDY #0\n        LDA (PTR),Y','SAVE_CRC_LOOP:\n        LDY #0\n        JSR SOURCE_BYTE')
        text=text.replace('SAVE_WRITE_LOOP:\n        JSR CHUNK\n        LDA #2\n        JSR TRANSFER','SAVE_WRITE_LOOP:\n        JSR CHUNK\n        JSR SAVE_TRANSFER')
        text=text.replace('RESTORE_LOOP:\n        JSR CHUNK\n        LDA #1\n        JSR TRANSFER','RESTORE_LOOP:\n        JSR CHUNK\n        JSR RESTORE_TRANSFER')
        text=text.replace('RESTORE_CRC:\n        LDA (PTR),Y','RESTORE_CRC:\n        JSR SOURCE_BYTE').replace('        INC COPYING\n','        JSR COPY_BEGIN\n')
        text=text.replace('        CODE\n','        INCLUDE "stream-eq.inc"\n        CODE\n',1)
    aux_src=ROOT/'tools/v2-spi/sram-layout.asm'
    (stage/aux_src.name).write_text(long_branches(aux_src.read_text()))
    def core_eq(symbols):
        (stage/'store-core-eq.inc').write_text(''.join(f'{n} EQU ${symbols[n]:04X}\n' for n in ('HEADER_CRC','READ_BLOCK'))+'BUF EQU $6400\n')
    core_eq(dict(HEADER_CRC=0x6C00,READ_BLOCK=0x6C00))
    aux,aas,_=assemble(stage,'sram-layout',0x6800,'AUX_END',0x6800)
    (stage/'store-aux-eq.inc').write_text(''.join(f'{n} EQU ${aas[n]:04X}\n' for n in ('SELECT_LAYOUT','EXTENT_LIMIT','FREE_PAGES','FORMAT_GUARD')))
    cut=text.index('SV_MAGIC DB')
    text=text[:cut].replace('        CODE\n','        INCLUDE "store-data-eq.inc"\n        INCLUDE "store-aux-eq.inc"\n        CODE\n',1)+'APP_END:\n        ENDMOD\n        END\n'
    (stage/src.name).write_text(long_branches(text))
    body,symbols,cells=assemble(stage,'sram-store',0x6C00,'APP_END',0x6C06)
    if args.streams:
        (stage/'stream-core-eq.inc').write_text(f'TRANSFER EQU ${symbols["TRANSFER"]:04X}\n')
        ext,es2,_=assemble(stage,'sram-stream',0x7B90,'EXT_END',0x7B90);assert es2==es or all(es2[n]==es[n] for n in ('SOURCE_BYTE','SAVE_TRANSFER','RESTORE_TRANSFER','COPY_BEGIN'))
        es=es2
    core_eq(symbols);aux,aas2,_=assemble(stage,'sram-layout',0x6800,'AUX_END',0x6800)
    assert all(aas2[n]==aas[n] for n in ('SELECT_LAYOUT','EXTENT_LIMIT','FREE_PAGES','FORMAT_GUARD')) and len(aux)<=256,len(aux)
    assert symbols['APP_END']<=0x7800,hex(symbols['APP_END'])
    # The saved R SRAM image loads at 4000. Its small bootstrap relocates the
    # linked utility into the foreground sector-staging workspace, not user RAM.
    size=len(body);source=0x4040
    stub=bytes((0x78,0xD8,0xA9,source&255,0x85,0xD2,0xA9,source>>8,0x85,0xD3,
                0xA9,0,0x85,0xD4,0xA9,0x6C,0x85,0xD5,0xA2,size>>8,0xA0,0,
                0xB1,0xD2,0x91,0xD4,0xC8,0xD0,0xF9,0xE6,0xD3,0xE6,0xD5,
                0xCA,0xD0,0xF2,
                0xA9,0x67,0x85,0xD5,0x64,0xD4,0xA2,2,0xA0,0,
                0xB1,0xD2,0x91,0xD4,0xC8,0xD0,0xF9,0xE6,0xD3,0xE6,0xD5,
                0xCA,0xD0,0xF2,0x4C,0,0x6C))
    # Page-rounded copy includes zero-filled state and padding.
    pages=(size+255)//256;stub=bytearray(stub);stub[19]=pages
    packed=bytes(stub)+bytes(64-len(stub))+body+bytes(pages*256-size)+data+bytes(256-len(data))+aux+bytes(256-len(aux))
    core_offset=64;data_offset=64+pages*256;aux_offset=data_offset+256;ext_offset=aux_offset+256
    if args.streams:
        # Legacy bootstrap remains a valid transport image; normal R SRAM uses
        # the preserving system loader. Extend bootstrap to copy hook code.
        bootstrap=bytearray(stub[:-3]);bootstrap[2]=0xA9;bootstrap[3]=0x80;bootstrap[6]=0xA9;bootstrap[7]=0x40
        extension_source=0x4000+128+pages*256+512
        bootstrap+=bytes((0xA9,extension_source&255,0x85,0xD2,0xA9,extension_source>>8,0x85,0xD3,0xA0,0))
        bootstrap+=bytes((0xB1,0xD2,0x99,0x90,0x7B,0xC8,0xC0,96,0xD0,0xF6,0x4C,0,0x6C))
        assert len(bootstrap)<=128 and len(ext)<=96
        packed=bytes(bootstrap)+bytes(128-len(bootstrap))+body+bytes(pages*256-size)+data+bytes(256-len(data))+aux+bytes(256-len(aux))+ext+bytes(96-len(ext))
        from beta4_migration import crc
        packed+=crc(packed).to_bytes(2,'big')
        core_offset=128;data_offset=128+pages*256;aux_offset=data_offset+256;ext_offset=aux_offset+256
        (OUT/'store-stream.bin').write_bytes(ext)
    assert len(stub)<=64 and 0x4000+len(packed)<=0x6500
    (OUT/'store-core.bin').write_bytes(body);(OUT/'sram.bin').write_bytes(packed)
    (OUT/'store-data.bin').write_bytes(data)
    (OUT/'store-layout.bin').write_bytes(aux)
    (OUT/'sram.s19').write_bytes(s19(dict(enumerate(packed,0x4000)),0x4000))
    meta=dict(version='1.2' if args.streams else '1.1',entry=0x4000,load_end=0x4000+len(packed)-1,streams=args.streams,core_offset=core_offset,data_offset=data_offset,aux_offset=aux_offset,ext_offset=ext_offset,ext_bytes=len(ext),
        relocated_start=0x6C00,relocated_end=symbols['APP_END']-1,core_bytes=size,data_bytes=len(data),data_start=0x6700,aux_bytes=len(aux),
        bytes=len(packed),symbols=symbols|ds|aas|es,sha256=hashlib.sha256(packed).hexdigest(),
        source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),aux_source_sha256=hashlib.sha256(aux_src.read_bytes()).hexdigest())
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('SRAM '+meta['version']+':',size,'core bytes;',len(aux),'layout bytes;',len(packed),'saved bytes; relocated end',hex(symbols['APP_END']-1))

if __name__=='__main__':main()
