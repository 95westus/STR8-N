"""Prepare a source-bound CONFIG A-then-S exercise; no live/device path."""
import argparse,json,shutil
from pathlib import Path
import prepare_ram_config_2609 as cfg
from installer.engine.legacy_transport import crc

ROOT,HERE,SESSION=cfg.ROOT,cfg.HERE,cfg.SESSION
BUILD=SESSION/'step10-CONFIG-build-r1'
READY=SESSION/'step10-CONFIG-ready'
SOURCE=SESSION/'step11-CONFIG-inspection'


def source():
    cfg.verify(BUILD)
    report=cfg.read(SOURCE/'report.json');audit=cfg.read(SOURCE/'audit.json')
    state=cfg.read(SESSION/'session.json');wearpath=Path(state['wear_history']);wear=cfg.read(wearpath)
    q=cfg.read(READY/'qualification.json');image=READY/cfg.BIN
    assert report['passed'] and report['final_REC_verified'] and report['saved_setting_writes']==0
    assert audit['passed'] and audit['report_sha256']==cfg.digest(SOURCE/'report.json') and audit['all_128KiB_flash_unchanged']
    assert not state['configuration_changed'] and state['last_completed_step']==11
    assert q['passed'] and q['checks']==31 and cfg.digest(image)==q['sha256']==report['RAM_BIN_sha256']
    for name,value in q['sources'].items():assert cfg.digest(HERE/name)==value
    banks=[]
    for n in range(4):
        a,b=(SOURCE/f'after-r{r}-b{n}.bin' for r in (1,2))
        assert a.read_bytes()==b.read_bytes();banks.append(a.read_bytes())
    base=report['baseline'];assert list(map(cfg.sha,banks))==base['bank_sha256']
    assert wear['counts']==base['counts'] and wear['sequence']==base['sequence']==1020
    assert wearpath.read_bytes()==(SOURCE/'host-wear-before.json').read_bytes()
    rows=cfg.snbt_records(banks);seq,off,row=max(rows,key=lambda value:value[0])
    assert len(rows)==7 and seq==1020 and off==0x4500 and row[7]==ord('S') and row[13]==0
    assert row[32:48].hex()==wear['config'] and row[160:164]==b'\xff'*4 and row[14:18]==b'\x08'*4
    assert int.from_bytes(row[18:22],'little')==cfg.GENERATION
    assert banks[3][0x4600:0x4800]==b'\xff'*512
    assert cfg.sha(banks[0])==cfg.WDC_SHA and cfg.sha(banks[3][-4096:])==cfg.F_SHA
    markerpath=ROOT/'output/qualification/device-operations/2609.json';marker=cfg.read(markerpath)
    assert marker['current_firmware_profile']=='b15-VX1-F-CD-MON-AB-E' and marker['CONFIG_inspection_verified']
    assert not any(value for name,value in marker.items() if name.endswith('_worker_active'))
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),base['bank_sha256']))
    assert cfg.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    paths=[SOURCE/'report.json',SOURCE/'audit.json',wearpath,image,READY/'qualification.json',
           BUILD/'ram-config-build.json',BUILD/'symbols.json',Path(__file__),HERE/'test_config_save_restore_2609.py',
           HERE/'test_ram_config_2609.py',HERE/'test_ram_config_b14.py',HERE/'test_b14_core.py',HERE/'test_b14_raw.py',
           *SOURCE.glob('after-r*-b?.bin')]
    return banks,base,row,{str(path):cfg.binding(path) for path in paths},cfg.digest(markerpath),str(wearpath)


def seal(row):
    row=bytearray(row);row[30:32]=crc(row[:30]).to_bytes(2,'little');row[252:254]=crc(row[:252]).to_bytes(2,'little');row[255]=0
    return bytes(row)


def admit_source(banks,plan):
    assert list(map(cfg.sha,banks))==plan['source_sha256'],'Changed or interrupted source; inspect and replan, never blind replay'


