"""Isolated beta24 generation 34: early keys, validated A/B and fixed recovery."""
import binascii,hashlib,json,shutil
from pathlib import Path
from build_bank_maint_v2 import long_branches
import build_v2_config as compiler
import build_v2_recovery as fw

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'BUILD/v2-board-name-fix006'
OUT=ROOT/'BUILD/v2-startup-keys'
GENERATION=34

def patch(text):
    old='BOOT_STARTUP_DOTS:      JSR V2W_BOOT_DELAY\n'
    new='''BOOT_STARTUP_DOTS:      JSR V2W_RAW_POLL
                        BCC BOOT_DOT_WAIT
                        AND #$DF
                        CMP #'A'
                        BEQ BOOT_WINDOW_A
                        CMP #'B'
                        BEQ BOOT_WINDOW_B
                        BRA BOOT_SHOW_CHOICES
BOOT_DOT_WAIT:          JSR V2W_BOOT_DELAY
'''
    assert text.count(old)==1;text=text.replace(old,new,1)
    text=text.replace('; Bounded choice before monitor/configuration. Output never waits for USB.','; Any non-A/B byte skips only the dots; slot selection remains validated.\nBOOT_SHOW_CHOICES:',1)
    text=text.replace("                        CMP #'S'\n", "                        AND #$DF\n                        CMP #'S'\n",1)
    text=text.replace("                        CMP #'s'\n                        BEQ BOOT_RECOVERY\n",'',1)
    text=text.replace("                        AND #$DF\n                        CMP #'A'\n                        BEQ BOOT_WINDOW_A\n                        CMP #'B'\n                        BNE BOOT_WINDOW_NEXT\n                        LDA #$B0", "                        CMP #'A'\n                        BEQ BOOT_WINDOW_A\n                        CMP #'B'\n                        BNE BOOT_WINDOW_NEXT\nBOOT_WINDOW_B:          LDA #$B0",1)
    text=text.replace('                        JSR BOOT_SLOT_CHECK\n                        BCC BOOT_WINDOW_NEXT','                        JSR BOOT_SLOT_CHECK\n                        BCC BOOT_SHOW_CHOICES',1)
    # A validated boot-time selection needs cold entry, like the timed default.
    # HOLD is the separate ordinary-return path and can require initialized RAM.
    text=text.replace('                        STA BOOT_ACTIVE\n                        JMP BOOT_HOLD','                        STA BOOT_ACTIVE\n                        JMP BOOT_LAUNCH',1)
    text=text.replace('A/B, S recovery, Enter default [3s]: ','A/B,S=REC,Enter default [3s]: ')
    text=text.replace('A/B; U A|B; W','A/B U A|B W')
    # Both launch callers already hold the validated/default slot in A.
    text=text.replace('BOOT_LAUNCH:            LDA #$84\n                        STA BOOT_CALL_PTR\n                        LDA BOOT_ACTIVE\n                        STA BOOT_CALL_PTR+1',
                      'BOOT_LAUNCH:            STA BOOT_CALL_PTR+1\n                        LDA #$84\n                        STA BOOT_CALL_PTR',1)
    launch='BOOT_LAUNCH:            STA BOOT_CALL_PTR+1\n                        LDA #$84\n                        STA BOOT_CALL_PTR\n                        JMP (BOOT_CALL_PTR)\n'
    assert text.count(launch)==1
    text=text.replace(launch,'                        DB $FF,$FF,$FF\n',1)
    text=text.replace('BOOT_RECOVERY:          JSR V2W_RX_RESET',launch+'\nBOOT_RECOVERY:          JSR V2W_RX_RESET',1)
    text=text.replace('A/B,S=REC,Enter default','A/B/S,Enter default',1)
    # Retain the private journal CRC addresses used by sealed service assets.
    text=text.replace('BOOT_COMPAT_DATA:','                        DB $FF,$FF\nBOOT_COMPAT_DATA:',1)
    return text

