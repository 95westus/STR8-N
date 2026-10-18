"""Cold-boot and stale-installer re-entry from preserved model-only images.

No hardware reset/serial access. Fake RTC/EEPROM/SRAM are separate emulator
devices; saved flash images remain read-only. This is not electrical testing.
"""
import argparse,json,os,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
import plan_beta35_offline as p

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    evidence=p.ROOT/'output/qualification/beta35-prerelease-2026-10-17'
    checkpoint=p.read(evidence/'transaction-model-checkpoint.json');prior_path=Path(checkpoint['report'])
    assert p.sha(prior_path.read_bytes())==checkpoint['report_sha256'];prior=p.read(prior_path);assert prior['passed'] and prior['cases']==46
    source=prior_path.parent;images=Path(checkpoint['build_report']).parent
    assert p.sha((images/'build-report.json').read_bytes())==checkpoint['build_report_sha256']
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');workspace=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'));sys.path.insert(0,str(workspace/'tools'))
    import serial
    def forbidden(*a,**kw):raise RuntimeError('Serial access forbidden in offline interrupted-boot model')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    from test_v2_status import fresh,boot,layout,snapshot
    from test_v2_sram_store import console
    import test_v2_rtc_upgrade as installer
    mf=p.read(workspace/'BUILD/v2-beta35-candidate/migrator/manifest.json');installer.S=mf['symbols'];installer.MANIFEST=mf;S=installer.S
    checks=[]
    def latest(banks):
        records=[]
        for off in range(0x4000,0x6000,128):
            r=bytes(banks[3][off:off+128])
            if r[:4]==b'WC\x01\0' and r[127]==0 and p.crc(r[:120])==int.from_bytes(r[120:122],'little'):
                records.append((int.from_bytes(r[4:8],'little'),r))
        assert records;return max(records,key=lambda x:x[0])[1]
    def record(label,**info):
        checks.append(dict(name=label,passed=True,**info));print('PASS',label,flush=True)
        (args.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n')
    try:
        # Explicitly qualify the prior harness's backward-date policy append.
        # This is expected firmware behavior, not an installer mutation.
        banks=[(source/'2609-complete'/f'b{i}.bin').read_bytes() for i in range(4)]
        cpu,m=fresh(primary=layout());m.fast=True;m.banks=[bytearray(b) for b in banks]
        before=snapshot(m);boot(cpu);after=snapshot(m)
        expected=bytearray(b'\xff'*32);expected[:4]=b'BA\x01\0';expected[4:8]=(6).to_bytes(4,'little')
        expected[8:15]=banks[3][0x1E68:0x1E6F];expected[12]=3
        expected[28:30]=p.crc(expected[:28]).to_bytes(2,'little');expected[31]=0
        wanted=list(banks);b3=bytearray(wanted[3]);assert b3[0x1E80:0x1EA0]==b'\xff'*32
        b3[0x1E80:0x1EA0]=expected;wanted[3]=bytes(b3)
        assert after[0]==wanted and after[1:]==before[1:] and not m.bus.writes
        assert b'Battery age uncertain' in m.tx and bytes(m.tx).endswith(b'B3> ')
        diagnostic=args.out/'backward-date-policy';diagnostic.mkdir()
        (diagnostic/'boot.txt').write_bytes(m.tx);(diagnostic/'expected-record.bin').write_bytes(expected)
        (diagnostic/'events.json').write_text(json.dumps(m.events,indent=2)+'\n')
        cpu2,m2=fresh(primary=layout());m2.fast=True;m2.banks=[bytearray(b) for b in wanted]
        before2=snapshot(m2);boot(cpu2)
        assert snapshot(m2)==before2 and not m2.events and not m2.bus.writes
        (diagnostic/'second-boot.txt').write_bytes(m2.tx)
        record('2609 backward-date battery policy',virtual_rtc='2026-10-08T19:53:15',
            exact_append_address='B3:9E80',sequence=6,stage=3,record_sha256=p.sha(expected),
            other_flash_eeprom_rtc_sram_unchanged=True,second_boot_no_additional_mutation=True)
        for case in prior['checks']:
            label=case['name'];folder=args.out/label;folder.mkdir()
            banks=[(source/label/f'b{i}.bin').read_bytes() for i in range(4)]
            assert p.bank_hashes(banks)==case['bank_sha256']
            cfg=latest(banks)[8:24];page=cfg[8];assert cfg[7:8]==b'P' and page in (0xA0,0xB0)
            cpu,m=fresh(primary=layout());m.fast=True;m.banks=[bytearray(b) for b in banks]
            # Archive policy high-water dates run through October 16. Use an
            # explicit forward-date virtual RTC for the transaction boot tests.
            m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2E 17 10 26 80 00')
            # Align only the fake EEPROM's EUI with the preserved EI binding,
            # without changing any saved flash byte or actual device.
            binding=bytes(m.banks[3][0x1C00:0x1C20])
            if binding[:3]==b'EI\1' and binding[31]==0 and p.crc(binding[:28])==int.from_bytes(binding[28:30],'little'):
                m.bus.ee[0xF2:0xF8]=binding[8:14]
            before=snapshot(m)
            try:
                boot(cpu)
                (folder/'boot.txt').write_bytes(m.tx)
                assert m.ram[0x7D30]==page,(label,'selected monitor mismatch',hex(m.ram[0x7D30]),hex(page))
                assert bytes(m.tx).endswith(b'B3> '),(label,bytes(m.tx[-500:]))
                reply=console(cpu,m,b'D 0200 0200\r',limit=10000000)
                (folder/'monitor-read.txt').write_bytes(reply)
                assert b'0200' in reply and b'5A' in reply and reply.endswith(b'B3> '),(label,reply)
                assert snapshot(m)==before,(label,'Cold boot or read command changed persistent emulator state')
                assert not m.events and not m.bus.writes,(label,m.events,m.bus.writes)
            except Exception:
                (folder/'boot-failure.txt').write_bytes(m.tx)
                for i,b in enumerate(m.banks):(folder/f'failed-b{i}.bin').write_bytes(b)
                raise
            record(label+' cold boot',selected_page=page,source_bank_sha256=case['bank_sha256'],persistent_state_unchanged=True,
                fake_identity_bound=bool(binding[:3]==b'EI\1'))
            board=label.split('-')[0] if label.endswith('-complete') else '2512'
            plan=p.read(images/board/'plan.json');path=images/board/'installer-model-only.s19'
            assert p.sha(path.read_bytes())==plan['installer_sha256']
            cells,entry=migration.read_s19(path)
            mem=installer.Memory(banks,set(map(tuple,plan['steps'])),{},commit_records={});mem.require_maintenance_commit=False
            for a,v in cells.items():mem.ram[a]=v
            retry=installer.CPU(memory=mem,pc=entry);mem.cpu=retry;mem.rx.extend(b'Y\r')
            installer.run(retry,lambda:retry.pc==S['MIG_HALT'])
            (folder/'reentry.txt').write_bytes(mem.tx)
            assert b'REFUSED/FAILED' in mem.tx and not b'MIGRATION VERIFIED' in mem.tx
            assert not mem.events and [bytes(b) for b in mem.banks]==banks
            record(label+' original installer re-entry refuses',mutation_events=0,persistent_flash_unchanged=True)
    except Exception:
        (args.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(workspace.resolve()):
            name=path.resolve().relative_to(workspace).as_posix();digest=p.sha(path.read_bytes());sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    report=dict(passed=True,cases=len(checks),saved_image_states=prior['cases'],checks=checks,
        finished_utc=datetime.now(timezone.utc).isoformat(),source_report=str(prior_path),source_report_sha256=checkpoint['report_sha256'],
        test_sha256=p.sha(Path(__file__).read_bytes()),model_sources=sources,serial_disabled=True,board_access=False,
        cold_boot_model_passed=True,original_installer_reentry_refusal_passed=True,
        virtual_rtc='2026-10-17T19:53:15',backward_date_battery_policy_explicitly_verified=True,
        physical_power_cycle_tested=False,electrical_partial_byte_failure_tested=False,
        wear_aware_restoration_qualified=False,additional_transaction_classes_qualified=False,
        route_qualified=False,installation_permitted=False,release_qualified=False,
        scope='Cold boot and unchanged-original-installer refusal for retained emulator images; fake devices only, no restoration')
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(checks),'cold-boot/re-entry checks on',prior['cases'],'saved emulator states; hardware/restore gates remain open')

if __name__=='__main__':main()
