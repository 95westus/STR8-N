"""Build optional EEPROM journal in B3:9, preserving old qualified outputs."""
import json,hashlib,shutil
from pathlib import Path
import build_v2_rtc_banner as banner
import build_v2_config as compiler
from build_bank_maint_v2 import long_branches

ROOT=banner.ROOT
OUT=ROOT/'BUILD/v2-rtc-journal'
VERSION='2.0b8'
GENERATION=17
BANNER_SOURCE='rtc-journal-banner.asm'
JOURNAL_SOURCE='journal.asm'
TRANSPORT_SOURCE='eeprom-transfer.inc'
JOURNAL_CODE_END=0xA000


def profile(source):
    # Both optional service sectors are system-owned; original user RAM unchanged.
    p=source/'str8n-v2-flash.inc';t=p.read_text()
    t=t.replace('CMP #$A0\n                        BCS V2_F_PROTECTED\n                        CMP #$80\n                        BEQ V2_F_PROTECTED',
        'CMP #$80\n                        BCS V2_F_PROTECTED')
    t=t.replace('CMP     #$A0\n                        BCS     V2_I_PROTECTED\n                        LDA V2_ADDR+1\n                        CMP #$80\n                        BEQ V2_I_PROTECTED',
        'CMP     #$80\n                        BCS     V2_I_PROTECTED')
    p.write_text(t)
    p=source/'str8n-v2.asm';p.write_text(p.read_text().replace('                        STZ SVC_DESC\n','                        STZ SVC_DESC\n                        STZ $7D19\n',1))
    p=source/'service-kernel.inc';p.write_text(p.read_text().replace('SVC_HEADER_MAGIC DB "RC",1,5','SVC_HEADER_MAGIC DB "RC",2,5'))
    p=source/'str8n-v2-sr.asm';t=p.read_text().replace('CMP #$90\n                        BCC SR_INVALID','CMP #$A0\n                        BCC SR_INVALID');p.write_text(t)


def finish():
    meta=json.loads((OUT/'split/build.json').read_text());entry=meta['provider_symbols']['EE_TRANSFER']
    stage=OUT/'journal-source';stage.mkdir(exist_ok=True)
    for name in ('kernel-rtc-api.inc','journal-eq.inc'):shutil.copyfile(ROOT/'tools/v2-rtc'/name,stage/name)
    (stage/'binding.inc').write_text(long_branches((ROOT/'tools/v2-rtc/binding.inc').read_text()).replace('BM_LONG_','BND_LONG_'))
    worker=json.loads((OUT/'build.json').read_text())['worker']['V2W_BYTE']
    trim=meta['provider_symbols'].get('TRIM_CONTROL',0)
    (stage/'journal-transport.inc').write_text(f'EE_TRANSFER EQU ${entry:04X}\nBIND_FLASH_BYTE EQU ${worker:04X}\nTRIM_CONTROL EQU ${trim:04X}\n')
    (stage/'journal.asm').write_text(long_branches((ROOT/'tools/v2-rtc'/JOURNAL_SOURCE).read_text()).replace('BM_LONG_','J_LONG_'))
    oldout,oldsource=compiler.OUT,compiler.SOURCE
    try:
        compiler.OUT,compiler.SOURCE=OUT/'journal',stage;(compiler.OUT/'asm').mkdir(parents=True,exist_ok=True)
        cells,s=compiler.assemble('journal',0x9000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
        body=compiler.dense_image(cells,0x9000,s['JOURNAL_END'])
    finally:compiler.OUT,compiler.SOURCE=oldout,oldsource
    prefix_size=JOURNAL_CODE_END-0x9000
    assert len(body)<prefix_size-2
    sector=body+bytes([255])*(prefix_size-2-len(body));sector+=banner.base.apps.fw.crc(sector).to_bytes(2,'big')
    sector+=bytes([255])*(4096-prefix_size)
    (OUT/'str8n-journal-9000-9fff.bin').write_bytes(sector)
    (OUT/'journal/build.json').write_text(json.dumps(dict(bytes=len(body),entry=0x9004,symbols=s,ee_entry=entry,sha256=hashlib.sha256(sector).hexdigest()),indent=2)+'\n')


def main():
    banner.OUT,banner.VERSION,banner.GENERATION=OUT,VERSION,GENERATION
    banner.BANNER_SOURCE=BANNER_SOURCE;banner.EXTRA_SOURCE_FILES=['journal-eq.inc'];banner.SOURCE_HOOK=profile;banner.POST_HOOK=finish
    banner.base.split.TRANSPORT_EXTRA=ROOT/'tools/v2-rtc'/TRANSPORT_SOURCE
    banner.base.split.PROVIDER_FORMAT=2
    banner.base.TEMPLATE_BASE=0x8DF0
    # Protect B3:9 against named flash app launch as well.
    original=banner.base.replace_once
    def replace(text,old,new):
        if old=='                       LDA AP_LIMIT+1\n                       CMP #$A0':
            new=new.replace("CMP #$90", "CMP #$A0")
        return original(text,old,new)
    banner.base.replace_once=replace
    banner.main()
    m=json.loads((OUT/'build.json').read_text());m.update(journal_sector=9,journal_descriptor=0x7D19,journal_cache='6B00-6BFF',eeprom_base=0,eeprom_slots=4,journal_bytes=json.loads((OUT/'journal/build.json').read_text())['bytes'])
    m.update(provider_format=2,maintenance_version='1.7')
    m['artifacts']['str8n-journal-9000-9fff.bin']=hashlib.sha256((OUT/'str8n-journal-9000-9fff.bin').read_bytes()).hexdigest()
    (OUT/'build.json').write_text(json.dumps(m,indent=2)+'\n')
    print('Journal',m['journal_bytes'],'bytes; EEPROM four slots; scratch reused outside flash mutations')


if __name__=='__main__':main()
