"""Reproduce VX1, test public calls after relocation, package without I/O."""
import argparse,json,shutil
from pathlib import Path
from datetime import datetime,timezone
import prepare_version_caps_2609 as p
from test_version_caps_2609 import machine,query,call,REC
from test_b14_raw import start,feed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','service_proof','installer_proof','rebuild','out'):parser.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    args=parser.parse_args();build=args.build.resolve();out=args.out.resolve();assert not out.exists()
    plan=p.verify(build);service=p.b.r.read(args.service_proof);installer=p.b.r.read(args.installer_proof)
    assert service['passed'] and installer['passed'] and service['build_plan_sha256']==installer['plan_sha256']==p.b.digest(build/'plan.json')
    assert service['test_source_sha256']==p.b.digest(p.HERE/'test_version_caps_2609.py')
    assert installer['test_source_sha256']==p.b.digest(p.HERE/'test_version_caps_installer_2609.py')
    extra=[]
    # Compile the same public provider with private code shifted by 32 bytes.
    variant=args.rebuild.resolve().with_name(args.rebuild.name+'-relocation')
    (variant/'s/core').mkdir(parents=True);shutil.copytree(build/'s/include',variant/'s/include')
    shutil.copytree(build/'payload',variant/'payload');shutil.copy2(build/'prototype-report.json',variant/'prototype-report.json')
    core=variant/'s/core'
    for name in ('str8n-v2-public.inc','version-caps-public.inc','version-caps-identities.inc'):shutil.copy2(build/'s/core'/name,core/name)
    source=(build/'s/core/version-caps-e000.asm').read_text().replace('VX_QUERY:\n','        DS 32,$EA\nVX_QUERY:\n',1)
    (core/'version-caps-e000.asm').write_text(source)
    a=p.assembler(variant);raw,es=a.link('core','version-caps-e000',0xe000,'VX_END')
    raw=bytearray(raw);raw[0xfc0:]=p.footer('EXT',0,'b15-vx1');raw[-2:]=b'\0\0'
    raw[0xfdc:0xffc]=p.normalized(raw,'EXT');raw[-2:]=p.crc(raw[:-2]).to_bytes(2,'big')
    symbols=p.b.r.read(build/'symbols.json');assert es['VX_QUERY']==symbols['extension']['VX_QUERY']+32
    symbols['extension']=es;p.save(variant/'symbols.json',symbols)
    banks=[bytearray((build/f'expected-b{n}.bin').read_bytes()) for n in range(4)];banks[3][0x6000:0x7000]=raw
    for cpu in ('65c816-e','65c02'):
        h=machine(variant,cpu,banks=list(map(bytes,banks)))
        value,data=query(h);assert value[0] and data[168:200]==raw[0xfdc:0xffc]
        h.c.pc=h.sy['core/monitor-a0']['V2_PROMPT'];h.c.sp=255;h.run(lambda:h.c.pc==h.w['V2W_GETC'])
        reply=h.port_command(1,b'VERSION\r',b'B3> ');assert b'Running MON: A' in reply and not h.m.events
        extra.append(dict(passed=True,case='unchanged-MON-public-calls-after-private-provider-relocation',cpu=cpu,bytes_shifted=32))
        print('PASS public calls after provider relocation',cpu,flush=True)
    # F and the public RAM client still expose F identity when neither MON is valid.
    banks=[bytearray((build/f'expected-b{n}.bin').read_bytes()) for n in range(4)]
    banks[3][0x2000:0x4000]=b'\xff'*8192
    h=machine(build,banks=list(map(bytes,banks)),slot=None)
    before=list(map(bytes,h.m.banks));start(h,1)
    image=(build/'payload/version-caps-query-RAM.bin').read_bytes();feed(h,1,image)
    h.run(lambda:h.c.pc==0x200);h.run(lambda:bytes(h.m.tx).endswith(REC))
    assert b'F: 2.0proto b15' in h.m.tx and b'MON A: unavailable' in h.m.tx and b'MON B: unavailable' in h.m.tx
    assert not h.m.events and list(map(bytes,h.m.banks))==before
    extra.append(dict(passed=True,case='raw-RAM-VERSION-with-both-MONs-invalid-and-reset-to-REC'))
    print('PASS F-only/RAM client VERSION and REC with invalid MONs',flush=True)
    rebuilt=p.build(args.rebuild)
    for name in ('version-caps-e000.bin','monitor-a0-version-caps.bin','monitor-b0-version-caps.bin','version-caps-query-RAM.bin','2609-VERSION-CAPS-RAM.bin'):
        assert (build/'payload'/name).read_bytes()==(args.rebuild/'payload'/name).read_bytes()
    assert rebuilt['expected_sha256']==plan['expected_sha256']
    extra.append(dict(passed=True,case='independent-byte-identical-rebuild',files=5))
    print('PASS independent identical rebuild of all five payloads',flush=True)
    out.mkdir(parents=True)
    for name in ('version-caps-e000.bin','monitor-a0-version-caps.bin','monitor-b0-version-caps.bin','version-caps-query-RAM.bin','2609-VERSION-CAPS-RAM.bin'):
        shutil.copy2(build/'payload'/name,out/name)
    shutil.copy2(args.service_proof,out/'service-proof.json');shutil.copy2(args.installer_proof,out/'installer-proof.json')
    shutil.copy2(args.service_proof.parent/'65c816-e-A-VERSION.txt',out/'simulated-VERSION.txt')
    shutil.copy2(args.service_proof.parent/'65c816-e-A-CAPS.txt',out/'simulated-CAPS.txt')
    report=dict(passed=True,hardware=False,board_access=False,serial_access=False,flashed=False,
        checks=service['checks']+installer['checks']+len(extra),service_groups=service['checks'],installer_groups=installer['checks'],additional=extra,
        prepared_utc=datetime.now(timezone.utc).isoformat(),board='2609',plan=str(build/'plan.json'),plan_sha256=p.b.digest(build/'plan.json'),
        F_unchanged=True,B0_backup_sha256=p.b.WDC_SHA,counts_before=plan['counts_before'],counts_planned=plan['counts_after'],
        no_new_permanent_RAM=True,query_scratch='D0-DF saved/restored; 6700-67FF transient; caller-owned output',
        discovery_profile='VX1 B3 ROM locator with a bank-restoring RAM client; F-published resident directory deferred',
        sources={path.name:p.b.digest(path) for path in [Path(__file__),p.HERE/'prepare_version_caps_2609.py',p.HERE/'test_version_caps_2609.py',p.HERE/'test_version_caps_installer_2609.py']},
        payloads={path.name:dict(bytes=path.stat().st_size,sha256=p.b.digest(path)) for path in out.glob('*.bin')},
        limitations=['Offline model evidence only; no board upload or flash write', 'New read-only VERSION/CAPS output for b15; old disabled RC1 VERSION package remains untouched',
                     'Native-mode calls, legacy E/B2 providers, debugger and resident v2.1 ABI remain unavailable', 'SHA IDs identify normalized built bytes; runtime integrity checks use CRC, not cryptographic authentication'])
    p.save(out/'qualification.json',report)
    text=f'''# 2609 minimal VERSION/capability extension — prepared; stop before flashing

**PASS: {report['checks']} offline groups/checks. No board port opened, RAM
uploaded, flash written, or authoritative wear history changed.**

| File | Role |
|---|---|
| `version-caps-e000.bin` | 4096-byte B3:E candidate, structured query and VERSION/CAPS renderer |
| `monitor-a0-version-caps.bin` | 4096-byte MON A with narrow VX1 hooks and independent build ID |
| `monitor-b0-version-caps.bin` | 4096-byte MON B with the same public contract |
| `version-caps-query-RAM.bin` | RAM $0200 display tool; callable bank-restoring query at $0203 |
| `2609-VERSION-CAPS-RAM.bin` | {plan['bytes']}-byte exact-source RAM installer; **not executed** |

F stays exactly `{p.b.F_SHA}`. B0 backup stays `{p.b.WDC_SHA}`. B0–B2 and B3:8/9/F
are outside the admitted write targets. The future installer reserves E 42→43,
A 50→51 and B 53→54 before each erase, in E/A/B order; C=78, D=47 and F=30 stay
unchanged. Reservations append at C300/C400/C500, sequences 1018–1020. Current
physical counts remain A=50/B=53/C=78/D=47/E=42/F=30. No configuration changes
are planned: default S, disabled opaque-bank mask, legacy body and unknown
lifetime mask FFFFFFFF remain intact.

The provider's public ROM descriptor is VX1 at B3:E000. The matching MONs
validate magic, format, extent, commit, entry bounds and full-sector CRC before
dispatching VERSION/CAPS. The old S/R/T/B29 provider gates stay disabled. No new
permanent RAM, bootstrap F rewrite, debugger, hardware initialization or native
service is introduced. F-initialized resident discovery is a later milestone.

Queries return a 224-byte VI/1 record with independent F, A, B and extension
identities, generations, validity/availability flags and legacy capability
returns. MON build IDs exclude the MI CRC and embedded ID; E IDs exclude the
sector CRC and embedded ID. Commit is normalized to zero. IDs are SHA-256 of
these defined bytes; runtime integrity uses CRC and does not claim signature
authentication. VERSION renders the public record. This is new b15 command
output; the old disabled RC1 VERSION package has not been altered.

The RAM query client restores caller PCR/ZP/SP; no query writes device registers
except that client's temporary bank selection/restoration. The provider itself
writes only its documented transient scratch and validated caller output. Both
CPUs/slots, malformed metadata, mixed identities, public calls after private
code relocation, missing/invalid MONs, installer failures, interruption states
and reproducibility were tested.

Future authorized installation: `C1` Enter, `L` Enter, send
`2609-VERSION-CAPS-RAM.bin` as raw binary at $0200; inspect W/V; `I` Enter then
`INSTALL VERSION` Enter. Keep durable host reservation/attempt logs. Completion
and V verify all four banks; Q returns to F REC. Those keystrokes are documented
only; none were sent to 2609 in this preparation. Never replay after changed
preimages or partial failure without a new recovery plan.

[Qualification](qualification.json) · [Service proof](service-proof.json) ·
[Installer proof](installer-proof.json) · [Simulated VERSION](simulated-VERSION.txt)
· [Simulated CAPS](simulated-CAPS.txt).
'''
    (out/'receipt.md').write_text(text,encoding='utf-8')
    print('PASS',report['checks'],'offline groups; VERSION/CAPS package ready; STOP before hardware',flush=True)


if __name__=='__main__':main()
