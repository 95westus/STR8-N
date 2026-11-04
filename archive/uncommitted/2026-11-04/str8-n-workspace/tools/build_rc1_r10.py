"""Build isolated RC1 r10 recovery-console firmware from qualified v1g.

Never reads a board. Frozen releases and src/current are not modified.
"""
import argparse, json, re, shutil, sys
from pathlib import Path
from str8build.assemble import Assembly
from str8build.formats import crc, db, save, sha, sealed
from str8build.images import boot_sector, version_asset, monitor_slot

ROOT=Path(__file__).resolve().parents[1]
IDENTITY='rc1-r10-recovery1'
GENERATION=51
COMPAT=0x52313031

def main():
    global IDENTITY,GENERATION,COMPAT
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--current-base',action='store_true',help='retain the complete current RC1 monitor/ASM feature baseline; build r10 p2')
    args=p.parse_args();base=args.base.resolve();out=args.out.resolve()
    assert not out.exists()
    if args.current_base:
        IDENTITY='rc1-r10p2-current';GENERATION=52;COMPAT=0x52313032
        report=json.loads((base/'build-report.json').read_text())
        assert report['passed'] and report['candidate_id']=='fixed-f-flow-size'
        parent=dict(candidate_build='fixed-f-flow-size',firmware_sha256='c85c4055eac41e5e522f1bc62f2bd354957018e3afc1ccdc25a91e52a55a980e')
    else:
        parent=json.loads((base/'candidate-provenance.json').read_text())
        assert parent['candidate_build']=='v1g-BRK82-84-edge-fix'
        assert parent['firmware_sha256']=='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
    assert sha((base/'firmware.bin').read_bytes())==parent['firmware_sha256']
    shutil.copytree(base,out)
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[]
    core=out/'s/core'
    # Bring only the already CPU-qualified fixed-F space optimizations and
    # recovery status initialization, not the development monitor/ASM tree.
    parent_core=base/'s/core' if args.current_base else ROOT/'release/candidates/rc1-r10p2/parent-core'
    if not parent_core.exists():parent_core=ROOT/'src/current/core'
    for name in ('str8n-v2-boot.asm','str8n-v2-journal.inc'):
        shutil.copyfile(parent_core/name,core/name)
    s=(core/'str8n-v2-boot.asm').read_text()
    # Keep all entries through SLOT_CHECK fixed for the inherited monitor.
    # Later private routines are linked together and VERSION receives symbols.
    start=s.index('BOOT_RECOVERY:')
    head=s[:start];tail=s[start:]
    tail=re.sub(r'(?m)^FBC_PAD_\w+:\n(?: DB \$FF(?:,\$FF)*\n)?','',tail)
    s=head+tail
    s=re.sub(r'(?m)^FBC_PAD_BOOT_SR_ROUTE:\n DB \$FF(?:,\$FF)*\n','',s)
    jp=core/'str8n-v2-journal.inc'
    j=jp.read_text();j=re.sub(r'(?m)^(F_SIZE_PADDING:\n) DB \$FF(?:,\$FF)*\n',r'\1',j)
    j=re.sub(r'(?m)^(FBC_PAD_\w+:\n)(?: DB \$FF(?:,\$FF)*\n)?',r'\1',j);jp.write_text(j)
    # Runtime components call the shared CRC at FAB4/FABD directly. Move the
    # vector image back to the tail and explicitly pin this private legacy ABI.
    j=j.replace('BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"\n','')
    jp.write_text(j)
    s=s.replace('BOOT_END:', 'BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"\nBOOT_END:')
    start=s.index('BOOT_RECOVERY:');stop=s.index('; U A|B ->')
    s=s[:start]+'''BOOT_RECOVERY:          JSR V2W_RX_RESET
                        STZ V2_SKIP_LF
                        LDX #<BOOT_RECOVERY_TEXT
                        LDY #>BOOT_RECOVERY_TEXT
                        JSR BOOT_PRINT
BOOT_MENU:              STZ V2_CANCEL_REQUEST
                        LDX #<BOOT_PROMPT_TEXT
                        LDY #>BOOT_PROMPT_TEXT
                        JSR BOOT_PRINT
                        JSR BOOT_READ_LINE
                        LDA V2_LINE
                        BEQ BOOT_MENU
                        CMP #'U'
                        BEQ BOOT_UPDATE
                        LDA V2_LINE+1
                        BNE BOOT_SYNTAX
                        LDA V2_LINE
                        CMP #'W'
                        BEQ BOOT_MENU_W
                        CMP #'A'
                        BEQ BOOT_MENU_A
                        CMP #'B'
                        BNE BOOT_SYNTAX
                        LDA #$B0
                        BRA BOOT_MENU_SLOT
BOOT_MENU_A:            LDA #$A0
BOOT_MENU_SLOT:         STA BOOT_DEST
                        STZ V2_PTR
                        STA V2_PTR+1
                        JSR BOOT_SLOT_CHECK
                        BCC BOOT_IMAGE_BAD
                        LDA BOOT_DEST
                        STA BOOT_ACTIVE
                        JMP BOOT_HOLD
BOOT_MENU_W:            JSR BOOT_REPORT
                        BRA BOOT_MENU
BOOT_SYNTAX:            LDA #BOOT_REASON_SYNTAX-BOOT_REASONS
                        JMP BOOT_REFUSE
BOOT_IMAGE_BAD:         LDA #BOOT_REASON_IMAGE-BOOT_REASONS
                        JMP BOOT_REFUSE

; Shared text reader: echo original keys, normalize ASCII case and CR/LF.
; Four bytes suffice to reject overlong commands; keep draining to delimiter.
BOOT_READ_LINE:         LDX #0
BOOT_LINE:              JSR BOOT_TEXT_GETC
                        CMP #13
                        BEQ BOOT_LINE_END
                        PHA
                        JSR V2W_PUTC
                        PLA
                        CMP #'a'
                        BCC BOOT_LINE_STORE
                        CMP #'z'+1
                        BCS BOOT_LINE_STORE
                        AND #$DF
BOOT_LINE_STORE:        CPX #4
                        BCS BOOT_LINE
                        STA V2_LINE,X
                        INX
                        BRA BOOT_LINE
BOOT_LINE_END:          STZ V2_LINE,X
                        JMP V2V_RAM_NEWLINE
BOOT_TEXT_GETC:         JSR V2W_GETC
                        LSR V2_SKIP_LF
                        BCC BOOT_TEXT_DELIM
                        CMP #10
                        BEQ BOOT_TEXT_GETC
BOOT_TEXT_DELIM:        CMP #13
                        BNE BOOT_TEXT_LF
                        INC V2_SKIP_LF
BOOT_TEXT_LF:           CMP #10
                        BNE BOOT_TEXT_DONE
                        LDA #13
BOOT_TEXT_DONE:         RTS

'''+s[stop:]
    s=s.replace('BNE FBC_UPDATE_REFUSE','BNE BOOT_SYNTAX',3)
    s=s.replace('BEQ FBC_UPDATE_REFUSE\nKEY_LONG_520:', 'BEQ BOOT_ACTIVE_BAD\nKEY_LONG_520:')
    s=s.replace('BEQ FBC_UPDATE_REFUSE\nKEY_LONG_531:', 'BEQ BOOT_PREFERRED_BAD\nKEY_LONG_531:')
    start=s.index('                        JSR V2W_GETC\n',s.index('BOOT_UPDATE_ALLOWED:'))
    stop=s.index('                        LDX #<BOOT_BINARY_TEXT',start)
    s=s[:start]+'''                        JSR BOOT_READ_LINE
                        LDA V2_LINE
                        CMP #'Y'
                        BNE BOOT_CONFIRM_BAD
                        LDA V2_LINE+1
                        BNE BOOT_CONFIRM_BAD
; Finish text input BEFORE the binary-ready prompt. A terminal must send
; the complete CRLF before SEND, and the host waits for SEND before binary.
; The grace window admits a split CRLF without dropping a binary 0A/03.
                        JSR V2W_BOOT_DELAY
                        JSR V2W_RAW_POLL
                        BCC BOOT_BINARY_READY
                        CMP #10
                        BNE BOOT_CONFIRM_BAD
BOOT_BINARY_READY:      JSR V2W_RX_RESET
                        STZ V2_SKIP_LF
'''+s[stop:]
    s=s.replace('FBC_UPDATE_REFUSE: JMP BOOT_UPDATE_BAD','''BOOT_ACTIVE_BAD:        LDA #BOOT_REASON_ACTIVE-BOOT_REASONS
                        BRA BOOT_REFUSE
BOOT_PREFERRED_BAD:     LDA #BOOT_REASON_PREFERRED-BOOT_REASONS
                        BRA BOOT_REFUSE
BOOT_CONFIRM_BAD:       LDA #BOOT_REASON_CONFIRM-BOOT_REASONS
                        BRA BOOT_REFUSE
BOOT_UPDATE_BAD:        LDA V2_FLASH_ERROR
                        CMP #1
                        BEQ BOOT_TIMEOUT_BAD
                        CMP #2
                        BEQ BOOT_VERIFY_BAD
                        LDA #BOOT_REASON_FLASH-BOOT_REASONS
                        BRA BOOT_REFUSE
BOOT_TIMEOUT_BAD:       LDA #BOOT_REASON_TIMEOUT-BOOT_REASONS
                        BRA BOOT_REFUSE
BOOT_VERIFY_BAD:        LDA #BOOT_REASON_VERIFY-BOOT_REASONS
BOOT_REFUSE:            PHA
                        LDX #<BOOT_FAILED_TEXT
                        LDY #>BOOT_FAILED_TEXT
                        JSR BOOT_PRINT
                        PLA
                        CLC
                        ADC #<BOOT_REASONS
                        TAX
                        LDA #>BOOT_REASONS
                        ADC #0
                        TAY
                        JSR BOOT_PRINT
                        JSR V2V_RAM_NEWLINE
                        JMP BOOT_MENU''')
    s=s.replace('BCC BOOT_UPDATE_BAD\n; Reject stale','BCC BOOT_IMAGE_BAD\n; Reject stale')
    s=s.replace('BCC BOOT_UPDATE_BAD\n                        BNE BOOT_UPDATE_NEW','BCC BOOT_GENERATION_BAD\n                        BNE BOOT_UPDATE_NEW')
    s=s.replace('                        BRA BOOT_UPDATE_BAD\nBOOT_UPDATE_NEW:', '                        BRA BOOT_GENERATION_BAD\nBOOT_UPDATE_NEW:')
    start=s.index('BOOT_UPDATE_BAD:        LDX #<BOOT_FAILED_TEXT')
    stop=s.index('BOOT_PRINT:',start)
    s=s[:start]+'''BOOT_GENERATION_BAD:    LDA #BOOT_REASON_GENERATION-BOOT_REASONS
                        JMP BOOT_REFUSE

'''+s[stop:]
    s=s.replace('"REFUSED",$0D,$0A,0','"REFUSED: ",0')
    s=s.replace('BOOT_CHOICE_MONITOR:', '''BOOT_REASONS:
BOOT_REASON_SYNTAX:     DB "use A/B/W/U A|B",0
BOOT_REASON_ACTIVE:     DB "active slot",0
BOOT_REASON_PREFERRED:  DB "preferred slot",0
BOOT_REASON_CONFIRM:    DB "cancelled",0
BOOT_REASON_IMAGE:      DB "invalid image/ABI/CRC",0
BOOT_REASON_GENERATION: DB "generation not newer",0
BOOT_REASON_FLASH:      DB "journal/wear refused",0
BOOT_REASON_TIMEOUT:    DB "flash timeout",0
BOOT_REASON_VERIFY:     DB "flash verify",0
BOOT_CHOICE_MONITOR:''')
    s=s.replace('                        NOP\n'*4,'')
    # Long error exits are explicit; do not depend on assembler relaxation.
    s=s.replace('BCC BOOT_IMAGE_BAD\n; Reject stale', 'BCS R10_IMAGE_OK\n                        JMP BOOT_IMAGE_BAD\nR10_IMAGE_OK:\n; Reject stale')
    for n in range(s.count('                        BCC BOOT_UPDATE_BAD')):
        s=s.replace('                        BCC BOOT_UPDATE_BAD', f'                        BCS R10_COMMIT_OK{n}\n                        JMP BOOT_UPDATE_BAD\nR10_COMMIT_OK{n}:',1)
    s=s.replace('JMP BOOT_UPDATE_BAD\nR10_COMMIT_OK1:', 'JMP BOOT_IMAGE_BAD\nR10_COMMIT_OK1:')
    # Preserve fixed-entry offset; no changes before recovery except source
    # optimizations whose anchors were already retained in the selected tree.
    (core/'str8n-v2-boot.asm').write_text(s)
    body,bs=a.link('core','str8n-v2-boot',0xf000,'BOOT_END')
    assert bs['J_CRC_INIT']<=0xfab4,hex(bs['J_CRC_INIT'])
    padding=0xfab4-bs['J_CRC_INIT']
    if padding:
        j=re.sub(r'(?m)^J_CRC_INIT:', ' DB '+','.join('$FF' for _ in range(padding))+'\nJ_CRC_INIT:',jp.read_text())
        jp.write_text(j);body,bs=a.link('core','str8n-v2-boot',0xf000,'BOOT_END')
    assert bs['J_CRC_INIT']==0xfab4 and bs['J_CRC_BYTE']==0xfabd
    assert bs['BOOT_END']<=0xffe0,hex(bs['BOOT_END'])
    oldsy=json.loads((base/'symbols.json').read_text());sy=dict(oldsy)
    for key in ('BOOT_SLOT_CHECK','BOOT_API_READ','BOOT_API_CFG','BOOT_ERASE_ENTRY','BOOT_API_W','BOOT_API_UPDATE','BOOT_API_PROMOTE'):
        assert bs[key]==oldsy['core/str8n-v2-boot'][key],key
    fixed=boot_sector(body,bs,sy['core/str8n-v2-vectors'],COMPAT)
    a.emit('str8n-v2-recovery-f000-ffff.bin',fixed);sy['core/str8n-v2-boot']=bs
    image=bytearray((base/'firmware.bin').read_bytes());image[-4096:]=fixed
    # VERSION calls private boot routines; regenerate its include and identify
    # the firmware independently of the archive/distribution revision.
    inc=''.join(f'{k} EQU ${v:04X}\n' for k,v in bs.items())
    (out/'s/version/boot-symbols.inc').write_text(inc)
    (out/'s/version/version-links.inc').write_text(inc)
    vp=out/'s/version/version.asm';v=vp.read_text()
    # A separate printed build line avoids changing any monitor text addresses.
    anchor='        JSR BOOT_SELECT'
    assert v.count(anchor)==1
    v=v.replace(anchor,'        LDX #<BUILD_TEXT\n        LDY #>BUILD_TEXT\n        JSR PRINT\n'+anchor)
    v=v.replace('UNNAMED_TEXT DB','BUILD_TEXT DB "Build: '+IDENTITY+'",13,10,0\nUNNAMED_TEXT DB')
    vp.write_text(v)
    version,_=a.link('version','version',0x6e00,'APP_END')
    assert len(version)<=0x300
    asset=version_asset(version,(out/'payload/pf-worker/asset.bin').read_bytes(),sy['core/str8n-v2-vectors'])
    a.emit('version/asset.bin',asset);image[0xf800:0x10000]=asset
    # New bootstrap contract; synchronize MAINT's strict marker guard.
    up=out/'s/xip/utilities.asm'
    guardpath=out/'s/maintenance/maint.inc' if args.current_base else up
    readpath=out/'s/edu/edu.inc' if args.current_base else up
    u=guardpath.read_text()
    sp=out/'s/xip/system.inc'
    sp.write_text(re.sub(r'(?m)^BOOT_COMPAT_DATA EQU \$[0-9A-F]+$',f'BOOT_COMPAT_DATA EQU ${bs["BOOT_COMPAT_DATA"]:04X}',sp.read_text()))
    for index,(old,new) in enumerate(zip((0x44424731).to_bytes(4,'little'),COMPAT.to_bytes(4,'little'))):
        oldtext=f'JSR X28_R{9+index}\n                        CMP #${old:02X}'
        assert u.count(oldtext)==1
        u=u.replace(oldtext,f'JSR X28_R{9+index}\n                        CMP #${new:02X}')
    guardpath.write_text(u)
    u=readpath.read_text()
    for index in range(4):
        u=u.replace(f'#<${0xf684+index:04X}',f'#<${bs["BOOT_COMPAT_DATA"]+index:04X}')
        u=u.replace(f'#>${0xf684+index:04X}',f'#>${bs["BOOT_COMPAT_DATA"]+index:04X}')
    readpath.write_text(u);util,_=a.link('xip','utilities',0x8000,'X28_END')
    asset=sealed(util,0x5800);a.emit('xip/utilities.bin',asset);image[0x8000:0xd800]=asset
    for page in (0xa0,0xb0):
        name=f'str8n-v2-recovery-slot-{page:02x}.bin'
        if args.current_base:
            if page==0xa0:
                text=json.loads((core/'text.json').read_text())
                first=next(i for i,m in enumerate(text) if m['name']=='V2_BAD_PREFIX');pool=bytearray()
                for i,m in enumerate(text):
                    raw=bytearray(m['text'].replace('{version}',f'2.0rc1 g{GENERATION:04X}').encode('ascii'))
                    if i<first:raw=raw[4:]
                    raw[-1]|=128;pool.extend(raw)
                db(core/'text-image.inc',pool,'V2_TEXT:\n')
            module=f'monitor-{page:02x}'
            body,ms=a.link('core',module,(page<<8)+128,'V2_END')
            slot=monitor_slot(body,ms,page,GENERATION,COMPAT)
            oldmon=oldsy['core/'+module]
            for key in ('V2_COMMAND_D','V2_M_EDIT','V2_REENTER','V2_RESET'):
                assert ms[key]==oldmon[key],(key,ms[key],oldmon[key])
        else:slot=bytearray((base/'payload'/name).read_bytes())
        slot[8:12]=GENERATION.to_bytes(4,'little');slot[20:24]=COMPAT.to_bytes(4,'little')
        slot[18:20]=crc(slot[:18]+slot[32:]).to_bytes(2,'little');a.emit(name,slot)
        off=0x10000+(page-0x80)*256;image[off:off+4096]=slot
    # Fresh-image journal only; preserving updater derives the owner's journal.
    from str8build.images import wear_record
    image[0x14000:0x14080]=wear_record(GENERATION)
    sy.update(a.symbols)
    (out/'firmware.bin').write_bytes(image);save(out/'symbols.json',sy)
    dbg=json.loads((out/'debugger-build.json').read_text());dbg.update(generation=GENERATION,firmware_sha256=sha(image),candidate_build=IDENTITY)
    save(out/'debugger-build.json',dbg)
    changed=[i for i in range(24) if image[i*4096:(i+1)*4096]!=(base/'firmware.bin').read_bytes()[i*4096:(i+1)*4096]]
    if args.current_base:
        # The assembler, source-store extension, debugger and dispatcher are
        # retained byte-for-byte from the actual boards' current RC1 baseline.
        old=(base/'firmware.bin').read_bytes()
        for lo,hi in ((0x1000,0x8000),(0x10000,0x12000),(0x16000,0x17000)):
            assert image[lo:hi]==old[lo:hi],(hex(lo),hex(hi))
    save(out/'r10-build.json',dict(identity=IDENTITY,generation=GENERATION,distribution='RC1 r10',boot_compatibility=COMPAT,
        parent_sha256=parent['firmware_sha256'],firmware_sha256=sha(image),fixed_f_end=bs['BOOT_END'],fixed_f_free=0xffe0-bs['BOOT_END'],changed_sectors=changed,
        offline_build=True,board_access=False,hardware_qualified=False,compiled=a.compiled,
        current_features_retained=args.current_base,boot_header=f'STR8-N 2.0rc1 g{GENERATION:04X}' if args.current_base else 'STR8-N 2.0rc1',generation_radix=16,
        sources={str(p.relative_to(out/'s')):sha(p.read_bytes()) for p in (out/'s').rglob('*') if p.suffix in ('.asm','.inc')}))
    print('Built',IDENTITY,'F free',0xffe0-bs['BOOT_END'],flush=True)

if __name__=='__main__':main()
