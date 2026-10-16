"""Offline beta28 XIP utilities; never opens a board or prepares an installer."""
import json,re,shutil,binascii
from pathlib import Path
from beta4_migration import crc,s19
from build_v2_spi_resident import assemble,sha
import build_v2_config as compiler
import build_v2_recovery as fw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'BUILD/v2-beta27';OUT=ROOT/'BUILD/v2-beta28'
GATE=0x7B90

def clean(text):
    return '\n'.join(l for l in text.splitlines() if not re.match(r'\s*(MODULE|XDEF|INCLUDE|CODE|ENDMOD|END)\b',l))+'\n'

def defs(text):
    return set(re.findall(r'^(\w+)(?::|[ \t]+(?:EQU|DB|DS)\b)',text,re.M))

def rename(text,mapping):
    # Never rewrite user-visible strings or comments.
    result=[]
    for line in text.splitlines():
        tokens=list(re.finditer(r'\b\w+\b',line.split(';',1)[0]))
        candidate=(tokens[0] if line[:1].isspace() else tokens[1] if len(tokens)>1 else None) if tokens else None
        protected=candidate.start() if candidate and candidate[0] in set('EQU DB DS LDA LDX LDY STA STX STY STZ ADC SBC CMP CPX CPY AND ORA EOR BIT ASL LSR ROL ROR INC DEC JMP JSR BCC BCS BEQ BNE BMI BPL BVC BVS BRA PHA PHP PHX PHY PLA PLP PLX PLY RTS RTI SEI CLI CLD SEC CLC TAX TAY TXA TYA TXS TSX INX INY DEX DEY NOP'.split()) else -1
        pieces=re.split(r'("[^"]*"|;.*$)',line)
        offset=0;renamed=[]
        for piece in pieces:
            renamed.append(piece if piece.startswith(('"',';')) else re.sub(r'\b\w+\b',lambda m:m[0] if offset+m.start()==protected else mapping.get(m[0],m[0]),piece))
            offset+=len(piece)
        result.append(''.join(renamed))
    return '\n'.join(result)+'\n'

def ramify(text,start,only=None,old=None):
    """Move declared mutable storage into RAM, keeping constant tables in ROM."""
    pos=start;rows=[];usage=[]
    for line in text.splitlines():
        m=re.fullmatch(r'\s*(\w+)\s+(DS\s+(\d+)|DB\s+0)\s*(?:;.*)?',line)
        if m and (only is None or m[1] in only):
            n=int(m[3]) if m[3] else 1
            address=old[m[1]] if old else pos
            rows.append(f'{m[1]} EQU ${address:04X}');usage.append(dict(name=m[1],address=address,bytes=n));pos=address+n
        else:rows.append(line)
    return '\n'.join(rows)+'\n',usage,pos

