"""Build the small saved EDU mode utility; never opens serial ports."""
import argparse,hashlib,json,shutil
from build_v2_spi_resident import ROOT,OUT,assemble
from beta4_migration import s19
from build_bank_maint_v2 import long_branches
def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--build',type=type(OUT),default=OUT);args=parser.parse_args();OUT=args.build.resolve()
    stage=OUT/'edu/source';stage.mkdir(parents=True,exist_ok=True);(stage.parent/'asm').mkdir(exist_ok=True)
    fw=json.loads((OUT/'build.json').read_text())
    constants={name:fw['boot'][name] for name in ('BOOT_API_PROMOTE','BOOT_API_READ')}
    constants.update(EDU_MAGIC_ADDRESS=fw.get('edu_magic_address',0xEE94),EDU_CONFIG_ENTRY=fw.get('edu_config_entry',0xEF50),EDU_STATUS_ENTRY=fw.get('edu_status_entry',0))
    (stage/'edu-fixed.inc').write_text(''.join(f'{name} EQU ${value:04X}\n' for name,value in constants.items()))
    src=ROOT/'tools/v2-spi/edu.asm';text=src.read_text();version='1.0'
    if fw.get('status_banner'):
        version='1.1';text=text.replace('MAGIC DB "ED",1,1','MAGIC DB "ED",1,2')
        start=text.index('        JSR READ_CONFIG\n',text.index("        CMP #'?'"));end=text.index('SET_MODE:\n',start)
        text=text[:start]+'        JSR EDU_STATUS_ENTRY\n        BRA PROMPT\n'+text[end:]
        text=text.replace('        JSR PRINT\nPROMPT:', '        JSR PRINT\n        JSR EDU_STATUS_ENTRY\n        LDX #<COMMAND_TEXT\n        LDY #>COMMAND_TEXT\n        JSR PRINT\nPROMPT:',1)
        start=text.index('CONFIRM:\n');end=text.index('        LDX #<CONFIRM_TEXT\n',start);text=text[:start]+'CONFIRM:\n'+text[end:]
        start=text.index('MODE_TEXT:\n');end=text.index('PRINT: ',start);text=text[:start]+text[end:]
        text=text.replace('TITLE DB "EDU 1.0",13,10,"? status; ON OFF Q",13,10,0','TITLE DB "EDU 1.1",0\nCOMMAND_TEXT DB "ON OFF ? Q",13,10,0')
        for line in ('ACTIVE_TEXT DB "EDU active: ",0\n','SAVED_TEXT DB "EDU saved: ",0\n','OFF_TEXT DB "OFF",13,10,0\n','ON_TEXT DB "ON",13,10,0\n'):text=text.replace(line,'')
        if fw.get('storage_services'):
            version='1.2';text=text.replace('DB "ED",1,2','DB "ED",1,3').replace('EDU 1.1','EDU 1.2').replace('        JSR EDU_STATUS_ENTRY','        LDA #1\n        JSR EDU_STATUS_ENTRY')
    (stage/'edu.asm').write_text(long_branches(text))
    body,s,_=assemble(stage,'edu',0x2000,'APP_END',0x2000)
    assert s['APP_END']<=0x2400,hex(s['APP_END'])
    if fw.get('status_banner'):assert len(body)+24<=0x300,'EDU record would overlap C900 status asset'
    if fw.get('storage_services'):assert len(body)+24<=0x280,'EDU record at C580 would overlap the C800 storage asset'
    (stage.parent/'edu.bin').write_bytes(body);(stage.parent/'edu.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    (stage.parent/'build.json').write_text(json.dumps(dict(version=version,bytes=len(body),end=s['APP_END'],sha256=hashlib.sha256(body).hexdigest(),source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),linked_source_sha256=hashlib.sha256(text.encode()).hexdigest(),symbols=s),indent=2)+'\n')
    print('EDU '+version+':',len(body),'bytes; automatic shared status' if fw.get('status_banner') else 'bytes; no service-RAM access; reset-only mode changes')
if __name__=='__main__':main()
