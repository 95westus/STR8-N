"""Audit the offline combined kit and join current, hash-bound test receipts."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_text())


def update_notes(result):
    path=HERE/'README.md'
    raw=path.read_bytes()
    title=b'## Offline combined RAM recovery kit, revision 1 (October 24)'
    # Preserve the existing cp1252 history and its byte contents outside this
    # new section. Re-running the auditor only replaces its own section.
    if title in raw:
        first=raw.index(title)
        last=raw.index(b'## Current 2512:',first)
        raw=raw[:first]+raw[last:]
    note=f'''## Offline combined RAM recovery kit, revision 1 (October 24)

The combined `recovery-kit.bin` is an offline RAM app, not new firmware.
All three physical boards are unchanged; no serial port was opened. It uses
the unchanged PR04 b14 F services and works in CPU models with MON A/B absent.
Do not load this app on RC1 g0034 or WDCMONv2: their private services differ.

| Component | Actual size/location |
|---|---|
| Combined raw BIN | 11,985 bytes, 0200-30D0; entry 0200 |
| Embedded original b14 MON images | 8,192 bytes total |
| Single shared RAM journal writer | 983 bytes at 0CF8-10CE |
| Reduction versus the two separate tools | 329 bytes (12,314 to 11,985) |
| Application RAM beyond the loaded app | 13,359 bytes at 30D1-64FF, unborrowed |
| F, unchanged | 3,572 active bytes; 3,669-byte body span; 395 contiguous free; 97 internal spare; 32 vector bytes |
| MON A/B, unchanged | 3,830-byte body + 128-byte header, 138 free each |

The app reuses the fixed-target MON routines and OIP1 protocol, with only one
copy of the journal writer. The 6700 journal frame, 6800-77FF staging buffer,
existing RAM worker/vector areas and reserved service state remain reserved.
The loaded app span is disposable; the tests preserve owner ZP and RAM beyond
it. A future live operation still needs fresh capture/escrow and serial ownership.

Prompt: `RAM KIT ? T I X Q> `. These are echoed **text commands followed by
Enter**, accepting lowercase, CR, LF or CRLF. Unlike the old standalone MON
kit, a single T/X/Q without Enter does not dispatch immediately.

| Command | Meaning |
|---|---|
| `?` | Complete help; uses the page-aware RAM printer |
| `T` | Restore embedded original b14 MON A/B, read back, commit last, restart through F |
| `I` | Existing OIP1 host read/write transfer, one complete 4096-byte sector plus CRC |
| `X` | Erase both MON slots after entering `ERASE`; checks both preimages first |
| `Q` | Software restart through F, using the current boot record |

F L still receives the app as a regular raw BIN at 0200 and starts it after
three seconds idle. The later I operation retains OIP1's separate 20-byte
header, exact 4096-byte payload, current-preimage CRC and payload CRC. It is
a host-driven transfer, rather than an arbitrary BIN pasted at the app menu.
I permits B0/B1/B2:8-F and B3:8/9/E; normal I requests cannot read or overwrite
B3:A/B/C/D/F. Only T/X own the MON sectors; C/D writes are managed journal
transactions. F remains read-only. T and I skip identical content without
an erase or wear increment. Writes require a valid journal and durable erase
reservation; a missing/corrupt journal is never initialized by this app.

The app checks its own CRC and matching F CRC at entry and before I/T/confirmed-X.
The known mutable OIP1 header/CRC/page bytes are normalized first. This is an
integrity check after raw execution begins, not verified F loading or authenticity.
Framing/TX failures still quarantine all late bytes, including T/X/ERASE/?/Q.

Final offline result: **{result['checks']} groups passed, zero final failures**, across
65C02 and 65C816 emulation: 18 combined integration groups, 14 MON/integrity/
quarantine guards, 120 OIP1 groups and 10 CRC-summary differential comparisons.
All {result['opaque_interrupted_mutation_prefixes']:,} opaque mutation prefixes in append/rollover were retried, with
{result['safe_opaque_reservation_refusals']:,} safe reservation refusals rather than unsafe continuation. Separately,
{result['MON_selected_interrupted_mutation_prefixes']} selected MON interruption prefixes reloaded through F and completed T.
These are CPU/NOR models, with differentially checked bulk/CRC summaries;
no physical power-cut, NMI or new console electrical timing proof is claimed.
The initial long-help page-wrap and harness corrections are retained in the
results' prior-attempt records. A second build reproduces the BIN byte-for-byte.

Evidence and artifact:
[results](../../BUILD/pr04-b14-recovery-kit-r3/recovery-kit-offline-results.json),
[BIN](../../BUILD/pr04-b14-recovery-kit-r3/payload/recovery-kit.bin),
[help text](../../BUILD/pr04-b14-recovery-kit-r3/recovery-kit-help.txt).
Builder: `build_recovery_kit.py`; integration: `test_recovery_kit.py`;
exhaustive OIP1 driver: `test_recovery_kit_accelerated.py`; additional guards:
`test_recovery_kit_guards.py`; audited receipt: `qualify_recovery_kit.py`.

### WDCMONv2 conversion assessment

Its MON restoration and write logic can be reused in a **WDC bootstrap build**,
but the present app is not that converter. It calls matching STR8-N RAM services
and F APIs before its integrity checks; T owns only A/B, and I protects F/C/D.
Putting these MON images into WDC B3 alone does not establish a coherent system.

A conversion build must load through the WDC debugger/S19 route, initialize
its own console/bank/flash/vector services in RAM, admit an exact supported
WDC image and CPU, and bind changes to preservation captures/device preimages.
It must establish compatible F plus MON A/B and initialize or migrate the
SNBT C/D journal with explicit unknown prior wear where history is absent.
Owner programs/retained RAM/settings and RTC time/trim remain preservation
requirements. Vendor-occupied C/D are not the same as a blank journal.
Normal opaque-command protections should remain intact; a separate migration
operation should own the admitted F/journal transition.

The existing exact-profile WDC factory planner/transport and documented
[WDC-to-RC1 route](../../docs/rc1/UNIFORM_UPGRADE.md) are useful foundations,
including source/CPU admission and transfer/readback ordering. Their historical
hardware results do not qualify WDC-to-this-b14-layout. New offline interruption
coverage is needed before any authorized board trial; before a valid F exists,
some interrupted factory states can still require the original programmer backup.
No WDC conversion command or board change was added here.

'''
    pos=raw.index(b'\n')+1
    path.write_bytes(raw[:pos]+b'\r\n'+note.replace('\n','\r\n').encode('cp1252')+raw[pos:])


def main(build,repro):
    info=read(build/'recovery-kit-build.json')
    data=(build/'payload/recovery-kit.bin').read_bytes()
    assert info['passed'] and len(data)==info['app_bytes']==11985
    assert sha(data)==info['app_sha256']
    assert binascii.crc_hqx(data[:-2],65535)==int.from_bytes(data[-2:],'little')
    assert data==(repro/'payload/recovery-kit.bin').read_bytes()
    for name,digest in info['sources'].items(): assert sha((HERE/name).read_bytes())==digest
    symbols=read(build/'symbols.json')['core/recovery-kit']
    assert symbols['CK_END']==0x200+len(data)<=0x6500
    assert symbols['JE_END']-symbols['JE_ENTER']==983
    for name,digest in info['unchanged_firmware'].items():
        assert sha((build/'payload'/name).read_bytes())==digest
        assert (build/'payload'/name).read_bytes()==(repro/'payload'/name).read_bytes()
    for slot,page in (('A','a0'),('B','b0')):
        offset=symbols[f'MA_IMAGE_{slot}']-0x200
        assert data[offset:offset+4096]==(build/f'payload/monitor-{page}-offline-component.bin').read_bytes()
    names=[f'recovery-kit-{mode}-{cpu}.json' for mode in ('integration','opaque','crc-summary') for cpu in ('65c02','65c816-e')]
    names+=['recovery-kit-guards.json']
    cases=[];receipts={}
    for name in names:
        path=build/name;r=read(path)
        assert r['passed'] and r['failures']==0 and r['hardware'] is False and r['serial_access'] is False,name
        assert r['checks']==len(r['cases']) and r['app_sha256']==sha(data)
        if name.startswith('recovery-kit-crc-summary'):
            checker=HERE/'test_recovery_kit_accelerated.py'
        elif name=='recovery-kit-guards.json': checker=HERE/'test_recovery_kit_guards.py'
        else: checker=HERE/'test_recovery_kit.py'
        assert sha(checker.read_bytes())==r['checker_sha256']
        for key,source in (('reused_checker_sha256','test_b14_tools.py'),('original_OIP_checker_sha256','test_opaque_installer.py')):
            if key in r: assert r[key]==sha((HERE/source).read_bytes())
        if 'symbols_sha256' in r: assert r['symbols_sha256']==sha((build/'symbols.json').read_bytes())
        assert not r.get('device_or_network_attempts',[])
        for key,digest in r.get('boards_and_lease_sha256',{}).items(): assert sha(Path(key).read_bytes())==digest
        if '-opaque-' in name:
            assert r['checks']==60 and r['mutation_prefixes']==8628
            assert r['accelerated_driver_sha256']==sha((HERE/'test_recovery_kit_accelerated.py').read_bytes())
            proof=r['CRC_loop_summary_proof'];assert sha(Path(proof['path']).read_bytes())==proof['sha256']
        cases+=r['cases'];receipts[name]=dict(path=str(path),sha256=sha(path.read_bytes()),checks=r['checks'])
    assert len(cases)==162 and len({(r['cpu'],r['case']) for r in cases})==162
    f=read(ROOT/'BUILD/pr04-b14-raw-r4/b14-qualification.json')
    help_start=symbols['CK_HELP_TEXT']-0x200
    help_text=data[help_start:].split(b'\0',1)[0]
    (build/'recovery-kit-help.txt').write_bytes(help_text)
    result=dict(passed=True,checks=len(cases),failures=0,hardware=False,serial_access=False,
        identity='b14 combined RAM recovery kit, offline revision 1; firmware remains 2.0proto b14',
        artifact=dict(path=str(build/'payload/recovery-kit.bin'),sha256=sha(data),bytes=len(data),range='0200-30D0',
                      entry='0200',spare_application_bytes=0x6500-symbols['CK_END'],self_CRC=True,
                      loading='F L raw BIN, no transport header/CRC; auto-run after 3 seconds idle'),
        writer=dict(copies=1,bytes=983,where=f'{symbols["JE_ENTER"]:04X}-{symbols["JE_END"]-1:04X}'),
        savings_vs_separate_tools_bytes=info['separate_tool_bytes']-len(data),
        firmware=dict(F=f['F'],MON=f['MON'],unchanged_sha256=info['unchanged_firmware']),
        groups=dict(combined_integration=18,MON_and_integrity_guards=14,opaque=120,CRC_acceleration_differential=10),
        opaque_interrupted_mutation_prefixes=sum(r.get('prefixes',0) for r in cases if r['case'].startswith('every-mutation-prefix')),
        MON_selected_interrupted_mutation_prefixes=sum(r.get('prefixes',0) for r in cases if r['case'].startswith('MON-restore-interruption')),
        successful_opaque_retries=sum(r.get('successful_retries',0) for r in cases),
        safe_opaque_reservation_refusals=sum(r.get('safe_reservation_refusals',0) for r in cases),
        commands=dict(help='?',restore='T',opaque='I',erase='X then ERASE',boot='Q',input='Text command then Enter, lowercase accepted'),
        reproducible_build=dict(path=str(repro),same_BIN=True),
        receipts=receipts,all_three_boards_unchanged=True,
        WDCMONv2=dict(current_app_compatible=False,conversion_implemented=False,
            reason='Depends on matching PR04 b14 F plus RAM console/flash/vector ABI before its integrity checks; T writes A/B only',
            reusable='MON/opaque algorithms and shared writer; exact-profile factory migration planning/transport exists separately',
            conversion_requires=['WDC debugger/S19 RAM bootstrap independent of STR8-N F',
                                 'Exact source/CPU admission and repeated preservation captures with device preimage checks',
                                 'Establish matching F/worker/vector ABI and initialize or migrate C/D SNBT without discarding known history',
                                 'Verify coherent MON A/B/F and preserve owner sectors, RAM/settings and RTC',
                                 'New CPU/NOR interruption proof and separately authorized hardware qualification']),
        prior_attempts=[dict(path=str(ROOT/'BUILD/pr04-b14-recovery-kit-r1'),status='build failed before tests; missing OI_PTR alias corrected'),
                        dict(path=str(ROOT/'BUILD/pr04-b14-recovery-kit-r2/recovery-kit-integration-65c02.json'),status='offline help printer wrap caught and fixed using the page-aware RAM printer'),
                        dict(path=str(build/'prior-integration-harness-failure.json'),status='harness expected both consoles after explicitly selecting USB; harness corrected to select BOTH'),
                        dict(path=str(build/'prior-opaque-harness-failure.json'),status='harness inherited old default prompt; overridden for the combined app'),
                        dict(path=str(build/'prior-dual-prompt-harness-failure.json'),status='harness sampled the preceding ACIA prompt tail; now waits at the input checkpoint'),
                        dict(status='CRC-summary differential harness initially compared old output history with an empty clone; both histories are now cleared at the checkpoint and final proofs passed'),
                        dict(status='two slow unaccelerated OIP1 attempts stopped without hardware access; full suite rerun with CRC summary differential proof')],
        limitations=['CPU/NOR models only; no live board qualification or electrical power-loss/NMI qualification',
                     'Bulk loops and CRC clock cycles are summarized after linked differential comparisons; no new physical console timing qualification',
                     'F raw loading has no transfer CRC/length; the app checks its own CRC after entry',
                     'CRC detects accidental corruption, not authenticity',
                     'Only disposable app range and reserved service RAM may be borrowed; any future live operation still needs current RAM/flash escrow and serial ownership',
                     'Current app requires b14 ABI; do not run it on RC1 g0034 or WDCMONv2'],
        checker_sha256=sha(Path(__file__).read_bytes()))
    output=build/'recovery-kit-offline-results.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    update_notes(result)
    print(json.dumps({k:result[k] for k in ('passed','checks','failures','groups','opaque_interrupted_mutation_prefixes','MON_selected_interrupted_mutation_prefixes')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--repro',type=Path,required=True)
    x=p.parse_args();main(x.build.resolve(),x.repro.resolve())
