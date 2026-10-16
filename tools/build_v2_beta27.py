"""Relocate beta27 utilities to B2; retain the fixed recovery/extension ABI."""
import json,re,shutil
from pathlib import Path
import build_v2_config as compiler
import build_v2_recovery as fw
from beta4_migration import crc,s19
from build_v2_spi_resident import assemble,sha

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'BUILD/v2-beta26'
OUT=ROOT/'BUILD/v2-beta27'

def replace(path,old,new,count=1):
    text=path.read_text();assert text.count(old)==count,(path,old,text.count(old))
    path.write_text(text.replace(old,new))

def main():
    assert not list(OUT.glob('hardware-qualification-*.json')), 'Preserve qualified package'
    parent=json.loads((BASE/'build.json').read_text())
    receipt=json.loads((BASE/'hardware-qualification-2609.json').read_text());assert receipt['passed']
    for name,digest in parent['artifacts'].items():assert sha((BASE/name).read_bytes())==digest,name
    shutil.copytree(BASE,OUT,dirs_exist_ok=True)
    for p in list(OUT.glob('*test-results.json'))+list(OUT.glob('hardware-qualification-*.json')):p.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    meta=dict(parent)
    # Relink the SRAM copy finalizer: all four transport fragments move +$1000.
    stage=OUT/'storage-status/source'
    p=stage/'status-links.inc';text=p.read_text()
    text=re.sub(r'(SRAM_(?:CORE|DATA|AUX|EXT)_SOURCE EQU \$)([0-9A-F]{4})',lambda m:m[1]+f'{int(m[2],16)+0x1000:04X}',text)
    p.write_text(text)
    raw=(ROOT/'tools/v2-spi/storage-services.inc').read_text()
    first,last=raw.index('FINALIZER:\n'),raw.index('FINAL_END:\n')
    final='        MODULE STORAGE_FINAL\n        XDEF FINAL_END\n        INCLUDE "str8n-v2-eq.inc"\n        INCLUDE "status-links.inc"\n        CODE\n'+raw[first:last]+'FINAL_END:\n        ENDMOD\n'
    (stage/'storage-finalizer.asm').write_text(final)
    body,_,_=assemble(stage,'storage-finalizer',0x6B00,'FINAL_END',0x6B00)
    assert len(body)<=256
    (stage/'storage-finalizer.bin.inc').write_text(''.join('        DB '+','.join(f'${v:02X}' for v in body[i:i+16])+'\n' for i in range(0,len(body),16)))
    replace(stage/'storage-services.inc','LDA #$A0','LDA #$B0',2)
    replace(stage/'storage-services.inc','CMP #$C8','CMP #$D8')
    replace(stage/'local-loader.inc','LDA #$E0','LDA #$F0')
    body,symbols,_=assemble(stage,'storage-status',0x6E00,'APP_END',0x6E07)
    assert len(body)<=2558
    asset=body+b'\xff'*(2558-len(body));asset+=crc(asset).to_bytes(2,'big')
    (OUT/'boot-status/asset.bin').write_bytes(asset)
    # All externally called EF entry addresses remain fixed.
    stage=OUT/'loader/source'
    for old,new in [('LDX #$C8','LDX #$D8'),('LDX #$E8','LDX #$F8'),('LDX #$D2','LDX #$E2')]:replace(stage/'version-loader.asm',old,new)
    loader,ls,_=assemble(stage,'version-loader',0xEF00,'AUX_END',0xEF0C)
    assert len(loader)<=254
    e=bytearray((BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes())
    e[0xF00:0xFFE]=loader+b'\xff'*(254-len(loader));e[-2:]=crc(e[:-2]).to_bytes(2,'big')
    assert crc(e)==crc(e[:0x800])==0
    (OUT/'str8n-v2-recovery-e000-efff.bin').write_bytes(e)
    (OUT/'str8n-v2-recovery-e000-efff.s19').write_bytes(s19(dict(enumerate(e,0xE000)),0xF004))
    # MAINT's map checks wrap $FFFF->$0000 when validating the VERSION asset.
    stage=OUT/'maint/beta27-source'
    shutil.copytree(BASE/'maint/map-source',stage,dirs_exist_ok=True)
    text=(BASE/'maint/bank-maint.asm').read_text()
    text=text.replace('BANK MAINT 2.1','BANK MAINT 2.2')
    text=text.replace('B2:C800-D1FF status; B2:E local/board + VERSION.','B2:D800-E1FF status; B2:F local/board + VERSION.')
    begin=text.index('X_FIND_FLASH:');end=text.index('X_FIND_READ:',begin)
    part=text[begin:end].replace('CMP #$C8','CMP #$D8').replace('CMP #$D0','CMP #$E0').replace('LDA #$D0','LDA #$E0')
    text=text[:begin]+part+text[end:]
    begin=text.index('MAP_FIRMWARE:')
    part=text[begin:]
    translations={'D0':'E0','E0':'F0','E7':'F7','E8':'F8','F0':'00','C8':'D8','D2':'E2'}
    part=re.sub(r'#\$(D0|E0|E7|E8|F0|C8|D2)\b',lambda m:'#$'+translations[m[1]],part)
    part=part.replace('C800-D1FF','D800-E1FF').replace('E000-E6FF; VERSION E800-EFFF','F000-F6FF; VERSION F800-FFFF')
    text=text[:begin]+part
    (stage/'bank-maint.asm').write_text(text)
    maint,ms,_=assemble(stage,'bank-maint',0x2000,'BM_END',0x2007)
    assert len(maint)+24<=12288 and ms['BM_END']<=0x5000
    (OUT/'maint/bank-maint.asm').write_text((stage/'bank-maint.asm').read_text())
    record=b'SR\x01\x3f\x00\x20'+len(maint).to_bytes(2,'little')+b'MAINT'.ljust(16,b'\0')+maint
    record+=b'\xff'*(12288-len(record))
    name='str8n-maint-2.2-b2-8000-afff.bin';(OUT/name).write_bytes(record)
    (OUT/'maint/board-name.bin').write_bytes(maint)
    (OUT/'maint/str8n-bank-maint-2.2-2000.s19').write_bytes(s19(dict(enumerate(maint,0x2000)),0x2000))
    (OUT/'maint/manifest.json').write_text(json.dumps(dict(version='2.2',entry=0x2000,bytes=len(maint),end=ms['BM_END'],symbols=ms,program_sha256=sha(maint),storage_sha256=sha(record),storage_bytes=len(record),storage_file=name,hardware_tested=False),indent=2)+'\n')
    # Same monitor instruction layout; the running slot reports beta27.
    messages=json.loads((OUT/'source/str8n-v2-text.json').read_text())
    first=next(i for i,m in enumerate(messages) if m['name']=='V2_BAD_PREFIX');pool=bytearray()
    for i,message in enumerate(messages):
        raw=bytearray(message['text'].replace('{version}','2.0b27').encode())
        if i<first:raw=raw[4:]
        raw[-1]|=128;pool.extend(raw)
    compiler.include_bytes(OUT/'asm/text-image.inc',pool)
    p=OUT/'asm/text-image.inc';p.write_text('V2_TEXT:\n'+p.read_text())
    compiler.OUT,compiler.SOURCE=OUT,OUT/'asm';fw.OUT=OUT
    slots={};monitors={}
    for page in (0xA0,0xB0):
        cells,sym=compiler.assemble(f'monitor-{page:02x}',(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=BASE/'asm'/f'monitor-{page:02x}.asm')
        body=compiler.dense_image(cells,(page<<8)+128,sym['V2_END'])
        prior=(BASE/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
        assert len(body)==3967 and sum(a!=b for a,b in zip(body,prior[128:128+len(body)]))==1
        slot=bytearray(fw.slot_image(body,sym,page,39,meta['boot_compatibility']))
        slot[70:72]=sym['V2_M_EDIT'].to_bytes(2,'little');slot[18:20]=crc(slot[:18]+slot[32:]).to_bytes(2,'little')
        stem=f'str8n-v2-recovery-slot-{page:02x}';(OUT/(stem+'.bin')).write_bytes(slot)
        (OUT/(stem+'.s19')).write_bytes(s19(dict(enumerate(slot,page<<8)),0xF004))
        slots[page]=slot;monitors[f'{page:02x}']=sym
    image=bytearray((BASE/'str8n-v2-recovery-a000-dfff.bin').read_bytes());image[:4096]=slots[0xA0];image[4096:8192]=slots[0xB0]
    (OUT/'str8n-v2-recovery-a000-dfff.bin').write_bytes(image)
    (OUT/'str8n-v2-recovery-a000-dfff.s19').write_bytes(s19(dict(enumerate(image,0xA000)),0xF004))
    folder=OUT/'migrator';p=folder/'rtc-migrator.asm'
    replace(p,'STR8-N 2.0b26 RTC/I2C MIGRATOR','STR8-N 2.0b27 RTC/I2C MIGRATOR')
    compiler.OUT,compiler.SOURCE=folder,folder/'asm'
    cells,sy=compiler.assemble('rtc-migrator',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=p)
    data=s19(cells,0x2000);(folder/'rtc-migrator-2000.s19').write_bytes(data)
    mm=json.loads((folder/'manifest.json').read_text());assert sy==mm['symbols']
    mm['sha256']=sha(data);(folder/'manifest.json').write_text(json.dumps(mm,indent=2)+'\n')
    meta['artifacts'].pop(parent['maintenance_storage_file'])
    meta['artifacts'][name]=sha(record)
    meta.update(version='2.0b27',generation=39,monitors=monitors,
        maintenance_version='2.2',maintenance_storage_file=name,maintenance_bank=2,maintenance_address=0x8000,sram_record_address=0xB000,
        status_asset_address=0xD800,status_asset_sha256=sha(asset),status_code_bytes=symbols['APP_END']-0x6E00,status_symbols=symbols,
        local_asset_address=0xF000,version_asset_address=0xF800,battery_asset_address=0xE200,
        version_loader_symbols=ls,version_loader_bytes=len(loader),storage_reserved_start=0xD800,storage_reserved_end=0x10000,
        relocated_b2_assets=True,parent_build_sha256=sha((BASE/'build.json').read_bytes()),fallback_version='2.0b26',fallback_generation=38,
        hardware_tested=False,board_access=False,boards_flashed=False)
    meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in meta['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    for n in ('str8n-v2-recovery-f000-ffff.bin','battery/asset.bin','local-display/asset.bin','version/asset.bin','clock/clock.bin'):
        assert (OUT/n).read_bytes()==(BASE/n).read_bytes(),n
    print('BETA27 generation 39; MAINT 2.2 in B2:8-A; SRAM B, WORK C-D, assets D8-FFFF; fixed F/ABI unchanged')

if __name__=='__main__':main()
