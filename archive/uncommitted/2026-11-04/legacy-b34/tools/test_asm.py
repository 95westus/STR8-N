"""Run the linked ROM assembler through the real launcher/console in the CPU model."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

import os
os.environ['STR8_RTC_BUILD'] = os.environ.get('STR8_ASM_CANDIDATE','BUILD/v2-beta34-candidate')
import build_asm as build
from build_v2_beta34 import descriptor
from test_v2_status import fresh, boot
from test_v2_sram_store import console
from test_v2_spi_resident import Memory, k
model = k.model

def command(cpu, line, limit=100000000):
    return console(cpu,cpu.memory,line,limit=max(limit,100000000))
model.command = command

OUT = build.ROOT/os.environ['STR8_RTC_BUILD']/'assembler'
build.OUT = OUT
REPORT = json.loads((OUT/'build.json').read_text())
IMAGE = (OUT/'asm-e000.bin').read_bytes()
S = REPORT['symbols']
SRC, SRC_LIMIT = S['SOURCE_START'], S['SOURCE_END']
BUF, BUF_LIMIT = S['OUTPUT_START'], S['OUTPUT_END']
BOOT_STATE = None


def fixture(off=False,primary=None):
    cpu,mem=fresh(off=off,primary=primary)
    config=bytes(mem.banks[3][0x4000:0x6000])
    mem.banks=[bytearray((OUT.parent/f'candidate/b{i}.bin').read_bytes()) for i in range(4)]
    mem.banks[3][0x4000:0x6000]=config
    mem.spi.banks=mem.banks
    return cpu,mem


def setup(shell=False,bank=1):
    global BOOT_STATE
    if BOOT_STATE is None:
        boot_cpu,boot_mem=fixture(off=True)
        boot(boot_cpu)
        BOOT_STATE=(bytes(boot_mem.ram),[bytes(b) for b in boot_mem.banks],
                    {r:getattr(boot_cpu,r) for r in ('pc','sp','p','a','x','y')})
    ram,banks,registers=BOOT_STATE
    mem=Memory();mem.ram[:]=ram;mem.banks=[bytearray(b) for b in banks];mem.spi.banks=mem.banks
    cpu=model.MPU(memory=mem,pc=registers['pc'])
    for name,value in registers.items():setattr(cpu,name,value)
    mem.cpu=cpu;mem.spi.cpu=cpu
    offset=REPORT['start']-0x8000
    mem.banks[bank][offset:offset+len(IMAGE)]=IMAGE
    mem.banks[bank][0x7000:]=(OUT/'vectors-f000.bin').read_bytes()
    mem.banks[3][0x66F4:0x6714]=descriptor(IMAGE,bank)
    from beta4_migration import crc
    mem.banks[3][0x67FE:0x6800]=crc(mem.banks[3][0x6000:0x67FE]).to_bytes(2,'big')
    if shell:
        assert f'STR8-N ASM {REPORT["version"]}'.encode() in model.command(cpu,b'ASM\r')
        assert mem.bank==bank
    else:
        mem.bank=bank
    return cpu,mem


def source(mem,lines):
    packed=bytearray()
    for i,line in enumerate(lines,1):
        if isinstance(line,str):line=line.encode('ascii')
        assert len(line)<=120
        packed+=i.to_bytes(2,'little')+bytes((len(line),0))+line
    assert len(packed)<=0x1c00
    mem.ram[SRC:SRC+len(packed)]=packed
    mem.ram[S['SRC_END']:S['SRC_END']+2]=(SRC+len(packed)).to_bytes(2,'little')


def assemble(lines,error=0,cpu_mem=None):
    cpu,mem=cpu_mem or setup()
    source(mem,lines)
    flash=[bytes(b) for b in mem.banks]
    protected=[bytes(mem.ram[a:b]) for a,b in ((0x40,0x100),(0x6500,0x6700))]
    initial_sp=cpu.sp
    failed=model.call(cpu,S['ASM_ASSEMBLE'],10000000)
    assert mem.ram[S['ERROR']]==error, (lines,mem.ram[S['ERROR']],mem.ram[S['LINENO']:S['LINENO']+2])
    assert failed==bool(error) and bool(mem.ram[S['RESULT_VALID']])==(not bool(error))
    assert [bytes(b) for b in mem.banks]==flash and not mem.events
    assert cpu.sp==initial_sp
    assert protected==[bytes(mem.ram[a:b]) for a,b in ((0x40,0x100),(0x6500,0x6700))]
    n=int.from_bytes(mem.ram[S['RESULT_LEN']:S['RESULT_LEN']+2],'little')
    origin=int.from_bytes(mem.ram[S['RESULT_ORIGIN']:S['RESULT_ORIGIN']+2],'little')
    return bytes(mem.ram[BUF:BUF+n]),origin,(cpu,mem)


def encoding_source():
    rows=json.loads((build.SOURCE/'opcodes.json').read_text())
    forms=dict(imp='',acc='A',imm='#$12',zpg='$12',zpx='$12,X',zpy='$12,Y',
        abs='$2345',abx='$2345,X',aby='$2345,Y',inx='($12,X)',iny='($12),Y',
        zpi='($12)',ind='($2345)',iax='($2345,X)',rel='*+2',zpr='$12,*+3')
    operands=dict(imp=b'',acc=b'',imm=b'\x12',zpg=b'\x12',zpx=b'\x12',zpy=b'\x12',
        abs=b'\x45\x23',abx=b'\x45\x23',aby=b'\x45\x23',inx=b'\x12',iny=b'\x12',
        zpi=b'\x12',ind=b'\x45\x23',iax=b'\x45\x23',rel=b'\0',zpr=b'\x12\0')
    lines=[r['name']+' '+forms[r['mode']] for r in rows]
    expected=b''.join(bytes((r['opcode'],))+ (b'\0' if r['name']=='BRK' else operands[r['mode']]) for r in rows)
    return lines,expected


def test_all_encodings():
    lines,expected=encoding_source()
    actual,origin,_=assemble(lines)
    assert actual==expected and origin==BUF
    # Independent WDC toolchain oracle for every instruction and address mode.
    oracle=OUT/'oracle.asm'
    oracle.write_text(' MODULE ORACLE\n CHIP W65C02S\n CODE\n'+''.join(' '+line+'\n' for line in lines)+'\n')
    import build_v2_config as compiler
    import build_v2_recovery as fw
    fw.link = compiler
    compiler.SOURCE = build.ROOT/'src/v2-config'
    fw.link.OUT=OUT
    memory,symbols=fw.link.assemble('oracle',BUF,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=oracle)
    linked=bytes(memory[a] for a in range(BUF,BUF+len(memory)))
    assert actual==linked, (actual.hex(),linked.hex())


def test_labels_and_expressions():
    actual,origin,_=assemble(['.ORG $2000','PORT = $12','start: lda #<done',
        'sta PORT','lda #>done','bne done','bra start','done: word start+2',
        'byte %10101010, 255, -1, \'x\', <($1234+2), >$1234','text "Hi\\n",0'])
    assert origin==0x2000
    assert actual==bytes.fromhex('A9 0A 85 12 A9 20 D0 02 80 F6 02 20 AA FF FF 78 36 12 48 69 0A 00'),actual.hex()
    for lines,expected in (
        (['ORG 0','LDA target','target: BYTE 0'],b'\xad\x03\x00\x00'),
        (['ORG 0','LDA <target','target: BYTE 0'],b'\xa5\x02\x00'),
        (['ORG $1000','BYTE 1','ORG $1004','BYTE 2'],b'\x01\0\0\0\x02'),
        (['FILL 3,$AB','END','INVALID'],b'\xab'*3),
        (['LDA #-1','ASL','INC','DEC A'],b'\xa9\xff\x0a\x1a\x3a'),
        (['BYTE (1+(2+3))-4, >($FF+1), -(-2)'],b'\x02\x01\x02'),
        (['TEXT "a\\\"b\\\\c\\t\\r\\0"'],b'a"b\\c\t\r\0'),
        (['RMB0 ptr','STX ptr,Y','STY ptr,X','ptr = $12'],b'\x07\x12\x96\x12\x94\x12'),
    ):
        actual,_,_=assemble(lines)
        assert actual==expected,(lines,actual.hex())


def test_org_fill():
    cases=[
        (['ORG $2000','BYTE $AA','ORG $2004,$FF','BYTE $55'],b'\xaa\xff\xff\xff\x55',0x2000),
        (['ORG $2000,$FF','BYTE 1','ORG $2004','BYTE 2'],b'\x01\0\0\0\x02',0x2000),
        (['ORG $2000','BYTE 1','ORG $2001,$FF','BYTE 2'],b'\x01\x02',0x2000),
        (['ORG $1000,$FF','ORG $2000,$AB','BYTE 1'],b'\x01',0x2000),
        (['ORG $2000','BYTE 1','ORG $2004,>($1234+1)','BYTE 2'],b'\x01\x12\x12\x12\x02',0x2000),
        (['ORG $2000','BYTE 1','ORG $2004,-1','BYTE 2'],b'\x01\xff\xff\xff\x02',0x2000),
        (['ORG $2000','BYTE 1','ORG $2004,<*','BYTE 2'],b'\x01\x01\x01\x01\x02',0x2000),
        (['ORG 0','BYTE 1','ORG 4,pad','pad = $FF','BYTE 2'],b'\x01\xff\xff\xff\x02',0),
        (['ORG $FFFB','BYTE 1','.ORG $FFFF,$AB ; comment','BYTE 2'],b'\x01\xab\xab\xab\x02',0xfffb),
        (['BYTE 1','ORG $0203,$AA','ORG $0205,$BB','ORG $0207','BYTE 2'],b'\x01\xaa\xaa\xbb\xbb\0\0\x02',0x0200),
    ]
    for lines,expected,origin in cases:
        actual,at,_=assemble(lines);assert actual==expected and at==origin,(lines,actual.hex(),at)
    for lines,error in (
        (['ORG $2000,'],1),(['ORG $2000,$FF,1'],1),(['ORG $2000,256'],5),
        (['ORG $2000,-129'],5),(['ORG $2000,missing'],3),
        (['BYTE 1','ORG earlier,$FF','earlier = $2004'],14),
        (['BYTE 1','ORG $0100,$FF'],5),(['BYTE 1','ORG $3301,$FF'],9),
        (['ORG $FFFF','BYTE 1','ORG $FFFF,$FF'],5)):
        assemble(lines,error)
    actual,_,_=assemble(['BYTE 1','ORG $3300,$FF'])
    assert actual==b'\x01'+b'\xff'*12543
    cpu,mem=setup(shell=True)
    model.command(cpu,b'PASTE\r')
    model.command(cpu,b'ORG $2000\rBYTE $AA\rORG $2004,$FF\rBYTE $55\r.\r')
    assert b'OK 5 bytes' in model.command(cpu,b'ASM\r')
    assert b'2000: AA FF FF FF 55' in model.command(cpu,b'DUMP\r')
    records=model.command(cpu,b'S19\r')
    assert b'S1082000AAFFFFFF55DB' in records,records
    model.command(cpu,b'30 ORG $2004,256\r')
    assert b'Value out of range' in model.command(cpu,b'ASM\r')
    assert b'Assemble successfully first' in model.command(cpu,b'S19\r')


def test_local_symbols():
    cases=[
        (['first: LDX #2','.loop: DEX','BNE .loop','second: LDX #3','.loop: DEX','BNE .loop'],
         bytes.fromhex('A2 02 CA D0 FD A2 03 CA D0 FD')),
        (['main: BRA .done','NOP','.done: WORD .done-main'],bytes.fromhex('80 01 EA 03 00')),
        (['one: BRA .end','two: BRA .end','.end: NOP'],None),
        (['main: NOP','.limit = 3','other = 4','BYTE .limit,other'],bytes.fromhex('EA 03 04')),
        (['loop: NOP','.loop: NOP','WORD loop,.loop'],bytes.fromhex('EA EA 00 02 01 02')),
        (['a: NOP','.loop: NOP','b: NOP','.loop: NOP','WORD .loop'],bytes.fromhex('EA EA EA EA 03 02')),
        (['a: NOP','.LoOp: NOP','bne .lOOp'],bytes.fromhex('EA EA D0 FD')),
        (['abcdefghijklmno: NOP','.abcdefghijklmno: BYTE 1','WORD .abcdefghijklmno'],bytes.fromhex('EA 01 01 02')),
        (['main: .ORG $1000','.word .next','.next: .byte 1','.ORG $1005,$FF'],bytes.fromhex('02 10 01 FF FF')),
        (['main: NOP','BRA .done','BYTE <.done, >.done','.done: RTS'],bytes.fromhex('EA 80 02 05 02 60')),
        (['root:','.x = 1','alias:','.x = 2','BYTE .x'],b'\x02'),
        (['root: BBR0 $12,.done','NOP','.done: RTS'],bytes.fromhex('0F 12 01 EA 60')),
    ]
    for lines,expected in cases:
        if expected is None:assemble(lines,3)
        else:
            actual,_,_=assemble(lines);assert actual==expected,(lines,actual.hex())
    for lines,error in (
        (['.loop: NOP'],15),(['BRA .loop'],15),(['global = 1','.loop: NOP'],15),
        (['main: NOP','.loop: NOP','.loop: RTS'],4),
        (['main: NOP','.value = 1','.value = 2'],4),
        (['main: NOP','WORD .missing'],3),
        (['main: NOP','.a = .later','.later: NOP'],14),
        (['main: NOP','.abcdefghijklmnop: NOP'],1),
        (['main: NOP','WORD main.loop'],1),
    ):assemble(lines,error)
    # Placeholder creation changes table order, not lexical scope identity.
    actual,_,_=assemble(['BRA last','first: NOP','.x: NOP','last: BRA .x','.x: RTS'])
    assert actual==bytes.fromhex('80 02 EA EA 80 00 60')
    # Every local counts toward the same 256-entry limit.
    actual,_,_=assemble(['root: NOP']+[f'.L{i}: NOP' for i in range(255)])
    assert actual==b'\xea'*256
    assemble(['root: NOP']+[f'.L{i}: NOP' for i in range(256)],8)
    assemble([f'G{i}: NOP' for i in range(256)]+['.x: NOP'],8)
    state=setup()
    assemble(['root: NOP','.loop: NOP'],cpu_mem=state)
    assemble(['.loop: NOP'],15,cpu_mem=state)
    cpu,mem=setup(shell=True)
    model.command(cpu,b'PASTE\r')
    model.command(cpu,b'first: LDX #2\r.loop: DEX\rBNE .loop\rsecond: LDX #3\r.loop: DEX\rBNE .loop\r.\r')
    assert b'OK 10 bytes' in model.command(cpu,b'ASM\r')
    assert b'A2 02 CA D0 FD A2 03 CA D0 FD' in model.command(cpu,b'DUMP\r')
    model.command(cpu,b'40\r')
    assert b'Duplicate symbol' in model.command(cpu,b'ASM\r')
    assert b'Assemble successfully first' in model.command(cpu,b'S19\r')


def test_errors_and_bounds():
    cases=[(['LDA missing'],3),(['x: NOP','x: RTS'],4),(['BYTE 256'],5),
        (['LDA #256'],5),(['LDA ($1234),Y'],5),(['BBR0 $100,*'],5),
        (['BRA *+130'],6),(['BRA *-127'],6),(['WAT'],2),(['STX $1234,X'],2),
        (['WORD $10000'],5),(['ORG later','later: NOP'],14),(['a = b','b = 1'],14),
        (['ORG $2000','BYTE 1','ORG $1000'],5),(['BYTE 1,'],1),(['NOP junk'],2),
        (['TEXT "unterminated'],1),(['BYTE (((((((((1)))))))))'],12),
        (['FILL 12545,0'],9),(['ORG $FFFF','WORD 1'],5),(['LDA #'],1)]
    for lines,error in cases:assemble(lines,error)
    for lines,expected in ((['BRA *+129'],b'\x80\x7f'),(['BRA *-126'],b'\x80\x80'),
                           (['ORG $FFFF','BYTE 1'],b'\x01')):
        actual,_,_=assemble(lines)
        assert actual==expected
    actual,_,_=assemble(['FILL 12544,$5A'])
    assert actual==b'\x5a'*12544
    assemble([f'L{i}: NOP' for i in range(257)],8)
    actual,_,_=assemble([f'L{i}: NOP' for i in range(256)])
    assert len(actual)==256


def test_editor_and_console():
    cpu,mem=setup(shell=True)
    flash=[bytes(b) for b in mem.banks]
    for line in (b'30 RTS\r',b'10 ORG $2000\r',b'20 LDA #1\r',b'20 LDA #2\r'):
        assert b'Error' not in model.command(cpu,line)
    listing=model.command(cpu,b'LIST\r')
    assert b'10 ORG $2000\r\n20 LDA #2\r\n30 RTS' in listing,listing
    assert b'OK 3 bytes, origin $2000, buffer $0200' in model.command(cpu,b'ASM\r')
    assert mem.ram[BUF:BUF+3]==b'\xa9\x02\x60'
    assert b'2000: A9 02 60' in model.command(cpu,b'DUMP\r')
    s19=model.command(cpu,b'S19\r').decode('ascii')
    records=[line for line in s19.splitlines() if re.fullmatch('S[19][0-9A-F]{8,}',line)]
    assert records==['S1062000A90260CE','S9032000DC'],records
    for line in (b'20\r',b'25 NOP\r',b'25\r'):
        assert b'Error' not in model.command(cpu,line)
    assert b'20 LDA' not in model.command(cpu,b'LIST\r')
    assert b'Assemble successfully first' in model.command(cpu,b'DUMP\r')
    assert b'OK 1 bytes' in model.command(cpu,b'ASM\r')
    assert b'Error' in model.command(cpu,b'20 '+b'A'*119+b'\r')
    assert b'30 RTS' in model.command(cpu,b'LIST\r')
    assert b'Error' in model.command(cpu,b'20 LDA #1\x03')
    assert b'Error' not in model.command(cpu,b'20 LDA #3\r\n')
    assert b'OK 3 bytes' in model.command(cpu,b'ASM\r')
    assert b'Error' not in model.command(cpu,b'NEW\r')
    assert b'30 RTS' not in model.command(cpu,b'LIST\r')
    assert b'B3>' in model.command(cpu,b'QUIT\r') and mem.bank==3
    assert [bytes(b) for b in mem.banks]==flash and not mem.events


def test_editor_capacity():
    cpu,mem=setup(shell=True)
    # Fill packed source exactly; rejected insertions must preserve all records.
    lines=[';'+'x'*119]*57+[';'+'x'*95]
    source(mem,lines)
    assert int.from_bytes(mem.ram[S['SRC_END']:S['SRC_END']+2],'little')==SRC_LIMIT
    before=bytes(mem.ram[SRC:SRC_LIMIT])
    assert b'Source full' in model.command(cpu,b'100 NOP\r')
    assert mem.ram[SRC:SRC_LIMIT]==before
    assert b'Error' not in model.command(cpu,b'1 NOP\r')
    assert b'Error' not in model.command(cpu,b'100 RTS\r')
    assert b'OK 2 bytes' in model.command(cpu,b'ASM\r')


def test_bulk_paste():
    cpu,mem=setup(shell=True)
    assert b'Paste source' in model.command(cpu,b'PASTE\r')
    pasted=b'ORG $2000\r\n'+b'NOP\r\n'*150+b'RTS\r\n.\r\n'
    assert b'Error' not in model.command(cpu,pasted)
    assert b'OK 151 bytes' in model.command(cpu,b'ASM\r')
    assert mem.ram[BUF:BUF+0x97]==b'\xea'*150+b'\x60'
    assert b'1520 RTS' in model.command(cpu,b'LIST\r')
    model.command(cpu,b'NEW\r')
    model.command(cpu,b'PASTE\r')
    out=model.command(cpu,b'A'*121+b'\rNOP\r.\r')
    assert b'Line too long' in out
    assert b'NOP' not in model.command(cpu,b'LIST\r')
    model.command(cpu,b'PASTE\r')
    assert b'Cancelled' in model.command(cpu,b'NOP\r\x03')
    assert b'OK 1 bytes' in model.command(cpu,b'ASM\r')


def test_generated_program():
    cpu,mem=setup(shell=True)
    before=[bytes(b) for b in mem.banks]
    assert b'Paste source' in model.command(cpu,b'PASTE\r')
    payload=(build.SOURCE/'hello.asm').read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r')+b'.\r'
    assert b'Error' not in model.command(cpu,payload)
    out=model.command(cpu,b'ASM\r')
    assert b'OK 23 bytes' in out,out
    assert b'B3>' in model.command(cpu,b'QUIT\r')
    out=model.command(cpu,b'G 0200\r')
    assert b'OK\r\n' in out and b'B3>' in out,out
    assert [bytes(b) for b in mem.banks]==before and not mem.events


def test_contiguous_code_window():
    assert (BUF,BUF_LIMIT,SRC,SRC_LIMIT,S['SYMBOL_START'],S['SYMBOL_END'],S['STATE_END']) == (0x0200,0x3300,0x3300,0x4F00,0x4F00,0x6300,0x6500)
    cpu,mem=setup(shell=True)
    initial=bytes(mem.ram[BUF:BUF_LIMIT])
    model.command(cpu,b'10 NOP\rLIST\rNEW\r10 FILL 12544,$AB\r')
    assert bytes(mem.ram[BUF:BUF_LIMIT])==initial, 'Editing must not touch user code'
    source_before=bytes(mem.ram[SRC:SRC_LIMIT])
    protected=bytes(mem.ram[0x6500:0x6700])
    result=model.command(cpu,b'ASM\r')
    assert b'OK 12544 bytes, origin $0200, buffer $0200' in result,result
    assert bytes(mem.ram[BUF:BUF_LIMIT])==b'\xAB'*12544
    assert bytes(mem.ram[SRC:SRC_LIMIT])==source_before
    assert bytes(mem.ram[0x6500:0x6700])==protected
    model.command(cpu,b'10 FILL 12545,$AB\r')
    result=model.command(cpu,b'ASM\r')
    assert b'Output full' in result and not mem.ram[S['RESULT_VALID']],result
    assert bytes(mem.ram[0x6500:0x6700])==protected


def test_other_application_banks():
    for bank in (0,2):
        cpu,mem=setup(shell=True,bank=bank)
        before=[bytes(b) for b in mem.banks]
        model.command(cpu,b'10 NOP\r')
        assert b'OK 1 bytes' in model.command(cpu,b'ASM\r')
        assert mem.bank==bank
        assert b'B3>' in model.command(cpu,b'QUIT\r') and mem.bank==3
        assert [bytes(b) for b in mem.banks]==before and not mem.events


def test_save_summary():
    cpu,mem=setup(shell=True)
    flash=[bytes(b) for b in mem.banks]
    for lines,ending in ((['BYTE 1'],'0200'),(['FILL 256,0'],'02FF'),
                         (['FILL 257,0'],'0300'),(['FILL 1439,0'],'079E'),
                         (['FILL 12544,0'],'32FF')):
        source(mem,lines)
        out=model.command(cpu,b'ASM\r')
        assert f'RAM $0200-${ending}\r\n'.encode() in out,out
        assert f'S 1 AUTO 0200 {ending} PROGRAM\r\n'.encode() in out,out
        assert b'After QUIT; change bank/name as needed:' in out
    for lines in ([],['ORG $0200']):
        source(mem,lines);out=model.command(cpu,b'ASM\r')
        assert b'RAM empty; nothing to save.' in out and b'S 1 AUTO ' not in out,out
    for lines in (['ORG $2000','BYTE 1,2,3'],['ORG $FFFF','BYTE 1']):
        source(mem,lines);out=model.command(cpu,b'ASM\r')
        assert b'ORG differs; use S19/load at origin before Store.' in out,out
        assert b'S 1 AUTO ' not in out,out
        # The summary must not leave DUMP's logical PC or S19's addressed
        # output in the physical-buffer coordinate system.
        dump=model.command(cpu,b'DUMP\r');s19=model.command(cpu,b'S19\r')
        logical=b'2000:' if lines[0].endswith('2000') else b'FFFF:'
        assert logical in dump and (b'S1062000010203' if logical==b'2000:' else b'S104FFFF01') in s19
    source(mem,['BOGUS']);out=model.command(cpu,b'ASM\r')
    assert b'Unknown instruction' in out and b'S 1 AUTO ' not in out and b'RAM $0200-' not in out
    assert [bytes(b) for b in mem.banks]==flash and not mem.events


def main():
    assert hashlib.sha256(IMAGE).hexdigest()==REPORT['sha256']
    for name,digest in REPORT['sources'].items():
        assert hashlib.sha256((build.SOURCE/name).read_bytes()).hexdigest()==digest
    (OUT/'test-results.json').unlink(missing_ok=True)
    passed=[]
    tests=[test_all_encodings,test_labels_and_expressions,test_org_fill,test_local_symbols,test_errors_and_bounds,
                 test_editor_and_console,test_editor_capacity,test_bulk_paste,test_generated_program,
                 test_contiguous_code_window,test_other_application_banks]
    if REPORT['version']!='0.4':tests.append(test_save_summary)
    for test in tests:
        started=time.monotonic()
        test()
        passed.append(test.__name__)
        print(f'PASS {test.__name__} ({time.monotonic()-started:.1f}s)',flush=True)
    (OUT/'test-results.json').write_text(json.dumps(dict(passed=passed,sha256=REPORT['sha256'],
        all_212_encodings_compared_with_wdc=True,physical_hardware_tested=False,
        native_816_execution_tested=False),indent=2)+'\n')


if __name__=='__main__':main()
