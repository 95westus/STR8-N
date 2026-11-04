"""Qualify RAM-only preflight against original, unmodified 2609 flash images."""
import argparse
from pathlib import Path
import prepare_edu_sram_preflight_2609 as p
from test_edu_sram_2609 import machine,call,request,intact,EDU,REC,start,feed


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();build,out=args.build.resolve(),args.out.resolve();info=p.verify(build)
    assert not out.exists();out.mkdir(parents=True);cases=[]
    def passed(cpu,case):
        cases.append(dict(passed=True,cpu=cpu,case=case));print('PASS',len(cases),cpu,case,flush=True)
    source=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)]
    for cpu in ('65c816-e','65c02'):
        h=machine(build,cpu,source);sy=h.sy['core/edu-preflight'];v=h.via;v.ifr=0x1a
        before=bytes(v.chip.data);start(h,1);feed(h,1,(build/'payload'/p.BIN).read_bytes())
        h.run(lambda:bytes(h.m.tx).endswith(EDU) or h.c.pc==sy['EC_HALT']);assert bytes(h.m.tx).endswith(EDU)
        assert not v.reads and not v.writes
        h.port_command(1,b'S\r',EDU);h.port_command(1,b'V\r',EDU)
        assert v.ifr==0x1a and v.port_reads==0
        h.port_command(1,b'A\r',EDU)
        for cmd in (b'R 00000 01',b'R 0FFFE 40',b'R 1FFC0 40'):
            reply=h.port_command(1,cmd+b'\r',EDU);assert b'STATUS COMPLETED MODE: 00 ' in reply
            address=int(cmd[2:7],16);count=int(cmd[8:],16)
            assert bytes(h.m.ram[0x6100:0x6100+count])==before[address:address+count]
        h.port_command(1,b'Q\r',REC);intact(h,before,0x40)
        (out/f'simulated-{cpu}-RAM-preflight.txt').write_bytes(bytes(h.m.tx));passed(cpu,'original-flash-no-ROM-service-info-ack-upper-lower-reads-Q-REC')
        for mode in (0,0x40,0x80):
            h=machine(build,cpu,source,mode=mode);v=h.via;before=bytes(v.chip.data)
            body=(build/'payload'/p.BIN).read_bytes();h.m.ram[0x200:0x200+len(body)]=body
            assert call(h,sy['ES_INIT'])==0
            for addr,count in ((0xfffe,64),(0x1ffff,1)):
                request(h,addr,count);assert call(h,sy['ES_READ'])==0
                assert bytes(h.m.ram[0x6100:0x6100+count])==before[addr:addr+count]
            intact(h,before,mode)
        passed(cpu,'RAM-linked-provider-all-chip-modes-and-end-array-preservation')
        h=machine(build,cpu,source);body=(build/'payload'/p.BIN).read_bytes();h.m.ram[0x200:0x200+len(body)]=body
        h.m.ram[sy['ES_READ']+10]^=1;h.c.pc=0x200;h.run(lambda:h.c.pc==sy['EC_HALT'])
        assert not h.via.reads and not h.via.writes and not h.m.events
        passed(cpu,'RAM-provider-code-corruption-covered-by-client-immutable-CRC')
    assert not p.p.base.ATTEMPTS
    p.p.base.save(out/'qualification.json',dict(passed=True,checks=len(cases),cases=cases,hardware=False,board_access=False,
        serial_access=False,flash_writes=0,SRAM_writes=0,BIN_sha256=info['sha256'],build_sha256=p.p.base.digest(build/'build.json'),
        checker_sha256=p.p.base.digest(__file__),peripheral_model_sha256=p.p.base.digest(p.p.HERE/'edu_sram_model.py')))
    print('PASS',len(cases),'RAM preflight groups; no device access',flush=True)


if __name__=='__main__':main()
