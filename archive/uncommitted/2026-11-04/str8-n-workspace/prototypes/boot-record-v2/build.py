"""Offline component prototype. No serial imports, board reads or full flash image."""
import argparse,json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from str8build.assemble import Assembly
from str8build.formats import db,save,sha
from str8build.images import boot_sector,monitor_slot
from prepare_monitor_size import offline,ATTEMPTS
offline()
HERE=Path(__file__).resolve().parent
COMPAT=0x31305250

def shared_console(core):
    """Move the selected MON implementations, retaining their call contracts."""
    mon=(core/'monitor-b0.asm').read_text()
    editor=mon[mon.index('\nV2_READ_LINE:')+1:mon.index(' ; IN X=message ordinal.')]
    parsers=(core/'str8n-v2-monitor.inc').read_text()
    parsers=parsers[parsers.index('\nV2_SKIP_SPACES:')+1:]
    # Keep normalized command storage but echo the character actually typed.
    begin=editor.index("                        CMP     #'a'")
    end=editor.index('                        JMP V2_LINE_BYTE',begin)
    editor=editor[:begin]+'''                        CPX     #V2_LINE_LIMIT
                        BCS V2_OVERFLOW
                        PHA
                        CMP     #'a'
                        BCC V2_STORE_CHAR
                        CMP     #'z'+1
                        BCS V2_STORE_CHAR
                        AND     #$DF
V2_STORE_CHAR:         STA     V2_LINE,X
                        INX
                        PLA
                        JSR     V2_PUTC
'''+editor[end:]
    source=editor+'FC_EDITOR_END:\n'+parsers+'FC_PARSERS_END:\n'
    names=re.findall(r'^(\w+):',source,re.M)
    mapping={name:('FC_'+name[3:] if name.startswith('V2_') else 'FC_'+name) for name in names if not name.startswith('FC_')}
    mapping.update(V2_GETC='V2W_GETC',V2_PUTC='V2W_PUTC',V2_NEWLINE='V2V_RAM_NEWLINE',V2_HEX_NIBBLE='V2V_RAM_HEX_NIBBLE')
    return re.sub(r'\b(?:'+ '|'.join(map(re.escape,mapping))+r')\b',lambda m:mapping[m[0]],source)

def long_branches(source):
    inverse={'BEQ':'BNE','BNE':'BEQ','BCS':'BCC','BCC':'BCS','BMI':'BPL','BPL':'BMI','BVS':'BVC','BVC':'BVS'}
    # First build uses explicit long branches; later measurements also show
    # the exact cost of these conservative encodings.
    rows=[];n=0
    for line in source.splitlines():
        m=re.match(r'^(\w+:)?\s*(BEQ|BNE|BCS|BCC|BMI|BPL|BVS|BVC|BRA)\s+(\w+)\s*$',line)
        if not m:rows.append(line);continue
        label,op,dest=m.groups()
        if label:rows.append(label)
        if op=='BRA':rows.append('        JMP '+dest)
        else:
            n+=1;skip='P_LONG_'+str(n)
            rows.extend(['        '+inverse[op]+' '+skip,'        JMP '+dest,skip+':'])
    return '\n'.join(rows)+'\n'