def prepare(out):
    out=Path(out).resolve();assert out.is_relative_to(ROOT/'output/qualification') and not out.exists()
    banks,base,row,inputs,marker_sha,wearpath=source()
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    stage=list(banks);operations=[]
    for name,target,address,seq in (('MON-A','A',0xc600,1021),('restored-S','S',0xc700,1022)):
        row=bytearray(row);row[7]=ord(target);row[8:12]=seq.to_bytes(4,'little')
        if target=='A':row[18:22]=stage[3][0x2008:0x200c]
        row=seal(row);updated=bytearray(stage[3]);updated[address-0x8000:address-0x8000+256]=row;stage[3]=bytes(updated)
        for bank,data in enumerate(stage):(out/f'{name}-b{bank}.bin').write_bytes(data)
        (out/f'{name}-journal-row.bin').write_bytes(row)
        operations.append(dict(stage=name,CONFIG_command='C '+target,address=f'{address:04X}',sequence=seq,
            erase=False,bytes=256,commit_offset=255,default=target,enabled_banks=0,counts=base['counts'],bank_sha256=list(map(cfg.sha,stage))))
    for bank,data in enumerate(banks):(out/f'source-b{bank}.bin').write_bytes(data)
    cfg.save(out/'baseline.json',base)
    plan=dict(passed=True,prepared=True,qualified=False,board='2609',hardware=False,board_access=False,serial_access=False,
        RAM_uploaded=False,saved_setting_writes=False,build=str(BUILD),ready=str(READY),BIN=cfg.BIN,
        BIN_sha256=cfg.digest(READY/cfg.BIN),source_sha256=list(map(cfg.sha,banks)),baseline=base,
        sequence_before=1020,sequence_temporary=1021,sequence_restored=1022,default_before='S',default_temporary='A',default_after='S',
        enabled_banks_before=0,enabled_banks_after=0,counts_before=base['counts'],counts_after=base['counts'],
        unknown_history_mask='ffffffff',MON_A_pinned_generation='8000000F',erase_count=0,
        journal_appends=['C600','C700'],operations=operations,
        source_marker_sha256=marker_sha,host_wear_history=wearpath,inputs=inputs,
        artifacts={str(path.relative_to(out)):cfg.binding(path) for path in [*out.glob('*.bin'),out/'baseline.json']},
        stop='Preparation only; do not send C A or C S to physical 2609',
        retry='Changed/torn/completed source refuses this exact plan. Read current journal and create an inspected recovery plan.')
    cfg.save(out/'plan.json',plan)
    print('PREPARED: C600 seq1021 default A; C700 seq1022 restore S; no erase; all counts and bank mask retained',flush=True)
    return plan


def verify(out):
    out=Path(out).resolve();plan=cfg.read(out/'plan.json')
    for name,value in plan['inputs'].items():assert cfg.digest(name)==value['sha256'],'Changed input '+name
    for name,value in plan['artifacts'].items():assert cfg.digest(out/name)==value['sha256'],'Changed artifact '+name
    assert plan['counts_before']==plan['counts_after'] and plan['erase_count']==0 and plan['journal_appends']==['C600','C700']
    return plan


