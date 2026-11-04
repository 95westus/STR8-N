"""Frozen core regression minus obsolete RLP1/D/V/R loader test blocks.

New raw loading/timing/autorun is tested separately; no CRC claims are retained.
"""
import types
from pathlib import Path
import test_b07 as frozen
from test_boot_startup import timed_step
sha=frozen.sha

def empty_cycles(n,port):
    return (112 if port==1 else 118)*n+4*((n+255)//256)+8*((n+65535)//65536)-1

def fast_idle(h):
    m,c=h.m,h.c
    if ('B14_IDLE' not in h.b or not getattr(h,'fast_idle',True) or c.pc!=h.b['B14_IDLE'] or m.rx or m.acia_rx
        or m.acia_wire or m.acia_latch is not None or m.acia_error or m.ram[0xf1]
        or getattr(m,'arrivals',None)):return
    port=m.ram[h.b['DC_BINARY']]
    if port not in (1,2):return
    x=c.x or 256;y=c.y or 256;z=m.ram[h.b['B14_TICKS']]
    n=x+256*(y-1)+65536*(z-1)
    if n<=1:return
    # Skip only complete empty polls. Execute the final poll normally so its
    # stack writes, flags, registers and I/O side effects are not synthesized.
    c.processorCycles+=empty_cycles(n,port)-empty_cycles(1,port)
    c.x=c.y=1;m.ram[h.b['B14_TICKS']]=1

def load_core():
    raw=frozen.BASE.read_bytes();assert sha(raw)==frozen.FROZEN_BASE_SHA256
    source=raw.decode().replace("b'OFFLINE PROTOTYPE S A B 0 1 2 3\\r\\n'",repr(frozen.NEW_CHOICES))
    source=source.replace("b'OFFLINE PROTOTYPE'","b'S=Recovery  A/B=Monitor  0-3=Bank'")
    source=source.replace("assert b'REFUSED: TX blocked' in h.m.acia_tx[n:]","assert b'REFUSED: command' in h.m.acia_tx[n:]")
    source=source.replace('dual-blocked-FT245-binary-aborts-and-restores-text','dual-blocked-FT245-removed-D-command-refusal')
    a=source.index("    h=fresh();body=bytes(range(64));h.port_command(1,b'L")
    b=source.index('    h=fresh();now=h.c.processorCycles;',a);source=source[:a]+source[b:]
    a=source.index('        # RAM loader framing/CRC/range and explicit run')
    b=source.index('        # Examine every observed program/erase boundary',a);source=source[:a]+source[b:]
    source=source.replace("if ram_config:self.m.ram[0x2000:0x2000+", "if ram_config:self.m.ram[0x0200:0x0200+")
    source=source.replace('h.c.pc=0x2000;prompt=', 'h.c.pc=0x0200;prompt=')
    source=source.replace('limit=4000000','limit=16000000')
    source=source.replace('            c,m=self.c,self.m;self.steps+=1','            c,m=self.c,self.m;self.steps+=1\n            fast_idle(self)')
    source=source.replace('            else:c.step()','            else:timed_step(c,m[c.pc])')
    module=types.ModuleType('b14_core');module.__file__=str(frozen.BASE)
    module.fast_idle=fast_idle;module.timed_step=timed_step
    exec(compile(source,str(frozen.BASE),'exec'),module.__dict__)
    return module,dict(base_checker_sha256=sha(raw),adapted_source_sha256=sha(source.encode()),
        removed_obsolete_blocks=['RLP1/header/CRC/range/explicit-R/loaded-image-readback', 'old dual-port framed-loader cases'],
        replacement='test_b14_raw.py and test_b14_tools.py',CONFIG_relocated_to_0200=True,
        frozen_checker_unchanged=True,adapter_sha256=sha(Path(__file__).read_bytes()))
