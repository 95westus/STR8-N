"""Exercise the flash arena's upper boundary and full-length source names offline."""
import hashlib
import json
from pathlib import Path
from test_rc1_source_flash import fixture, packed, OUT


def main():
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    full=packed([(i,';'+'X'*119) for i in range(1,58)]+[(58,';'+'Y'*95)])
    checks=[]
    for cpu in ('65c02','65c816-e'):
        for edu in (False,True):
            # Only C/D is erased; AAAA remains opaque owner data. Programming
            # data at D555 must remain distinct from the worker's command
            # writes to D555/AAAA, which must preserve their stored contents.
            h=fixture(cpu,edu=edu);h.set_source(full)
            h.m.banks[0][:]=b'\xA5'*32768
            h.m.banks[0][0x4000:0x6000]=b'\xFF'*8192
            before=bytes(h.m.banks[0])
            h.command('SAVE FLASH LASTPAIR',contains='Source saved')
            assert h.m.banks[0][0x4000:0x4002]==b'SF'
            assert h.m.banks[0][:0x4000]==before[:0x4000]
            assert h.m.banks[0][0x6000:]==before[0x6000:]
            assert any(address==0xD555 for _,address,_ in h.m.events)
            h.set_source(b'',dirty=0)
            h.command('LOAD FLASH LASTPAIR',contains='Source loaded')
            assert h.source()==full
            # One final erased sector cannot satisfy a two-sector source.
            h=fixture(cpu,edu=edu);h.set_source(full)
            h.m.banks[0][:]=b'\xA5'*32768
            h.m.banks[0][0x5000:0x6000]=b'\xFF'*4096
            before=bytes(h.m.banks[0])
            h.command('SAVE FLASH NOFIT',contains='Source storage: 51')
            assert bytes(h.m.banks[0])==before and not h.m.events
            # Exact maximum name length is accepted without a terminator in
            # the sixteen-byte name field and refuses same-name replacement.
            h=fixture(cpu,edu=edu);source=packed([(10,'SEI'),(20,'END')]);h.set_source(source)
            h.command('SAVE FLASH abcdefghijklmnop',contains='Source saved')
            before=bytes(h.m.banks[0])
            h.command('SAVE FLASH ABCDEFGHIJKLMNOP',contains='Source storage: 50')
            assert bytes(h.m.banks[0])==before
            h.set_source(b'',dirty=0)
            h.command('LOAD FLASH ABCDEFGHIJKLMNOP',contains='Source loaded')
            assert h.source()==source
            label=f'{cpu}, {"EDU" if edu else "bare SXB"}: final C/D sector pair, D555 data, end-boundary refusal, sixteen-character names'
            checks.append(label);print('PASS',label,flush=True)
    report=dict(passed=True,checks=checks,board_access=False,sector_erases=0,
        firmware_sha256=hashlib.sha256((OUT/'firmware.bin').read_bytes()).hexdigest(),harness_sha256=digest)
    (OUT/'flash-edge-tests.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
