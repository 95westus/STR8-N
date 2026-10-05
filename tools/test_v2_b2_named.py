"""Execute named registration, routing, collision and reset contracts."""
import hashlib
import json
import test_v2_b2 as host
import test_v2_b2_autoload as auto

TABLE,COUNT=0x7690,0x76B0

def command(cpu,line):
    cpu.pc=host.boot.SYM['V2_PROMPT'];host.boot.hold(cpu)
    return host.send(cpu,line.encode()+b'\r')

def publish(cpu,name,target=0x7800,name_at=0x7740):
    cpu.memory.ram[name_at:name_at+len(name)+1]=name.encode()+b'\0'
    descriptor=name_at.to_bytes(2,'little')+target.to_bytes(2,'little')
    cpu.memory.ram[0x2200:0x2204]=descriptor
    ok,lo,hi,kind=host.lookup(cpu,'COMMAND.REGISTER',2)
    assert ok and kind==1
    return host.call(cpu,lo+256*hi,0,0x22,0)[:2]

def check_example_and_autoload():
    cpu,mem=auto.fresh();auto.edit(cpu,'+X');auto.edit(cpu,'+H')
    out=auto.reset(cpu)
    assert out.startswith(b'.'*160+b'\r\nK registered')
    assert mem.ram[COUNT]==8
    assert b'HELLO FROM X' in command(cpu,'HELLO')
    assert b'Named: HELLO ECHO ' in command(cpu,'H')
    assert b'SOME TEXT\r\n' in command(cpu,'ECHO some text')
    assert b'HELLO FROM X' in command(cpu,'X HELLO')
    assert b'SOME TEXT\r\n' in command(cpu,'X ECHO some text')
    assert b'Bad cmd' in command(cpu,'HELLOX')
    assert b'Bad cmd' in command(cpu,'ECHOX text')
    for bank in range(4):
        command(cpu,'B'+str(bank))
        assert b'HELLO FROM X' in command(cpu,'HELLO')
    command(cpu,'B3')
    assert b'conflict' not in command(cpu,'G C700')
    assert mem.ram[COUNT]==8
    auto.edit(cpu,'-X');auto.reset(cpu)
    assert mem.ram[COUNT]==0 and b'Bad cmd' in command(cpu,'HELLO')

def check_dispatch_and_collisions():
    cpu,mem=auto.fresh()
    # Handler stores X, the original-line argument offset, then reports handled.
    mem.ram[0x7800:0x7806]=b'\x8e\x00\x23\xa9\x01\x60'
    assert publish(cpu,'DIR')==(True,0)
    assert b'Bad' not in command(cpu,'DIR   TEST') and mem.ram[0x2300]==6
    assert b'Bad' not in command(cpu,'D1000 1000')
    assert publish(cpu,'DIR',name_at=0x7750)==(False,2)
    assert publish(cpu,'D',name_at=0x7760)==(False,1)
    assert publish(cpu,'DABC',name_at=0x7760)==(False,1)
    assert publish(cpu,'MFFFF',name_at=0x7760)==(False,1)
    assert publish(cpu,'Y',name_at=0x7760)==(True,0)
    ok,lo,hi,_=host.lookup(cpu,'COMMAND.REGISTER',1);assert ok
    assert host.call(cpu,lo+256*hi,ord('Y'),0,0x78)[:2]==(False,2)
    assert host.call(cpu,lo+256*hi,ord('Z'),0,0x78)[:2]==(True,0)
    assert publish(cpu,'Z',name_at=0x7770)==(False,2)

def check_validation_capacity_and_lifetime():
    cpu,mem=auto.fresh()
    mem.ram[0x7800:0x7803]=b'\xa9\x01\x60'
    for name in ('','lower','BAD NAME','A'*16):assert publish(cpu,name)==(False,1)
    assert publish(cpu,'GOOD',target=0x2000)==(False,1)
    assert publish(cpu,'A'*15)==(True,0)
    for i,key in enumerate('BCDEFGH',1):
        assert publish(cpu,'WORD'+key,name_at=0x7700+i*8)==(True,0)
    assert mem.ram[COUNT]==32
    assert publish(cpu,'NINTH',name_at=0x7790)==(False,3)
    auto.reset(cpu);assert mem.ram[COUNT]==0
    assert b'Bad cmd' in command(cpu,'WORDB')

def check_provider_rollback_and_authenticated_code():
    cpu,mem=auto.fresh();auto.edit(cpu,'+X')
    # Y publishes a name but fails initialization: no partial record survives.
    mem.banks[3][0x4D00:0x4D07]=b'\x4c\x07\xcdEX\x01Y'
    mem.banks[3][0x4D07:0x4D14]=bytes.fromhex('A9 70 A2 CD A0 00 20 00 ED 18 A9 01 60')
    mem.banks[3][0x4D70:0x4D74]=bytes.fromhex('80 CD 90 CD')
    mem.banks[3][0x4D80:0x4D87]=b'BROKEN\0'
    mem.banks[3][0x4D90:0x4D93]=bytes.fromhex('A9 01 60')
    auto.edit(cpu,'+Y CD00')
    assert b'Y registration failed' in auto.reset(cpu)
    assert mem.ram[COUNT]==8
    assert b'HELLO FROM X' in command(cpu,'HELLO')
    assert b'Bad ' in command(cpu,'BROKEN') # Unmatched B-prefixed input reaches core B.
    mem.banks[3][0x6D20]^=1
    auto.reset(cpu)
    assert mem.ram[COUNT]==0 and mem.ram[host.MGR['MG_READY']]==0
    assert b'B0-3 D addr' in command(cpu,'?')

def main():
    checks=[check_example_and_autoload,check_dispatch_and_collisions,
            check_validation_capacity_and_lifetime,check_provider_rollback_and_authenticated_code]
    for check in checks:check();print('PASS:',check.__name__,flush=True)
    result=dict(passed=[c.__name__ for c in checks],physical_hardware_tested=False,
        firmware_sha256=hashlib.sha256(host.boot.IMAGE).hexdigest(),
        provider_sha256=hashlib.sha256(auto.HX).hexdigest())
    (host.firmware.OUT/'named-command-tests.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
