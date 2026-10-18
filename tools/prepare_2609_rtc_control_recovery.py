"""Build/model a RAM-only, fixed $00->$80 RTC control recovery; no ports."""
import hashlib,json,shutil,sys
from pathlib import Path
import build_v2_config as compiler

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tmp/rcv2609e'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
CODE='''
        XDEF RECOVERY_CONTROL
RECOVERY_CONTROL:
        PHP
        SEI
        CLD
        INC BUSY
        JSR INIT
        BCC RC_FINISH
        JSR SNAPSHOT
        BCC RC_FINISH
        LDA RTC_RAW+8
        CMP #$0E
        BNE RC_DENIED
        LDA RTC_RAW
        AND #$80
        BEQ RC_DENIED
        LDA RTC_RAW+3
        AND #8
        BEQ RC_DENIED
        LDA RTC_RAW+7
        CMP #$80
        BEQ RC_OK
        CMP #0
        BNE RC_DENIED
        LDA #7
        STA REGADDR
        LDA #1
        STA COUNT
        LDA #$80
        STA WRITEBUF
        JSR WRITE_REGS
        BCC RC_FINISH
        JSR SNAPSHOT
        BCC RC_FINISH
        LDA RTC_RAW+7
        CMP #$80
        BNE RC_VERIFY_BAD
RC_OK:  LDA #0
        BRA RC_FINISH
RC_DENIED:
        LDA #6
        BRA RC_FINISH
RC_VERIFY_BAD:
        LDA #7
RC_FINISH:
        STA RC_STATUS
        JSR RESTORE
        STZ BUSY
        PLP
        LDX #0
RC_TEXT_LOOP:
        LDA RC_TEXT,X
        BEQ RC_PRINT_STATUS
        PHX
        JSR $7E6D
        PLX
        INX
        BRA RC_TEXT_LOOP
RC_PRINT_STATUS:
        LDA RC_STATUS
        JSR $7E7C
        JSR $7E7F
        JMP $7E67
RC_STATUS DB 0
RC_TEXT DB "RTC CONTROL STATUS ",0
'''

def main():
    assert not OUT.exists();OUT.mkdir();stage=OUT/'source';stage.mkdir()
    (OUT/'asm').mkdir()
    source=ROOT/'tools/v2-rtc/rtc-service.asm';text=source.read_text();assert text.count('\nSERVICE_END\n')==1
    (stage/'control-recovery.asm').write_text(text.replace('\nSERVICE_END\n',CODE+'\nSERVICE_END\n'))
    shutil.copyfile(ROOT/'tools/v2-rtc/rtc-api.inc',stage/'rtc-api.inc')
    compiler.OUT=OUT;compiler.SOURCE=stage
    cells,S=compiler.assemble('control-recovery',0x3000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    assert S['SERVICE_END']<0x3fc0
    from beta4_migration import s19
    (OUT/'control-recovery.s19').write_bytes(s19(cells,S['RECOVERY_CONTROL']))
    import test_v2_rtc as model
    checks=[]
    for name,ctrl,trim,present,stuck,want in (
        ('restore',0,14,True,None,0),('already-restored',128,14,True,None,0),
        ('wrong-trim',0,0,True,None,6),('alarm-control',16,14,True,None,6),
        ('missing-device',0,14,False,None,2),('bus-stuck',0,14,True,'sda',1)):
        memory=model.BusMemory(present=present,stuck=stuck);memory.regs[7]=ctrl;memory.regs[8]=trim
        original=bytes(memory.regs)
        for address,value in cells.items():memory.ram[address]=value
        for address in (0x7e6d,0x7e7c,0x7e7f):memory.ram[address]=0x60
        cpu=model.MPU(memory=memory,pc=S['RECOVERY_CONTROL'])
        for _ in range(3000000):
            if cpu.pc==0x7e67:break
            cpu.step()
        else:raise AssertionError('Recovery helper did not return to HOLD')
        result=memory.ram[S['RC_STATUS']];assert result==want,(name,result,want)
        assert memory.writes==([(7,128)] if name=='restore' else []),(name,memory.writes)
        assert bytes(memory.regs[:7])==original[:7] and bytes(memory.regs[8:])==original[8:]
        assert memory.ddr==memory.initial_ddr
        assert (memory.latch^memory.initial_latch)&memory.initial_ddr==0
        assert set(memory.accesses)<={0xde,0xdf}
        checks.append(dict(name=name,passed=True,status=result,RTC_data_writes=memory.writes))
    report=dict(passed=True,cases=len(checks),checks=checks,entry=S['RECOVERY_CONTROL'],
        first=min(cells),last=max(cells),image_sha256=sha(OUT/'control-recovery.s19'),
        source_sha256=sha(source),builder_sha256=sha(Path(__file__)),board_access=False,
        writes_limited_to_RTC_register7_value128=True,firmware_changes=False)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),'fixed-control recovery CPU/I2C cases; no port opened')

if __name__=='__main__':main()
