"""B12 adaptation of frozen regression: replace D/V tests with refusal checks."""
import hashlib,types
from pathlib import Path
import test_b07 as frozen
sha=frozen.sha

def load_core():
    raw=frozen.BASE.read_bytes();assert sha(raw)==frozen.FROZEN_BASE_SHA256
    source=raw.decode()
    source=source.replace("b'OFFLINE PROTOTYPE S A B 0 1 2 3\\r\\n'",repr(frozen.NEW_CHOICES))
    source=source.replace("b'OFFLINE PROTOTYPE'","b'S=Recovery  A/B=Monitor  0-3=Bank'")
    source=source.replace("assert b'REFUSED: TX blocked' in h.m.acia_tx[n:]", "assert b'REFUSED: command' in h.m.acia_tx[n:]")
    source=source.replace('dual-blocked-FT245-binary-aborts-and-restores-text','dual-blocked-FT245-removed-D-refusal-on-ACIA')
    a=source.index('    n=len(h.m.tx);other=len(h.m.acia_tx);h.m.ft_block_after=')
    b=source.index('    for port in (1,2):',a)
    source=source[:a]+'''    for key in (b'D\\r',b'V\\r'):
        out=h.port_command(1,key)
        assert b'REFUSED: command' in out and h.m.ram[0x7c78]==1
        assert bytes(h.m.ram[0x2000:0x2040])==body and not h.m.events
    passed(cpu,'dual-removed-DV-refuse-with-valid-image-preserved')
'''+source[b:]
    a=source.index("            out=h.port_command(port,b'V'+ending)")
    b=source.index("            assert h.m.ram[0x7c2b]",a)
    source=source[:a]+'''            out=h.port_command(port,b'V'+ending)
            assert out==b'V\\r\\nREFUSED: command\\r\\nREC> '
            h.run(lambda:h.c.pc==h.w['V2W_GETC']);assert bytes(alt[n:])==out
'''+source[b:]
    before="out=h.command(b'V\\r');assert out.startswith(b'V\\r\\n'+body+crc(body).to_bytes(2,'little'))"
    assert source.count(before)==1
    source=source.replace(before,"out=h.command(b'V\\r');assert out==b'V\\r\\nREFUSED: command\\r\\nREC> ' and h.m.ram[0x7c78]==1")
    before="assert out==b'D\\r\\n'+before+crc(before).to_bytes(2,'little')+b'REC> ';passed(cpu,'RAM-preload-escrow')"
    assert source.count(before)==1
    source=source.replace(before,"assert out==b'D\\r\\nREFUSED: command\\r\\nREC> ' and bytes(h.m.ram[0x2000:0x6000])==before;passed(cpu,'RAM-removed-D-refuses-without-overwrite')")
    module=types.ModuleType('b12_core');module.__file__=str(frozen.BASE)
    exec(compile(source,str(frozen.BASE),'exec'),module.__dict__)
    return module,dict(base_checker_sha256=sha(raw),adapted_source_sha256=sha(source.encode()),
        D_V_cases_replaced_with_refusal_tests=True,frozen_checker_unchanged=True,
        adapter_sha256=sha(Path(__file__).read_bytes()))
