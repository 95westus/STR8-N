"""Offline CONFIG exercise from audited ES1 seq1021; no device/serial path."""
import argparse,shutil
from pathlib import Path
import prepare_config_save_restore_2609 as old

cfg=old.cfg
ROOT,HERE,SESSION=cfg.ROOT,cfg.HERE,cfg.SESSION
BUILD,READY=old.BUILD,old.READY
SOURCE=SESSION/'step17-EDU-SRAM-install'
TEST='test_config_save_restore_seq1021_2609.py'


def source():
    cfg.verify(BUILD);state=cfg.read(SESSION/'session.json');report=cfg.read(SOURCE/'report.json');audit=cfg.read(SOURCE/'audit.json');close=cfg.read(SOURCE/'closeout.json')
    wearpath=Path(state['wear_history']);wear=cfg.read(wearpath);q=cfg.read(READY/'qualification.json')
    assert report['passed'] and report['final_REC_verified'] and report['port_released'] and report['saved_setting_writes']==0
    assert audit['passed'] and close['passed'] and audit['report_sha256']==wear['execution_report_sha256']==cfg.digest(SOURCE/'report.json')
    assert close['audit_sha256']==cfg.digest(SOURCE/'audit.json') and audit['fresh_pre_install_and_two_post_install_arrays_match_both_originals']
    assert state['last_completed_step']==17 and state['EDU_SRAM_ROM_installed'] and not state['configuration_changed']
    assert wearpath==SOURCE/'host-wear-after.json' and wear['sequence']==1021 and wear['counts'][24]==27
    assert q['passed'] and q['checks']==31 and cfg.digest(READY/cfg.BIN)==q['sha256']=='9d98ce51026f1a2f88f4ee1a34ab5a6d853d17371a98d34035b6923ee98e921d'
    for name,value in q['sources'].items():assert cfg.digest(HERE/name)==value
    banks=[];paths=[]
    for n in range(4):
        a,b=(SOURCE/f'final-r{r}-b{n}.bin' for r in (1,2));assert a.read_bytes()==b.read_bytes();banks.append(a.read_bytes());paths.extend((a,b))
    assert list(map(cfg.sha,banks))==report['expected_sha256'] and cfg.sha(banks[0])==cfg.WDC_SHA and cfg.sha(banks[3][-4096:])==cfg.F_SHA
    rows=cfg.snbt_records(banks);seq,offset,row=max(rows);assert len(rows)==8 and seq==1021 and offset==0x4600
    assert row[7]==ord('S') and row[13]==0 and row[14:18]==b'\x08'*4 and row[160:164]==b'\xff'*4
    assert row[32:48].hex()==wear['config'] and int.from_bytes(row[18:22],'little')==cfg.GENERATION
    assert [int.from_bytes(row[64+3*n:67+3*n],'little') for n in range(32)]==wear['counts'] and banks[3][0x4700:0x4900]==b'\xff'*512
    srampaths=[SESSION/f'step16-EDU-SRAM-preflight-live/SRAM-pass{n}-131072.bin' for n in (1,2)]
    srampaths.extend(SOURCE/(name+'-131072.bin') for name in ('SRAM-before-install','SRAM-after-pass1','SRAM-after-pass2'))
    sram=srampaths[0].read_bytes();assert len(sram)==131072 and all(path.read_bytes()==sram for path in srampaths)
    assert cfg.sha(sram)==report['SRAM_sha256']==audit['SRAM_sha256']=='56cd2490028e7c6b4ee07fb26c87ea75d9d665f10c6406263c0c0f4000116a9e'
    markerpath=ROOT/'output/qualification/device-operations/2609.json';marker=cfg.read(markerpath)
    assert marker['current_firmware_profile']=='b15-VX1-ES1-F-CD-MON-AB-E-8' and marker['EDU_SRAM_ROM_installed'] and marker['EDU_SRAM_provider_verified']
    assert not any(value for key,value in marker.items() if key.endswith('_worker_active'))
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),map(cfg.sha,banks)))
    assert cfg.read(ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    paths.extend([*srampaths,SOURCE/'report.json',SOURCE/'audit.json',SOURCE/'closeout.json',wearpath,READY/cfg.BIN,READY/'qualification.json',
        BUILD/'ram-config-build.json',BUILD/'symbols.json',Path(__file__),HERE/TEST,HERE/'edu_sram_model.py',HERE/'test_config_save_restore_2609.py',
        HERE/'test_ram_config_2609.py',HERE/'test_ram_config_b14.py',HERE/'test_b14_core.py',HERE/'test_b14_raw.py'])
    base=dict(cfg.read(BUILD/'baseline.json'),source_run=str(SOURCE),bank_sha256=list(map(cfg.sha,banks)),counts=wear['counts'],sequence=1021,
        config=wear['config'],SRAM_sha256=cfg.sha(sram),SRAM_bytes=131072,SRAM_mode='40',SRAM_source=str(srampaths[0]),EDU_SRAM_ROM_installed=True)
    return banks,base,row,{str(path.resolve()):cfg.binding(path) for path in paths},cfg.digest(markerpath),str(wearpath)


def admit_source(banks,plan):return old.admit_source(banks,plan)


def admit_SRAM(data,plan):
    assert len(data)==131072 and cfg.sha(data)==plan['baseline']['SRAM_sha256'],'Retained SRAM differs; inspect before any save'


def prepare(out):
    out=Path(out).resolve();assert out.is_relative_to(ROOT/'output/qualification') and not out.exists()
    banks,base,row,inputs,marker,wear=source();out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    stage=list(banks);operations=[]
    for name,target,address,seq in (('MON-A','A',0xc700,1022),('restored-S','S',0xc800,1023)):
        row=bytearray(row);row[7]=ord(target);row[8:12]=seq.to_bytes(4,'little')
        if target=='A':row[18:22]=stage[3][0x2008:0x200c]
        row=old.seal(row);image=bytearray(stage[3]);image[address-0x8000:address-0x8000+256]=row;stage[3]=bytes(image)
        for n,data in enumerate(stage):(out/f'{name}-b{n}.bin').write_bytes(data)
        (out/f'{name}-journal-row.bin').write_bytes(row)
        operations.append(dict(stage=name,CONFIG_command='C '+target,address=f'{address:04X}',sequence=seq,erase=False,bytes=256,
            commit_offset=255,default=target,enabled_banks=0,counts=base['counts'],bank_sha256=list(map(cfg.sha,stage))))
    for n,data in enumerate(banks):(out/f'source-b{n}.bin').write_bytes(data)
    cfg.save(out/'baseline.json',base)
    plan=dict(passed=True,prepared=True,qualified=False,board='2609',hardware=False,board_access=False,serial_access=False,RAM_uploaded=False,
        saved_setting_writes=False,build=str(BUILD),ready=str(READY),BIN=cfg.BIN,BIN_sha256=cfg.digest(READY/cfg.BIN),source_sha256=list(map(cfg.sha,banks)),baseline=base,
        sequence_before=1021,sequence_temporary=1022,sequence_restored=1023,default_before='S',default_temporary='A',default_after='S',
        enabled_banks_before=0,enabled_banks_after=0,counts_before=base['counts'],counts_after=base['counts'],unknown_history_mask='ffffffff',erase_count=0,
        MON_A_pinned_generation='8000000F',journal_appends=['C700','C800'],operations=operations,source_marker_sha256=marker,host_wear_history=wear,
        inputs=inputs,artifacts={str(path.relative_to(out)):cfg.binding(path) for path in [*out.glob('*.bin'),out/'baseline.json']},
        stop='Offline preparation only; no physical RAM upload or C A/C S',retry='Read current journal and replan changed/torn/completed sources; do not replay blindly')
    cfg.save(out/'plan.json',plan);verify(out)
    print('PREPARED C700 seq1022 default A; C800 seq1023 restore S; zero erases; all counts incl B3:8=27 and SRAM retained',flush=True);return plan


def verify(out):
    out=Path(out).resolve();plan=cfg.read(out/'plan.json')
    for name,info in plan['inputs'].items():assert cfg.digest(name)==info['sha256'],'Changed input '+name
    for name,info in plan['artifacts'].items():assert cfg.digest(out/name)==info['sha256'],'Changed artifact '+name
    assert plan['counts_before']==plan['counts_after'] and plan['counts_after'][24]==27 and plan['erase_count']==0 and plan['journal_appends']==['C700','C800']
    a=[(out/f'source-b{n}.bin').read_bytes() for n in range(4)];admit_source(a,plan);admit_SRAM(Path(plan['baseline']['SRAM_source']).read_bytes(),plan)
    previous=max(cfg.snbt_records(a))[2]
    for op in plan['operations']:
        row=bytearray(previous);row[7]=ord(op['default']);row[8:12]=op['sequence'].to_bytes(4,'little')
        if op['default']=='A':row[18:22]=a[3][0x2008:0x200c]
        row=old.seal(row);address=int(op['address'],16)-0x8000;assert a[3][address:address+256]==b'\xff'*256
        b=bytearray(a[3]);b[address:address+256]=row;a[3]=bytes(b)
        assert [ (out/f'{op["stage"]}-b{n}.bin').read_bytes() for n in range(4)]==a and list(map(cfg.sha,a))==op['bank_sha256']
        assert (out/f'{op["stage"]}-journal-row.bin').read_bytes()==row;previous=row
    return plan


def package(plan_dir,tests,repro,ready):
    plan_dir,tests,repro,ready=map(lambda path:Path(path).resolve(),(plan_dir,tests,repro,ready));assert not ready.exists()
    plan=verify(plan_dir);other=verify(repro);proof=cfg.read(tests/'qualification.json')
    assert proof['passed'] and proof['checks']==25 and not proof['hardware'] and not proof['serial_access']
    assert proof['plan_sha256']==cfg.digest(plan_dir/'plan.json') and proof['checker_sha256']==cfg.digest(HERE/TEST)
    assert proof['retained_SRAM_checks']>0 and proof['no_SPI_access'] and proof['SRAM_sha256']==plan['baseline']['SRAM_sha256']
    for path in plan_dir.glob('*.bin'):assert path.read_bytes()==(repro/path.name).read_bytes()
    assert cfg.digest(ROOT/'output/qualification/device-operations/2609.json')==plan['source_marker_sha256'] and not cfg.ATTEMPTS
    ready.mkdir(parents=True);(ready/'.gitignore').write_text('*\n');shutil.copy2(READY/cfg.BIN,ready/cfg.BIN)
    for name in ('plan.json','baseline.json'):shutil.copy2(plan_dir/name,ready/name)
    for path in tests.glob('simulated-*.txt'):shutil.copy2(path,ready/path.name)
    shutil.copy2(tests/'qualification.json',ready/'qualification.json');shutil.copy2(tests/'adapter.json',ready/'adapter.json')
    receipt=f'''# 2609 CONFIG exercise from seq1021 — prepared only

**PASS: {proof['checks']} offline groups, {proof['mutation_prefixes']} interrupted
append prefixes.** Both CPU models and USB/ACIA console models. No serial port,
RAM upload, flash erase, actual saved-setting write or SRAM transaction.

Use the unchanged, previously USB-inspected **`{cfg.BIN}`**, 2728 bytes,
load/entry $0200, SHA-256 `{plan['BIN_sha256']}`. F/MON/ES1 are unchanged.

| Stage | Prospective command | Journal | Default | Banks | Erases |
|---|---|---|---|---|---|
| Actual board | None | C600 seq1021 | S | 00 | 0 |
| Temporary MON A | `C A` | C700 seq1022 | A, generation 8000000F | 00 | 0 |
| Restore recovery | `C S` | C800 seq1023 | S | 00 | 0 |

All 32 counts remain unchanged, including B3:8=27, A=51, B=54, C=78, D=47,
E=43, F=30 and unknown-lifetime mask FFFFFFFF. B0, ES1 B3:8, B3:9, MONs,
VX1, F and every other non-appended byte are preserved. The peripheral model
starts with the actual retained 131072-byte SRAM backup; CONFIG/boot paths make
no SPI register access or SRAM data/mode writes. Its before/after array hash is
`{plan['baseline']['SRAM_sha256']}`; {proof['retained_SRAM_checks']} checks passed.

## Future hardware sequence — not executed

1. Double-read all four banks; admit this exact seq1021 source, S/mask00, all
   counts and blank C700/C800. Read retained SRAM through ES1 and compare both
   original backups. Preserve owner RAM if needed. Keep USB and board identity
   exclusive; no other board work is part of this exercise.
2. At REC: `C1` Enter, `L` Enter, send `{cfg.BIN}` after SEND BIN. Inspect bare
   `B`, bare `C`, `W`; then `Q` to REC and `A` Enter to MON A. Independently dump
   `D 0200 0CA7`, compare all app bytes (only CONFIG_ROW=4 display state differs),
   and use `G 0200` to re-enter the verified RAM app.
   **Preparation stops before `C A`.** CONFIG has no separate Save command.
3. After later live authorization, `C A` Enter once; require OK and displays
   DEFAULT=A, banks00 and exact prior counts. `Q` and let the countdown expire:
   saved A must boot without typing A. Check `D 7D30 7D30` gives A0 and
   `D C700 C7FF` equals the planned committed seq1022 row. `J3` then single `S`
   reaches REC manually while A stays saved.
4. Reload the same CONFIG BIN, inspect bare C, Q back to saved A, repeat the
   independent RAM dump and G re-entry; only then `C S` Enter once. Require OK,
   DEFAULT=S, banks00 and unchanged counts. Q must reach REC without an S key.
5. Double-read all flash and compare exactly the two planned appends. Re-read
   all SRAM and compare both backups, retain mode40 and preserve all contents.
   Finish at REC, close the port, retain original wear history and create a new
   verified host record at seq1023 with the same counts. Do not overwrite an
   old journal image to restore policy.

Interruption: inspect the current committed row and any torn pages; the exact
old plan refuses changed/torn/completed sources. If A remains saved, choose S
manually and prepare only the needed S append, skipping dirty pages. If S is
already committed, do not append another C S. Missing/bad/uncommitted MON A is
refused; unavailable saved A falls back to REC, where RAM CONFIG can restore S.

[Qualification](qualification.json) · [Plan](plan.json) · [Model adapter](adapter.json)
· [Simulated 816 USB](simulated-walkthrough-65c816-e-port1.txt).
Models are not physical/electrical interruption or ACIA qualification. This is
preparation only: physical 2609 remains seq1021/S/banks00, B0 and SRAM intact.
'''
    (ready/'receipt.md').write_text(receipt,encoding='utf-8')
    cfg.save(ready/'manifest.json',{str(path.relative_to(ready)):cfg.binding(path) for path in ready.iterdir() if path.is_file() and path.name!='manifest.json'})
    print('PACKAGED',proof['checks'],'groups;',proof['mutation_prefixes'],'prefixes; no physical writes',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','verify','package'));parser.add_argument('--out',type=Path,required=True)
    for name in ('tests','repro','ready'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args()
    if args.command=='prepare':prepare(args.out)
    elif args.command=='verify':verify(args.out);print('PASS exact seq1021 plan; no device access')
    else:package(args.out,args.tests,args.repro,args.ready)