def main():
    shutil.copytree(OLD,OUT,dirs_exist_ok=True);stage=OUT/'asm';inputs=OUT/'inputs';meta=json.loads((OUT/'build.json').read_text())
    source=patch((OUT/'source/str8n-v2-boot.asm').read_text())
    (OUT/'source/str8n-v2-boot.asm').write_text(source)
    path=inputs/'str8n-v2-boot.asm';path.write_text(long_branches(source).replace('BM_LONG_','KEY_LONG_'))
    for page in ('a0','b0'):shutil.copyfile(stage/f'monitor-{page}.asm',inputs/f'monitor-{page}.asm')
    compiler.OUT=OUT;compiler.SOURCE=stage
    def assemble(name,origin):return compiler.assemble(name,origin,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=inputs/(name+'.asm'))
    cells,s=assemble('str8n-v2-boot',0xE000)
    cells,s=fw.relax_branches(path,cells,s,lambda:assemble('str8n-v2-boot',0xE000))
    cells,s=assemble('str8n-v2-boot',0xF000);body=compiler.dense_image(cells,0xF000,s['BOOT_END'])
    assert len(body)<=0xFE0,('F capacity',len(body))
    f=bytearray((OLD/'str8n-v2-recovery-f000-ffff.bin').read_bytes());f[:0xFE0]=b'\xff'*0xFE0;f[:len(body)]=body
    cookie=binascii.crc32(f)&0xFFFFFFFF;offset=s['BOOT_COMPAT_DATA']-0xF000
    assert f[offset:offset+4]==bytes(4);f[offset:offset+4]=cookie.to_bytes(4,'little')
    (stage/'boot-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in s.items() if n.startswith('BOOT_') and v>=0xF000 and n!='BOOT_API_ERASE'))
    for name,value in meta['boot'].items():
        if name.startswith('J_') and value>=0xF000:assert s[name]==value,('journal ABI moved',name)
    assert s['BOOT_SR_ROUTE']==meta['boot']['BOOT_SR_ROUTE'], 'shared application route ABI moved'
    (stage/'app-fixed-symbols.inc').write_text(f"AP_CRC_INIT EQU ${s['J_CRC_INIT']:04X}\nAP_CRC_BYTE EQU ${s['J_CRC_BYTE']:04X}\nAP_SLOT_ROUTE EQU ${s['BOOT_SR_ROUTE']:04X}\n")
    fw.OUT=OUT;slots={};monitors={}
    for page in (0xA0,0xB0):
        name=f'monitor-{page:02x}';cells,sym=assemble(name,(page<<8)+128)
        code=compiler.dense_image(cells,(page<<8)+128,sym['V2_END']);assert len(code)<=3968
        slot=bytearray(fw.slot_image(code,sym,page,GENERATION,cookie))
        # E's map/RAM-edit dispatcher uses the twentieth private service word.
        slot[70:72]=sym['V2_M_EDIT'].to_bytes(2,'little')
        slot[18:20]=fw.crc(slot[:18]+slot[32:]).to_bytes(2,'little')
        slot=bytes(slot);slots[page]=slot;monitors[f'{page:02x}']=sym
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(slot)
    (OUT/'str8n-v2-recovery-f000-ffff.bin').write_bytes(f)
    shutil.copyfile(stage/'launcher.asm',inputs/'launcher.asm')
    cells,launcher=assemble('launcher',0xE000)
    code=compiler.dense_image(cells,0xE000,launcher['AP_END']);assert len(code)==meta['launcher_bytes']
    e=bytearray((OLD/'str8n-v2-recovery-e000-efff.bin').read_bytes());e[:len(code)]=code
    e[0x7FE:0x800]=fw.crc(e[:0x7FE]).to_bytes(2,'big');e[-2:]=fw.crc(e[:-2]).to_bytes(2,'big')
    assert fw.crc(e)==0 and fw.crc(e[:0x800])==0
    (OUT/'str8n-v2-recovery-e000-efff.bin').write_bytes(e)
    # Aggregate ROM containers are historical outputs; update A/B and F fields.
    for name,start,end in (('str8n-v2-recovery-a000-dfff.bin',0xA000,0xE000),):
        blob=bytearray((OUT/name).read_bytes());blob[:4096]=slots[0xA0];blob[4096:8192]=slots[0xB0];(OUT/name).write_bytes(blob)
    meta.update(generation=GENERATION,boot=s,boot_bytes=len(body),boot_compatibility=cookie,monitors=monitors,launcher=launcher,
                startup_keys=True,fixed_f_unchanged=False,private_ram_edit_service=True)
    # MAINT refuses an unrecognized fixed core before using any RAM ABI calls.
    # Rebind its four-byte core identity guard; every other instruction stays.
    folder=OUT/'maint';path=folder/'bank-maint.asm';text=path.read_text()
    oldmeta=json.loads((OLD/'build.json').read_text())
    for i,value in enumerate(cookie.to_bytes(4,'little')):
        address=oldmeta['boot']['BOOT_COMPAT_DATA']+i
        oldvalue=oldmeta['boot_compatibility'].to_bytes(4,'little')[i]
        before=f'LDA ${address:04X}\n                        CMP #${oldvalue:02X}'
        assert text.count(before)==1
        text=text.replace(before,f'LDA ${address:04X}\n                        CMP #${value:02X}',1)
    path.write_text(text);compiler.OUT=folder;compiler.SOURCE=folder/'asm'
    cells,maint=compiler.assemble('bank-maint',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=path)
    program=compiler.dense_image(cells,0x2000,maint['BM_END'])
    prior=(OLD/'maint/board-name.bin').read_bytes()
    assert len(program)==len(prior) and sum(a!=b for a,b in zip(program,prior))<=4
    from beta4_migration import s19
    (folder/'board-name.bin').write_bytes(program)
    (folder/'str8n-bank-maint-2.0-2000.s19').write_bytes(s19(dict(enumerate(program,0x2000)),0x2000))
    name=meta['maintenance_storage_file'];record=bytearray((OLD/name).read_bytes());record[24:24+len(program)]=program
    (OUT/name).write_bytes(record)
    manifest=json.loads((folder/'manifest.json').read_text())
    manifest.update(symbols=maint,program_sha256=hashlib.sha256(program).hexdigest(),storage_sha256=hashlib.sha256(record).hexdigest())
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for name in meta['artifacts']:meta['artifacts'][name]=hashlib.sha256((OUT/name).read_bytes()).hexdigest()
    for name in meta['source_sha256']:
        path=OUT/'source'/name
        if path.is_file():meta['source_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    for name in ('str8n-rtc-component-8000-8fff.bin','str8n-journal-9000-9fff.bin','local-display/asset.bin','boot-status/asset.bin'):
        assert (OUT/name).read_bytes()==(OLD/name).read_bytes(),name
    print('STARTUP KEYS generation',GENERATION,'; F bytes',len(body),'of 4064; new matched A/B slots; services unchanged',flush=True)

if __name__=='__main__':main()
