"""Port paired DBG1 to BASE1 public BRK/HOLD; no old monitor/flash hooks."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0';REF=REPO/'monitors/devtools/legacy-reference/debugger';OUT=REPO/'monitors/devtools/base1/debugger'
sys.path.insert(0,str(REPO/'tools'));from build_mona import sha

def run():
 OUT.mkdir(parents=True,exist_ok=False)
 source=(REF/'debugger.asm').read_text();start=source.index('DBG_ENTRY:');end=source.index('DBG_CAPTURE:',start)
 activation='''; Single-session RAM1 entry. Caller supplies DBG_TARGET, then launches it.
; Hooks never remain armed at a monitor prompt: X or program HOLD tears down.
DBG_ENTRY:
 SEI
 CLD
 LDA $7E02
 CMP #$57
 BNE DBG_ARM_REFUSE
 LDA $7E03
 CMP #$7E
 BNE DBG_ARM_REFUSE
 LDA $7E67
 CMP #$4C
 BNE DBG_ARM_REFUSE
 LDA $7E68
 CMP #$93
 BNE DBG_ARM_REFUSE
 LDA $7E69
 CMP #$7E
 BNE DBG_ARM_REFUSE
 LDA DBG_TARGET
 STA PTR
 LDA DBG_TARGET+1
 STA PTR+1
 JSR DBG_VALID_PC
 BCC DBG_ARM_REFUSE
 JSR $7E88
 TXA
 STA DBG_CPU
 STZ ACTIVE
 STZ BUSY
 STZ RUNMODE
 STZ REG_VALID
 LDX #39
DBG_ARM_CLEAR:
 STZ BPS,X
 DEX
 BPL DBG_ARM_CLEAR
 LDA $7E02
 STA OLD_BRK
 LDA $7E03
 STA OLD_BRK+1
 LDX #2
DBG_SAVE_HOLD:
 LDA $7E67,X
 STA OLD_HOLD,X
 DEX
 BPL DBG_SAVE_HOLD
 LDA #<DBG_BRK_WRAPPER
 STA $7E02
 LDA #>DBG_BRK_WRAPPER
 STA $7E03
 LDA #<DBG_HOLD
 STA $7E68
 LDA #>DBG_HOLD
 STA $7E69
 JMP (DBG_TARGET)
DBG_ARM_REFUSE:
 LDX #<TXT_ARM_REFUSE
 LDY #>TXT_ARM_REFUSE
 JSR DBG_PRINT
 JMP $7E67
DBG_BRK_WRAPPER:
 PHA
 PHX
 PHY
 LDA $7FEC
 PHA
 JMP DBG_CAPTURE
; Patches and owned public hooks are removed before MON can reuse scratch.
DBG_HOLD:
 SEI
 CLD
 JSR DBG_UNPATCH
 LDA OLD_BRK
 STA $7E02
 LDA OLD_BRK+1
 STA $7E03
 LDX #2
DBG_RESTORE_HOLD:
 LDA OLD_HOLD,X
 STA $7E67,X
 DEX
 BPL DBG_RESTORE_HOLD
 STZ ACTIVE
 STZ BUSY
 STZ REG_VALID
 JMP $7E67
TXT_ARM_REFUSE: DB "DBG refused: vector owner or RAM target",13,10,0
'''
 source=source[:start]+activation+source[end:]
 start=source.index(' LDA BANK\n AND #$EE',source.index('DBG_SAVE_IMAGES:'));end=source.index('DBG_RAM_SOURCE:',start)
 source=source[:start]+source[end:]
 source=source.replace(' JSR DBG_UNPATCH\n STZ ACTIVE\n STZ BUSY\n STZ REG_VALID\n JMP $7E67',' JMP DBG_HOLD',1)
 # Internal checked D/M replaces all calls into old MON and its7DF9 hook.
 start=source.index('DBG_SHARED_PREPARE:');end=source.index('DBG_LOW_MEMORY:',start)
 source=source[:start]+'DBG_SHARED_PREPARE:\n JMP DBG_LOW_MEMORY\n'+source[end:]
 source=source.replace(" STA TEMP_A\n JSR DBG_HEX_WORD", " STA TEMP_A\n JSR DBG_HEX_WORD",1)
 source=source.replace(' CMP #2\n BCC DBG_LOW_MEMORY\n LDA TEMP_A', ' CMP #2\n BCC DBG_LOW_MEMORY\n CMP #$40\n BCS DBG_MEMORY_BAD\n LDA TEMP_A',1)
 source=source.replace(' JMP DBG_LOW_MEMORY\nDBG_LOW_MEMORY:', ' JMP DBG_LOW_MEMORY\nDBG_MEMORY_BAD:\n JMP DBG_ERROR\nDBG_LOW_MEMORY:',1)
 source=source.replace(' INC COUNT\n JSR DBG_SPACES\n BNE DBG_LOW_PARSE',' INC COUNT\n LDA COUNT\n CMP #9\n BCS DBG_LOW_ERROR\n JSR DBG_SPACES\n BNE DBG_LOW_PARSE',1)
 old='DBG_LOW_STACK:\n STA STACK_IMAGE,X\nDBG_LOW_WRITTEN:'
 new='DBG_LOW_STACK:\n CPY #1\n BEQ DBG_WRITE_STACK\n STA (PTR)\n BRA DBG_LOW_WRITTEN\nDBG_WRITE_STACK:\n STA STACK_IMAGE,X\nDBG_LOW_WRITTEN:'
 assert old in source;source=source.replace(old,new)
 # RAM1 leaves0200-3FFF to applications and protects its own code/tables.
 start=source.index('DBG_VALID_PC:');end=source.index('; BRK functions',start)
 source=source[:start]+'''DBG_VALID_PC:
 LDA PTR+1
 CMP #2
 BCC DBG_NOT_VALID
 CMP #$40
 BCS DBG_NOT_VALID
DBG_IS_VALID:
 SEC
 RTS
DBG_NOT_VALID:
 CLC
 RTS

'''+source[end:]
 # Remove unused monitor bank-switch gates while retaining stack/ZP resume.
 start=source.index('RAM_MON_GATE EQU');end=source.index('RAM_RESUME EQU',start);source=source[:start]+source[end:]
 source=source.replace(' DB "DG",1,1',' DB "DG",2,1',1).replace(' DW $1000,DBG_ENTRY,DBG_SYSTEM_REGISTER,AS_OP_TABLE,AS_OP_END',' DW $1000,DBG_ENTRY,DBG_SYSTEM_REGISTER,AS_OP_TABLE,AS_OP_END',1)
 source=source.replace('JMP FAST_RETURN','JMP DBG_FAST_IMAGE')
 (OUT/'debugger.asm').write_text(source,encoding='utf-8')
 layout=(REF/'layout.inc').read_text()
 changes={'ACTIVE':0x7070,'BUSY':0x7071,'RUNMODE':0x7072,'REG_VALID':0x7073,'REGISTRY':0x7400}
 for n,v in changes.items():layout,count=re.subn(rf'^{n} EQU \$[0-9A-F]+',f'{n} EQU ${v:04X}',layout,flags=re.M);assert count==1,n
 layout=re.sub(r'^FAST_RETURN EQU .*','; Early nested return uses local DBG_FAST_IMAGE.',layout,flags=re.M)
 layout+='\nOLD_BRK EQU $7074\nOLD_HOLD EQU $7076\nDBG_CPU EQU $7079\nDBG_TARGET EQU $707A\n'
 (OUT/'layout.inc').write_text(layout)
 for name in ('disasm.inc','step-flow.inc'):(OUT/name).write_text((REF/name).read_text().replace('$7D01','DBG_CPU'))
 (OUT/'provenance.json').write_text(json.dumps(dict(reference={p.name:sha(p.read_bytes()) for p in REF.glob('*')},F_changed=False,status='PORT_SOURCE_NOT_LIVE'),indent=2))
 print('Created separate BASE1 DBG RAM1 sources; legacy guards/hooks removed')

if __name__=='__main__':run()