def package(out,tests,ready):
    out,tests,ready=(Path(value).resolve() for value in (out,tests,ready));assert not ready.exists()
    plan=verify(out);proof=cfg.read(tests/'qualification.json')
    assert proof['passed'] and not proof['hardware'] and not proof['serial_access']
    assert proof['plan_sha256']==cfg.digest(out/'plan.json') and proof['checker_sha256']==cfg.digest(HERE/'test_config_save_restore_2609.py')
    assert cfg.digest(ROOT/'output/qualification/device-operations/2609.json')==plan['source_marker_sha256']
    assert not cfg.ATTEMPTS
    ready.mkdir(parents=True);(ready/'.gitignore').write_text('*\n')
    shutil.copy2(READY/cfg.BIN,ready/cfg.BIN)
    for name in ('plan.json','baseline.json'):shutil.copy2(out/name,ready/name)
    for path in tests.glob('simulated-*.txt'):shutil.copy2(path,ready/path.name)
    shutil.copy2(tests/'qualification.json',ready/'qualification.json')
    receipt=f'''# 2609 CONFIG MON A / restore S exercise — prepared only

**PASS: {proof['checks']} offline groups; no device access, RAM upload or actual
saved-setting write. Physical 2609 remains default S, all banks disabled.**

Use the already hardware-inspected **`{cfg.BIN}`**, 2,728 bytes, unchanged.
SHA-256: `{plan['BIN_sha256']}`. This RAM app is loaded with F raw L at `$0200`;
no new firmware or sector image is installed by this exercise preparation.

| Stage | Prospective command | New committed journal | Default | Enabled banks | Erases |
|---|---|---|---|---|---|
| Current verified board | Inspection only completed | Latest C500, seq 1020 | S | 00 | — |
| Save temporary MON A | `C A` Enter at RAM CONFIG | C600, seq 1021 | A, generation 8000000F | 00 | 0 |
| Restore recovery | `C S` Enter at RAM CONFIG | C700, seq 1022 | S | 00 | 0 |

Both settings saves append a full-CRC snapshot, verify its body and commit last.
All 32 tracked erase counts, unknown mask FFFFFFFF, legacy settings and bank
entries remain unchanged. B0 WDCMONV2 and every non-journal flash byte are
preserved. Counts remain A=51, B=54, C=78, D=47, E=43, F=30.

## Future exact exercise — not executed

1. Read all four banks twice; admit the exact source and blank C600/C700.
   Verify the current wear history, S default, mask 00 and exact CONFIG RAM app.
2. At REC, use C1 Enter, L Enter; send `{cfg.BIN}` after SEND BIN. Inspect
   bare B, bare C and W. Q Enter returns to REC; A Enter launches MON A manually.
   Read `D 0200 0CA7` Enter and compare the entire loaded app with the qualified
   BIN, allowing only CONFIG_ROW=4 from the displays. `G 0200` Enter re-enters
   that verified RAM app without another raw upload.
   **Preparation stops before the next command.**
3. After separate live authorization, send `C A` Enter. Expect OK. Bare B/C
   must show DEFAULT=A and all banks OFF; W must match every prior count.
   The writer verifies its body and commit before returning OK.
4. `Q` Enter restarts F. Let the countdown expire without typing A: the saved
   default must launch MON A. Verify its banner and active page A0 with
   `D 7D30 7D30` Enter. Read `D C600 C6FF` Enter and independently verify the
   complete planned seq1021 row, CRCs, commit, mask and pinned generation.
   `J3` Enter then `S` (no Enter) selects recovery manually;
   that selection does not change the saved A default.
5. Reload the same CONFIG BIN from REC. Bare C confirms A; Q Enter boots that
   saved MON A again. Repeat the independent RAM D dump and `G 0200` before
   writing, so the second raw upload is also verified.
   Send `C S` Enter once. Expect OK.
   Bare B/C must show DEFAULT=S with all banks OFF; W must still match.
6. `Q` Enter must reach REC on countdown expiry without an S override.
   Double-read all banks, verify only the two planned journal appends,
   sequence 1022, restored policy, all counts and B0; close the port and stop.

Restore means a **new `C S` journal append**, not flashing an older C/D image.
The final boot policy matches the original; journal history and sequence advance.
The normal plan needs no sector erase and does not reset or reinitialize counters.
The existing host history is retained during preparation; any later successful
hardware exercise needs a new verified host record at sequence 1022 with the
same counts. Do not rewrite the earlier history file.

## Interruption and recovery boundary

No automatic replay: a changed, torn or completed preimage is outside this exact
plan. Inspect the latest committed journal before proceeding. A torn A save
leaves S or A; a torn S restore leaves A or S. Select S manually at boot choices
to reach recovery while the saved default is still A. Under an inspected
recovery plan, append only the required S restoration, skipping any torn page.
If the saved default is already S, do not send C S again: it would append again.
An unavailable MON A falls back to recovery; the RAM CONFIG can restore S
without a working monitor. These paths are model-tested, not electrical trials.

[Qualification](qualification.json) · [Plan](plan.json) ·
[Simulated 65C816 USB walkthrough](simulated-walkthrough-65c816-e-port1.txt).
Private expected bank/row images are verification escrow, not flash payloads.
MON's D/G RAM validation path is newly rehearsed offline here; this preparation
does not claim a physical G-to-CONFIG trial or execute either saved-setting command.
The legacy CONFIG qualification and USB inspection remain archived separately.
ACIA and electrical power interruption are not newly board-qualified.
'''
    (ready/'receipt.md').write_text(receipt,encoding='utf-8')
    source_dir=ready/'source';source_dir.mkdir()
    for name in ('prepare_config_save_restore_2609.py','test_config_save_restore_2609.py'):shutil.copy2(HERE/name,source_dir/name)
    cfg.save(ready/'manifest.json',{str(path.relative_to(ready)):cfg.binding(path) for path in ready.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PACKAGED',proof['checks'],'groups;',proof['mutation_prefixes'],'interrupted-write prefixes; no physical writes',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify','package']);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--tests',type=Path);parser.add_argument('--ready',type=Path)
    args=parser.parse_args()
    if args.command=='package':package(args.out,args.tests,args.ready)
    elif args.command=='prepare':prepare(args.out)
    else:verify(args.out);print('PASS plan inputs/artifacts; no device access',flush=True)
