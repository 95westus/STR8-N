"""Package reproducible b15 CONFIG and CPU/NOR evidence; never access devices."""
import argparse,json,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
import prepare_ram_config_2609 as p
import test_ram_config_2609 as t


def current_rollover(build,cpu):
    banks=[bytearray((build/f'source-b{n}.bin').read_bytes()) for n in range(4)]
    original=t.legacy.latest(banks)
    for n,page in enumerate(range(0xc6,0xcf),1021):
        row=bytearray(original);row[8:12]=n.to_bytes(4,'little')
        banks[3][(page-0x80)*256:(page-0x7f)*256]=t.legacy.core.seal(row)
    h=t.current_machine(build,cpu,banks=list(map(bytes,banks)))
    before=t.legacy.latest(h.m.banks)
    assert b'OK\r\n' in t.legacy.command(h,1,b'B 1 9000')
    row=t.legacy.latest(h.m.banks)
    counts=p.read(build/'baseline.json')['counts'].copy();counts[29]+=1
    assert [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==counts
    assert row[7]==ord('S') and row[13]==2 and row[15]==9
    assert row[32:64]+row[160:252]==before[32:64]+before[160:252]
    assert int.from_bytes(row[8:12],'little')==1031
    erases=[event for event in h.m.events if event[0]=='erase']
    assert len(erases)==1 and erases[0][1:3]==(3,0xd000)
    reserved=bytes(h.m.banks[3][0x4f00:0x5000])
    # The durable reservation can already publish the requested boot tuple;
    # both the reservation and final row must retain the complete wear history.
    assert reserved[7]==ord('S') and reserved[13]==2 and reserved[15]==9 and reserved[255]==0
    assert int.from_bytes(reserved[8:12],'little')==1030
    assert [int.from_bytes(reserved[64+3*n:67+3*n],'little') for n in range(32)]==counts
    selected={0,len(h.m.snapshots)//2,len(h.m.snapshots)-1}
    selected.update(i for i,event in enumerate(h.m.events) if event[0]=='erase')
    for index in sorted(selected):
        prefix=list(map(bytearray,h.initial_banks));prefix[3][0x4000:0x6000]=h.m.snapshots[index]
        latest=t.legacy.latest(prefix)
        assert latest[32:64]+latest[160:252]==original[32:64]+original[160:252]
        actual=[int.from_bytes(latest[64+3*n:67+3*n],'little') for n in range(32)]
        assert actual in (p.read(build/'baseline.json')['counts'],counts)
        t.legacy.reboot_reader(build,cpu,prefix)
    t.legacy.preserved(h);t.legacy.reboot_reader(build,cpu,h.m.banks)
    return dict(passed=True,cpu=cpu,case='captured-history-model-only-rollover-preserves-high-counts-and-unknowns',
                erases=['B3:D'],D_before=47,D_after=48,selected_prefixes=len(selected))


def qualify(build,repro,out):
    build,repro,out=map(lambda value:Path(value).resolve(),(build,repro,out));assert not out.exists(),'Fresh ready output required'
    info=p.verify(build);other=p.verify(repro)
    assert info['app_sha256']==other['app_sha256']
    body=(build/'payload'/p.BIN).read_bytes();assert body==(repro/'payload'/p.BIN).read_bytes()
    cases=[];receipts={}
    for cpu in ('65c02','65c816-e'):
        path=build/f'ram-config-tests-{cpu}.json';proof=p.read(path)
        assert proof['passed'] and proof['checks']==14 and proof['failures']==0
        assert not proof['hardware'] and not proof['serial_access']
        assert proof['checker_sha256']==p.digest(p.HERE/'test_ram_config_2609.py')
        assert proof['legacy_checker_sha256']==p.digest(p.HERE/'test_ram_config_b14.py')
        assert proof['app_sha256']==info['app_sha256'] and proof['build_sha256']==p.digest(build/'ram-config-build.json')
        assert all(row['passed'] for row in proof['cases'])
        cases.extend(proof['cases']);receipts[str(path)]=p.digest(path)
        cases.append(current_rollover(build,cpu));print('PASS captured-history rollover',cpu,flush=True)
    cases.append(dict(passed=True,case='independent-build-byte-reproduction'))
    closeout=p.read(p.SESSION/'step09-VERSION-install/closeout.json')
    marker=p.ROOT/'output/qualification/device-operations/2609.json'
    assert p.digest(marker)==closeout['marker_sha256'],'Actual board marker changed during preparation'
    assert p.read(p.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    p.baseline();assert not p.ATTEMPTS
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    shutil.copy2(build/'payload'/p.BIN,out/p.BIN)
    sy=p.read(build/'symbols.json')['core/ram-config'];help_offset=sy['CONFIG_HELP_TEXT']-0x200
    (out/'CONFIG-help.txt').write_bytes(body[help_offset:].split(b'\0',1)[0])
    for path in build.glob('simulated-inspection-*.txt'):shutil.copy2(path,out/path.name)
    p.save(out/'baseline.json',info['baseline'])
    sources={name:p.digest(p.HERE/name) for name in ('prepare_ram_config_2609.py','ram-config-b15.asm',
             'test_ram_config_2609.py','qualify_ram_config_2609.py','test_ram_config_b14.py','test_b14_core.py','test_b14_raw.py')}
    result=dict(passed=True,board='2609',checks=len(cases),failures=0,hardware=False,board_access=False,
        serial_access=False,RAM_uploaded=False,flashed=False,saved_setting_writes=False,
        BIN=p.BIN,bytes=len(body),sha256=p.sha(body),load_address='0200',end_exclusive=info['end_exclusive'],
        byte_reproducible=True,exact_b15_F_sha256=p.F_SHA,build=str(build),build_sha256=p.digest(build/'ram-config-build.json'),
        repro=str(repro),sources=sources,receipts=receipts,cases=cases,
        mutation_prefixes=sum(row.get('prefixes',0) for row in cases),
        actual_default='S',actual_enabled_banks=0,actual_counts=info['baseline']['counts'],
        actual_sequence=1020,actual_B0_sha256=p.WDC_SHA,actual_board_marker_unchanged=True,
        known_limitation='CPU/NOR model qualification only; no physical CONFIG or ACIA trial on 2609')
    p.save(out/'qualification.json',result)
    receipt=f'''# 2609 matching b15 RAM CONFIG — prepared, no device access

**PASS: {len(cases)} offline groups; two independent builds identical. No serial
port opened, RAM upload, flash operation or saved-setting write occurred.**

File: **`{p.BIN}`**, {len(body)} bytes, raw L start `$0200`, end exclusive
`${info['end_exclusive']}`. This is a RAM application, not a flash-sector image.
SHA-256: `{p.sha(body)}`.

The app links the exact installed b15 F symbols and frozen full-CRC/duplicate-history
journal engine. F SHA-256 is `{p.F_SHA}`. F, MON A/B, VX1 E and the journal format
were not rebuilt or installed by this step. The ready directory contains only the
CONFIG BIN and evidence; source bank images remain in the private build escrow.

Actual 2609 remains **default S; all banks disabled; sequence 1020**. Counts are
A=51, B=54, C=78, D=47, E=43, F=30; all 32 counts, legacy configuration and unknown
prior lifetime remain unchanged. B0 WDCMONV2 SHA-256 is `{p.WDC_SHA}`.

Tests cover both 65C02 and 65C816 emulation, USB and modeled ACIA, raw L,
help/display/wear/Q without writes on captured 2609 images, disabled targets,
malformed/cancelled lines, all 26 permitted bank/entry pairs, damaged or ambiguous
journals, sequence/reservation/wear exhaustion, append/rollover interruption
prefixes and selected retries. Disposable models also test A/B generation pinning,
bank enable/entry/default writes and rollover with 2609's existing high counts.
Those simulated settings changes did not reach a physical board. All non-C/D
flash, including B0 and VX1, is preserved by the tested writer.

## Future inspection sequence — not executed

1. Verify the current bank images and exact F/RAM services before transfer.
2. At REC>, send `C1` Enter, `L` Enter; after `SEND BIN`, send `{p.BIN}` as raw bytes.
3. Wait for the three-second idle autorun and `RAM CONFIG ? B C I W Q>`.
4. Use `?` Enter, bare `B` Enter, bare `C` Enter and `W` Enter to inspect.
5. `Q` Enter restarts F; the saved default S returns to REC>.

Expected settings: `DEFAULT=S`, B0–B3 `OFF ENTRY=8000`. `W` shows six-digit
hexadecimal counts, followed by `UNKNOWN HISTORY`. The simulated captures are
explicitly model evidence, not new console logs from 2609.

**Stop before any saved-setting command.** `B bank entry` enables a bank and
saves its entry immediately. `C target` appends a saved default immediately;
even `C S` is a write when S is already selected. `I` writes only on entirely
blank C/D and is refused on 2609's initialized journals; do not use it here.
There is no draft/Save menu or general disable command. Recovery `C1` selects
USB for the runtime session; it does not persist a console setting.

[Qualification](qualification.json) · [Current baseline](baseline.json) ·
[Help text](CONFIG-help.txt) · [Simulated 65C816 USB inspection](simulated-inspection-65c816-e-port1.txt).

The exact F match is an admission requirement, not an on-device cryptographic
check by this app. Raw L does not verify its transfer. A future live inspection
must use independent RAM readback before any settings operation. ACIA remains
not board-tested; the numbered settings menu and broader configuration editor
remain separate work.
'''
    (out/'receipt.md').write_text(receipt,encoding='utf-8')
    snapshot=out/'source';snapshot.mkdir()
    for name in sources:shutil.copy2(p.HERE/name,snapshot/name)
    p.save(out/'manifest.json',{str(path.relative_to(out)):p.binding(path) for path in out.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS CONFIG qualification',len(cases),'groups;',result['mutation_prefixes'],'mutation prefixes;',len(body),'bytes; no hardware access',flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','repro','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();qualify(args.build,args.repro,args.out)
