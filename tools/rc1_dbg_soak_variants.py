"""RAM-only, E=1-compatible varying ASM sources for the v1g soak."""
import hashlib
import re

def cases():
    result=[]
    for seed in (0x12,0x25,0x38,0x4B):
        prefix=['ORG $0200','SEI','CLD','LDX #$FF','TXS','LDY #$00']
        def add(name,body,registers,carry,memory=None,output=None,services=()):
            lines=[f'{10*(i+1)} {line}' for i,line in enumerate(prefix+body+['END'])]
            result.append(dict(name=f'{name}-{seed:02X}',family=name,seed=seed,lines=lines,
                               registers=registers,carry=carry,memory=memory or {},
                               console_contains=output,services=list(services),native_debugging=False))
        tail=['BRK $01','JMP $7E67']
        add('query',[f'LDA #${seed:02X}','BRK $80']+tail,[1,16,4],True,services=[0x80])
        add('arithmetic',[f'LDA #${seed:02X}','CLC','ADC #$07','TAX','CLC']+tail,
            [seed+7,seed+7,0],False)
        add('indexed-copy',['LDX #$00','copy: LDA data,X','STA $0600,X','INX','CPX #$04','BNE copy','LDA $0603']+tail+
            ['data: BYTE '+','.join(f'${seed+i:02X}' for i in range(4))],
            [seed+3,4,0],True,{'0600':bytes(seed+i for i in range(4)).hex()})
        count=2+(seed&3)
        add('counted-branch',['LDX #$00','again: INX',f'CPX #${count:02X}','BNE again',f'LDA #${seed:02X}']+tail,
            [seed,count,0],True)
        add('subroutine',[f'LDA #${seed:02X}','CLC','JSR plus']+tail+['plus: ADC #$09','RTS'],
            [seed+9,255,0],False)
        add('register-trace',[f'LDA #${seed:02X}',f'LDX #${seed+1:02X}',f'LDY #${seed+2:02X}','SEC','BRK $83']+tail,
            [seed,seed+1,seed+2],True,output=f'A={seed:02X} X={seed+1:02X} Y={seed+2:02X}',services=[0x83])
        text=f'v1g-{seed:02X}'
        add('text-output',['LDA #<text','LDX #>text',f'LDY #${len(text):02X}','CLC','BRK $84']+tail+
            [f'text: TEXT "{text}"'],[0x15,2,len(text)],False,output=text,services=[0x84])
        uid=0xC0+(seed&15)
        add('user-register-call-remove',['LDA #<request','LDX #>request','BRK $81','BCC failed',f'BRK ${uid:02X}',
            f'LDA #${uid:02X}','BRK $82','BCC failed']+tail+['failed: BRK $7F','JMP $7E67',
            f'request: BYTE ${uid:02X}','WORD handler','BYTE 0',f'handler: LDA #${seed:02X}','STA $7002',
            f'LDA #${seed^0x55:02X}','STA $7004','RTS'],[0,2,seed^0x55],True,services=[0x81,0x82,uid])
        add('text-invalid-range',[f'LDA #${seed:02X}','LDA #$00','LDX #$65','LDY #$01','SEC','BRK $84']+tail,
            [1,0x65,1],False,services=[0x84])
        add('unregister-invalid-id',[f'LDA #${seed:02X}','LDA #$00','LDX #$23','LDY #$34','SEC','BRK $82']+tail,
            [1,0x23,0x34],False,services=[0x82])
    return result

def check_stop(case,context,image,console):
    assert len(context)==7
    pc=int.from_bytes(context[:2],'little')
    assert image[pc-0x200-2:pc-0x200]==b'\x00\x01', 'Unexpected stop (failure branch or service)'
    assert list(context[2:5])==case['registers'],(case['name'],context.hex(),case['registers'])
    assert bool(context[5]&1)==case['carry'],(case['name'],'carry',context.hex())
    assert context[6]==255,(case['name'],'stack',context.hex())
    if case['console_contains']:
        assert case['console_contains'].encode() in console,(case['name'],'missing output',console[-250:])

def check_hold_cleanup(link):
    """HOLD invalidates the registry; physical slot bytes may remain stale.

    7BFC..7BFF are ACTIVE, BUSY, RUNMODE and REG_VALID. A registry is usable
    only when REG_VALID is A5; HOLD must clear all four lifecycle bytes.
    """
    lifecycle=link.dump(0x7BFC,0x7BFF)
    assert lifecycle==bytes(4),('HOLD lifecycle/registry invalidation failed',lifecycle.hex())
    return dict(lifecycle_hex=lifecycle.hex(),registry_valid=False)

def asm_unit(link,transport,case):
    """Assemble on board; execute only bytes already qualified in both CPU models."""
    expected=bytes.fromhex(case['assembled_hex'])
    text=link.command('ASM',b'ASM> ');assert b'ASM 0.5' in text
    text+=link.command('NEW',b'ASM> ')
    for line in case['lines']:text+=link.command(line,b'ASM> ')
    answer=link.command('ASM',b'ASM> ');text+=answer
    assert re.search(rb'OK '+str(len(expected)).encode()+rb' bytes\b',answer),(case['name'],answer)
    text+=link.command('DUMP',b'ASM> ')+link.command('S19',b'ASM> ')+link.command('QUIT')
    actual=transport.read_range(link,0x200,0x200+len(expected)-1)
    assert actual==expected,'ASM output differs; execution refused'
    console=link.command('G 0200',b'DBG> ');text+=console
    context=link.dump(0x7000,0x7006,b'DBG> ')
    check_stop(case,context,actual,console)
    for address,body in case['memory'].items():
        data=bytes.fromhex(body);assert transport.read_range(link,int(address,16),int(address,16)+len(data)-1,b'DBG> ')==data
    text+=link.command('C')
    cleanup=check_hold_cleanup(link)
    assert transport.read_range(link,0x200,0x200+len(expected)-1)==expected
    return dict(passed=True,name=case['name'],family=case['family'],services=case['services'],
                source_sha256=hashlib.sha256(('\n'.join(case['lines'])+'\n').encode()).hexdigest(),
                bytes=len(expected),output_sha256=hashlib.sha256(expected).hexdigest(),context_hex=context.hex(),
                exact_model_image_verified_before_execution=True,HOLD_cleanup=cleanup,native_debugging=False),text
