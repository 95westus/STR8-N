"""Build/test a RAM-only BASE1 RTC reader; never opens hardware or builds F."""
import ast,binascii,hashlib,json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'release/str8nf-v0.2.0'
OUT=ROOT/'BUILD/rtc-base1-2512-20261029'
sys.path[:0]=[str(ROOT/'tools'),str(REPO/'tools')]
from str8build.assemble import Assembly
from build_system import long_branches
sha=lambda b:hashlib.sha256(bytes(b)).hexdigest()
crc=lambda b:binascii.crc_hqx(bytes(b),65535)
PROMPT=b'RTC BASE1 READ ONLY> '


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copytree(REPO/'src',OUT/'s')
    a=object.__new__(Assembly);a.out=OUT;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[]
    assert a.assembler and a.linker
    stage=OUT/'s/core'
    original=ROOT/'BUILD/rtc-ram-0200-20261026'
    assert sha((original/'collector.bin').read_bytes())=='24a54bd1ded3785647234ece4ad2ed37d42ad0c993716fbd75a0bc04901af8bd'
    source=(original/'s/collector/collector.asm').read_text()
    tail="LDA #'@'\n        JSR $7E6D\n        JMP $7E67"
    assert source.count(tail)==3
    source=source.replace(tail,'RTS')
    (stage/'rtc-api.inc').write_bytes((original/'s/collector/rtc-api.inc').read_bytes())
    (stage/'rtc-sampler.asm').write_text(source,encoding='ascii')
    sampler,ss=a.link('core','rtc-sampler',0x2000,'SERVICE_END')
    assert 0x2000+len(sampler)<0x3000
    prefix=('        MODULE BASE1_RTC_SESSION\n        INCLUDE "str8n-v2-eq.inc"\n'
        '        INCLUDE "str8n-v2-public.inc"\n        INCLUDE "vectors-symbols.inc"\n'
        '        INCLUDE "boot-symbols.inc"\n        CODE\n')
    service=(stage/'mon-absent-service.inc').read_text()
    service=service.replace('MS_START:\n','MS_ACTIVE EQU $7C76\nMS_START:\n        LDA #1\n        STA MS_ACTIVE\n',1)
    service=service.replace("        CMP #'F'\n","        CMP #'R'\n        BEQ MS_RTC\n        CMP #'H'\n        BEQ MS_HISTORY\n        CMP #'I'\n        BEQ MS_IDENTITY\n        CMP #'F'\n",1)
    service=service.replace("        CMP #'J'\n        BEQ MS_BOOT\n",'')
    service=service.replace('MS_WRITE:\n','MS_WRITE:\n        STZ MS_ACTIVE\n',1)
    service=service.replace('MS_BOOT:\n        STZ DC_BINARY\n        JSR V2W_RX_RESET\n        JMP $F004\n','')
    handlers='''MS_RTC:
        LDA MS_ACTIVE
        BEQ MS_BAD
        JSR $2000
        LDA #$00
        STA V2_PTR
        LDA #$14
        STA V2_PTR+1
        LDA #64
        BRA MS_R_SETUP
MS_HISTORY:
        LDA MS_ACTIVE
        BEQ MS_BAD
        JSR $2003
        LDA #$80
        STA V2_PTR
        LDA #$14
        STA V2_PTR+1
        LDA #0
        BRA MS_R_SETUP
MS_IDENTITY:
        LDA MS_ACTIVE
        BEQ MS_BAD
        JSR $2006
        LDA $1481
        STA $1586
        LDA #$80
        STA V2_PTR
        LDA #$15
        STA V2_PTR+1
        LDA #7
MS_R_SETUP:
        STA MS_PAGES
        LDA #'@'
        JSR V2W_PUTC
        BCC MS_LOCK
        JSR J_CRC_INIT
MS_R_BYTE:
        LDA (V2_PTR)
        PHA
        JSR J_CRC_BYTE
        PLA
        JSR V2W_PUTC
        BCC MS_LOCK
        INC V2_PTR
        BNE MS_R_INC
        INC V2_PTR+1
MS_R_INC:
        DEC MS_PAGES
        BNE MS_R_BYTE
        JMP MS_SUM
'''
    service=service.replace('MS_PROMPT: DB "RAM SERVICE BASE1> ",0',handlers+'MS_PROMPT: DB "RTC BASE1 READ ONLY> ",0')
    assert 'MS_BOOT:' not in service and "CMP #'J'" not in service
    (stage/'rtc-session-service.asm').write_text(long_branches(prefix+service+'\n        ENDMOD\n        END\n'),encoding='ascii')
    raw,sy=a.link('core','rtc-session-service',0x6800,'MS_END')
    assert sy['MS_END']<0x7800
    loader='MS_BOOTSTRAP:\n        SEI\n        CLD\n'
    for label,body,dest in [('MS_BLOB',raw,0x6800),('RTC_BLOB',sampler,0x2000)]:
        for offset in range(0,len(body),256):
            size=min(256,len(body)-offset);loop=f'COPY_{label}_{offset}'
            loader+=f'        LDX #0\n{loop}:\n        LDA {label}+{offset},X\n        STA ${dest+offset:04X},X\n        INX\n'
            if size!=256:loader+=f'        CPX #{size}\n'
            loader+=f'        BNE {loop}\n'
    loader+='        JMP $6800\n'
    for label,body in [('MS_BLOB',raw),('RTC_BLOB',sampler)]:
        loader+=label+':\n'
        for n in range(0,len(body),16):loader+=' DB '+','.join(f'${v:02X}' for v in body[n:n+16])+'\n'
    (stage/'rtc-session-loader.asm').write_text(prefix+loader+'MS_LOAD_END:\n        ENDMOD\n        END\n',encoding='ascii')
    image,ls=a.link('core','rtc-session-loader',0x200,'MS_LOAD_END')
    assert ls['MS_LOAD_END']<0x1400
    (OUT/'2512-RTC-BASE1-RAM.bin').write_bytes(image)
    (OUT/'sampler.bin').write_bytes(sampler);(OUT/'service.bin').write_bytes(raw)
    symbols={'sampler':ss,'service':sy,'loader':ls}
    (OUT/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
    sys.path[:0]=[str(ROOT/'tmp/phase13-history/tools'),str(ROOT/'tmp/migration-python')]
    import test_v2_rtc as model
    model.OUT=ROOT/'BUILD/v2-rtc-phase1'
    node=next(n for n in ast.parse((ROOT/'tmp/phase13-history/tools/test_v2_i2c.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Devices')
    namespace={'Memory':model.BusMemory};exec(compile(ast.Module(body=[node],type_ignores=[]),'archived-read-only-I2C-model','exec'),namespace)
    eqs={n:int(v,16) for p in ('vectors-symbols.inc','boot-symbols.inc') for n,v in re.findall(r'^(\w+)\s+EQU\s+\$([0-9A-Fa-f]+)',(stage/p).read_text(),re.M)}
    f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert sha(f)=='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
    checks=[]
    for options in ({},{'rtc_present':False},{'stuck':'scl'},{'stuck':'sda'}):
        mem=namespace['Devices'](**options);mem.devices[0x57]=bytearray(range(256));mem.ram[0xf000:]=f
        owner=bytes((n*7+3)&255 for n in range(0x6500));zp=bytes((n*3+1)&255 for n in range(0xe0))
        mem.ram[0x200:0x6700]=owner;mem.ram[:0xe0]=zp;mem.ram[0x200:0x200+len(image)]=image
        cpu=model.MPU(memory=mem,pc=0x200);cpu.sp=0xff;cpu.p=0x24
        queue=bytearray();output=bytearray();read_index=0
        def run():
            for steps in range(12_000_000):
                if cpu.pc==eqs['BOOT_RECOVERY']:return 'REC'
                if cpu.pc==eqs['V2W_GETC']:
                    if not queue:return 'WAIT'
                    cpu.a=queue.pop(0);cpu.pc=cpu.stPopWord()+1;continue
                if cpu.pc==eqs['V2W_PUTC']:
                    output.append(cpu.a);cpu.p|=1;cpu.pc=cpu.stPopWord()+1;continue
                if cpu.pc in (eqs['V2W_SELECT'],eqs['V2W_RX_RESET'],eqs['BOOT_CON_SELECT']):
                    cpu.pc=cpu.stPopWord()+1;continue
                if cpu.pc==eqs['BOOT_PRINT']:
                    ptr=cpu.x+256*cpu.y
                    while mem.ram[ptr]:output.append(mem.ram[ptr]);ptr+=1
                    cpu.pc=cpu.stPopWord()+1;continue
                cpu.step()
            raise AssertionError(('Unbounded CPU',hex(cpu.pc)))
        assert run()=='WAIT' and output==PROMPT
        assert mem.ram[0x2000:0x2000+len(sampler)]==sampler and mem.ram[0x6800:0x6800+len(raw)]==raw
        packets=[]
        for command,count in ((b'R',64),(b'H',256),(b'I',7)):
            output.clear();queue.extend(command);assert run()=='WAIT'
            assert output[0]==64 and output[-len(PROMPT):]==PROMPT
            body=bytes(output[1:1+count]);assert len(output)==1+count+2+len(PROMPT)
            assert int.from_bytes(output[1+count:3+count],'little')==crc(body)
            packets.append(body)
        if not options:
            assert packets[0][0]==0 and packets[1][0]==0 and packets[1][128:]==bytes(range(128))
            assert packets[2]==bytes(range(0xf2,0xf8))+b'\0'
        output.clear();queue.extend(b'W'+owner+crc(owner).to_bytes(2,'little'));assert run()=='WAIT'
        output.clear();queue.extend(b'Y'+zp+crc(zp).to_bytes(2,'little'));assert run()=='WAIT'
        assert mem.ram[0x200:0x6700]==owner and mem.ram[:0xe0]==zp
        output.clear();queue.extend(b'RHI');assert run()=='WAIT' and b'@' not in output
        output.clear();queue.extend(b'Q');assert run()=='REC'
        assert not mem.writes and mem.ram[0xf000:]==f and mem.ddr==mem.initial_ddr
        checks.append({'fault':options,'passed':True,'owner_RAM_ZP_restored':True,'I2C_device_data_writes':0})
    proof={'passed':True,'CPU':'65C02 only','bytes':len(image),'sha256':sha(image),'sampler_sha256':sha(sampler),'service_sha256':sha(raw),'F_rebuilt':False,'flash_writes':0,'RTC_or_EEPROM_data_writes':0,'checks':checks,'serial_ports_opened':False,'source_sha256':{str(p.relative_to(OUT)):sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.asm','.inc')},'builder_sha256':sha(Path(__file__).read_bytes())}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({k:v for k,v in proof.items() if k!='source_sha256'},indent=2))


if __name__=='__main__':main()
