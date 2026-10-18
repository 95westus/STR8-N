"""Offline source recognition, both active slots, unknown and legacy refusal."""
import json
from pathlib import Path
import migrate_v2 as u

def main():
    checks=[]
    for name in u.CATALOG:
        p=u.ROOT/'BUILD'/name
        if not (p/'build.json').exists():continue
        meta=u.read(p/'build.json')
        banks=[bytearray(b'\xff'*32768) for _ in range(4)];banks[3][0x7000:]=(p/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
        for page in (0xA0,0xB0):
            i=(page-0x80)*256;banks[3][i:i+4096]=(p/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
            found=u.identify(banks,page);assert found['version']==meta['version'] and found['generation']==meta['generation'] and found['inactive_page']==page^0x10
        banks[3][0x7100]^=1
        try:u.identify(banks,0xA0)
        except ValueError:pass
        else:raise AssertionError('Unknown core accepted')
        checks.append(name+' A/B source recognized; altered F refused')
    legacy=u.ROOT/'BUILD/v2-a24c1/str8n-v2-a24c1-f000-ffff.bin'
    assert legacy.exists()
    banks=[bytearray(b'\xff'*32768) for _ in range(4)];banks[3][0x7000:]=legacy.read_bytes()
    found=u.identify(banks,None)
    assert found['route']=='legacy-conversion-required' and not found['bootable_source_fallback'] and not found['execution_qualified']
    # Mutable legacy config is normalized, never mistaken for an A/B source.
    banks[3][0x7FD0:0x7FE0]=u.m.default_config();assert u.identify(banks,None)['route']==found['route']
    checks.append('beta1 exact and config-bearing images require explicit legacy conversion; no inactive-slot guarantee')
    out=u.ROOT/'output/qualification/beta25-unified-2026-10-14/source-recognition.json'
    out.write_text(json.dumps(dict(passed=True,checks=checks,board_access=False),indent=2)+'\n')
    print('\n'.join('PASS '+c for c in checks))

if __name__=='__main__':main()
