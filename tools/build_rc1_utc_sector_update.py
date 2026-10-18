"""Build a narrow RAM updater using rc1's resident wear-accounted flash worker.

Pins all static B3 bytes, the live worker and the target payload on-device.
Dynamic C/D journals are validated/accounted by rc1 itself, never reconstructed.
The persistent binding/name/offset area at B3:9C00-9FFF is preserved, not pinned
to a historical snapshot; the sealed 9000-9BFF executable remains pinned.
No clock, trim, EEPROM or SPI-SRAM operation is present.
"""
import hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
BASE=Q/'rc1-utc-2609-2604-hardware-2026-10-18-r2';OUT=Q/'rc1-utc-2609-2604-hardware-2026-10-18-r4'
read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    OUT.mkdir(exist_ok=True);assert not (OUT/'preparation.json').exists();prep=read(BASE/'preparation.json');kit=Path(prep['package'])/'migration';sys.path.insert(0,str(kit));import legacy_transport as wire
    target=(kit/'payload/str8n-rtc-component-8000-8fff.bin').read_bytes();assert wire.crc(target)==0 and b' [power-fail UTC]\0' in target
    build=ROOT/'tmp/ru3';symbols=read(build/'symbols.json');ws=symbols['core/str8n-v2-worker'];worker=bytes(int(x,16) for x in re.findall(r'\$([0-9A-F]{2})',(build/'s/core/worker-image.inc').read_text()));assert len(worker)==ws['V2W_END']-0x7800 and sha(worker)==read(build/'build-report.json')['compiled'][0]['sha256'];plans={}
    for board in ('2609','2604'):
        folder=OUT/board;folder.mkdir(exist_ok=True);s=folder/'s';s.mkdir(exist_ok=True);old=(BASE/(board+'-utc')/'source-b3.bin').read_bytes();static=old[:0x1c00]+old[0x2000:0x4000]+old[0x6000:]
        template=r'''        MODULE UTC_UPDATE
        XDEF START
        XDEF CODE_END
P EQU $E0
E EQU $2300
H EQU $2302
T EQU $2306
DEST EQU $E2
        CODE
START:  SEI
        CLD
        LDA $7D00
        CMP #3
        BEQ RES_OK
        JMP REFUSE
RES_OK: JSR INIT_HASH
        LDX #$80
        LDY #$9C
        JSR PAGE_RANGE
        LDX #$A0
        LDY #$C0
        JSR PAGE_RANGE
        LDX #$E0
        LDY #0
        JSR PAGE_RANGE
        LDX #3
CHECK_STATIC:
        LDA H,X
        CMP STATIC_HASH,X
        BEQ STATIC_BYTE_OK
        JMP REFUSE
STATIC_BYTE_OK:
        DEX
        BPL CHECK_STATIC
        JSR INIT_HASH
        STZ P
        LDA #$78
        STA P+1
        LDA #<@WORKER_END@
        STA E
        LDA #>@WORKER_END@
        STA E+1
        JSR HASH_RANGE
        LDX #3
CHECK_WORKER:
        LDA H,X
        CMP WORKER_HASH,X
        BEQ WORKER_BYTE_OK
        JMP REFUSE
WORKER_BYTE_OK:
        DEX
        BPL CHECK_WORKER
        JSR INIT_HASH
        LDX #$40
        LDY #$50
        JSR PAGE_RANGE
        LDX #3
CHECK_TARGET:
        LDA H,X
        CMP TARGET_HASH,X
        BEQ TARGET_BYTE_OK
        JMP REFUSE
TARGET_BYTE_OK:
        DEX
        BPL CHECK_TARGET
        ; Copy the verified source-built target into rc1's sector buffer.
        STZ P
        STZ DEST
        LDA #$40
        STA P+1
        LDA #$68
        STA DEST+1
        LDY #0
COPY:   LDA (P),Y
        STA (DEST),Y
        INY
        BNE COPY
        INC P+1
        INC DEST+1
        LDA P+1
        CMP #$50
        BNE COPY
        LDA #3
        STA $F3
        LDA #$80
        STA $EE
        LDA #1
        STA $EF
        STZ $F5
        ; The unchanged rc1 worker checks and advances the actual wear journal
        ; before erase, programs and compares every byte, then restores B3.
        JSR @MUTATE@
        BCC WRITE_OK
        JMP FAILED
WRITE_OK:
        JSR INIT_HASH
        LDX #$80
        LDY #$90
        JSR PAGE_RANGE
        LDX #3
CHECK_FLASH:
        LDA H,X
        CMP TARGET_HASH,X
        BEQ FLASH_BYTE_OK
        JMP FAILED
FLASH_BYTE_OK:
        DEX
        BPL CHECK_FLASH
        LDX #0
SUCCESS_TEXT:
        LDA OK_TEXT,X
        BEQ PRINT_LABEL
        JSR $7E6D
        INX
        BRA SUCCESS_TEXT
PRINT_LABEL:
        LDX #0
LABEL_CHAR:
        LDA @LABEL@,X
        BEQ DONE
        JSR $7E6D
        INX
        BRA LABEL_CHAR
DONE:   JSR $7E7F
        JMP $7E67
REFUSE: LDX #0
REF_CHAR:
        LDA REF_TEXT,X
        BEQ DONE
        JSR $7E6D
        INX
        BRA REF_CHAR
FAILED: LDX #0
FAIL_CHAR:
        LDA FAIL_TEXT,X
        BEQ DONE
        JSR $7E6D
        INX
        BRA FAIL_CHAR
INIT_HASH:
        LDX #3
INIT_LOOP:
        LDA SEED,X
        STA H,X
        DEX
        BPL INIT_LOOP
        RTS
PAGE_RANGE:
        STZ P
        STZ E
        STX P+1
        STY E+1
HASH_RANGE:
        LDA (P)
        JSR FNV
        INC P
        BNE RANGE_CHECK
        INC P+1
RANGE_CHECK:
        LDA P
        CMP E
        BNE HASH_RANGE
        LDA P+1
        CMP E+1
        BNE HASH_RANGE
        RTS
FNV:    EOR H
        STA H
        LDX #3
TERM_COPY:
        LDA H,X
        STA T,X
        DEX
        BPL TERM_COPY
        LDX #1
        JSR SHIFT_ADD
        LDX #3
        JSR SHIFT_ADD
        LDX #3
        JSR SHIFT_ADD
        LDX #1
        JSR SHIFT_ADD
        LDA H+3
        CLC
        ADC T+1
        STA H+3
        RTS
SHIFT_ADD:
        ASL T
        ROL T+1
        ROL T+2
        ROL T+3
        DEX
        BNE SHIFT_ADD
        CLC
        LDA H
        ADC T
        STA H
        LDA H+1
        ADC T+1
        STA H+1
        LDA H+2
        ADC T+2
        STA H+2
        LDA H+3
        ADC T+3
        STA H+3
        RTS
SEED DB $C5,$9D,$1C,$81
STATIC_HASH DB @STATIC@
WORKER_HASH DB @WORKER@
TARGET_HASH DB @TARGET@
OK_TEXT DB "UTC UPDATE VERIFIED ",0
REF_TEXT DB "UTC UPDATE REFUSED; NO FLASH WRITE",0
FAIL_TEXT DB "UTC UPDATE FAILED; KEEP POWER ON",0
CODE_END:
        ENDMOD
        END
'''
        data=template.replace('@WORKER_END@',f'${ws["V2W_END"]:04X}').replace('@MUTATE@',f'${ws["V2W_MUTATE"]:04X}').replace('@LABEL@',f'${symbols["banner/rtc-banner"]["POWERFAIL_TEXT"]:04X}')
        for token,body in [('STATIC',static),('WORKER',worker),('TARGET',target)]:data=data.replace('@'+token+'@',','.join(f'${n:02X}' for n in wire.fnv(body).to_bytes(4,'little')))
        (s/'utc.asm').write_text(data)
        logs=[]
        for cmd in [[shutil.which('wdc02as'),'-G','-L','-S','-W','utc.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c2000','-hm19','-j','-o','utc.s19','utc.obj']]:
            result=subprocess.run(cmd,cwd=s,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr));save=s/'build-log.json';save.write_text(json.dumps(logs,indent=2)+'\n');assert result.returncode==0,result.stdout+result.stderr
        cells={}
        for line in (s/'utc.s19').read_text().splitlines():
            raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
            if line[1]=='1':cells.update(dict(enumerate(raw[3:-1],int.from_bytes(raw[1:3],'big'))))
        assert set(cells)==set(range(0x2000,max(cells)+1)) and max(cells)<0x2300
        code_bytes=len(cells);cells.update(dict(enumerate(target,0x4000)));cells={a:cells.get(a,0) for a in range(0x2000,0x5000)};entry=0x2000;blob=wire.s19(cells,entry);(folder/'updater.s19').write_bytes(blob)
        assert wire.read_s19(folder/'updater.s19',max_end=0x6500)==(cells,entry)
        info=dict(board=board,passed=True,s19_sha256=sha(blob),entry=entry,code_bytes=code_bytes,target_bytes=len(target),target_sha256=sha(target),static_B3_hash=wire.fnv(static),worker_hash=wire.fnv(worker),source_reference=str(BASE/(board+'-utc')/'source-b3.bin'),dynamic_journals_handled_by_current_firmware=True,host_memory_readbacks=False,clock_trim_commands=False)
        (folder/'build.json').write_text(json.dumps(info,indent=2)+'\n');plans[board]=info
    (OUT/'preparation.json').write_text(json.dumps(dict(passed=True,boards=plans,package=prep['package'],published_zip_sha256=prep['published_zip_sha256'],supersedes_refused_plan=str(BASE),board_access=False,one_wear_accounted_sector_erase=True),indent=2)+'\n')
    print('PASS narrow resident-worker updaters built; current journals stay authoritative; CPU tests pending')
if __name__=='__main__':main()
