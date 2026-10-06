"""Build STR8-N's RAM migrator template; contains no vendor firmware."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_config as link
from build_bank_maint_v2 import long_branches

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-beta4/migrator'
SOURCE=ROOT/'src/v2-beta4'
NAME='str8n-v2-b4-migrator-2000'

def main():
    stage=OUT/'asm';stage.mkdir(parents=True,exist_ok=True)
    for p in SOURCE.glob('*.inc'):shutil.copyfile(p,stage/p.name)
    flash=(stage/'str8n-v2-flash-worker.inc').read_text()
    for routine in ('V2W_ACCOUNT','V2W_READY'):
        flash=flash.replace(f'                        JSR     {routine}\n                        BCC     V2W_FINISH\n','')
    (stage/'str8n-v2-flash-worker.inc').write_text(flash)
    link.OUT=OUT;link.SOURCE=stage
    worker=OUT/'migration-worker.asm';worker.write_text((SOURCE/'str8n-v2-worker.asm').read_text())
    wm,ws=link.assemble('migration-worker',0x7800,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=worker)
    wd=link.dense_image(wm,0x7800,ws['V2W_END'])
    assert len(wd)<=1024
    link.include_bytes(stage/'migration-worker-image.inc',wd)
    (stage/'migration-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in ws.items() if n.startswith('V2W_')))
    copy=[' LDX #0','MIG_COPY_WORKER:']
    offsets=list(range(0,len(wd)-255,256))
    if len(wd)%256:offsets.append(len(wd)-256)
    for offset in offsets:copy += [f' LDA MIG_WORKER+${offset:04X},X',f' STA $7800+${offset:04X},X']
    (stage/'migration-copy.inc').write_text('\n'.join(copy+[' INX',' BNE MIG_COPY_WORKER'])+'\n')
    link.include_bytes(stage/'migration-table.inc',b'\xff'*72)
    text=(SOURCE/'str8n-v2-migration.asm').read_text()
    text=text.replace('START:                  SEI','START:                  SEC\n                        DB $FB\n                        SEI')
    text=text.replace('                        STZ MIG_INDEX','                        JSR MIG_IDENTIFY\n                        BCC MIG_FAIL\n                        STZ MIG_INDEX',1)
    text=text.replace('                        CMP #$06','                        CMP MIG_PLAN_COUNT')
    text=text.replace('BETA1 -> RECOVERY; REPLACES B3:A-F. INITIAL F WRITE IS NOT POWER-LOSS SAFE.',
                      'STR8-N 2.0b4 + MAINT MIGRATOR; B3:8-F. KEEP POWER STABLE UNTIL VERIFIED.')
    text=text.replace('                        INC MIG_INDEX\n', '''                        INC MIG_INDEX
                        LDA MIG_COMMIT_AFTER
                        BEQ MIG_STORAGE_READY
                        CMP MIG_INDEX
                        BNE MIG_STORAGE_READY
                        LDA #$03
                        STA V2_FLASH_PTR
                        LDA #$80
                        STA V2_FLASH_PTR+1
                        LDA #$3F
                        STA V2_FLASH_DATA
                        JSR V2W_BYTE
                        BCC MIG_FAIL
MIG_STORAGE_READY:
''',1)
    text=text.replace('MIG_TABLE:             INCLUDE', '''; Host patches the verified plan and count before loading this RAM image.
MIG_PLAN_COUNT:        DB $00
MIG_COMMIT_AFTER:      DB $00
MIG_IDENTIFY:          LDA #$AA
                        STA $D555
                        LDA #$55
                        STA $AAAA
                        LDA #$90
                        STA $D555
                        LDA $8000
                        STA $620D
                        LDA $8001
                        STA $620E
                        LDA #$F0
                        STA $8000
                        LDA $620D
                        CMP #$BF
                        BNE MIG_ID_BAD
                        LDA $620E
                        CMP #$B5
                        BNE MIG_ID_BAD
                        LDA MIG_PLAN_COUNT
                        BEQ MIG_ID_BAD
                        CMP #$09
                        BCS MIG_ID_BAD
                        SEC
                        RTS
MIG_ID_BAD:            CLC
                        RTS
MIG_TABLE:             INCLUDE''')
    assembly=OUT/(NAME+'.asm');assembly.write_text(long_branches(text),encoding='ascii')
    memory,symbols=link.assemble(NAME,0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=assembly)
    end=symbols['MIG_END'];assert end<0x4000
    data=link.dense_image(memory,0x2000,end)
    lines=[link.record('0',0,b'STR8-N 2.0b4 RAM migration template')]
    lines += [link.record('1',a,data[a-0x2000:a-0x2000+32]) for a in range(0x2000,end,32)]
    lines += [link.record('9',0x2000)]
    target=OUT/(NAME+'.s19');target.write_text('\n'.join(lines)+'\n')
    manifest=dict(entry=0x2000,first=0x2000,last=end-1,table=symbols['MIG_TABLE'],
        count=symbols['MIG_PLAN_COUNT'],symbols=symbols,worker=ws,
        commit_after=symbols['MIG_COMMIT_AFTER'],table_bytes=72,max_sectors=8,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),vendor_firmware_included=False)
    (OUT/'migrator.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'RAM migrator: {len(data)} bytes; unified entry; independent worker; guarded sector transfers')

if __name__=='__main__':main()
