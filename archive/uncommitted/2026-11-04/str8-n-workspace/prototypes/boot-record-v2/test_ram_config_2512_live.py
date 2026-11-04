"""Rehearse the exact captured 2512 settings test and its preserving rollback."""
import argparse
import json
import shutil
from pathlib import Path
import board_ram_config_2512 as live
from test_b14_core import load_core
from test_b14_raw import start, feed
from build import long_branches
from str8build.assemble import Assembly

core, _ = load_core()
core.GENERATION = 0x8000000e


def build_fixed(run, original):
    stage = run/'fixed-build'
    if stage.exists(): stage = run/'fixed-build-recheck'
    assert not stage.exists()
    shutil.copytree(live.BUILD/'s',stage/'s'); (stage/'payload').mkdir()
    header = '''        MODULE FIXED_CONFIG_2512
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        CODE
FIX_START:
        SEI
        CLD
        LDA #<JE_ENTER
        STA $7C60
        LDA #>JE_ENTER
        STA $7C61
FIX_MENU:
        LDX #<FIX_PROMPT
        LDY #>FIX_PROMPT
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        BCC FIX_BAD
        LDA V2_LINE+1
        BNE FIX_BAD
        LDA V2_LINE
        CMP #'Q'
        BEQ FIX_QUIT
        CMP #'D'
        BEQ FIX_DISABLE
        CMP #'R'
        BNE FIX_BAD
        LDA #0
        BRA FIX_DISPATCH
FIX_DISABLE:
        LDA #1
FIX_DISPATCH:
        STA FIX_MODE
        LDA #6
        JSR JE_ENTER
        BCC FIX_BAD
        LDX #<FIX_OK
        LDY #>FIX_OK
        BRA FIX_MESSAGE
FIX_BAD:
        LDX #<FIX_ERROR
        LDY #>FIX_ERROR
FIX_MESSAGE:
        JSR BOOT_PRINT
        JMP FIX_MENU
FIX_QUIT:
        JMP BOOT_RECOVERY
; Bound to the captured boot fields except sequence and the three fields
; explicitly varied by this test. Full CRC/history admission occurs first.
CONFIG_BANK_APPLY:
        LDX #29
FIX_COMPARE:
        CPX #14
        BEQ FIX_NEXT
        CPX #13
        BEQ FIX_NEXT
        CPX #7
        BEQ FIX_NEXT
        CPX #8
        BCC FIX_COMPARE_BYTE
        CPX #12
        BCC FIX_NEXT
FIX_COMPARE_BYTE:
        LDA JE_FRAME,X
        CMP FIX_TEMPLATE,X
        BNE FIX_FAIL
FIX_NEXT:
        DEX
        BPL FIX_COMPARE
        LDA JE_FRAME+7
        CMP #'B'
        BEQ FIX_MASK
        CMP #'0'
        BNE FIX_FAIL
FIX_MASK:
        LDA JE_FRAME+13
        CMP #14
        BEQ FIX_ENTRY
        CMP #15
        BNE FIX_FAIL
FIX_ENTRY:
        LDA JE_FRAME+14
        CMP #8
        BEQ FIX_REQUEST
        CMP #10
        BNE FIX_FAIL
FIX_REQUEST:
        LDA FIX_MODE
        BEQ FIX_RESTORE
        ; Disable only from the exact original boot tuple.
        LDA JE_FRAME+7
        CMP #'B'
        BNE FIX_FAIL
        LDA JE_FRAME+13
        CMP #15
        BNE FIX_FAIL
        LDA JE_FRAME+14
        CMP #8
        BNE FIX_FAIL
        LDA #14
        STA JE_FRAME+13
        BRA FIX_VALIDATE
FIX_RESTORE:
        LDA FIX_TEMPLATE+7
        STA JE_FRAME+7
        LDX #29
FIX_RESTORE_BYTE:
        LDA FIX_TEMPLATE,X
        STA JE_FRAME,X
        DEX
        CPX #11
        BNE FIX_RESTORE_BYTE
FIX_VALIDATE:
        JSR BOOT_CHECK_FIELDS
        BCC FIX_FAIL
        JMP JE_APPEND
FIX_FAIL:
        JMP JE_FAIL
FIX_PROMPT: DB "FIXED CONFIG D R Q> ",0
FIX_OK: DB "OK",13,10,0
FIX_ERROR: DB "REFUSED",13,10,0
FIX_MODE: DB 0
FIX_TEMPLATE:
'''
    header += '        DB '+','.join(f'${b:02X}' for b in original[:30])+'\n'
    header += '        INCLUDE "config-engine.inc"\nFIX_END:\n        ENDMOD\n        END\n'
    app = stage/'s/core/fixed-config.asm'
    app.write_text(long_branches(header).replace('P_LONG_','FIX_LONG_'))
    a = object.__new__(Assembly); a.out = stage; a.assembler = shutil.which('wdc02as'); a.linker = shutil.which('wdcln')
    a.symbols = {}; a.compiled = []
    body, sy = a.link('core','fixed-config',0x200,'FIX_END')
    assert 0x200+len(body) <= 0x6500
    if (run/'fixed-config.bin').exists(): assert (run/'fixed-config.bin').read_bytes()==body
    else: live.durable(run/'fixed-config.bin',body)
    return body