def main():
    assert not list(OUT.glob('hardware-qualification-*.json'))
    parent=json.loads((BASE/'build.json').read_text())
    assert json.loads((BASE/'hardware-qualification-2609.json').read_text())['passed']
    for n,h in parent['artifacts'].items():assert sha((BASE/n).read_bytes())==h,n
    shutil.copytree(BASE,OUT,dirs_exist_ok=True)
    for p in list(OUT.glob('*test-results.json'))+list(OUT.glob('hardware-qualification-*.json')):p.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    stage=OUT/'xip/source';stage.mkdir(parents=True,exist_ok=True)
    kernel=parent['worker'];equ=''.join(f'K_{n} EQU ${a:04X}\n' for n,a in kernel.items() if n.startswith('V2W_'))
    equ+='X28_GATE EQU $7B90\nX28_READ EQU $7BB1\nX28_EXEC EQU $7BCB\nX28_TAIL EQU $7BD3\nX28_CALL EQU $7B9D\nX28_BANK EQU $7BFA\nX28_CALL_BANK EQU $7BFB\nX28_PTR EQU $DA\n'
    # Fixed gates are assembled separately and checked against the public offsets.
    gate='''        MODULE XIP_GATE
        XDEF G_END
        INCLUDE "kernel.inc"
        CODE
G_START:
        PHP
        PHA
        PHX
        LDA X28_CALL_BANK
        JSR K_V2W_SELECT
        PLX
        PLA
        PLP
G_CALL: JSR $FFFF
        PHP
        PHA
        PHX
        LDA #2
        JSR K_V2W_SELECT
        PLX
        PLA
        PLP
        RTS
G_READ:
        PHP
        PHX
        LDA X28_BANK
        JSR K_V2W_SELECT
        PLX
        PLP
        LDA (X28_PTR),Y
        PHP
        PHA
        PHX
        LDA #2
        JSR K_V2W_SELECT
        PLX
        PLA
        PLP
        RTS
G_EXEC:
        LDA #3
        JSR K_V2W_SELECT
        JMP ($00FE)
G_TAIL:
        LDA X28_CALL_BANK
        JSR K_V2W_SELECT
        JMP (X28_CALL+1)
G_END:
        ENDMOD
'''
    (stage/'kernel.inc').write_text(equ);(stage/'gate.asm').write_text(gate)
    gb,gs,_=assemble(stage,'gate',GATE,'G_END',0x8000)
    equ=re.sub(r'X28_(READ|EXEC|TAIL|CALL) EQU \$[0-9A-F]+',lambda m:f'X28_{m[1]} EQU ${gs["G_"+m[1]]:04X}',equ)
    (stage/'kernel.inc').write_text(equ)
    gb,gs,_=assemble(stage,'gate',GATE,'G_END',0x8000);assert len(gb)<=0x6A
    compiler.include_bytes(stage/'gate-image.inc',gb)
    wrappers={};readers={}
    def call(target,bank='#3',tail=False):
        key=(target,bank,tail)
        if key not in wrappers:wrappers[key]=f'X28_C{len(wrappers)}'
        return wrappers[key]
    def reader(operand):
        if operand not in readers:readers[operand]=f'X28_R{len(readers)}'
        return readers[operand]
    # SRAM: core, layout and hook code are all linked into the same B2 image.
    parts={n:clean((BASE/f'store/source/{f}').read_text()) for n,f in [('C','sram-store.asm'),('A','sram-layout.asm'),('D','sram-data.asm'),('S','sram-stream.asm')]}
    own={n:{d:f'SM_{n}_{d}' for d in defs(t)} for n,t in parts.items()}
    combined={}
    for mapping in own.values():combined.update(mapping)
    smdata=json.loads((BASE/'store/build.json').read_text())
    mutable=set(defs(parts['D'][parts['D'].index('ADDR DS'):]))
    parts['D'],smram,_=ramify(parts['D'],0,mutable,smdata['symbols'])
    parts['C']=parts['C'].replace('JMP (ENTRY)','LDA ENTRY\n        STA $FE\n        LDA ENTRY+1\n        STA $FF\n        JMP X28_EXEC')
    parts['C']=parts['C'].replace('TITLE DB "SRAM 1.2"','TITLE DB "SRAM 1.3"')
    parts['D']=parts['D'].replace('SRAM 1.2','SRAM 1.3')
    sram='\n'.join(rename(parts[n],combined|own[n]) for n in ('C','A','S','D'))
    sram=f'''SM_INIT:
        LDX #{sum(r['bytes'] for r in smram)-1}
SM_CLEAR:
        STZ ${min(r['address'] for r in smram):04X},X
        DEX
        BPL SM_CLEAR
        SEC
        RTS
SM_ENTRY:
        JSR SM_INIT
        JMP SM_C_START
'''+sram
    # WORK keeps only request/cache state in staging and a 64-byte compatibility
    # block at $5000; every API entry remounts state from retained SRAM.
    work=clean((BASE/'workspace/source/workspace.asm').read_text())
    work,workram,wend=ramify(work,0x6800)
    buf=next(r for r in workram if r['name']=='BUF')
    work=work.replace(f'BUF EQU ${buf["address"]:04X}','BUF EQU $6400');buf['address']=0x6400
    assert wend<=0x6B00
    work=work.replace('WORK 1.2','WORK 1.3')
    work=work.replace('#>START','#>$5000').replace('#>APP_END','#>$5040').replace('#<APP_END','#<$5040')
    work=work.replace('API:    SEI','API:    JSR SAVE_WINDOW\n        JSR CLEAR_STATE\n        SEI')
    work=work.replace('API_RETURN:\n','API_RETURN:\n        JSR RESTORE_WINDOW\n')
    work=work.replace('QUIT:   JMP $7E67','QUIT:   JSR RESTORE_WINDOW\n        JMP $7E67')
    work=work.replace('CPU_OK: LDA #0', '''CPU_OK:
        LDA TEMP+1
        CMP #$64
        BCC WINDOW_OK
        BNE WINDOW_START
        LDA TEMP
        BEQ WINDOW_OK
WINDOW_START:
        LDA C+1
        CMP #$64
        BCC WINDOW_BAD
        BNE WINDOW_OK
        LDA C
        CMP #$40
        BCS WINDOW_OK
WINDOW_BAD:
        JMP BAD_ARG
WINDOW_OK: LDA #0''')
    work=f'''ENTRY:  JSR SAVE_WINDOW
        JSR CLEAR_STATE
        JMP CONSOLE
SAVE_WINDOW:
        PHA
        PHX
        LDX #63
SAVE_WINDOW_LOOP:
        LDA $6400,X
        STA $6A40,X
        DEX
        BPL SAVE_WINDOW_LOOP
        PLX
        PLA
        RTS
RESTORE_WINDOW:
        PHA
        PHX
        LDX #63
RESTORE_WINDOW_LOOP:
        LDA $6A40,X
        STA $6400,X
        DEX
        BPL RESTORE_WINDOW_LOOP
        PLX
        PLA
        RTS
CLEAR_STATE:
        PHX
        LDX #0
CLEAR_LOOP:
        STZ $6800,X
        STZ $6900,X
        INX
        BNE CLEAR_LOOP
        LDX #{wend-0x6A00-1}
CLEAR_TAIL:
        STZ $6A00,X
        DEX
        BPL CLEAR_TAIL
        PLX
        RTS
'''+work
    work=rename(work,{n:'WK_'+n for n in defs(work)})
    # EDU no longer switches the mapped bank in flash. All B3 calls go through
    # the bank-safe RAM gate, and tiny mutable state lives outside formatter RAM.
    edu=clean((BASE/'edu/source/edu.asm').read_text())
    a=edu.index('        LDA $7FEC');b=edu.index('        LDX #3',a);edu=edu[:a]+edu[b:]
    edu=edu.replace('QUIT:   LDA OLD_BANK\n        STA $7FEC\n        JMP $7E67','QUIT:   JMP '+call('$7E67',tail=True))
    edu=edu.replace('EDU 1.2','EDU 1.3')
    for symbol,target in [('EDU_STATUS_ENTRY','$EF09'),('EDU_CONFIG_ENTRY','$EF00'),('BOOT_API_PROMOTE','$F039'),('BOOT_API_READ','$F0B2')]:
        edu=re.sub(r'\b(JSR|JMP) '+symbol+r'\b',lambda m:m[1]+' '+call(target),edu)
    edu=edu.replace('LDA EDU_MAGIC_ADDRESS,X','JSR '+reader('$EE92,X'))
    edu,edram,eend=ramify(edu,0x7CF0);assert eend<=0x7D00
    edu=rename(edu,{n:'ED_'+n for n in defs(edu)})
    # MAINT: bank selection becomes a logical data-view selection. Only reads
    # of banked addresses use the RAM read gate. Constants/code always see B2.
    maint=clean((BASE/'maint/bank-maint.asm').read_text())
    maint=maint.replace('START:                  SEI','START:                  SEI\n                        LDX #$FF\nX28_CLEAR_MAINT:        STZ $6200,X\n                        DEX\n                        BPL X28_CLEAR_MAINT')
    a=maint.index('V2W_SELECT:');b=maint.index('MAP_STATUS EQU',a)
    maint=maint[:a]+'''V2W_SELECT:
        STA X28_BANK
        TAX
        LDA $7FEC
        AND #$11
        ORA BANK_BITS,X
        RTS
BANK_BITS DB $CC,$CE,$EC,$EE
'''+maint[b:]
    a=maint.index('V2W_ACCOUNT:');b=maint.index('RTC_OWNER_TEXT:',a);maint=maint[:a]+maint[b:]
    # Existing RAM workers handle all flash busy intervals; B2 is protected
    # against mutation while its utilities are executing.
    maint=maint.replace('CONFIRM:                LDA DB','CONFIRM:                LDA DB\n                        CMP #2\n                        BNE X28_CONFIRM_OTHER\n                        JMP CONFIRM_NO\nX28_CONFIRM_OTHER:      LDA DB')
    maint=maint.replace('CMP #$62\n                        BCC RANGE_FAIL','CMP #$64\n                        BCC RANGE_FAIL')
    a=maint.index('RTC_RAM_CONTINUE:');b=maint.index('RANGE_EDITOR:',a)
    maint=maint[:a]+'RTC_RAM_CONTINUE:\n'+maint[b:]
    a=maint.index('BM_STAGE:');b=maint.index('BM_READ:',a)
    maint=maint[:a]+'BM_STAGE:               JMP BM_BAD\n'+maint[b:]
    maint=re.sub(r'^.*DB "  S 8 / S 9[^\n]*\n','',maint,flags=re.M)
    maint=maint.replace('B3:8-F are protected.','B2 utilities and B3:8-F protected.').replace('Erased does not mean available. B3:8-F protected.','Erased does not mean available. B2 utilities and B3:8-F protected.')
    maint=maint.replace('BANK MAINT 2.2','BANK MAINT 2.3')
    maint=maint.replace('RAM 0200-64FF program; 6500-66FF services protected','MAINT RAM: 5000-63FF buffers/state; 7B90-7BFF gateway')
    maint=maint.replace('JMP $6C03','JMP SM_C_API')
    maint=maint.replace('JMP (DST)','LDA DST\n                        STA X28_CALL+1\n                        LDA DST+1\n                        STA X28_CALL+2\n                        LDA MAPBANK\n                        STA X28_CALL_BANK\n                        JMP X28_TAIL')
    # A=3 used to copy the SRAM executable to RAM. The XIP manager only needs
    # its mutable state reset; AUTO (A=5) still calls the shared executive.
    maint=maint.replace('LDA #3\n        JSR $EF09','JSR SM_INIT')
    maint=maint.replace('SM_SOURCE_BYTE_HOOK','SM_D_SOURCE_BYTE_HOOK').replace('SM_SAVE_TRANSFER_HOOK','SM_D_SAVE_TRANSFER_HOOK').replace('SM_RESTORE_TRANSFER_HOOK','SM_D_RESTORE_TRANSFER_HOOK')
    links=(BASE/'maint/beta27-source/storage-maint-links.inc').read_text()
    # Remaining SM_* aliases refer to the relocated core/data symbols.
    for name in re.findall(r'^(SM_\w+) EQU',links,re.M):
        original=name[3:]
        if original in combined:maint=re.sub(r'\b'+name+r'\b',combined[original],maint)
    # Guard X's flash destination, including the non-erasing byte writer.
    maint=maint.replace('X_CHECK_DEST:', 'X_CHECK_DEST:\n        LDA X_DIRECTION\n        BEQ X28_X_DEST_OK\n        LDA X_BANK\n        CMP #2\n        BNE X28_X_DEST_OK\n        JMP X_BAD\nX28_X_DEST_OK:')
    maint,mram,mend=ramify(maint,0x6200);assert mend<=0x6300
    # Map the checked native bundle as firmware rather than fake saved records.
    maint=maint.replace('        LDA MAPSEC\n        CMP #$E0\n', '        LDA MAPSEC\n        CMP #$E0\n        BCS X28_MAP_ASSET\n        JMP MF_YES\nX28_MAP_ASSET:\n        CMP #$E0\n',1)
    maint=maint.replace('MF_DESCRIPTION:\n','MF_DESCRIPTION:\n        LDA MAPSEC\n        CMP #$E0\n        BCS X28_MAP_DESC_ASSET\n        LDX #<X28_UTIL_TEXT\n        LDY #>X28_UTIL_TEXT\n        JMP PRINT\nX28_MAP_DESC_ASSET:\n')
    maint=maint.replace('BM_END:','X28_UTIL_TEXT DB "Flash utilities 8000-D7FF",0\nBM_END:')
    # Local references to legacy copied worker entry labels become fixed-kernel
    # RAM calls wrapped to restore B2 before any utility instruction resumes.
    worker_names=set(re.findall(r'\bV2W_\w+\b',maint)) - {'V2W_SELECT'}
    # Fixed thunk order makes the generated image independent of Python's hash
    # seed, while retaining the identities used by this candidate's map.
    order=('V2W_MUTATE','V2W_SNAPSHOT','V2W_ANALYZE','V2W_READ','V2W_BYTE')
    assert {n for n in worker_names if n in kernel}==set(order)
    for n in order:
        if n in kernel:maint=re.sub(r'\b(JSR|JMP) '+n+r'\b',lambda m:m[1]+' '+call('K_'+n,'V2_SELECTED' if n in ('V2W_BYTE','V2W_ERASE_RAW') else '#3'),maint)
    for target in ('$F0B2','$EF09','$E011','BOOT_API_ERASE','BOOT_SLOT_CHECK','MAP_CRC_INIT','MAP_CRC_BYTE'):
        resolved={'MAP_CRC_INIT':'$FAB4','MAP_CRC_BYTE':'$FABD'}.get(target,target)
        maint=re.sub(r'\b(JSR|JMP) '+re.escape(target)+r'\b',lambda m:m[1]+' '+call(resolved),maint)
    for target in ('$F007','$E80E'):
        maint=maint.replace('JMP '+target,'JMP '+call(target,tail=True))
    # Indirect flash reads use the logical view; RAM operands retain direct LDA.
    maint=re.sub(r'\bLDA (\((?:SRC|DST|V2_PTR|TZ_PTR)\)(?:,Y)?)',lambda m:'JSR '+reader(m[1]),maint)
    maint=re.sub(r'\bLDA (\$[89A-F][0-9A-F]{3}(?:,X)?)',lambda m:'JSR '+reader(m[1]),maint)
    # Readers refer to pre-namespace ZP aliases, so expand their names here.
    mm={n:'MM_'+n for n in defs(maint)}
    readers={rename(k,mm).strip():v for k,v in readers.items()}
    maint=rename(maint,mm)
    # External monitor constants; standalone clean() removed include directives.
    shared=(BASE/'asm/str8n-v2-eq.inc').read_text()
    shared='\n'.join(l for l in shared.splitlines() if 'INCLUDE' not in l)
    service=(BASE/'asm/service-eq.inc').read_text()
    boot_eq=(BASE/'asm/boot-symbols.inc').read_text()
    (stage/'system.inc').write_text(shared+'\n'+service+'\n'+boot_eq+'\n')
    extra=[]
    for (target,bank,tail),name in wrappers.items():
        extra.append(f'''{name}:
        PHP
        PHA
        LDA #<{target}
        STA X28_CALL+1
        LDA #>{target}
        STA X28_CALL+2
        LDA {bank}
        STA X28_CALL_BANK
        PLA
        PLP
        JMP {'X28_TAIL' if tail else 'X28_GATE'}
''')
    for operand,name in readers.items():
        index=operand.endswith(',X');indirect=operand.startswith('(')
        ptr=operand.split(')')[0][1:] if indirect else operand.split(',')[0]
        extra.append(name+':\n        PHP\n        PHA\n')
        if indirect:
            extra.append(f'        LDA {ptr}\n        STA X28_PTR\n        LDA {ptr}+1\n        STA X28_PTR+1\n')
        else:
            extra.append(f'        LDA #<{ptr}\n        STA X28_PTR\n        LDA #>{ptr}\n        STA X28_PTR+1\n')
        if index:
            extra.append('        TXA\n        CLC\n        ADC X28_PTR\n        STA X28_PTR\n        BCC '+name+'_PTR\n        INC X28_PTR+1\n'+name+'_PTR:\n')
        if not operand.endswith(',Y'):
            # Preserve Y while making a non-indexed read. The result flags are
            # set explicitly after restoring the original processor flags.
            extra.append('        PLA\n        PLP\n        PHY\n        LDY #0\n        JSR X28_READ\n        PLY\n        ORA #0\n        RTS\n')
        else:extra.append('        PLA\n        PLP\n        JMP X28_READ\n')
    # Shared image header and the 64-byte WORK bootstrap carrier are constants.
    prefix='''X28_HEADER: DB "UX",1,0
        JMP MM_START
        JMP SM_ENTRY
        JMP WK_ENTRY
        JMP ED_START
        JMP X28_APPS
X28_GATE_IMAGE:
        INCLUDE "gate-image.inc"
X28_WORK_STUB:
        INCLUDE "work-stub.inc"
'''
    (stage/'work-stub.inc').write_text('        DS 64\n')
    apps_return=parent['launcher']['AP_LIST']+5
    # call() is normally collected before extra is emitted; emit this final
    # simple tail thunk explicitly for the validated flash utility inventory.
    appscode=f'''X28_APPS:
        LDX #15
X28_APPS_SAVE_ZP:
        LDA $D0,X
        PHA
        DEX
        BPL X28_APPS_SAVE_ZP
        LDX #<X28_APPS_TEXT
        LDY #>X28_APPS_TEXT
        JSR WK_PRINT
        LDX #0
X28_APPS_RESTORE_ZP:
        PLA
        STA $D0,X
        INX
        CPX #16
        BNE X28_APPS_RESTORE_ZP
        LDA $7D2E
        STA V2_SELECTED
        PHP
        PHA
        LDA #<${apps_return:04X}
        STA X28_CALL+1
        LDA #>${apps_return:04X}
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL
X28_APPS_TEXT DB 13,10,"MAINT FLASH B2",13,10,"SRAM FLASH B2",13,10,"WORK FLASH B2; API 5003",13,10,"EDU FLASH B2",13,10,0
'''
    text='        MODULE XIP_UTILITIES\n        XDEF X28_END\n        INCLUDE "kernel.inc"\n        INCLUDE "system.inc"\n        CODE\n'+prefix+maint+sram+work+edu+'\n'.join(extra)+appscode+'X28_END:\n        ENDMOD\n'
    (stage/'utilities.asm').write_text(text)
    body,symbols,_=assemble(stage,'utilities',0x8000,'X28_END',0x8020)
    # Work bootstrap enters from any mapped bank and restores that bank on API
    # return. It reinstalls the short RAM gate after S19/staging reuse.
    stub=f'''        MODULE WORK_XIP_STUB
        XDEF STUB_END
        INCLUDE "kernel.inc"
        CODE
        JMP STUB_CONSOLE
        JMP STUB_API
        DB "WK",1,2
STUB_API:
        PHP
        SEI
        PHA
        LDA $7FEC
        PHA
        PHX
        LDA #2
        JSR K_V2W_SELECT
        LDX #{len(gb)-1}
STUB_COPY:
        LDA ${symbols['X28_GATE_IMAGE']:04X},X
        STA $7B90,X
        DEX
        BPL STUB_COPY
        PLX
        PLA
        STA STUB_OLD_BANK
        PLA
        JSR ${symbols['WK_API']:04X}
        PHP
        PHA
        LDA STUB_OLD_BANK
        STA $7FEC
        PLA
        PLP
        PLP
        RTS
STUB_CONSOLE:
        LDA #2
        JSR K_V2W_SELECT
        JMP ${symbols['WK_ENTRY']:04X}
STUB_OLD_BANK DB 0
STUB_END:
        ENDMOD
'''
    # Flags returned by WORK API must survive caller-bank restoration; entry
    # PHP is not restored because the API defines its return flags.
    stub=stub.replace('        PHP\n        SEI','        SEI',1).replace('        PLP\n        PLP\n','        PLP\n')
    (stage/'work-stub.asm').write_text(stub)
    wb,ws,_=assemble(stage,'work-stub',0x5000,'STUB_END',0x5100);assert len(wb)<=64
    compiler.include_bytes(stage/'work-stub.inc',wb+b'\xff'*(64-len(wb)))
    body,ss,_=assemble(stage,'utilities',0x8000,'X28_END',0x8020)
    assert ss==symbols and len(body)<=0x57FE,(len(body),hex(ss['X28_END']))
    asset=body+b'\xff'*(0x57FE-len(body));asset+=crc(asset).to_bytes(2,'big');assert crc(asset)==0
    (OUT/'xip/utilities.bin').write_bytes(asset)
    manifest=dict(version='2.0b28',generation=40,candidate_only=True,board_access=False,boards_flashed=False,flash_bank=2,flash_start=0x8000,flash_end=0xD7FF,flash_reserved_bytes=len(asset),flash_linked_bytes=len(body),flash_spare_bytes=0x57FE-len(body),symbols=symbols,gate_symbols=gs,ram_gate_bytes=len(gb),ram_gate_reserved=[0x7B90,0x7BFF],work_stub_bytes=len(wb),work_stub_reserved=[0x5000,0x503F],mutable=dict(MAINT=mram,SRAM=smram,WORK=workram,EDU=edram),sha256=sha(asset))
    (OUT/'xip/build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    integrate(parent,manifest)
    print('BETA28 XIP utility image:',len(body),'linked / 22528 reserved bytes;',0x57FE-len(body),'spare; RAM gate',len(gb),'WORK stub',len(wb))

def integrate(parent,xip):
    stage=OUT/'storage-status/source'
    text=(BASE/'storage-status/source/storage-services.inc').read_text()
    a=text.index('STORAGE:');b=text.index('LEGACY_R:',a)
    route='''STORAGE:
        CMP #8
        BNE XIP_NOT_APPS
        LDX #4
        JSR V2_SKIP_SPACES
        BEQ XIP_APPS_OK
        JMP SR_CLI_BAD
XIP_APPS_OK:
        LDA #4
        STA $7D2D
        JMP XIP_LOAD
XIP_NOT_APPS:
        CMP #5
        BNE XIP_NOT_AUTO
        JMP AUTO_FIND
XIP_NOT_AUTO:
        CMP #3
        BNE XIP_NORMAL
        JMP XIP_FAIL
XIP_NORMAL:
        LDA $7C00
        CMP #'R'
        BEQ XIP_R
        JMP LEGACY_S
XIP_R:
        LDX #1
        JSR V2_SKIP_SPACES
        CMP #'2'
        BNE XIP_NAME_START
        INX
        JSR V2_SKIP_SPACES
XIP_NAME_START:
        STX $7D2C
'''
    for i,name in enumerate(('MAINT','SRAM','WORK','EDU')):
        route+=f'''        LDX $7D2C
        LDY #0
XIP_MATCH_{i}:
        LDA XIP_NAME_{i},Y
        BEQ XIP_END_{i}
        CMP $7C00,X
        BNE XIP_NEXT_{i}
        INX
        INY
        BRA XIP_MATCH_{i}
XIP_END_{i}:
        JSR V2_SKIP_SPACES
        BEQ XIP_FOUND_{i}
        JMP SR_CLI_BAD
XIP_FOUND_{i}:
        LDA #{i}
        STA $7D2D
        JMP XIP_LOAD
XIP_NEXT_{i}:
'''
    route+='        JMP LEGACY_R\n'
    text=text[:a]+route+text[b:]
    a=text.index('LOAD_MANAGER:');b=text.index('FLASH_BYTE:',a)
    text=text[:a]+text[b:]
    a=text.index('FINALIZER:');b=text.index('AUTO_FIND:',a)
    text=text[:a]+text[b:]
    text=text.replace('CMP #$D8','CMP #$80')
    text=re.sub(r'^MANAGER_(?:NAME|EXPECTED|ERROR) DB[^\n]*\n','',text,flags=re.M)
    load=f'''XIP_LOAD:
        LDA $7D2D
        CMP #1
        BNE XIP_VERIFY
        LDA $7D07
        AND #8
        BNE XIP_VERIFY
        JMP XIP_FAIL
XIP_VERIFY:
        LDA V2_SELECTED
        STA $7D2E
        LDA #2
        STA V2_SELECTED
        STZ V2_ADDR
        LDA #$80
        STA V2_ADDR+1
        LDA #4
        STA V2_COUNT
        JSR V2W_READ
        LDX #3
XIP_HEADER_CHECK:
        LDA V2_BYTES,X
        CMP XIP_MAGIC,X
        BNE XIP_FAIL
        DEX
        BPL XIP_HEADER_CHECK
        JSR AP_CRC_INIT
XIP_CRC:
        JSR FLASH_BYTE
        JSR AP_CRC_BYTE
        INC V2_ADDR
        BNE XIP_CRC
        INC V2_ADDR+1
        LDA V2_ADDR+1
        CMP #$D8
        BNE XIP_CRC
        LDA $7D38
        ORA $7D39
        BNE XIP_FAIL
        LDA #2
        JSR ${parent['worker']['V2W_SELECT']:04X}
        LDX #{xip['ram_gate_bytes']-1}
XIP_GATE_COPY:
        LDA ${xip['symbols']['X28_GATE_IMAGE']:04X},X
        STA $7B90,X
        DEX
        BPL XIP_GATE_COPY
        LDA #3
        STA $7BFA
        STA $7BFB
        STA V2_SELECTED
        LDA $7D2D
        CMP #2
        BNE XIP_ENTER
        LDX #63
XIP_STUB_COPY:
        LDA ${xip['symbols']['X28_WORK_STUB']:04X},X
        STA $5000,X
        DEX
        BPL XIP_STUB_COPY
XIP_ENTER:
        LDA $7D2D
        ASL A
        TAX
        LDA XIP_ENTRIES,X
        STA $FE
        LDA XIP_ENTRIES+1,X
        STA $FF
        JMP ($00FE)
XIP_FAIL:
        LDA #3
        STA V2_SELECTED
        JSR ${parent['worker']['V2W_SELECT']:04X}
        JMP SR_CLI_BAD
XIP_ENTRIES:
'''
    for n in ('MM_START','SM_ENTRY','WK_ENTRY','ED_START','X28_APPS'):
        addr=xip['symbols'][n];load+=f'        DB ${addr&255:02X},${addr>>8:02X}\n'
    for i,n in enumerate(('MAINT','SRAM','WORK','EDU')):load+=f'XIP_NAME_{i} DB "{n}",0\n'
    load+='XIP_MAGIC DB "UX",1,0\n'
    text+=load
    (stage/'storage-services.inc').write_text(text)
    body,ss,_=assemble(stage,'storage-status',0x6E00,'APP_END',0x6E07)
    assert len(body)<=2558,('status overflow',len(body))
    asset=body+b'\xff'*(2558-len(body));asset+=crc(asset).to_bytes(2,'big');(OUT/'boot-status/asset.bin').write_bytes(asset)
    stage=OUT/'loader/source'
    text=(BASE/'loader/source/version-loader.asm').read_text().replace('        CMP #6\n','        CMP #8\n        BCS RANGE_READY\n        CMP #6\n',1)
    (stage/'version-loader.asm').write_text(text)
    lb,ls,_=assemble(stage,'version-loader',0xEF00,'AUX_END',0xEF0C);assert len(lb)<=254
    e=bytearray((BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes());e[0xF00:0xFFE]=lb+b'\xff'*(254-len(lb))
    offset=parent['launcher']['AP_LIST']-0xE000;e[offset:offset+5]=bytes((0xA9,8,0x4C,9,0xEF))
    e[0x7FE:0x800]=crc(e[:0x7FE]).to_bytes(2,'big');e[-2:]=crc(e[:-2]).to_bytes(2,'big');assert crc(e)==crc(e[:0x800])==0
    (OUT/'str8n-v2-recovery-e000-efff.bin').write_bytes(e)
    (OUT/'str8n-v2-recovery-e000-efff.s19').write_bytes(s19(dict(enumerate(e,0xE000)),0xF004))
    # XIP B2 needs its own hardware vectors. Keep the existing VERSION image
    # size/whole-image CRC contract, moving the two-byte seal into tail padding
    # immediately before the vector pocket. The reset route is the initialized
    # RAM reset ABI; B2 is a provider bank entered only after fixed B3 boot.
    v=bytearray((BASE/'version/asset.bin').read_bytes())
    routes={'nmi':parent['vectors']['V2V_NMI'],'reset':parent['vectors']['V2V_RAM_RESET_ENTRY'],'irq_brk':parent['vectors']['V2V_IRQ_BRK']}
    v[-8:]=b'\xff\xff'+b''.join(routes[n].to_bytes(2,'little') for n in ('nmi','reset','irq_brk'))
    seed=crc(v[:-10])
    for word in range(65536):
        patch=word.to_bytes(2,'big')
        if binascii.crc_hqx(patch+v[-8:],seed)==0:
            v[-10:-8]=patch;break
    else:raise AssertionError('No CRC patch for provider vectors')
    assert crc(v)==0 and v[:parent['version_code_bytes']]==(BASE/'version/asset.bin').read_bytes()[:parent['version_code_bytes']]
    (OUT/'version/asset.bin').write_bytes(v)
    # Versioned monitor templates use the unchanged fixed F ABI.
    messages=json.loads((OUT/'source/str8n-v2-text.json').read_text());pool=bytearray();first=next(i for i,m in enumerate(messages) if m['name']=='V2_BAD_PREFIX')
    for i,m in enumerate(messages):
        raw=bytearray(m['text'].replace('{version}','2.0b28').encode())
        if i<first:raw=raw[4:]
        raw[-1]|=128;pool.extend(raw)
    compiler.include_bytes(OUT/'asm/text-image.inc',pool);p=OUT/'asm/text-image.inc';p.write_text('V2_TEXT:\n'+p.read_text())
    compiler.OUT,compiler.SOURCE=OUT,OUT/'asm';fw.OUT=OUT;monitors={};slots={}
    for page in (0xA0,0xB0):
        cells,sy=compiler.assemble(f'monitor-{page:02x}',(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=BASE/'asm'/f'monitor-{page:02x}.asm')
        body=compiler.dense_image(cells,(page<<8)+128,sy['V2_END']);slot=bytearray(fw.slot_image(body,sy,page,40,parent['boot_compatibility']))
        slot[70:72]=sy['V2_M_EDIT'].to_bytes(2,'little');slot[18:20]=crc(slot[:18]+slot[32:]).to_bytes(2,'little');slots[page]=slot;monitors[f'{page:02x}']=sy
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(slot)
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.s19').write_bytes(s19(dict(enumerate(slot,page<<8)),0xF004))
    reference=ROOT/'output/qualification/beta27-2026-10-15/2609/upgrade'
    banks=[bytearray((reference/f'post-reset-b{i}.bin').read_bytes()) for i in range(4)]
    banks[2][:0x5800]=(OUT/'xip/utilities.bin').read_bytes();banks[2][0x5800:0x6200]=asset
    banks[2][0x7800:0x8000]=v
    banks[3][0x6000:0x7000]=e;banks[3][0x2000:0x3000]=slots[0xA0]
    from beta4_migration import journal,metadata,config_sum
    j=journal(banks[3]);cfg=bytearray(j[8:24]);cfg[7:13]=b'P\xA0'+(40).to_bytes(4,'little');cfg[14:]=config_sum(cfg)
    counts=[int.from_bytes(j[24+i*3:27+i*3],'little') for i in range(32)]
    banks[3][0x4000:0x5000]=metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    folder=OUT/'candidate';folder.mkdir(exist_ok=True)
    for i,b in enumerate(banks):(folder/f'b{i}.bin').write_bytes(b)
    (OUT/'str8n-v2-recovery-a000-dfff.bin').write_bytes(slots[0xA0]+slots[0xB0]+banks[3][0x4000:0x6000])
    (OUT/'str8n-v2-recovery-a000-dfff.s19').write_bytes(s19(dict(enumerate((OUT/'str8n-v2-recovery-a000-dfff.bin').read_bytes(),0xA000)),0xF004))
    meta=dict(parent);meta.update(version='2.0b28',generation=40,monitors=monitors,xip_utilities=True,candidate_only=True,board_access=False,boards_flashed=False,hardware_tested=False,parent_build_sha256=sha((BASE/'build.json').read_bytes()),status_symbols=ss,status_code_bytes=ss['APP_END']-0x6E00,status_asset_sha256=sha(asset),version_loader_symbols=ls,version_loader_bytes=len(lb),maintenance_version='2.3',native_utility_manifest='xip/build.json',fallback_version='2.0b27',fallback_generation=39)
    meta['artifacts']=dict(parent['artifacts']);meta['artifacts']['xip/utilities.bin']=xip['sha256'];meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in meta['artifacts']}
    meta.update(version_asset_sha256=sha(v),b2_provider_vectors=routes,version_crc_patch_address=0xFFF6)
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    (folder/'manifest.json').write_text(json.dumps(dict(candidate_only=True,installation_permitted=False,board_access=False,boards_flashed=False,banks=[sha(b) for b in banks],build_sha256=sha((OUT/'build.json').read_bytes()),note='Reference images for offline tests; no installer generated. Flash wear counts are unchanged.'),indent=2)+'\n')

if __name__=='__main__':main()
