"""Check hardware client's bulk archive/restoration and copied WORK results."""
import json
from test_v2_spi_resident import boot,k,OUT
from test_v2_sram_store import console
from test_v2_workspace import install,req
CLIENT=OUT/'hardware-client';META=json.loads((CLIENT/'build.json').read_text());BODY=(CLIENT/'client.bin').read_bytes()

def main():
    cpu,m=boot();m.ram[0x2000:0x2000+len(BODY)]=BODY
    m.ram[0x3E00:0x3E10]=bytes((1,0,0,0,1,0,0x40,64,0,0,0,0,0,0,0,0))
    m.ram[0x3E20:0x3E23]=bytes((1,3,0))
    before=bytes(m.spi.devices[0].data)
    output=k.model.command(cpu,b'G 2003\r',80000000)
    assert b'SPI: 00' in output and m.ram[0x4000:0x6000]==before[0x10000:0x12000],(output[-250:],m.ram[0x3E10:0x3E39].hex(),m.ram[0x3E00:0x3E10].hex())
    m.ram[0x3E00:0x3E10]=bytes((2,0,0,0,1,0,0x40,64,0,0,0,0,0,0,0,0));m.ram[0x3E22]=0xA5
    output=k.model.command(cpu,b'G 2003\r',80000000)
    assert b'SPI: 00' in output and bytes(m.spi.devices[0].data)==before and m.ram[0x66AE]==1
    print('PASS actual bulk READ / privileged preserving WRITE with restored policy',flush=True)
    install(cpu,m);m.ram[0x2000:0x2000+len(BODY)]=BODY;m.fast=True
    m.ram[0x3E40:0x3E60]=req(6,key=b'FORMAT!!');m.ram[0x3E21]=3
    assert b'SPI: 00' in console(cpu,m,b'G 2006\r')
    assert m.ram[0x3E38]==0 and m.ram[0x3E33]==m.ram[0x3E34]
    m.ram[0x3E40:0x3E60]=req(1,size=64)
    assert b'SPI: 00' in console(cpu,m,b'G 2006\r') and m.ram[0x3E60:0x3E80][4]<4
    (CLIENT/'test-results.json').write_text(json.dumps(dict(passed=True,sha256=META['sha256'],resident_artifacts=k.REPORT['artifacts']),indent=2)+'\n')
    print('PASS hardware WORK front door copies results before HOLD',flush=True)

if __name__=='__main__':main()