def machine(cpu,banks):
    h=core.Machine(live.BUILD,cpu,opaque=True)
    h.m.banks[:]=[bytearray(b) for b in banks]
    h.recovery();h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
    return h


def load(h,body,prompt):
    start(h,1);feed(h,1,body)
    h.run(lambda:bytes(h.m.tx).endswith(prompt))


def command(h,line,prompt):
    out=h.port_command(1,line+b'\r',prompt)
    assert out==line+b'\r\nOK\r\n'+prompt,out


def reset_recovery(h):
    n=len(h.m.tx);h.m.rx.extend(b'Q\r')
    h.run(lambda:len(h.m.tx)>n and bytes(h.m.tx).endswith(live.CHOICES))
    h.m.rx.extend(b'S');h.run(lambda:bytes(h.m.tx).endswith(live.REC))


def main(run):
    assert live.read(run/'state.json')['capture_passed']
    if (run/'model-proof.json').exists():
        live.durable(run/'model-proof-prior-host-helper.json',(run/'model-proof.json').read_bytes())
    original=(run/'original-record.bin').read_bytes()
    banks=[(run/f'before-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert banks==[(run/f'before-r2-b{n}.bin').read_bytes() for n in range(4)]==live.expected_source()
    assert live.latest(banks)==original
    fixed=build_fixed(run,original)
    cfg=(live.BUILD/'payload/ram-config-offline.bin').read_bytes()
    live.durable(run/'original-settings.bin',live.settings(original))
    cases=[];forecasts={}
    for cpu in ('65c02','65c816-e'):
        h=machine(cpu,banks);owner=bytes(h.m.ram[:0xe0])
        load(h,fixed,live.FIX);command(h,b'D',live.FIX)
        assert live.latest(h.m.banks)[13]==14
        h.port_command(1,b'Q\r',live.REC)
        load(h,cfg,live.CFG)
        show=h.port_command(1,b'B\r',live.CFG)
        assert b'B0 OFF ENTRY=8000' in show and b'DEFAULT=B' in show
        command(h,b'B 0 A000',live.CFG);command(h,b'C 0',live.CFG)
        r=live.latest(h.m.banks);assert r[7]==ord('0') and r[13]==15 and r[14]==10
        saved=list(map(bytes,h.m.banks));reset_recovery(h)
        load(h,cfg,live.CFG)
        command(h,b'B 0 8000',live.CFG);command(h,b'C B',live.CFG)
        r=live.latest(h.m.banks)
        assert live.settings(r)==live.settings(original)
        assert r[32:64]+r[160:252]==original[32:64]+original[160:252]
        restored=list(map(bytes,h.m.banks))
        for phase,postimage in (('saved',saved),('restored',restored)):
            for n,data in enumerate(postimage):
                path=run/f'expected-{phase}-b{n}.bin'
                if cpu=='65c02' and not path.exists():live.durable(path,data)
                else:assert path.read_bytes()==data,'CPU postimages differ'
            for n in range(4):
                for offset in range(0,32768,4096):
                    if n==3 and offset in (0x4000,0x5000):continue
                    assert postimage[n][offset:offset+4096]==banks[n][offset:offset+4096]
        erases=[(e[1],e[2]) for e in h.m.events if e[0]=='erase']
        assert erases==[(3,0xc000)]
        for index in range(32):
            a=int.from_bytes(original[64+index*3:67+index*3],'little')
            b=int.from_bytes(r[64+index*3:67+index*3],'little')
            assert b==a+int(index==28)
        assert bytes(h.m.ram[:0xe0])==owner
        # Independently qualify the bounded emergency restore from saved state.
        rollback=machine(cpu,saved);load(rollback,fixed,live.FIX);command(rollback,b'R',live.FIX)
        assert live.settings(live.latest(rollback.m.banks))==live.settings(original)
        damaged=bytearray(banks[3]);damaged[0x5d20]^=1
        bad=list(banks);bad[3]=bytes(damaged)
        refused=machine(cpu,bad);load(refused,fixed,live.FIX)
        assert b'REFUSED' in refused.port_command(1,b'D\r',live.FIX) and not refused.m.events
        cases.append(dict(cpu=cpu,passed=True,mutations=len(h.m.events),journal_erases=erases,
                          temporary_disable=True,actual_enable=True,entry_and_default_persisted=True,
                          original_settings_restored=True,bounded_emergency_restore=True,damaged_journal_refused=True))
        print('PASS',cpu,'exact-source enable/entry/default/reset/restore; one C erase; bounded emergency restore',flush=True)
    artifacts=[live.BUILD/'payload/ram-config-offline.bin',live.BUILD/'ram-config-qualification.json',
               live.SERVICE/'payload/mon-service-load.bin',run/'fixed-config.bin',run/'original-record.bin']
    proof=dict(passed=True,hardware=False,serial_access=False,checks=len(cases),cases=cases,journal_erases=['B3:C'],
        source_bank_sha256=list(map(live.sha,banks)),original_settings_hex=live.settings(original).hex(),
        helper_sha256=live.sha((live.HERE/'board_ram_config_2512.py').read_bytes()),
        checker_sha256=live.sha(Path(__file__).read_bytes()),
        artifact_sha256={str(p):live.sha(p.read_bytes()) for p in artifacts})
    live.save(run/'model-proof.json',proof)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run.resolve())
