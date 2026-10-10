"""Build beta15 with a reset-latched EDU OFF mode; no board access."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_spi_resident as spi
from beta4_migration import s19
ROOT=spi.ROOT;OUT=spi.OUT
def profile(source):
    p=source/'service-eq.inc';p.write_text(p.read_text()+'\nSVC_INIT EQU $EE98\n')
    p=source/'service-kernel.inc';t=p.read_text();assert t.count('\nSVC_INIT\n')==1;p.write_text(t.replace('\nSVC_INIT\n','\nSVC_ENABLED\n'))
    p=source/'str8n-v2-config.inc';t=p.read_text();old='                        INC     V2_CONFIG\n';assert t.count(old)==1
    p.write_text(t.replace(old,old+'                        LDA $7D28\n                        STA V2_CONFIG+13\n'))
    p=source/'str8n-v2.asm';t=p.read_text();old='                        STZ V2_CONFIG+13\n';assert t.count(old)==1;t=t.replace(old,'')
    old='V2_DISPATCH:           LDA SVC_BANNER_PTR+1\n                        BEQ TIME_SKIP\n                        JSR $890A\n                        BCS V2_PROMPT\nTIME_SKIP:              JSR AP_TRY'
    assert old in t;t=t.replace(old,old.replace('JSR $890A','JSR $EF53'));p.write_text(t)
    p=source/'str8n-v2-text.json';texts=json.loads(p.read_text())
    for row in texts:
        if row['name']=='V2_HELP':row['text']=row['text'].replace('[label]','[name]').replace('label|bank','name|bank')
    p.write_text(json.dumps(texts,indent=2)+'\n')
def main():
    spi.VERSION='2.0b15';spi.GENERATION=24;spi.PROFILE_EXTRA=profile;spi.main()
    meta=json.loads((OUT/'build.json').read_text());assert meta['sr_bytes']<=0x694
    e=bytearray((OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes())
    stage=OUT/'edu-hooks/source';stage.mkdir(parents=True,exist_ok=True);(stage.parent/'asm').mkdir(exist_ok=True)
    for p in (OUT/'source').glob('*.inc'):shutil.copyfile(p,stage/p.name)
    links={k:meta['launcher'][k] for k in ('SVC_ENABLED','SVC_DONE')};links.update(BOOT_API_READ=meta['boot']['BOOT_API_READ'])
    spi.equs(stage/'edu-links.inc',links)
    shutil.copyfile(ROOT/'tools/v2-spi/edu-boot.asm',stage/'edu-boot.asm')
    boot,bs,_=spi.assemble(stage,'edu-boot',0xEE94,'AUX_END',0xEE98);assert len(boot)<=108,len(boot)
    links['OFF_TEXT']=bs['OFF_TEXT'];spi.equs(stage/'edu-links.inc',links)
    shutil.copyfile(ROOT/'tools/v2-spi/edu-console-hooks.asm',stage/'edu-console-hooks.asm')
    hooks,hs,_=spi.assemble(stage,'edu-console-hooks',0xEF50,'AUX_END',0xEF59);assert len(hooks)<=174,len(hooks)
    assert e[0xE94:0xF00]==b'\xff'*108
    e[0xE94:0xE94+len(boot)]=boot
    help_text=b'\r\nAPPS lists programs; R MAINT loads maintenance.\r\nR EDU: saved ON/OFF.\r\n\0';assert len(help_text)<=80
    e[0xF00:0xFFE]=b'\xff'*254;e[0xF00:0xF00+len(help_text)]=help_text;e[0xF50:0xF50+len(hooks)]=hooks
    crc=spi.journal.banner.base.apps.fw.crc;e[-2:]=crc(e[:-2]).to_bytes(2,'big');assert crc(e)==0 and crc(e[:0x800])==0
    (OUT/'str8n-v2-recovery-e000-efff.bin').write_bytes(e)
    (OUT/'str8n-v2-recovery-e000-efff.s19').write_bytes(s19(dict(enumerate(e,0xE000)),0xF004))
    meta.update(edu_mode=True,edu_flag_offset=13,edu_off_tag=0xA5,edu_latch=0x7D27,edu_pending=0x7D28,edu_boot_bytes=len(boot),edu_hook_bytes=len(hooks),edu_ram_end_off=0x66FF,edu_ram_end_on=0x64FF)
    meta['artifacts']['str8n-v2-recovery-e000-efff.bin']=hashlib.sha256(e).hexdigest()
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('EDU reset-latched mode:',len(boot),'+',len(hooks),'bytes in existing E pockets; no new sector/RAM')
if __name__=='__main__':main()
