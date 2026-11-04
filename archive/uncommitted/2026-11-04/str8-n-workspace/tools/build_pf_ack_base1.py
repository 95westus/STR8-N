"""One-off BASE1 save-before-ACK RAM tool; read-only campaign stays unchanged."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/'tools/build_rtc_base1.py'
OUT=ROOT/'BUILD/pf-ack-base1-2512-20261029'
assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()=='089173072e66106c099a1031f2a834bbeb6ff53b2bbe6a8aed5c9add2e528e56'
source=ORIGINAL.read_text()
def change(old,new):
    global source
    assert source.count(old)==1,old
    source=source.replace(old,new)
change("OUT=ROOT/'BUILD/rtc-base1-2512-20261029'","OUT=ROOT/'BUILD/pf-ack-base1-2512-20261029'")
change("original=ROOT/'BUILD/rtc-ram-0200-20261026'","original=ROOT/'BUILD/rtc-pf-ack-2512-20261027'")
change("assert sha((original/'collector.bin').read_bytes())=='24a54bd1ded3785647234ece4ad2ed37d42ad0c993716fbd75a0bc04901af8bd'","assert sha((original/'ack.bin').read_bytes())==json.loads((original/'proof.json').read_text())['sha256']")
source=source.replace("original/'s/collector/collector.asm'","original/'s/ack/ack.asm'").replace("original/'s/collector/rtc-api.inc'","original/'s/ack/rtc-api.inc'")
change('assert source.count(tail)==3','assert source.count(tail)==4')
change("sampler,ss=a.link('core','rtc-sampler',0x2000,'SERVICE_END')","sampler,ss=a.link('core','rtc-sampler',0x2000,'SERVICE_END')")
change("service=service.replace(\"        CMP #'J'\\n        BEQ MS_BOOT\\n\",'')", """service=service.replace("        CMP #'J'\\n        BEQ MS_BOOT\\n",'')
    service=service.replace("        CMP #'R'\\n", "        CMP #'T'\\n        BEQ MS_STAGE\\n        CMP #'C'\\n        BEQ MS_COMMIT\\n        CMP #'A'\\n        BEQ MS_ACK\\n        CMP #'R'\\n",1)
    service=service.replace('        STA MS_ACTIVE\\n','        STA MS_ACTIVE\\n        STZ MS_COMMIT_USED\\n        STZ MS_ACK_USED\\n',1)
    service=service.replace('MS_ACTIVE EQU $7C76','MS_COMMIT_USED EQU $7C77\\nMS_ACK_USED EQU $7C78\\nMS_ACTIVE EQU $7C76')""")
handlers='''MS_STAGE:
        LDA MS_ACTIVE
        BEQ MS_BAD
        LDA MS_COMMIT_USED
        BNE MS_BAD
        LDX #0
MS_STAGE_NEXT:
        PHX
        JSR V2W_GETC
        PLX
        STA $1600,X
        INX
        CPX #178
        BNE MS_STAGE_NEXT
        JMP MS_MENU
MS_COMMIT:
        LDA MS_ACTIVE
        BEQ MS_BAD
        LDA MS_COMMIT_USED
        BNE MS_BAD
        INC MS_COMMIT_USED
        JSR $2009
        BRA MS_ACK_STATUS
MS_ACK:
        LDA MS_ACTIVE
        BEQ MS_BAD
        LDA MS_COMMIT_USED
        CMP #1
        BNE MS_BAD
        LDA MS_ACK_USED
        BNE MS_BAD
        INC MS_ACK_USED
        JSR $200C
MS_ACK_STATUS:
        LDA #$60
        STA V2_PTR
        LDA #$17
        STA V2_PTR+1
        LDA #4
        JMP MS_R_SETUP
'''
change("    handlers='''MS_RTC:","    handlers='''"+handlers+"MS_RTC:")
source=source.replace('RTC BASE1 READ ONLY> ','PF ACK BASE1> ').replace('2512-RTC-BASE1-RAM.bin','2512-PF-ACK-BASE1-RAM.bin')
source=source.replace("assert ls['MS_LOAD_END']<0x1400","assert ls['MS_LOAD_END']<0x1400")
tests=r'''
    # Full service and relocated ACK engine, including exact durable-log-before-clear.
    ee=bytearray(b'\xff'*256)
    for slot in range(4):
        row=bytearray(32);row[:8]=b'PF\x01'+bytes([slot+1])+b'JR\x20\xa5';row[28:30]=crc(row[:28]).to_bytes(2,'little');ee[32*slot:32*slot+32]=row
    ee[255]=0
    outage=bytes([0x14,0x20,0x28,0x0a,0x14,0x20,0x28,0x0a])
    record=bytearray(b'PF\x01\x01JR\x20\xa5'+(1).to_bytes(4,'little')+outage+bytes([234,7,10,28,0xff,5,20,0]))
    record+=crc(record).to_bytes(2,'little')+b'\xff\xa5';assert len(record)==32
    request=b'PAK1'+bytes([0,0,0x80,0x0c])+outage+record+ee[:128];request+=crc(request).to_bytes(2,'little');assert len(request)==178
    for case in ('normal','bad-crc','bad-magic','changed-preimage','changed-outage','protected','wrong-trim','ACK-without-commit','page-NACK'):
        mem=namespace['Devices'](nack_data=4 if case=='page-NACK' else None);mem.devices[0x57]=bytearray(ee)
        mem.rtc_regs[:9]=bytes([0x80,0x20,0x05,0x3b,0x28,0x10,0x26,0x80,0x0c]);mem.rtc_regs[0x18:0x20]=outage
        mem.ram[0xf000:]=f;mem.ram[0x200:0x6700]=owner;mem.ram[:0xe0]=zp;mem.ram[0x200:0x200+len(image)]=image
        if case=='changed-preimage':mem.devices[0x57][40]^=1
        if case=='changed-outage':mem.rtc_regs[0x18]^=1
        if case=='protected':mem.devices[0x57][255]=0x0c
        if case=='wrong-trim':mem.rtc_regs[8]=0
        initial_rtc=bytes(mem.rtc_regs);initial_ee=bytes(mem.devices[0x57]);seen=0
        cpu=model.MPU(memory=mem,pc=0x200);cpu.sp=0xff;cpu.p=0x24
        queue=bytearray();output=bytearray()
        def ack_run():
            nonlocal seen
            for steps in range(12_000_000):
                if cpu.pc==eqs['BOOT_RECOVERY']:return 'REC'
                if cpu.pc==eqs['V2W_GETC']:
                    if not queue:return 'WAIT'
                    cpu.a=queue.pop(0);cpu.pc=cpu.stPopWord()+1;continue
                if cpu.pc==eqs['V2W_PUTC']:output.append(cpu.a);cpu.p|=1;cpu.pc=cpu.stPopWord()+1;continue
                if cpu.pc in (eqs['V2W_SELECT'],eqs['V2W_RX_RESET'],eqs['BOOT_CON_SELECT']):cpu.pc=cpu.stPopWord()+1;continue
                if cpu.pc==eqs['BOOT_PRINT']:
                    ptr=cpu.x+256*cpu.y
                    while mem.ram[ptr]:output.append(mem.ram[ptr]);ptr+=1
                    cpu.pc=cpu.stPopWord()+1;continue
                cpu.step()
                for dev,address,value in mem.writes[seen:]:
                    if dev==0x6f:
                        assert address==3 and value==0x0b
                        assert bytes(mem.devices[0x57][:32])==record,'ACK before the complete committed record'
                    else:assert dev==0x57 and 0<=address<32,'Write outside selected PF journal slot'
                seen=len(mem.writes)
            raise AssertionError(('Unbounded ACK CPU',case,hex(cpu.pc)))
        assert ack_run()=='WAIT'
        req=bytearray(request)
        if case=='bad-crc':req[-1]^=1
        if case=='bad-magic':req[0]=0;req[-2:]=crc(req[:-2]).to_bytes(2,'little')
        output.clear();queue.extend(b'T'+req);assert ack_run()=='WAIT' and output==PROMPT
        output.clear();queue.extend(b'A' if case=='ACK-without-commit' else b'C');assert ack_run()=='WAIT'
        if case=='normal':
            assert output[0]==64 and output[1]==0 and output[2]==1
            assert mem.rtc_regs[3]&16 and bytes(mem.devices[0x57][:32])==record
            output.clear();queue.extend(b'A');assert ack_run()=='WAIT'
            assert output[0]==64 and output[1]==0 and output[2]==3
            assert not mem.rtc_regs[3]&16 and not any(mem.rtc_regs[0x18:0x20])
            final=bytearray(record);final[30]=0;assert bytes(mem.devices[0x57][:32])==final
            count=len(mem.writes);output.clear();queue.extend(b'CA');assert ack_run()=='WAIT' and b'@' not in output and len(mem.writes)==count
        else:
            assert not any(dev==0x6f for dev,_,_ in mem.writes) and mem.rtc_regs[3]&16
            if case!='page-NACK':assert not mem.writes
        assert mem.rtc_regs[:3]==initial_rtc[:3] and mem.rtc_regs[4:0x18]==initial_rtc[4:0x18]
        assert bytes(mem.devices[0x57][32:])==initial_ee[32:]
        output.clear();queue.extend(b'W'+owner+crc(owner).to_bytes(2,'little'));assert ack_run()=='WAIT'
        queue.extend(b'Y'+zp+crc(zp).to_bytes(2,'little'));assert ack_run()=='WAIT'
        assert mem.ram[0x200:0x6700]==owner and mem.ram[:0xe0]==zp
        count=len(mem.writes);output.clear();queue.extend(b'TCAQ');assert ack_run()=='REC' and len(mem.writes)==count
        checks.append({'ACK_case':case,'passed':True,'all_existing_other_PF_records_preserved':True,'time_trim_and_flash_unchanged':True,'owner_RAM_ZP_restored':True})
'''
change("    proof={'passed':True",tests+"\n    proof={'passed':True")
change("'RTC_or_EEPROM_data_writes':0","'allowed_device_data_writes':'Selected blank PF journal slot; commit/readback before RTC register 03 ACK; acknowledgment marker last'")
namespace=dict(__name__='pf_ack_base1_builder',__file__=str(Path(__file__).resolve()))
exec(compile(source,str(Path(__file__).resolve()),'exec'),namespace)
if __name__=='__main__':
    namespace['main']()
    (OUT/'adapted-builder.py').write_text(source,encoding='utf-8')
