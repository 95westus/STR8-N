"""Package tested/reproduced ES1 candidates. File operations only; no serial path."""
import argparse,shutil
from pathlib import Path
import prepare_edu_sram_2609 as p
import prepare_edu_sram_preflight_2609 as pre
import edu_sram_backup as backup


def qualify(build,repro,preflight,pre_repro,tests,pre_tests,out):
    build,repro,preflight,pre_repro,tests,pre_tests,out=map(lambda v:Path(v).resolve(),(build,repro,preflight,pre_repro,tests,pre_tests,out))
    assert not out.exists();info=p.verify(build);again=p.verify(repro);pi=pre.verify(preflight);pr=pre.verify(pre_repro)
    for name in (p.PROVIDER,p.CLIENT,p.INSTALLER):
        assert (build/'payload'/name).read_bytes()==(repro/'payload'/name).read_bytes()
    assert (preflight/'payload'/pre.BIN).read_bytes()==(pre_repro/'payload'/pre.BIN).read_bytes()
    checks=[];receipts={}
    for folder,manifest,count,checker in ((tests,build/'plan.json',33,'test_edu_sram_2609.py'),
                                          (pre_tests,preflight/'build.json',6,'test_edu_sram_preflight_2609.py')):
        path=folder/'qualification.json';q=p.base.read(path)
        assert q['passed'] and q['checks']==len(q['cases'])==count and all(row['passed'] for row in q['cases'])
        assert not q['hardware'] and not q['serial_access'] and q['flash_writes']==q['SRAM_writes']==0
        assert q['build_sha256']==p.base.digest(manifest) and q['checker_sha256']==p.base.digest(p.HERE/checker)
        assert q['peripheral_model_sha256']==p.base.digest(p.HERE/'edu_sram_model.py')
        checks.extend(q['cases']);receipts[str(path)]=p.base.digest(path)
    bq=backup.selftest();assert bq['passed'];checks.extend(dict(passed=True,case='backup-parser-'+s) for s in bq['cases'])
    checks.extend((dict(passed=True,case='reproduced-ROM-client-installer'),dict(passed=True,case='reproduced-RAM-preflight')))
    marker=p.ROOT/'output/qualification/device-operations/2609.json';wear=Path(p.base.read(p.SESSION/'session.json')['wear_history'])
    assert p.base.digest(marker)==info['marker_sha256'] and p.base.read(p.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    assert p.base.read(wear)['sequence']==1020 and p.base.read(wear)['counts']==info['counts_before']
    assert not p.base.ATTEMPTS
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    for name in (p.PROVIDER,p.CLIENT,p.INSTALLER):shutil.copy2(build/'payload'/name,out/name)
    shutil.copy2(preflight/'payload'/pre.BIN,out/pre.BIN)
    shutil.copy2(build/'plan.json',out/'plan.json');shutil.copy2(wear,out/'actual-host-wear-before.json')
    (out/'old-B3-8-4096.bin').write_bytes((build/'source-b3.bin').read_bytes()[:4096])
    shutil.copy2(build/'action-00.bin',out/'planned-C600-256.bin')
    for folder in (tests,pre_tests):
        for path in folder.glob('simulated-*.txt'):shutil.copy2(path,out/path.name)
    (out/'SRAM-full-pass-commands.txt').write_bytes(b''.join(f'R {a:05X} 40\r\n'.encode() for a in range(0,131072,64)))
    shutil.copy2(p.HERE/'edu_sram_backup.py',out/'edu_sram_backup.py')
    p.base.save(out/'backup-parser-selftest.json',bq)
    names=('prepare_edu_sram_2609.py','prepare_edu_sram_preflight_2609.py','edu-sram-ro-provider.asm','edu-sram-ro-client.asm',
           'test_edu_sram_2609.py','test_edu_sram_preflight_2609.py','edu_sram_model.py','edu_sram_backup.py',
           'qualify_edu_sram_2609.py','test_b14_core.py','test_b14_raw.py','test_b07.py','test.py')
    sources={name:p.base.digest(p.HERE/name) for name in names}
    result=dict(passed=True,board='2609',checks=len(checks),cases=checks,hardware=False,board_access=False,serial_access=False,
        RAM_uploaded=False,flash_writes=0,saved_setting_writes=0,SRAM_writes=0,SRAM_mode_writes=0,host_wear_updated=False,
        byte_reproducible=True,build=str(build),build_sha256=p.base.digest(build/'plan.json'),repro=str(repro),
        preflight_build=str(preflight),preflight_build_sha256=p.base.digest(preflight/'build.json'),preflight_repro=str(pre_repro),
        sources=sources,receipts=receipts,actual_marker_sha256=p.base.digest(marker),actual_host_wear_sha256=p.base.digest(wear),
        source_sha256=info['source_sha256'],expected_sha256=info['expected_sha256'],default='S',enabled_banks=0,
        sequence_actual=1020,sequence_planned=1021,counts_actual=info['counts_before'],counts_planned=info['counts_after'],
        artifacts={path.name:p.base.binding(path) for path in out.iterdir() if path.is_file() and path.suffix!='.md'},
        limitations=['Read-only first stage; no named storage/WORK/saved EDU activation port',
                    'No physical EDU/electrical/cold-reset/battery retention/ACIA test',
                    'READ completion and configured 128KiB capacity do not prove physical presence or capacity',
                    'No SRAM write, mode write, format, repartition or C/D journal relocation',
                    'Exact checkpoint only; changed/interrupted/completed state requires new plan'])
    p.base.save(out/'qualification.json',result)
    table='\n'.join(f'| `{name}` | {p.base.binding(out/name)["bytes"]:,} | `{p.base.digest(out/name)}` |' for name in (pre.BIN,p.INSTALLER,p.PROVIDER,p.CLIENT))
    text=f'''# 2609 b15 EDU/SRAM — prepared, not installed

**PASS: {len(checks)} offline groups.** CPU/NOR and bit-level VIA/SRAM tests on
65C816 emulation and 65C02; independent WDC builds reproduce all four BINs.
No serial port opened, RAM uploaded, flash, saved setting or retained SRAM
written. Physical 2609 remains REC / S / banks 00 / sequence 1020.

| File | Bytes | SHA-256 |
|---|---:|---|
{table}

All RAM BINs load/enter at $0200 through C1, L, SEND BIN and the receive-idle
interval. The 4096-byte B3:8 provider image is a programmer payload, not RAM
input. Its body is {info['provider_body_bytes']} bytes, ending ${info['provider_body_end']}.

First use the RAM-only PREFLIGHT tool without a flash install. It supplies
`? S V A R aaaaa nn Q` and reads at most 64 bytes per request. INIT/S touch no
VIA pins; V inspects control registers; A explicitly acknowledges only guarded
idle disabled-CB flags by one ORB read. R uses only addressed READ and RDMR,
preserving all 131072 data bytes and the chip mode. It has no write/probe/format
or saved EDU switch. Status 00 means transfer completed; presence is unproven.

The proposed installer changes **C600 (append only) and B3:8 (one erase)**.
It commits seq1021 / S / banks00 with B3:8 count 26 → 27 before erasing 8000.
All other counts, original B0, B1/B2, B3:9 and A–F are retained except the C600
append. Configuration body and unknown-lifetime mask remain unchanged. The
actual host wear record is still seq1020; the planned values are not actual
history. `V W` inspect; `I` then `INSTALL EDU` is the later flash path. Progress
prints each action, blank/body/commit verification, all-bank validation and Q
to REC. This kit preparation does not authorize or execute that path.

[Operator sequence, keystrokes, ownership and acceptance](../../../../docs/STR8N_B15_EDU_SRAM_ONBOARDING.md)
· [Qualification](qualification.json) · [Exact plan](plan.json)
· [Simulated 816 installer](simulated-65c816-e-installer.txt)
· [Simulated RAM-only preflight](simulated-65c816-e-RAM-preflight.txt).

Full retained-array backup requires two dedicated pass logs, each with exactly
2048 ordered, successful 64-byte R replies, 00000 through 1FFC0. The supplied
`SRAM-full-pass-commands.txt` is an address list for a prompt-paced host tool;
do not paste it blindly into an unpaced terminal. `edu_sram_backup.py` opens no
port and assembles/verifies two such logs:

```text
python edu_sram_backup.py --first pass1-console.txt --second pass2-console.txt --out SRAM-backup
```

It rejects missing/duplicate/out-of-order addresses, failed reads, short data,
changed mode and differing arrays. Retain both BINs, the source logs and hashes.
Do not treat the simulated transcripts here as physical backups.

Before later installation double-read all current flash and preserve old B3:8;
afterward independently double-read and match exact planned flash. Repeat both
complete SRAM exports and compare with the pre-install baseline. Then inspect
the installed provider with the non-PREFLIGHT client and Q to REC. Preserve
actual attempt reservations on interruption and create a fresh plan; no blind
replay. Leave default S/banks disabled.

This is an optional ES1 ROM locator plus explicit RAM client, with no F/MON
patch or automatic reset activation. Named storage/WORK, legacy EDU ON/OFF
reclaim and SRAM-backed journals are later work. C/D stay in flash. Physical
EDU, reset/retention and ACIA qualification remain outstanding.
'''
    (out/'receipt.md').write_text(text,encoding='utf-8')
    print('PASS packaged',len(checks),'offline groups;',out,flush=True);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','repro','preflight','pre-repro','tests','pre-tests','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();qualify(args.build,args.repro,args.preflight,args.pre_repro,args.tests,args.pre_tests,args.out)
