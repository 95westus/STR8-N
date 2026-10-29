"""Independent phase-1 and phase-2 checks for the current build."""
import json

from .formats import save, sha


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Baselines:
    def __init__(self, root, source, layout):
        self.meta = read(source/'baseline.json')
        self.phase1_path = root/'tests/baselines/phase1.json'
        self.phase2_path = root/'tests/baselines/phase2.json'
        self.phase2 = read(self.phase2_path)
        if sha(self.phase1_path.read_bytes()) != self.meta['phase1_manifest_sha256']:
            raise ValueError('Phase-1 baseline manifest changed')
        self.phase1 = read(self.phase1_path)['baselines']['rc1-asm-dev']
        if sha((source/'baseline.json').read_bytes()) != self.phase2['source_inventory']['baseline.json']['sha256']:
            raise ValueError('Current baseline metadata differs from phase 2')
        entry = self.phase2['evidence']['direct-source-build']
        evidence = root/entry['file']
        if sha(evidence.read_bytes()) != entry['sha256']:
            raise ValueError('Phase-2 build evidence changed')
        self.evidence = read(evidence)
        self.layout = layout
        self.legacy = (root/'tests/baselines/phase1-legacy-debugger.bin').read_bytes()
        if sha(self.legacy) != self.meta['baseline_expected']['debugger-a000.bin']['sha256']:
            raise ValueError('Phase-1 legacy debugger fixture changed')
        self.uchess = (source/'apps/uchess/uchess-record.bin').read_bytes()
        if sha(self.uchess) != self.meta['uchess_record_sha256']:
            raise ValueError('UCHESS record differs from phase 1')
        self.target = None
        if (source/'target.json').exists():
            selection = read(source/'target.json')
            fixture = root/selection['fixture']
            approved = {'console-edit':'5ccab9fd0ce49063b99411f879efcd1e3eb9a3d1096376c085989fe37c0a265e',
                        'monitor-size-branches':'efb5f2c031be32d268aefb9bc14a16d0b8f7f4bef12974293664de517ec83dad',
                        'fixed-f-size-recovery':'7fcec7cdbf8a9c9aed0766894d0d63a396c48d38e2da7cf90f894a565f2485f1',
                        'fixed-f-flow-size':'c85c4055eac41e5e522f1bc62f2bd354957018e3afc1ccdc25a91e52a55a980e',
                        'rc1-r10p2-current':'0df4a802d618c0df5e658dcf2cd05037f0a892a209abaeac6bca0d595c468945'}
            if selection['candidate'] not in approved or selection['firmware_sha256'] != approved[selection['candidate']]:
                raise ValueError('Unrecognized selected firmware target')
            if sha(fixture.read_bytes()) != selection['fixture_sha256']:
                raise ValueError('Selected target fixture changed')
            self.target = read(fixture)
            if self.target['firmware_sha256'] != selection['firmware_sha256']:
                raise ValueError('Selected firmware and fixture differ')
        expected = self.target if self.target and self.target['candidate']=='rc1-r10p2-current' else self.meta
        for name in ('version','generation','boot_compatibility'):
            if layout[name] != expected[name]:
                raise ValueError('Layout differs from selected baseline: '+name)

    def verify(self, assembly, source_symbols, debugger_symbols, image, debugger):
        if self.target is not None:
            return self.verify_target(assembly, source_symbols, debugger_symbols, image, debugger)
        out, meta = assembly.out, self.meta
        save(out/'symbols.json', assembly.symbols)
        save(out/'source-symbols.json', source_symbols)
        fingerprint = lambda value: sha(json.dumps(value, sort_keys=True, separators=(',',':')).encode())
        symbols = {name: fingerprint(value) == meta['symbol_fingerprints'].get(name)
                   for name, value in assembly.symbols.items()}
        symbols['source-store/source'] = fingerprint(source_symbols) == meta['source_symbol_fingerprint']
        symbols['debugger/debugger'] = fingerprint(debugger_symbols) == meta['debugger_symbol_fingerprint']
        artifacts = {p.relative_to(out/'payload').as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
                     for p in sorted((out/'payload').rglob('*')) if p.is_file()}
        comparison = {name:dict(expected=expected, actual=artifacts.get(name), match=artifacts.get(name)==expected)
                      for name, expected in meta['baseline_expected'].items()}
        checks = {
            'phase1_firmware': sha(image) == self.phase1['existing_firmware_sha256'],
            'phase2_firmware': sha(image) == self.phase2['firmware_sha256'],
            'phase1_symbol_file': sha((out/'symbols.json').read_bytes()) == self.phase1['existing_symbols_sha256'],
            'phase2_payloads': artifacts == self.evidence['artifacts'],
            'phase2_current_debugger': sha(debugger) == self.evidence['current_debugger_sha256'],
            'symbol_inventory': set(assembly.symbols) == set(meta['symbol_fingerprints']),
            'payload_inventory': set(artifacts) == set(meta['baseline_expected']),
            'debugger_in_image': image[0x2000:0x3000] == debugger,
        }
        passed = all(checks.values()) and all(symbols.values()) and all(r['match'] for r in comparison.values())
        report = dict(version=meta['version'], generation=meta['generation'], candidate_id=meta['candidate_id'],
            passed=passed, board_access=False, installation_permitted=False, source_only=False,
            firmware_sha256=sha(image), firmware_matches=checks['phase1_firmware'] and checks['phase2_firmware'],
            baseline_checks=checks, symbol_checks=symbols, symbol_inventory_matches=checks['symbol_inventory'],
            comparison=comparison, artifacts=artifacts, compiled=assembly.compiled, source_files=assembly.sources,
            baseline_manifest_sha256=sha((out/'s/baseline.json').read_bytes()),
            phase1_manifest_sha256=sha(self.phase1_path.read_bytes()), phase2_manifest_sha256=sha(self.phase2_path.read_bytes()),
            current_debugger_component='debugger/debugger-a000.bin', current_debugger_sha256=sha(debugger),
            compatibility_only_artifacts=['payload/debugger-a000.bin'], legacy_debugger_export_sha256=sha(self.legacy),
            binary_inputs=['apps/uchess/uchess-record.bin','tests/baselines/phase1-legacy-debugger.bin (compatibility export only)'],
            deferred=meta['deferred'])
        save(out/'debugger-build.json',dict(generation=meta['generation'],board_access=False,
            debugger_bank=1,debugger_address=0xA000,debugger_code_bytes=debugger_symbols['DEBUG_END']-0xA000,
            sector_bytes=4096,remaining_bytes=0xAFFE-debugger_symbols['DEBUG_END'],
            debugger_symbols=debugger_symbols,firmware_sha256=sha(image),application_ram_end_unchanged=True))
        return report

    def verify_target(self, assembly, source_symbols, debugger_symbols, image, debugger):
        out, target = assembly.out, self.target
        save(out/'symbols.json', assembly.symbols)
        save(out/'source-symbols.json', source_symbols)
        fingerprint = lambda value: sha(json.dumps(value, sort_keys=True, separators=(',',':')).encode())
        artifacts = {p.relative_to(out/'payload').as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
                     for p in sorted((out/'payload').rglob('*')) if p.is_file()}
        checks = dict(firmware=sha(image)==target['firmware_sha256'],
            payloads=artifacts==target['artifacts'],
            symbols={k:fingerprint(v) for k,v in assembly.symbols.items()}==target['symbol_fingerprints'],
            source_symbols=fingerprint(source_symbols)==target['source_symbol_fingerprint'],
            debugger_symbols=fingerprint(debugger_symbols)==target['debugger_symbol_fingerprint'],
            debugger_in_image=image[0x2000:0x3000]==debugger)
        report = dict(passed=all(checks.values()),candidate_id=target['candidate'],
            version=self.layout['version'],generation=self.layout['generation'],board_access=False,
            installation_permitted=False,firmware_sha256=sha(image),firmware_matches=checks['firmware'],
            target_checks=checks,artifacts=artifacts,compiled=assembly.compiled,source_files=assembly.sources,
            historical_phase1_and_phase2_retained=True,current_debugger_sha256=sha(debugger),
            compatibility_only_artifacts=['payload/debugger-a000.bin'])
        save(out/'debugger-build.json',dict(debugger_symbols=debugger_symbols,board_access=False,
            debugger_code_bytes=debugger_symbols['DEBUG_END']-0xA000,firmware_sha256=sha(image)))
        return report
