"""Build MAINT's verified flash/SRAM copies; no hardware access."""
import hashlib,json,shutil
from pathlib import Path
import build_bank_maint_rtc as base
from build_bank_maint_v2 import long_branches
from build_v2_spi_resident import equs
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-storage'
SPI_MAP=False

def main():
    # Generate the existing maintenance feature set before adding transfers.
    base.OUT=OUT/'maint';base.KERNEL_OUT=OUT;base.VERSION='1.7';base.JOURNAL=True;base.main()
    folder=OUT/'maint';path=folder/(base.base.NAME+'.asm');stage=folder/'asm'
    sm=json.loads((OUT/'store/build.json').read_text())['symbols'];meta=json.loads((OUT/'build.json').read_text())
    links={'SM_'+n:sm[n] for n in ('SOURCE_BYTE_HOOK','SAVE_TRANSFER_HOOK','RESTORE_TRANSFER_HOOK','LOAD','LENGTH','ENTRY','BP','COUNT','BEST_SEQ','TRANSFER')}
    links.update({n:meta['worker'][n] for n in ('V2W_READ','V2W_BYTE')})
    if SPI_MAP:
        links.update({'SPI_MAP_CRC_'+n:meta['launcher']['AP_CRC_'+n] for n in ('INIT','BYTE')})
    equs(stage/'storage-maint-links.inc',links)
    text=path.read_text().replace('1.7','1.8')
    text=text.replace('HELP:                   DB', 'HELP:                   DB "X bank NAME S NAME / X S NAME bank NAME",13,10\n                        DB')
    text=text.replace("                        CMP #'?'", "                        CMP #'X'\n                        BEQ X_COPY\n                        CMP #'?'",1)
    text=text.replace('BM_END:', '        INCLUDE "storage-maint-links.inc"\n'+long_branches((ROOT/'tools/v2-spi/storage-maint.inc').read_text()).replace('BM_LONG_','X_LONG_')+'\nBM_END:')
    version='1.9' if SPI_MAP else '1.8'
    if SPI_MAP:
        from build_v2_spi_map import map_source
        text=text.replace('1.8','1.9')
        text=text.replace('MAP_ACCESS_NOTE:        LDX #<MAP_ACCESS_NOTE_TEXT',
                          'MAP_ACCESS_NOTE:        LDA #3\n                        JSR V2W_SELECT\n                        JSR SPI_MAP_ALLOCATION\n                        LDX #<MAP_ACCESS_NOTE_TEXT')
        text=text.replace('RTC_RAM_MAP_DONE:',
                          '                        BRA SPI_MAP_RAM_DONE\nRTC_RAM_MAP_DONE:\n                        LDX #<SPI_MAP_RAM_OFF_TEXT\n                        LDY #>SPI_MAP_RAM_OFF_TEXT\n                        JSR PRINT\nSPI_MAP_RAM_DONE:')
        text=text.replace('RTC/I2C or journal services','RTC/I2C, SPI/SRAM or journal services')
        text=text.replace('I RTC/I2C;', 'I shared services;')
        text=text.replace('BM_END:',map_source()+'\nSPI_MAP_RAM_OFF_TEXT DB "RAM 0200-66FF program; services inactive",13,10,0\nBM_END:')
    path.write_text(long_branches(text).replace('BM_LONG_','MX_LONG_'))
    link=base.base.link;link.OUT=folder;link.SOURCE=stage
    def compile():return link.assemble(base.base.NAME,0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=path)
    cells,sym=compile();cells,sym=base.fw.relax_branches(path,cells,sym,compile)
    body=link.dense_image(cells,0x2000,sym['BM_END']);assert sym['BM_END']<=0x5000
    header=b'SR\x01\x3F\0\x20'+len(body).to_bytes(2,'little')+b'MAINT'.ljust(16,b'\0')
    size=(len(header+body)+4095)//4096*4096;record=header+body+b'\xff'*(size-len(header+body))
    name=f'str8n-maint-{version}-b1-8000-{0x8000+size-1:04x}.bin';(OUT/name).write_bytes(record)
    (folder/f'str8n-bank-maint-{version}-2000.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    manifest=dict(version=version,entry=0x2000,bytes=len(body),end=sym['BM_END'],symbols=sym,program_sha256=hashlib.sha256(body).hexdigest(),storage_sha256=hashlib.sha256(record).hexdigest(),storage_bytes=size,hardware_tested=False,storage_file=name)
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    meta.update(maintenance_version=version,maintenance_storage_file=name)
    meta['artifacts'][name]=manifest['storage_sha256']
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(f'UNFLASHED MAINT {version}:',len(body),'bytes; stored',size,'bytes; flash-only; COPY keeps source')

if __name__=='__main__':main()
