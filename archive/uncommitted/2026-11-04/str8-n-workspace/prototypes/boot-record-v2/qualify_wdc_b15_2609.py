"""Audit and package the offline 2609 F-only step; never opens a board port."""
import argparse
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path
import wdc_b15_2609 as planning
from installer.engine import legacy_transport as wire,runtime as r
from installer.common import save

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','reproduction','tests','boot','out'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();plan=args.plan.resolve();out=args.out.resolve();assert not out.exists()
    info=planning.verify(plan);again=planning.verify(args.reproduction)
    tests=r.read(args.tests/'model-proof.json');boot=r.read(args.boot/'boot-proof.json')
    for proof in (tests,boot):
        assert proof['passed'] and not any(proof[k] for k in ('hardware','serial_access','board_access','flashed'))
        assert proof['plan_sha256']==planning.digest(plan/'plan.json') and proof['installer_sha256']==info['installer_sha256']
    assert tests['test_source_sha256']==planning.digest(planning.HERE/'test_wdc_b15_2609.py')
    assert boot['test_source_sha256']==planning.digest(planning.HERE/'test_wdc_b15_F_only_boot.py')
    assert boot['model_source_sha256']==tests['test_source_sha256']
    assert tests['checks']==22 and boot['checks']==22
    tx=info['transaction'];assert tx['planned_erase_order']==[[3,15]] and len(tx['operations'])==1
    operation=tx['operations'][0];assert (operation['bank'],operation['address'],operation['commit_address'])==(3,0xf000,None)
    image=(plan/'b15-F-4096.bin').read_bytes();assert len(image)==4096 and image==(plan/'transfer-00.bin').read_bytes()
    assert planning.digest(plan/'b15-F-4096.bin')==boot['F_sha256']==info['F_sha256']
    source=[(plan/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert source[:3]==expected[:3] and source[3][:-4096]==expected[3][:-4096] and expected[3][-4096:]==image
    assert r.sha(source[0])==planning.WDC_SHA and source[0]==source[3]
    assert not planning.snbt_records(source) and not planning.snbt_records(expected)
    assert tx['reserved_counts']==[n+(i==31) for i,n in enumerate(tx['counts_before'])]
    assert tx['sequence_before']==tx['sequence_after'] and not tx['onboard_journal_initialized']
    names=['installer-model-only.s19','b15-F-4096.bin','transfer-00.bin','plan.json']
    names += [f'{kind}-b{n}.bin' for kind in ('source','expected') for n in range(4)]
    for name in names:assert (plan/name).read_bytes()==(args.reproduction/name).read_bytes(),'Reproduction differs: '+name
    cells,entry=wire.read_s19(plan/'installer-model-only.s19')
    assert set(cells)==set(range(0x2000,0x4000)) and entry==0x3700
    assert bytes(cells[a] for a in range(entry,entry+16))==planning.NATIVE_ENTRY
    assert int.from_bytes(bytes(cells[a] for a in range(0x3f00,0x3f04)),'little')==wire.fnv(bytes(cells[a] for a in range(0x2000,0x3f00)))
    marker=r.read(planning.ROOT/'output/qualification/device-operations/2609.json')
    assert marker['current_firmware_profile']=='original-WDCMONV2-65C816' and marker['stock_boot_verified'] and not marker['physical_reset_pending']
    assert marker['current_physical_bank_sha256']=={f'B{n}':r.sha(b) for n,b in enumerate(source)}
    assert r.read(planning.ROOT/'output/qualification/serial-coordination/owner.json')['kind']=='idle'
    success=[c for c in tests['cases'] if c.get('fault') is None and 'mode' in c]
    assert {c['mode'] for c in success}=={'native','emulation'}
    assert all(c['B0_B1_B2_and_nonF_B3_preserved_at_every_prefix'] and c['one_F_sector_only'] for c in success)
    prefixes=success[0]['mutation_prefixes'];assert all(c['mutation_prefixes']==prefixes for c in success)
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    for name in ('b15-F-4096.bin','installer-model-only.s19','transfer-00.bin'):shutil.copyfile(plan/name,out/name)
    report=dict(passed=True,board='2609',scope='F only: B3:F000-FFFF, exactly 4096 bytes',hardware_qualified=False,
        serial_access=False,board_access=False,flashed=False,stopped_before_flashing=True,
        plan=str(plan/'plan.json'),plan_sha256=planning.digest(plan/'plan.json'),
        F_sha256=info['F_sha256'],F_bytes=4096,installer_sha256=info['installer_sha256'],installer_entry_hex='3700',
        offline_checks=tests['checks']+boot['checks'],installer_checks=tests['checks'],F_up_checks=boot['checks'],
        mutation_prefixes_checked_per_success=prefixes,byte_identical_second_build=True,
        every_nonF_byte_preserved=True,B0_WDC_backup_preserved=True,C_D_initialized=False,MON_images_transferred=False,
        references={str(path.resolve()):planning.digest(path) for path in (args.tests/'model-proof.json',args.boot/'boot-proof.json')},
        operator_notes=['First boot reaches F recovery; no compatible MON or SNBT is installed in this stage',
            'RAM tools returning from F-only execution use RESET at $7E64; HOLD at $7E67 requires an active MON',
            'The one F erase is reserved in host metadata only; C/D remain byte-identical to WDC',
            'No automatic replay of a partial F installation; changed preimages are refused',
            'A physical interruption during F programming can require external recovery; B0 remains the original WDC copy'],
        finished_utc=datetime.now(timezone.utc).isoformat())
    save(out/'qualification.json',report)
    lines=['# 2609 WDCMONV2 → b15 — F-only preparation','',
        '**Prepared and tested offline. Stopped before flashing. 2609 remains on original WDCMONV2.**','',
        '| Artifact / check | Result |','|---|---|',
        '| Direct flash image | [b15-F-4096.bin](b15-F-4096.bin), exactly 4096 bytes for B3:$F000–$FFFF |',
        '| Factory-WDC RAM migrator | [installer-model-only.s19](installer-model-only.s19), RAM $2000–$3FFF; 65C816 entry $3700 |',
        '| Migrator transfer | [transfer-00.bin](transfer-00.bin), identical to the direct F BIN |',
        '| Planned flash operations | One B3:F erase/program/verify |',
        '| All other sectors | Byte-identical to source at every modeled mutation prefix, including B0 WDC backup |',
        '| MON / C / D / providers / languages | No payloads or flash writes in this step |',
        f'| Fresh offline checks | {report["offline_checks"]}: {tests["checks"]} installer + {boot["checks"]} F-up groups |',
        f'| NOR mutation prefixes | {prefixes} checked on each successful native/emulation run |',
        '| Second build | Installer, F BIN, transfer and source/target verification images reproduced byte for byte |','',
        'The installer normalizes original 65C816 native/emulation entry into E=1, DP=0 and DBR=0. It checks its loaded code/tables and all four complete source banks before erasing F. Exact RAM readback precedes EXEC in the tested stock loader. Stale banks, changed tables, wrong flash ID, cancellation, corrupt transfer, erase/program verification failures and altered host files were exercised.', '',
        'Both the direct-programmer F overlay and the RAM-migrated factory image boot into F recovery without MON, a new journal or provider sectors. Default/manual recovery, unavailable MON/bank selections, Ctrl-C cancellation and an eight-byte raw RAM app load/autorun/RESET were tested. Selected interrupted erase/program states refuse the original plan before additional mutation.', '',
        '**F-only return rule:** RAM RESET at `$7E64` restarts F and returns to recovery. HOLD at `$7E67` resumes the active MON; it must not be used before MON is installed. The original failed HOLD characterization is retained in the earlier test-attempt directory. The qualified b15 F bytes were not modified.', '',
        'No C/D journal is initialized, so the possible F erase is tracked only in the host plan. Power loss during F programming can still require external recovery. These are CPU/NOR and simulated transport tests, not a hardware installation or electrical power-cut qualification.', '',
        'The earlier five-sector MON/journal plan is superseded by the owner’s F-only instruction and must not be used. Full source/target bank images in the private master plan are verification escrow; the only flash transfer is the single F BIN.', '',
        f'F SHA-256: `{info["F_sha256"]}`.', '',
        '[Qualification record](qualification.json) · [Master plan](../step02-F-only-plan-r1/plan.json) · [Installer checks](../step02-F-only-tests-r1/model-proof.json) · [F-up checks](../step02-F-only-boot-r2/boot-proof.json).']
    (out/'receipt.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    source_dir=out/'source';source_dir.mkdir()
    for name in ('wdc_b15_2609.py','wdc-b15-guard.asm','test_wdc_b15_2609.py','test_wdc_b15_F_only_boot.py','qualify_wdc_b15_2609.py'):
        shutil.copyfile(planning.HERE/name,source_dir/name)
    save(out/'manifest.json',{str(path.relative_to(out)):dict(bytes=path.stat().st_size,sha256=planning.digest(path)) for path in out.rglob('*') if path.is_file() and path.name!='manifest.json'})
    print('PASS',report['offline_checks'],'offline groups;',prefixes,'mutation prefixes/run; only F payload; no hardware writes',out/'receipt.md',flush=True)

if __name__=='__main__':main()
