"""Fault injection and unchanged erase guards for the F-only candidate."""
import json
from test_v2_fix005 import *

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    image=(OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    for mode in ('wrong-slot','timeout'):
        b=banks();c,m=boot(b)
        if mode=='wrong-slot':data=(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()
        else:data=image;m.fault='timeout'
        text=model.update(c,0xA0,data)
        assert b'REFUSED' in text and m.banks[3][0x201F]==0xFF,(mode,text[-200:])
        assert not any(e[0]=='erase' for e in m.events) and not m.ram[0xF4]
        preserved(m,b,((3,0x2000,0x3000),))
        if mode=='wrong-slot':assert not m.events
        else:
            c,r=boot(m.banks);assert b'COMMITTED' in model.update(c,0xA0,image)
    passed('wrong-slot upload refuses before writes; bootstrap program timeout leaves slot uncommitted and matching retry succeeds')
    b=banks();b[3][0x2000:0x3000]=image;base=[bytes(v) for v in b]
    c,m=boot(base,b'A');m.fault='timeout';text=provision(c)
    assert b'REFUSED' in text and m.banks[3][0x407F]==0xFF and not any(e[0]=='erase' for e in m.events)
    c,r=boot(m.banks,b'A');assert b'Journal initialized' in provision(c)
    passed('journal program timeout leaves commit erased; reset/reload resumes exact bytes without erase')
    c,m=boot(base,b'A');m.ram[0x2000:0x2000+len(UTILITY)]=UTILITY;c.pc=0x2000;m.rx.extend(b'Y\r')
    model.run(c,lambda:c.pc==META['bootstrap_symbols']['VERIFY_BODY'],1000000)
    m.banks[3][0x4000]^=1
    text=model.command(c,b'');assert b'REFUSED' in text and m.banks[3][0x407F]==0xFF
    passed('body corruption injected immediately before verification never publishes the journal commit')
    for fault in ('count','sequence','foreign-record'):
        b=[bytearray(v) for v in base];counts=[0]*32
        if fault=='count':counts[27]=0xFFFFFF
        elif fault=='foreign-record':counts[0]=1
        record=metadata(default_config(),counts,0xFFFFFFFF if fault=='sequence' else 1)
        b[3][0x4000:0x4080]=record;c,m=boot(b,b'A')
        assert b'REFUSED' in provision(c) and not m.events
        if fault!='foreign-record':
            data=model.newer(0xB0,META['generation']+1)
            assert b'REFUSED' in model.update(c,0xB0,data) and not m.events
        preserved(m,b)
    passed('existing foreign journal, saturated erase count and exhausted sequence remain protected with zero writes/erases')
    # An established journal keeps the active-slot, preference and stale-image
    # guards. This utility deliberately cannot reset existing wear history.
    c,m=boot(base,b'A');provision(c);baseline=[bytes(v) for v in m.banks];n=len(m.events)
    assert b'REFUSED' in model.command(c,b'U A\r') and len(m.events)==n
    assert b'REFUSED' in model.update(c,0xB0,(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()) and len(m.events)==n
    assert [bytes(v) for v in m.banks]==baseline
    passed('active monitor and equal-generation replacement still refuse; existing history is never reset')
    (OUT/'f-only-fault-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=META['artifacts'],
        bootstrap_utility_sha256=META['bootstrap_utility_sha256'],board_access=False,boards_flashed=False),indent=2)+'\n')

if __name__=='__main__':main()
