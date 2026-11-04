"""Additional combined-app MON/journal/F integrity and RAM-scope checks."""
import argparse
import json
from pathlib import Path
import test_recovery_kit as ck

t=ck.t


def main(build):
    rows=[]
    t.base.GENERATION=json.loads((build/'prototype-report.json').read_text())['experimental_generation']
    def passed(cpu,case,**extra):
        rows.append(dict(cpu=cpu,case=case,passed=True,**extra))
        print('PASS',cpu,case,flush=True)
    for cpu in ('65c02','65c816-e'):
        for label,records in (
                ('missing-journal',[]),
                ('corrupt-journal',[(0xc000,bytes(256))]),
                ('divergent-journal',[(0xc000,t.base.record()),(0xc100,t.base.record(counts=[3]*32))]),
                ('saturated-MON-wear',[(0xc000,t.base.record(counts=[0xffffff]*32))])):
            h=ck.Combined(build,cpu,rows=records)
            owner_zp=bytes(h.m.ram[:0xe0])
            tail=bytes(h.m.ram[h.i['CK_END']:0x6500])
            h.load(via_f=True)
            original=tuple(map(bytes,h.m.banks))
            h.m.arm(None)
            out=h.command(b'T\r',ck.F_REC)
            assert b'MON KIT REFUSED/FAILED' in out and not h.m.events
            assert tuple(map(bytes,h.m.banks))==original
            assert bytes(h.m.ram[:0xe0])==owner_zp and bytes(h.m.ram[h.i['CK_END']:0x6500])==tail
            passed(cpu,label+'-MON-restore-refuses-no-writes-no-journal-initialization')
        h=ck.Combined(build,cpu)
        # Alter a harmless F padding byte, leaving its callable APIs intact.
        h.m.banks[3][0x7fdf]^=1
        body=(build/'payload/recovery-kit.bin').read_bytes()
        h.m.ram[0x200:0x200+len(body)]=body
        original=tuple(map(bytes,h.m.banks));h.m.arm(None)
        h.c.pc=0x200
        h.run(lambda:bytes(h.m.tx).endswith(ck.F_REC))
        assert b'MON KIT REFUSED/FAILED' in h.m.tx and not h.m.events
        assert tuple(map(bytes,h.m.banks))==original
        passed(cpu,'mismatching-F-CRC-refuses-app-before-menu-or-any-write')
        h=ck.Combined(build,cpu)
        body=bytearray((build/'payload/recovery-kit.bin').read_bytes());body[-3]^=1
        original=tuple(map(bytes,h.m.banks));h.m.arm(None)
        out=ck.raw_load(h,build,body=body,prompt=ck.F_REC)
        assert b'MON KIT REFUSED/FAILED' in out and not h.m.events
        assert tuple(map(bytes,h.m.banks))==original
        passed(cpu,'corrupt-raw-app-refuses-at-initial-self-check')
        h=ck.Combined(build,cpu);ck.raw_load(h,build);h.m.arm(None)
        original=tuple(map(bytes,h.m.banks))
        h.request(t.frame(magic=b'BAD!'),result_ending=t.LOCKED)
        t.assert_quarantined(h)
        output=(bytes(h.m.tx),bytes(h.m.acia_tx))
        for queue in (h.m.rx,h.m.acia_rx): queue.extend(b'T\rX\rERASE\r?\rQ\r')
        end=h.steps+20000
        h.run(lambda:h.steps>=end,limit=20001)
        h.run(lambda:h.c.pc==h.i['OI_LOCK_DRAIN'])
        assert not h.m.rx and not h.m.acia_rx and not h.m.events
        assert tuple(map(bytes,h.m.banks))==original
        assert output==(bytes(h.m.tx),bytes(h.m.acia_tx))
        passed(cpu,'quarantined-binary-tail-cannot-invoke-new-T-X-ERASE-help-Q-commands')
    t.base.save(build/'recovery-kit-guards.json',dict(passed=True,hardware=False,serial_access=False,
        checks=len(rows),failures=0,cases=rows,app_sha256=t.sha((build/'payload/recovery-kit.bin').read_bytes()),
        checker_sha256=t.sha(Path(__file__).read_bytes()),device_or_network_attempts=t.base.ATTEMPTS))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
    main(p.parse_args().build.resolve())
