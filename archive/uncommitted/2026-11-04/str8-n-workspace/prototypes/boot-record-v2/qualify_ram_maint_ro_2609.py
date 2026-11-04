"""Package reproducible read-only RAM MAINT and both CPU receipts; file-only."""
import argparse,shutil
from pathlib import Path
import prepare_ram_maint_ro_2609 as p


def qualify(build,repro,tests816,tests02,out):
    build,repro,tests816,tests02,out=(Path(value).resolve() for value in (build,repro,tests816,tests02,out))
    assert not out.exists();info=p.verify(build);other=p.verify(repro)
    assert info['sha256']==other['sha256'] and (build/'payload'/p.BIN).read_bytes()==(repro/'payload'/p.BIN).read_bytes()
    cases=[];receipts={}
    for cpu,folder in (('65c816-e',tests816),('65c02',tests02)):
        path=folder/'qualification.json';proof=p.base.read(path)
        assert proof['passed'] and proof['checks']==len(proof['cases'])==16 and proof['failures']==0
        assert not proof['hardware'] and not proof['serial_access'] and proof['flash_writes']==proof['saved_setting_writes']==0
        assert proof['CPU']==cpu and proof['BIN_sha256']==info['sha256']
        assert proof['build_sha256']==p.base.digest(build/'build.json') and proof['checker_sha256']==p.base.digest(p.HERE/'test_ram_maint_ro_2609.py')
        assert all(row['passed'] for row in proof['cases'])
        cases.extend(proof['cases']);receipts[str(path)]=p.base.digest(path)
    cases.append(dict(passed=True,case='independent-WDC-build-byte-reproduction'))
    marker=p.ROOT/'output/qualification/device-operations/2609.json'
    assert p.base.digest(marker)==info['marker_sha256'] and p.base.read(p.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    assert not p.base.ATTEMPTS
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n');shutil.copy2(build/'payload'/p.BIN,out/p.BIN)
    for folder in (tests816,tests02):
        for path in folder.glob('simulated-*.txt'):shutil.copy2(path,out/path.name)
    shutil.copy2(build/'baseline.json',out/'baseline.json')
    sy=p.base.read(build/'symbols.json')['core/ram-maint-ro'];body=(out/p.BIN).read_bytes()
    help_text=body[sy['MA_HELP_TEXT']-0x200:].split(b'\0',1)[0];(out/'MAINT-help.txt').write_bytes(help_text)
    sources={name:p.base.digest(p.HERE/name) for name in ('ram-maint-ro-b15.asm','prepare_ram_maint_ro_2609.py',
             'test_ram_maint_ro_2609.py','qualify_ram_maint_ro_2609.py','test_b14_core.py','test_b14_raw.py')}
    result=dict(passed=True,checks=len(cases),failures=0,board='2609',hardware=False,board_access=False,serial_access=False,
        RAM_uploaded=False,flash_writes=0,saved_setting_writes=0,BIN=p.BIN,bytes=info['bytes'],sha256=info['sha256'],
        load_address='0200',end_exclusive=info['end_exclusive'],buffer='5000-5FFF',immutable_end_exclusive=info['immutable_end_exclusive'],
        byte_reproducible=True,no_writer_linked=True,exact_F_sha256=info['F_sha256'],guard_cases=['immutable code','F','RA descriptor','RAM worker','RAM vectors'],
        build=str(build),build_sha256=p.base.digest(build/'build.json'),repro=str(repro),receipts=receipts,sources=sources,
        baseline=info['baseline'],actual_board_marker_unchanged=True,commands=info['commands'],cases=cases,
        limitations=['CPU/NOR model tests only; no live 2609 MAINT upload',
                     'IRQ masked; 65C816 emulation with D/DBR/PBR zero',
                     'ACIA is modeled only; tool borrows RAM buffer 5000-5FFF',
                     'Read-only stage; no copy/edit/flash/CONFIG-save or general old-system MAINT services'])
    p.base.save(out/'qualification.json',result)
    receipt=f'''# 2609 b15 RAM MAINT RO — prepared, no board writes

**PASS: {len(cases)} offline groups on both CPUs and modeled USB/ACIA; independent
build identical. No port opened, RAM upload, flash or saved-setting write.**

File **`{p.BIN}`**, **{info['bytes']:,} bytes**, load/entry `$0200`, end exclusive
`${info['end_exclusive']}`. SHA-256: `{info['sha256']}`.

This first-stage b15 MAINT has **no linked writer**. It supports map, reads,
buffer display, compare, CRC and Q only. The old full-system MAINT's erase,
copy, patch, fill, write, NAME, record/source-store and launch operations are
not enabled. F/MON/VX1 and the journal format are unchanged.

## Commands

```text
M [1|2|3]                 Grid / sector roles (default) / wear
R src first last          Read 1-4096 bytes into RAM buffer $5000-$5FFF
D [offset [end]]          Display valid buffer bytes; D alone shows up to 16
K [src first last]        CRC16-CCITT-FALSE of buffer or selected range
V src first last dst start  Compare ranges; report first differing destination
?                        Help
Q                        Restart F using the saved default
```

Numbers are hex; addresses/offsets use four digits. `src`/`dst` are `R` for
RAM or flash bank `0`–`3`. Readable user RAM is `$2000–$64FF`; flash is
`$8000–$FFFF`. R refuses a RAM source overlapping its own `$5000–$5FFF` buffer.
K/V read their selected ranges without copying. They can inspect that buffer.
I/O/service RAM is excluded from user ranges. R changes only its tool-owned
buffer; all flash and settings operations are absent/refused.

Map roles identify the preservation policy, not validated image contents. All
B0 sectors are WDC-BACKUP PROTECTED; B3 A/B are MON slots, C/D journals, E VX1
and F boot. Other sectors remain OWNER/UNCLASSIFIED. E/U means all FF/programmed,
not free/allocatable. M3 displays actual admitted 24-bit erase counts and unknown
history flags. Missing, body-CRC-damaged or conflicting snapshots show unknown
counts instead of inventing them. The tool performs no journal repair.

At entry it checks the immutable-code CRC, exact installed F CRC,
RA descriptor, and copied RAM worker/vector CRCs before any private F call.
A mismatch sets its RAM error byte and halts before the prompt. CRC detects
corruption, not authenticity; raw L still executes before these checks.

## Future inspection example — not run on hardware

At REC, use C1 Enter then L Enter; after SEND BIN, send the exact BIN. It starts
after the three-second idle interval and presents `MAINT RO>`.

```text
?
M 1
M
M 3
R 3 F000 F00F
D
K
K 3 F000 FFFF
V 0 8000 800F 0 8000
Q
```

Each line takes Enter. Expected state remains sequence 1020, DEFAULT=S,
BANKS=00, UNKNOWN=FFFFFFFF. Q therefore returns to REC after the countdown.
All 32 wear counts and the B0 backup stay unchanged. Counts A=51, B=54, C=78,
D=47, E=43, F=30 retain their tracked lower-bound meaning.

The disposable tool owns its loaded span, stack, ZP E0–FF, existing console/read
workspace and the 4 KiB buffer. Preserve owner RAM before any later live load
when it matters; no larger permanent RAM reservation or flash install is made.
It restores B3 and preserves unrelated PCR bits after banked reads. It does not
automatically restore the borrowed RAM on Q.

Tests include linked CRC opcodes and unaccelerated startup, all five startup
guard refusals, complete current wear display, erased/used scan boundaries,
all-bank and 4 KiB/FFFF reads, RAM reads, buffer bounds/overlap, range CRC with
independent host values, full-bank compare and first mismatch, PCR-bit retention,
45 malformed/write-command refusals per port, CR/LF/CRLF and cancelled input,
all-flash and unowned-RAM preservation, and Q to saved-S recovery. Larger CRC
cases use the existing CPU-model style shortcut after linked-opcode checks.

[Qualification](qualification.json) · [Baseline](baseline.json) · [Help](MAINT-help.txt) ·
[Simulated 65C816 USB](simulated-MAINT-65c816-e-port1.txt).

This is preparation only. Physical 2609 remains at its prior F-demo checkpoint,
default S, disabled banks, all original journals/wear and B0 intact. No live
MAINT or physical ACIA/electrical interruption qualification is claimed.
'''
    (out/'receipt.md').write_text(receipt,encoding='utf-8')
    snapshot=out/'source';snapshot.mkdir()
    for name in sources:shutil.copy2(p.HERE/name,snapshot/name)
    p.base.save(out/'manifest.json',{str(path.relative_to(out)):p.base.binding(path) for path in out.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS packaged',p.BIN,info['bytes'],'bytes;',len(cases),'groups; no device access',flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','repro','tests816','tests02','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();qualify(args.build,args.repro,args.tests816,args.tests02,args.out)
