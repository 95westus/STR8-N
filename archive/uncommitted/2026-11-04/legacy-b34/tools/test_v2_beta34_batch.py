"""Changed BATCH allowlist: APPS stays usable, ASM stops before launch."""
import hashlib
import json
import test_asm as a
from test_v2_status import boot,layout


def main():
    cpu,m=a.fixture(primary=layout());m.fast=True;boot(cpu)
    checks=[]
    flash=[bytes(b) for b in m.banks]
    for line in ('BATCH APPS;VERSION','BATCH APPS ;VERSION'):
        print('CHECK',line,flush=True)
        out=a.command(cpu,line.encode()+b'\r')
        assert b'BATCH done' in out and b'ASM installed B1:E000' in out and b'2.0b34' in out,out
        assert b'ASM>' not in out and out.endswith(b'B3> ')
        checks.append(line)
    for line in ('BATCH ASM;VERSION','BATCH A;VERSION','BATCH APPSX;VERSION'):
        print('CHECK',line,flush=True)
        out=a.command(cpu,line.encode()+b'\r')
        assert b'BATCH stopped: unsupported' in out and b'ASM>' not in out and b'Running:' not in out,out
        assert out.endswith(b'B3> ') and not m.ram[0x7EE4]
        checks.append(line)
    out=a.command(cpu,b'BATCH SRAM;BOGUS;Q\r')
    assert b'BATCH stopped: command failed' in out and out.endswith(b'SRAM> '),out
    a.command(cpu,b'Q\r');checks.append('native command error stops remaining Q')
    out=a.command(cpu,b'BATCH MAINT;NAME TEST;Q\r')
    assert out.endswith(b'Type YES: '),out
    out=a.command(cpu,b'\x1b')
    assert b'BATCH canceled' in out and out.endswith(b'BM> '),out
    a.command(cpu,b'Q\r');checks.append('ESC cancels remaining queue at confirmation')
    assert [bytes(b) for b in m.banks]==flash and not m.events
    out=a.OUT.parent
    (out/'beta34-batch.json').write_text(json.dumps(dict(passed=True,checks=checks,
        build_sha256=hashlib.sha256((out/'build.json').read_bytes()).hexdigest(),
        no_flash_writes=True,board_access=False),indent=2)+'\n')
    print('PASS exact APPS allowlist, ASM refusal, native error and ESC; flash unchanged',flush=True)


if __name__=='__main__':main()