def shorten(source,symbols):
    inverse={'BEQ':'BNE','BNE':'BEQ','BCS':'BCC','BCC':'BCS','BMI':'BPL','BPL':'BMI','BVS':'BVC','BVC':'BVS'}
    def replace(m):
        op,label,dest=m.groups()
        if label in symbols and dest in symbols and -128<=symbols[dest]-(symbols[label]-3)<=127:
            return '        '+inverse[op]+' '+dest+'\n'
        return m.group(0)
    return re.sub(r'        (BEQ|BNE|BCS|BCC|BMI|BPL|BVS|BVC) (JE_LONG_\d+)\n        JMP (\w+)\n\2:\n',replace,source)

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,default=ROOT/'BUILD/rc1-r10p2-g0034');p.add_argument('--out',type=Path,required=True);p.add_argument('--shared-console',action='store_true');p.add_argument('--dual-console',action='store_true');p.add_argument('--opaque-installer',action='store_true');p.add_argument('--bench-core',action='store_true');p.add_argument('--boot-countdown',action='store_true');p.add_argument('--startup-drain',action='store_true');args=p.parse_args()
    if args.startup_drain:args.boot_countdown=True
    if args.boot_countdown:args.opaque_installer=True
    if args.bench_core:args.opaque_installer=True
    if args.opaque_installer:args.dual_console=True
    if args.dual_console:args.shared_console=True
    compat=0x34305250 if args.boot_countdown else (0x33305250 if args.dual_console else (0x32305250 if args.shared_console else COMPAT))
    generation=0x80000006 if args.startup_drain else (0x80000005 if args.boot_countdown else (0x80000004 if args.opaque_installer else (0x80000003 if args.dual_console else (0x80000002 if args.shared_console else 0x80000001))))
    base=args.base.resolve();out=args.out.resolve();assert not out.exists()
    protected={str(x.relative_to(ROOT)):sha(x.read_bytes()) for x in (ROOT/'src/current').rglob('*') if x.is_file()}
    out.mkdir(parents=True);shutil.copytree(base/'s',out/'s');(out/'payload').mkdir()
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');assert a.assembler and a.linker;a.symbols={};a.compiled=[]
    old=json.loads((base/'symbols.json').read_text());core=out/'s/core'
    console=shared_console(core) if args.shared_console else ''
    if args.dual_console:
        eq=out/'s/include/str8n-v2-eq.inc';eq.write_text(eq.read_text()+'\n'+(HERE/'dual-eq.inc').read_text())
        # Per-port CRLF normalization is below the editor. Retain its input
        # owner through command dispatch, then release at the next empty read.
        console=console.replace('FC_READ_LINE:\n','''FC_READ_LINE:
        LDA V2_RX_BAD
        ORA V2_RX_COUNT
        BNE FC_KEEP_OWNER
        STZ DC_OWNER
FC_KEEP_OWNER:
''')
        begin=console.index('                        LSR     V2_SKIP_LF');end=console.index('                        CMP     #$0D',begin)
        console=console[:begin]+'''        PHA
        LDA DC_LAST
        AND DC_SKIP
        BEQ FC_LF_END
        LDA DC_LAST
        TRB DC_SKIP
        PLA
        JMP FC_LINE_BYTE
FC_LF_END:
        PLA
        JMP FC_LINE_END
FC_NOT_LF:
        PHA
        LDA DC_LAST
        TRB DC_SKIP
        PLA
'''+console[end:]
        console=console.replace('                        INC     V2_SKIP_LF\n','''        PHA
        LDA DC_LAST
        TSB DC_SKIP
        PLA
''')
        console=console.replace('FC_BACKSPACE:          TXA\n                        BEQ FC_LINE_BYTE','FC_BACKSPACE:          TXA\n        BNE FC_ERASE_BACKSPACE\n        JMP FC_LINE_BYTE\nFC_ERASE_BACKSPACE:')
        (core/'str8n-v2-ram-console.inc').write_text(long_branches((HERE/'dual-console.inc').read_text()).replace('P_LONG_','JE_LONG_'))
        # Resident B3 writes are already prohibited by MON F/I. Reject the
        # unreachable legacy SELF path explicitly and remove its retry UI.
        flash=(core/'str8n-v2-flash-worker.inc').read_text()
        begin=flash.index('; Never return through old ROM.');end=flash.index('; IN A=byte, output ready',begin)
        flash=flash[:begin]+flash[end:]
        begin=flash.index('                        LDA     V2_SELF\n');end=flash.index('; IN A=byte, output ready',begin)
        flash=flash[:begin]+'''                        STZ V2_NMI_HOLD
                        LDA V2_FLASH_ERROR
                        CMP #1
                        RTS
'''+flash[end:]
        flash=flash.replace('V2W_MUTATE:            SEI','''V2W_MUTATE:            LDA V2_SELF
                        BEQ DC_MUTATE_ALLOWED
                        LDA #3
                        STA V2_FLASH_ERROR
                        SEC
                        RTS
DC_MUTATE_ALLOWED:     SEI''')
        (core/'str8n-v2-flash-worker.inc').write_text(flash)
        worker_source=(core/'str8n-v2-worker.asm').read_text().replace('V2W_END:\n','''; Free the old eight-byte RAM-vector alignment gap for POLL/CHKC.
V2W_CAPS_QUERY:
        LDA #STR8V2_CAPS_FORMAT
        LDX #STR8V2_CAPS_FLAGS
        LDY #STR8V2_CAPS_LENGTH
        SEC
        RTS
V2W_END:
''').replace('                        INCLUDE "str8n-v2-eq.inc"','                        INCLUDE "str8n-v2-eq.inc"\n                        INCLUDE "str8n-v2-public.inc"')
        (core/'str8n-v2-worker.asm').write_text(worker_source)
    original=(ROOT/'src/current/core/str8n-v2-boot.asm').read_text()
    # Keep the proven RAM I/O and flash primitives, but route journal requests
    # to MON/CONFIG. This image is an upper bound before worker pruning.
    worker,ws=a.link('core','str8n-v2-worker',0x7800,'V2W_END')
    if args.dual_console:
        driver=(core/'str8n-v2-ram-console.inc').read_text()
        for _ in range(10):
            compact=shorten(driver,ws)
            if compact==driver:break
            driver=compact;(core/'str8n-v2-ram-console.inc').write_text(driver)
            worker,ws=a.link('core','str8n-v2-worker',0x7800,'V2W_END')
        assert len(worker)<=1020,'Worker overlaps line buffer or DBG metadata'
        vector_source=(core/'str8n-v2-vectors.asm').read_text().replace('LDY     #(STR8V2_BOARD_FT245|STR8V2_BOARD_FT245_PRESENT)','LDY     #(STR8V2_BOARD_FT245|STR8V2_BOARD_FT245_PRESENT|STR8V2_BOARD_ACIA|STR8V2_BOARD_ACIA_TIMED)').replace('BEQ     V2V_RAM_BOARD_DONE','CMP     #2\n                        BNE     V2V_RAM_BOARD_DONE').replace('LDY     #STR8V2_BOARD_FT245','LDY     #(STR8V2_BOARD_FT245|STR8V2_BOARD_FT245_PRESENT|STR8V2_BOARD_ACIA|STR8V2_BOARD_ACIA_TIMED|STR8V2_BOARD_SELECTED_ACIA)').replace('LDA     V2_RESIDENT','LDA     #3')
        begin=vector_source.index('V2V_RAM_CAPS_QUERY:');end=vector_source.index('; Keep the public RAM descriptor',begin)
        vector_source=vector_source[:begin]+'''V2V_RAM_CAPS_QUERY EQU V2W_CAPS_QUERY
V2V_RAM_CON_POLL_ENTRY: JMP V2W_CON_POLL
V2V_RAM_CHKC_ENTRY: JMP V2W_CHKC
        DB "DC"
'''+vector_source[end:]
        (core/'str8n-v2-vectors.asm').write_text(vector_source)
    db(core/'worker-image.inc',worker);(core/'worker-public-symbols.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in ws.items() if k.startswith('V2W_')))
    vectors,vs=a.link('core','str8n-v2-vectors',0x7e20,'V2V_END');db(core/'vectors-image.inc',vectors)
    if args.dual_console:
        assert 0x7e20+len(vectors)<=0x7ef0,'Vector code overlaps relocated DBG stub'
        (core/'vectors-symbols.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in {**ws,**vs}.items() if k.startswith(('V2W_','V2V_')))+f'V2_VECTOR_SIZE EQU ${len(vectors):02X}\n')
        # The expanded worker will be checked against the RAM map after link.
        copy=[' LDX #0','BOOT_COPY_WORKER:']
        for offset in [*range(0,len(worker)-255,256),len(worker)-256]:
            copy.extend([f' LDA BOOT_WORKER_IMAGE+${offset:04X},X',f' STA V2_WORKER+${offset:04X},X'])
        (core/'worker-copy.inc').write_text('\n'.join(copy+[' INX',' BNE BOOT_COPY_WORKER'])+'\n')
    prefix=original[:original.index('                        JSR BOOT_SELECT')]
    if args.shared_console:
        for label,target in [('BOOT_API_LINE','FC_READ_LINE'),('BOOT_API_HEX_WORD','FC_HEX_WORD'),('BOOT_API_HEX_BYTE','FC_HEX_BYTE')]:
            prefix=prefix.replace('                        JMP BOOT_RESERVED',label+': JMP '+target,1)
    prefix+='''        STZ RL_VALID
        LDA #<BOOT_NO_SERVICE
        STA JE_HANDLER
        LDA #>BOOT_NO_SERVICE
        STA JE_HANDLER+1
        JMP BOOT_START_CHOICES
'''
    slot=original[original.index('\nBOOT_SLOT_CHECK:')+1:original.index('; Returning private services')]
    route=original[original.index('BOOT_SR_ROUTE:'):original.index('BOOT_RECOVERY:')]
    reader=original[original.index('BOOT_READ_LINE:'):original.index('; U A|B ->')]
    if args.shared_console:reader='BOOT_READ_LINE: JMP BOOT_API_LINE\n'
    printer=original[original.index('BOOT_PRINT:'):original.index('BOOT_RECOVERY_TEXT:')]
    journal=(ROOT/'src/current/core/str8n-v2-journal.inc').read_text();crc=journal[journal.index('\nJ_CRC_INIT:')+1:journal.index('FBC_PAD_BOOT_REPORT:')]
    extra=(HERE/'boot.inc').read_text().replace('        LDY #>BR_STRINGS','        LDY #>BR_USAGE')
    if args.boot_countdown:
        start=extra.index('BOOT_START_CHOICES:\n');end=extra.index('BR_DEFAULT:\n',start)
        extra=extra[:start]+(HERE/'boot-countdown.inc').read_text()+'\n'+extra[end:]
        start=extra.index('BR_KEY:\n');end=extra.index('BR_BANK EQU',start)
        keys=extra[start:end].replace('BEQ BR_DEFAULT','BEQ BR_NO_KEY').replace('BCC BR_WINDOW','BCC BR_NO_KEY').replace('BCS BR_WINDOW','BCS BR_NO_KEY')
        extra=extra[:start]+keys+extra[end:]
    # Messages can cross pages: use complete addresses rather than a shared hi.
    extra=extra.replace('LDX #<BR_USAGE\n        BRA BR_MESSAGE','LDX #<BR_USAGE\n        LDY #>BR_USAGE\n        BRA BR_MESSAGE').replace('LDX #<BR_REFUSED\nBR_MESSAGE:\n        LDY #>BR_USAGE','LDX #<BR_REFUSED\n        LDY #>BR_REFUSED\nBR_MESSAGE:')
    if args.shared_console:
        extra=extra.replace('        JSR BOOT_READ_LINE\n','        JSR BOOT_READ_LINE\n        BCC BR_SYNTAX\n').replace('DB "PR01"','DB "PR02"')
    if args.dual_console:
        extra=extra.replace('DB "PR02"','DB "PR03"')
        if args.boot_countdown:extra=extra.replace('DB "PR03"','DB "PR04"')
        extra=extra.replace('BOOT_MENU:\n','BOOT_MENU:\n        STZ DC_BINARY\n')
        extra=extra.replace('        LDA V2_LINE+1\n','''        LDA V2_LINE
        CMP #'C'
        BEQ DC_MODE_COMMAND
        LDA V2_LINE+1
''',1)
        extra=extra.replace('BR_SYNTAX:\n','''DC_MODE_COMMAND:
        LDA V2_LINE+2
        BNE BR_SYNTAX
        LDA V2_LINE+1
        SEC
        SBC #'0'
        JSR BOOT_CON_SELECT
        BCC BR_SYNTAX
        JMP BOOT_MENU
BR_SYNTAX:
''')
        extra=extra.replace('RL_LOAD:\n','RL_LOAD:\n        LDA DC_LAST\n        STA DC_BINARY\n')
        extra=extra.replace('RL_OUTPUT:\n','RL_OUTPUT:\n        LDA DC_LAST\n        STA DC_BINARY\n')
        extra=extra.replace('        JSR V2W_PUTC\n        JSR RL_ADVANCE','        JSR V2W_PUTC\n        BCC DC_BINARY_TX_BAD\n        JSR RL_ADVANCE')
        extra=extra.replace('        LDA J_CRC\n        CMP RL_HEADER+12','        LDA V2_RX_BAD\n        BNE BR_ERROR\n        LDA J_CRC\n        CMP RL_HEADER+12')
        extra=extra.replace('        JSR V2W_PUTC\n        LDA J_CRC+1','        JSR V2W_PUTC\n        BCC DC_BINARY_TX_BAD\n        LDA J_CRC+1').replace('        JSR V2W_PUTC\n        JMP BOOT_MENU','        JSR V2W_PUTC\n        BCC DC_BINARY_TX_BAD\n        JMP BOOT_MENU')
        extra=extra.replace('RL_GET:\n','''DC_BINARY_TX_BAD:
        LDX #<DC_TX_ERROR
        LDY #>DC_TX_ERROR
        STZ DC_BINARY
        JMP BR_MESSAGE
DC_TX_ERROR: DB "REFUSED: TX blocked",13,10,0
RL_GET:
''')
        extra=extra.replace('RAM recovery L/R/D/V A/B','RAM recovery L/R/D/V A/B C1/2/3')
        extra+='''BOOT_CON_SELECT:
        DEC A
        CMP #3
        BCS BOOT_CON_SELECT_BAD
        INC A
        STA V2_CONSOLE
        JSR V2W_RX_RESET
        SEC
        RTS
BOOT_CON_SELECT_BAD:
        CLC
        RTS
'''
    source=prefix+extra+slot+route+reader+printer+crc+'''BOOT_HOLD:
        LDA BOOT_ACTIVE
        JMP BOOT_LAUNCH
'''
    source=long_branches(source)
    if args.startup_drain:
        assert source.count('BOOT_START_CHOICES:\n        JSR BOOT_SELECT')==1
        source=source.replace('BOOT_START_CHOICES:\n        JSR BOOT_SELECT', 'BOOT_START_CHOICES:\n        JMP BOOT_STARTUP')
    if args.shared_console:
        (core/'prototype-console.inc').write_text(console)
        source+='BOOT_API_SKIP: JMP FC_SKIP_SPACES\n        INCLUDE "prototype-console.inc"\n'
    source+='''
BOOT_WORKER_IMAGE: INCLUDE "worker-image.inc"
BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"
'''
    if args.startup_drain:source+=(HERE/'boot-startup.inc').read_text()+'\n'
    source+='''
BOOT_END:
        ENDMOD
        END
'''
    (core/'str8n-v2-boot.asm').write_text(source)
    body,bs=a.link('core','str8n-v2-boot',0xf000,'BOOT_END');assert len(body)<=4064
    a.emit('f-offline-component.bin',boot_sector(body,bs,vs,compat))
    # MONs have independent copies of a single source implementation. The RAM
    # CONFIG component links the same implementation without needing either.
    api=''.join(f'{k} EQU ${v:04X}\n' for k,v in bs.items() if ((k.startswith('BOOT_') and v>=0xf000) or k in ('J_CRC_INIT','J_CRC_BYTE')) and k!='BOOT_API_ERASE')
    (core/'boot-symbols.inc').write_text(api)
    private=(core/'app-fixed-symbols.inc').read_text().replace('$FAB4',f'${bs["J_CRC_INIT"]:04X}').replace('$FABD',f'${bs["J_CRC_BYTE"]:04X}')
    (core/'app-fixed-symbols.inc').write_text(private)
    engine_source=(HERE/'engine.inc').read_text()
    if args.opaque_installer:
        guard=(HERE/'journal-guard.inc').read_text()
        engine_source=engine_source.replace('        LDX #15\nJE_CFG_COPY:','        JSR JE_CHECK_DUPLICATES\n        BCC JE_READ_BAD\n        LDX #15\nJE_CFG_COPY:').replace('JE_END:',guard+'\nJE_END:')
    engine=long_branches(engine_source)
    # Distinct label namespaces for generated branch trampolines.
    engine=engine.replace('P_LONG_','JE_LONG_')
    (core/'prototype-engine.inc').write_text(engine)
    (core/'str8n-v2-config.inc').write_text((HERE/'mon-config.inc').read_text())
    monitor=(base/'s/core/monitor-b0.asm').read_text()
    if args.bench_core:
        monitor,n=re.subn(r'^AP_CHECK:\s+LDA \$E000\s*$', 'AP_CHECK:\n        CLC\n        RTS\nAP_LEGACY_DISABLED: LDA $E000',monitor,flags=re.M)
        assert n==1,'Bench E-provider gate was not installed'
        anchor='B29_CHECK_PROVIDER:\n';assert monitor.count(anchor)==1
        monitor=monitor.replace(anchor,'B29_CHECK_PROVIDER:\n        STZ $7EF4\n        STZ $7EE4\n        RTS\nB29_LEGACY_DISABLED:\n')
    if args.shared_console:
        start=monitor.index('\nV2_READ_LINE:')+1;end=monitor.index(' ; IN X=message ordinal.',start)
        monitor=monitor[:start]+'V2_READ_LINE: JMP BOOT_API_LINE\n\n'+monitor[end:]
        helpers=(core/'str8n-v2-monitor.inc').read_text();start=helpers.index('\nV2_SKIP_SPACES:')+1
        (core/'str8n-v2-monitor.inc').write_text(helpers[:start]+'''V2_SKIP_SPACES: JMP BOOT_API_SKIP
V2_HEX_WORD: JMP BOOT_API_HEX_WORD
V2_HEX_BYTE: JMP BOOT_API_HEX_BYTE
''')
        public=out/'s/include/str8n-v2-public.inc'
        public_text=public.read_text().replace('; $F01C is retained as a reserved ROM-table slot. Line editing is monitor\n; policy, not part of the bank-independent application ABI.','; PR02 prototype uses this ROM slot for line editing, requiring B3 visible.\n; It remains reserved in the stock g0034 ABI; no bank-independent line call.')
        public.write_text(public_text+'''\n; PR02 prototype only: B3 must remain visible; shared line/scratch are not reentrant.
; READ_LINE: C=valid; X=length; Y=0/overflow=1/invalid=2/cancel=3.
; HEX_WORD/BYTE: X=line offset; C=valid; V2_VALUE=result; X=delimiter.
STR8V2_PROTO_READ_LINE EQU $F01C
STR8V2_PROTO_HEX_WORD EQU $F02E
STR8V2_PROTO_HEX_BYTE EQU $F031
''')
        if args.dual_console:
            public.write_text(public.read_text()+'''\n; PR03 dual-console extension, identified by "DC" at $7E5E.
STR8V2_PROTO_CON_POLL EQU $7E58
STR8V2_PROTO_CHKC EQU $7E5B
STR8V2_PROTO_CON_SIGNATURE EQU $7E5E
''')
    start=monitor.index('                        LDA     V2_AUTO\n',monitor.index('; Bootstrap already'))
    end=monitor.index('V2_BOOT_DELAY_DONE:',start)
    monitor=monitor[:start]+'''        LDA #<JE_ENTER
        STA JE_HANDLER
        LDA #>JE_ENTER
        STA JE_HANDLER+1
V2_BOOT_MONITOR:
'''+monitor[end:]
    monitor=monitor.replace('JSR $FAB4','JSR J_CRC_INIT').replace('JSR $FABD','JSR J_CRC_BYTE')
    monitor=monitor.replace('B29_GATE_END:\nV2_END:','B29_GATE_END:\n        INCLUDE "prototype-engine.inc"\nV2_END:')
    # Explicit prototype banner; generation is not a new accepted release.
    image=bytes(int(x,16) for x in re.findall(r'\$([0-9A-Fa-f]{2})',(core/'text-image.inc').read_text()))
    assert b'2.0rc1 g0034' in image
    banner=b'2.0proto b06' if args.startup_drain else (b'2.0proto b05' if args.boot_countdown else (b'2.0proto b04' if args.opaque_installer else (b'2.0proto b03' if args.dual_console else (b'2.0proto b02' if args.shared_console else b'2.0proto b01'))))
    image=image.replace(b'2.0rc1 g0034',banner);db(core/'text-image.inc',image,'V2_TEXT:\n')
    slots=[]
    for page in (0xa0,0xb0):
        name=f'monitor-{page:02x}'
        (core/(name+'.asm')).write_text(monitor.replace('V2_IMAGE_PAGE EQU $B0',f'V2_IMAGE_PAGE EQU ${page:02X}'))
        mon,ms=a.link('core',name,(page<<8)+128,'V2_END')
        if page==0xa0:
            for _ in range(10):
                compact=shorten(engine,ms)
                if compact==engine:break
                engine=compact;(core/'prototype-engine.inc').write_text(engine)
                mon,ms=a.link('core',name,(page<<8)+128,'V2_END')
        slots.append(dict(slot='A' if page==0xa0 else 'B',body_bytes=len(mon),header_bytes=128,allocated_bytes=128+len(mon),free=3968-len(mon),writer_start=ms['JE_ENTER'],writer_end=ms['JE_END'],writer_bytes=ms['JE_END']-ms['JE_ENTER'],fits=len(mon)<=3968))
        if len(mon)<=3968:
            image_slot=monitor_slot(mon,ms,page,generation,compat)
            if args.dual_console:
                # Keep fixed bank-switch entry $7848. Relocate the 15-byte
                # DBG trampoline into unused RAM between writer input/state.
                header=image_slot[72:128].replace(bytes.fromhex('9D817B'),bytes.fromhex('9D507C')).replace(bytes.fromhex('A9818D027EA97B8D037E'),bytes.fromhex('A9508D027EA97C8D037E'))
                if args.bench_core:
                    old_pointer=bytes.fromhex('A9508D027EA97C8D037E');assert header.count(old_pointer)==1
                    header=header.replace(old_pointer,bytes([0xA9,vs['V2V_DEFAULT']&255,0x8D,2,0x7e,0xA9,vs['V2V_DEFAULT']>>8,0x8D,3,0x7e]))
                image_slot=bytearray(image_slot);image_slot[72:128]=header
                from str8build.formats import crc as image_crc
                image_slot[18:20]=image_crc(image_slot[:18]+image_slot[32:]).to_bytes(2,'little')
            a.emit(name+'-offline-component.bin',image_slot)
    config='''        MODULE RAM_CONFIG_PROTOTYPE
        XDEF CONFIG_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        CODE
CONFIG_START:
        SEI
        CLD
        LDA #<JE_ENTER
        STA $7C60
        LDA #>JE_ENTER
        STA $7C61
CONFIG_MENU:
        LDX #<CONFIG_TEXT
        LDY #>CONFIG_TEXT
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        LDA V2_LINE
        CMP #'I'
        BEQ CONFIG_INIT
        CMP #'W'
        BEQ CONFIG_W
        CMP #'C'
        BEQ CONFIG_C
        CMP #'Q'
        BEQ CONFIG_QUIT
        BRA CONFIG_MENU
CONFIG_INIT: LDA #5
        BRA CONFIG_CALL
CONFIG_W: LDA #4
        BRA CONFIG_CALL
CONFIG_C:
        LDA V2_LINE+1
        CMP #' '
        BNE CONFIG_MENU
        LDA V2_LINE+3
        BNE CONFIG_MENU
        LDA V2_LINE+2
        STA $7C62
        LDA #1
CONFIG_CALL:
        JSR JE_ENTER
        LDX #<CONFIG_OK
        BCS CONFIG_RESULT
        LDX #<CONFIG_BAD
        LDY #>CONFIG_BAD
        BRA CONFIG_PRINT
CONFIG_RESULT: LDY #>CONFIG_OK
CONFIG_PRINT:
        JSR BOOT_PRINT
        BRA CONFIG_MENU
CONFIG_QUIT: JMP $F004
CONFIG_TEXT: DB "CONFIG prototype I(blank only) W C target Q> ",0
CONFIG_OK: DB "OK",13,10,0
CONFIG_BAD: DB "REFUSED",13,10,0
        INCLUDE "prototype-engine.inc"
CONFIG_END:
        ENDMOD
        END
'''
    if args.shared_console:
        config=config.replace('        JSR BOOT_READ_LINE\n','''        JSR BOOT_READ_LINE
        BCS CONFIG_INPUT_OK
        LDX #<CONFIG_BAD
        LDY #>CONFIG_BAD
        JMP CONFIG_PRINT
CONFIG_INPUT_OK:
''')
    (core/'ram-config.asm').write_text(long_branches(config).replace('P_LONG_','CF_LONG_'))
    cfg,cs=a.link('core','ram-config',0x2000,'CONFIG_END');a.emit('ram-config-offline.bin',cfg)
    installer=None
    if args.opaque_installer:
        from installer_build import build_installer
        installer=build_installer(a,core,out,long_branches)
    save(out/'symbols.json',a.symbols)
    assert protected=={name:sha((ROOT/name).read_bytes()) for name in protected},'Selected source changed during prototype build'
    report=dict(prototype=True,board_access=False,hardware_qualified=False,deployable=False,base_firmware_sha256=sha((base/'firmware.bin').read_bytes()),f=dict(bytes=len(body),free=4064-len(body),end=bs['BOOT_END'],hardware_vector_reservation=32,worker_bytes=len(worker),vectors_bytes=len(vectors)),monitors=slots,config=dict(start=0x2000,end=cs['CONFIG_END'],bytes=len(cfg),writer_start=cs['JE_ENTER'],writer_bytes=cs['JE_END']-cs['JE_ENTER']),shared_writer_storage='Independent ROM copy in each MON slot; same source links in standalone RAM CONFIG. No E/B0/B1/B2 sector added.',compiled=a.compiled,all_components_fit=all(s['fits'] for s in slots))
    report.update(shared_console=args.shared_console,dual_console=args.dual_console,bench_core=args.bench_core,boot_countdown=args.boot_countdown,startup_drain=args.startup_drain,experimental_generation=generation,bootstrap_contract=compat.to_bytes(4,'little').decode(),banner=banner.decode(),journal_duplicate_guard=bool(args.opaque_installer))
    if args.startup_drain:
        report['startup_sequence']=dict(USB_wait_seconds=3,input_drain_seconds=1,drain_message='Consuming input',countdown_seconds=3,initial_input_consumption=False,drain='Fixed iteration budget with cycle-balanced physical FT245/ACIA ready/empty paths; software RX state cleared before and after',binary_transfers='Startup/J3 only; binary transfer handlers unchanged')
    if args.boot_countdown:
        report['startup_countdown']=dict(display='3 2 1 0',seconds_at_8MHz=3,poll_slice_milliseconds=10,policy='Fixed three seconds; saved target honored; stored timeout byte preserved but not used by this UI',ignored_input='CR/LF and invalid keys consume their normal slice without restarting the countdown')
    if installer:report['installer']=installer
    if args.dual_console:
        report['console']=dict(editor_bytes=bs['FC_EDITOR_END']-bs['FC_READ_LINE'],parser_bytes=bs['FC_PARSERS_END']-bs['FC_SKIP_SPACES'],worker_end=ws['V2W_END'],worker_limit=0x7bfc,worker_spare=0x7bfc-ws['V2W_END'],state_start=0x7c29,state_end_exclusive=0x7c30,debugger_trampoline_start=0x7c50,debugger_trampoline_end_exclusive=0x7c5f,ram_extension=dict(POLL=vs['V2V_RAM_CON_POLL_ENTRY'],CHKC=vs['V2V_RAM_CHKC_ENTRY'],signature=0x7e5e),initial_mode='BOTH',mode_masks=dict(FT245=1,ACIA=2,BOTH=3),recovery_select='C1 FT245 / C2 ACIA / C3 BOTH; runtime only',text_output='Best effort mirror; blocked FT245 bytes skipped with sticky lost bit. ACIA uses fixed pacing, not TDRE.',text_input='Fair polling; first input owns a line; competing input drains through its terminator; Ctrl-C accepted from either enabled port.',binary='Initiating port only for load/readback/escrow; blocked FT245 output aborts; text mode restored afterward.',acia=dict(enabled=True,baud=19200,transmit='Existing fixed 8MHz timing loop',receive_errors='Parity/framing/overrun poison the text line or binary load'),ram_layout='No application RAM or $6800-$77FF staging borrowed; DBG metadata $7BFC-$7BFF and registry $7C30-$7C3F preserved; trampoline moved to $7C50-$7C5E; fixed bank selector $7848 retained.',legacy_self_rewrite='Already unreachable via MON B3 F/I protections; now rejects V2_SELF before mutation; retry UI removed.')
    if args.shared_console and not args.dual_console:
        original_f=(base/'payload/str8n-v2-recovery-f000-ffff.bin').read_bytes()
        offset=old['core/str8n-v2-boot']['BOOT_WORKER_IMAGE']-0xf000
        report['console']=dict(editor_bytes=bs['FC_EDITOR_END']-bs['FC_READ_LINE'],parser_bytes=bs['FC_PARSERS_END']-bs['FC_SKIP_SPACES'],editor_start=bs['FC_READ_LINE'],parser_start=bs['FC_SKIP_SPACES'],facade_entries={k:bs[k] for k in ('BOOT_API_LINE','BOOT_API_HEX_WORD','BOOT_API_HEX_BYTE','BOOT_API_SKIP')},worker_identical_to_baseline=worker==original_f[offset:offset+len(worker)],worker_sha256=sha(worker),execution='Text helpers in F/B3; I/O stays in copied RAM worker, usable from every bank.',acia=dict(enabled=False,send_start=ws['V2W_ACIA_SEND'],send_bytes=ws['V2W_UNLOCK']-ws['V2W_ACIA_SEND'],raw_poll_start=ws['V2W_ACIA_RAW_POLL'],raw_poll_bytes=ws['V2W_PUTC']-ws['V2W_ACIA_RAW_POLL'],tx_start=ws['V2W_TX_ACIA'],tx_bytes=ws['V2W_TX_CANCEL']-ws['V2W_TX_ACIA'],conditional_init_bytes=ws['V2W_CON_READY']-ws['V2W_CON_INITIALIZE'],note='Existing dormant routines retained; dispatcher selects FT245. Conditional initialization count includes its LSR/branch.'))
    report.update(device_or_network_attempts=ATTEMPTS,selected_source_unchanged=True,selected_source_hashes=protected,prototype_sources={p.name:sha(p.read_bytes()) for p in HERE.iterdir() if p.is_file()},new_f_features=['read-only boot record scan','S/A/B/0/1/2/3','framed CRC16 RAM load','RAM readback and escrow','explicit RAM run']+(['shared line editor and hex/space parsers'] if args.shared_console else []),limitations=['Not a full firmware image or deployment kit','Old arbitrary-address C/autostart replaced by C default-target; timeout and entry pages are record fields, not UI commands yet','Unchanged auxiliary providers/debugger are not relinked or qualified','Damaged nonblank journals refuse; recovery/migration tooling is not implemented','Timeout tick is CPU-cycle checked; no physical timing qualification','ACIA transport remains dormant and is not qualified by FT245 model tests'])
    if args.dual_console:
        report['new_f_features']+=['dual FT245/ACIA initial console','queued nonblocking POLL and CHKC RAM extension','exclusive binary port ownership','bounded FT245 text output and binary abort on TX blockage']
        report['limitations'][-1]='ACIA tested with register/timing models only; no electrical/CTS/baud hardware qualification. ACIA wire blockage is not software-detected.'
    if args.opaque_installer:
        report['new_ram_tools']=['OIP1 opaque whole-sector installer via verified F RLP1 load/run; MON A/B not required']
        report['limitations'][3]='Nonblank damaged/ambiguous journals refuse; automatic repair is not implemented. Exact-preimage legacy migration is a separate deployment-plan tool.'
        report['limitations'] += ['Opaque target can be torn by interruption; retry requires fresh preimage CRC and an admissible durable wear reservation',
                                  'Malformed/incomplete binary transfers lock the RAM installer until reset; no text-command escape']
    if args.bench_core:
        report['limitations'][2]='Legacy E/B2 providers and DBG1 bytes are retained but explicitly inactive; basic boot/recovery/MON bench profile only'
    save(out/'prototype-report.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('selected_source_hashes','prototype_sources','compiled')},indent=2))

if __name__=='__main__':main()
