"""Inventory exact beta35 migration evidence without opening hardware ports."""
import argparse
import binascii
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FLEET=ROOT/'output/qualification/beta35-fleet-2026-10-16'
OLD=ROOT/'output/qualification/beta34-fleet-2026-10-16'
BOARDS=['2205','2512','2604','2609']


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def valid_slot(data,page):
    return (len(data)==4096 and data[:4]==b'MI\x01'+bytes([page]) and data[31]==0
            and binascii.crc_hqx(data[:18]+data[32:],0xFFFF)==int.from_bytes(data[18:20],'little'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path,help='Evidence directory with models/<board>/report.json')
    p.add_argument('--doc',type=Path)
    args=p.parse_args()
    assert not (args.root/'migration-matrix.json').exists(),'Retain earlier audit; choose a new evidence directory'
    if args.doc:assert not args.doc.exists(),'Retain/review existing matrix before replacing it'
    meta=read(ROOT/'release/beta35/release.json');layout=read(ROOT/'release/beta35/layout.json')
    clean=ROOT/'tmp/c35e/payload';rows=[]
    for name,info in meta['expected'].items():assert sha(clean/name)==info['sha256']
    for board in BOARDS:
        folder=FLEET/board;plan=read(folder/'plan.json');historical=read(folder/'model.json')
        hardware=read(folder/'hardware.json');model_path=args.root/'models'/board/'report.json';fresh=read(model_path)
        assert fresh['passed'] and len(fresh['checks'])==18 and all(c['passed'] for c in fresh['checks'])
        assert plan['installer_sha256']==fresh['installer_sha256']==historical['installer_sha256']==sha(folder/'installer.s19')
        assert plan['build_sha256']==fresh['build_sha256']==meta['candidate_build_sha256']
        assert hardware['passed'] and hardware['build_sha256']==plan['build_sha256']
        assert hardware['host_readbacks'] is False and hardware['internal_program_verification'] is True
        prior_folder=OLD/'fresh/2512' if board=='2512' else OLD/board/'hardware'
        prefix='flash-1-b' if board=='2512' else 'final-b'
        prior=[(prior_folder/f'{prefix}{b}.bin').read_bytes() for b in range(4)]
        expected=[(folder/f'expected-b{b}.bin').read_bytes() for b in range(4)]
        assert [hashlib.sha256(b).hexdigest() for b in prior]==plan['prior_hashes']
        assert [hashlib.sha256(b).hexdigest() for b in expected]==plan['expected_hashes']==fresh['expected_hashes']
        a=prior[3][0x2000:0x3000];b=prior[3][0x3000:0x4000];target=expected[3][0x3000:0x4000]
        assert valid_slot(a,0xA0) and valid_slot(b,0xB0) and valid_slot(target,0xB0)
        assert int.from_bytes(a[8:12],'little')==40 and int.from_bytes(b[8:12],'little')==46
        assert int.from_bytes(target[8:12],'little')==47
        assert a==expected[3][0x2000:0x3000] and prior[3][0x6000:]==expected[3][0x6000:]
        changed={(bank,sector) for bank in range(4) for sector in range(8,16)
                 if prior[bank][(sector-8)*4096:(sector-7)*4096]!=expected[bank][(sector-8)*4096:(sector-7)*4096]}
        assert changed==set(map(tuple,plan['steps']))
        assert prior[3][0x1C00:0x2000]==expected[3][0x1C00:0x2000]
        counts=plan['counts_before'][:]
        for bank,sector in plan['steps']:counts[bank*8+sector-8]+=1
        assert counts==plan['counts_after']
        for segment in layout['segments']:
            data=(clean/segment['file']).read_bytes()[segment['offset']:segment['offset']+segment['bytes']]
            offset=segment['address']-0x8000
            assert expected[segment['bank']][offset:offset+len(data)]==data,(board,segment)
        rows.append({'board':board,'source_version':'2.0b34','source_generation':46,
            'target_version':'2.0b35','target_generation':47,'prior_fallback_generation':40,
            'retains_A28_replaces_B34':True,'inactive_slot_only_update':False,
            'all_13_canonical_ranges_match':True,'unchanged_recovery_E_F':True,
            'unlisted_flash_sectors_unchanged':True,'mutable_service_records_unchanged':True,
            'tracked_erase_increments_exact':True,'model_cases':len(fresh['checks']),
            'plan_sha256':sha(folder/'plan.json'),'installer_sha256':plan['installer_sha256'],
            'fresh_model_report':str(model_path.resolve()),'fresh_model_report_sha256':sha(model_path),
            'historical_hardware_report_sha256':sha(folder/'hardware.json'),
            'historical_internal_verification':True,'fresh_hardware_test':False,'fresh_host_readback':False})
    gaps=[
        {'source':'Stock WDC monitor','target':'2.0b35','status':'pending target-owned route and qualification'},
        {'source':'Published beta1/a24c1','target':'2.0b35','status':'pending legacy layout conversion, backup/restore and qualification'},
        {'source':'Published beta4','target':'2.0b35','status':'pending target-specific layout conversion and qualification; beta25 proof is not transitive'},
        {'source':'Other intermediate 2.0 layouts / either active slot','target':'2.0b35','status':'pending exact source catalog, ABI/profile planning and qualification'},
        {'source':'Unknown/corrupt/occupied destinations','target':'2.0b35','status':'pending generalized target planner refusal coverage'},
    ]
    active=read(ROOT/'output/qualification/active-rtc-campaign.json')
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    report={'version':'2.0b35','generation':47,'finished_utc':datetime.now(timezone.utc).isoformat(),
        'evidence_inventory_passed':True,'full_migration_matrix_qualified':False,
        'release_qualified':False,'installation_permitted':False,'board_access':False,
        'candidate_build_sha256':meta['candidate_build_sha256'],'fresh_model_cases':sum(r['model_cases'] for r in rows),
        'exact_routes':rows,'pending_routes':gaps,'deferred':['ACIA','crypto'],
        'rtc_baseline_unchanged':True,'harness_sha256':sha(Path(__file__)),
        'model_limit':'W65C02 instruction model; initial XCE byte handled by historical harness; not native 816 or electrical power-cut qualification',
        'public_launcher_audit':'Existing migrate_v2 catalog/default routes target beta25-era layouts, not a package-owned universal beta35 path',
        'next_action':'Develop and qualify the target-specific offline planner/converters for declared published sources; keep hardware gates pending'}
    (args.root/'migration-matrix.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.doc:
        lines=['# Beta35 migration support matrix','',
            'Target: 2.0b35 generation 47. This is a prerelease evidence inventory; the',
            'general migration matrix and installable release remain unqualified.','',
            '## Fresh exact-fixture checks','',
            '| Historical fixture | Source/target | Fresh offline cases | Hardware evidence |',
            '| --- | --- | --- | --- |']
        for row in rows:lines.append(f"| {row['board']} | b34 gen 46 -> b35 gen 47 | 18 passed | Earlier internal install verification; no fresh test/readback |")
        lines += ['',
            'All 72 model cases passed: exact final banks and erase order, FNV opcode',
            'equivalence, retained A, verified final monitor commit, stale preimages for',
            'each changed bank, and corrupt/incomplete payloads at every transfer row.',
            'An incomplete transfer waits without mutating that row or committing the',
            'new monitor. Earlier completed rows may already have changed. This does',
            'not prove atomic migration or electrical power-cut recovery.','',
            'These exact plans preserve B28 in A and replace B34 in B from RAM. They',
            'do not preserve the previously active B34 monitor as an inactive-slot-only',
            'upgrade would. Recovery E/F, unlisted sectors and mutable service records',
            'remain unchanged. Wear increments match the seven declared sector erases.',
            'All 13 canonical payload ranges match the freshly source-built review kit.',
            'The emulator uses the W65C02 model and the historical initial-XCE handling;',
            'no native 816 or new physical acceptance is claimed.','',
            '## Routes still requiring beta35 qualification','',
            '| Source | Status |','| --- | --- |']
        for gap in gaps:lines.append(f"| {gap['source']} | {gap['status']} |")
        lines += ['',
            'The existing generic launcher catalog/default selection still describes',
            'beta25-era routes. Do not treat recognition of an older source or a b4-to-b25',
            'test as a qualified b4-to-b35 upgrade. A release-owned beta35 planner must',
            'select the exact source/ABI/layout automatically, preserve user data and',
            'settings, reject unknown/occupied ranges, and qualify backup restoration',
            'and interrupted commits before the published forward-upgrade promise can',
            'be made for beta35. Physical qualification remains after the protected drift',
            'interval; no powered-off board was contacted.','',
            'Owner-local evidence: `'+str((args.root/'migration-matrix.json').relative_to(ROOT) if args.root.is_absolute() else args.root/'migration-matrix.json')+'`.',
            'ACIA and crypto remain deferred. RTC clocks, trims and baseline are unchanged.','']
        args.doc.parent.mkdir(parents=True,exist_ok=True);args.doc.write_text('\n'.join(lines))
    print('PASS evidence inventory:',len(rows),'exact routes,',report['fresh_model_cases'],'fresh model cases; generalized routes remain pending')


if __name__=='__main__':main()
