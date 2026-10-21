"""Exact-image RC1 upgrade planning. This module never imports serial or opens a port.

Generation is metadata, not identity: distinct generation-50 images have distinct
profiles. Normal upgrades always select v1g. Restore uses the immediate source
escrow and retains current owner settings/data and monotonically reserved wear.
"""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'engine'))
import runtime as r
import board_plan as legacy


def package(root=HERE):
    root = Path(root).resolve()
    manifest = r.read(root / 'uniform-manifest.json')
    r.require(manifest['schema'] == 1 and manifest['default_target'] == 'v1g', 'Wrong uniform kit')
    r.require(manifest['native_debugging'] is False and manifest['RTC_drift_in_release_qualification'] is False, 'Wrong scope')
    for name, info in manifest['files'].items():
        body = legacy.safe(root, name).read_bytes()
        r.require(len(body) == info['bytes'] and r.sha(body) == info['sha256'], 'Changed kit member: ' + name)
    return manifest


def identify(root, manifest, banks):
    r.clean_journal(banks)
    matches = []
    for name, profile in manifest['profiles'].items():
        if all(banks[row['bank']][row['address']-0x8000:row['address']-0x7000] ==
               legacy.safe(root, row['file']).read_bytes() for row in profile['sectors']):
            matches.append(name)
    r.require(len(matches) == 1, 'Unknown, mixed or corrupt RC1 image; no writes permitted')
    source = matches[0]
    _, _, row, _ = r.clean_journal(banks)
    cfg = row[8:24]
    r.require(int.from_bytes(cfg[9:13], 'little') == manifest['profiles'][source]['generation'], 'Image/journal generation differs')
    r.require(cfg[7] != ord('P') or cfg[8] in (0xA0, 0xB0), 'Unknown monitor preference')
    return source


def derive(root, manifest, banks, target='v1g'):
    source = identify(root, manifest, banks)
    r.require(target in manifest['profiles'], 'Unknown target profile')
    if target == source:
        return source, None, [], banks
    desired = list(map(bytearray, banks))
    for row in manifest['profiles'][target]['sectors']:
        offset = row['address'] - 0x8000
        desired[row['bank']][offset:offset+4096] = legacy.safe(root, row['file']).read_bytes()
    _, _, row, _ = r.clean_journal(banks)
    cfg = row[8:24]
    target_cfg = bytearray(cfg)
    target_cfg[9:13] = manifest['profiles'][target]['generation'].to_bytes(4, 'little')
    target_cfg[14:] = r.migration.config_sum(target_cfg)
    tx, data, expected = r.transaction(banks, list(map(bytes, desired)), bytes(target_cfg), 'uniform RC1 ' + source + ' -> ' + target)
    allowed = {(s['bank'], s['address']) for s in manifest['profiles'][target]['sectors']} | {(3, 0xC000), (3, 0xD000)}
    r.require(all((op['bank'], op['address'] & 0xF000) in allowed for op in tx['operations']), 'Undeclared destination')
    r.require(expected[0] == banks[0], 'B0 changed')
    return source, tx, data, expected


def read_capture(root):
    """Verify archive identity/repeats/RAM without assuming an RC1 journal."""
    import bootstrap_routes
    _,m,_=bootstrap_routes.modules(HERE)
    identity,banks=m.capture(root)
    for name in ('application-ram.bin','restore-application-ram.s19'):
        r.require(name in identity['files'],'Missing application RAM escrow')
    ram=(Path(root)/'application-ram.bin').read_bytes()
    r.require(len(ram) in (0x6300,0x6500) and (Path(root)/'restore-application-ram.s19').read_bytes()==r.migration.s19(dict(enumerate(ram,0x200)),0x200), 'Invalid RAM archive')
    return identity,banks


def prepare(root, capture, out, *, target='v1g', accept_unknown_wear_history=False, history=None, metadata_escrow=None):
    root, capture, out = map(lambda p: Path(p).resolve(), (root, capture, out))
    manifest = package(root)
    identity, banks = read_capture(capture)
    r.require(not out.exists() and not out.is_relative_to(capture), 'Fresh private plan directory required')
    try: identify(root,manifest,banks)
    except ValueError:
        r.require(target=='v1g','Legacy source only supports forward migration to current v1g')
        import bootstrap_routes
        result=bootstrap_routes.prepare(root,capture,out,accept_unknown_wear_history=accept_unknown_wear_history,history=history,metadata_escrow=metadata_escrow)
        verify(root,out)
        return result
    source, tx, data, expected = derive(root, manifest, banks, target)
    if tx is None:
        out.mkdir(parents=True)
        info = dict(action='already-current-no-write', transaction=None, source_sha256=r.hashes(banks), expected_sha256=r.hashes(banks))
    else:
        info = r.compose(root/'engine/template', out, banks, tx, data, expected)
        info['action'] = 'direct-upgrade'
    import shutil
    shutil.copytree(capture, out/'capture')
    info.update(schema=1, board=identity['board'], usb_serial=identity['usb_serial'], source_profile=source,
                target_profile=target, uniform_manifest_sha256=r.sha((root/'uniform-manifest.json').read_bytes()),
                capture_manifest_sha256=r.sha((out/'capture/capture.json').read_bytes()), native_debugging=False,
                RTC_drift_in_release_qualification=False, intermediate_generation49=False)
    legacy.save(out/'plan.json', info)
    (out/'.gitignore').write_text('*\n')
    verify(root, out)
    return info


def verify(root, plan):
    root, plan = Path(root).resolve(), Path(plan).resolve()
    manifest = package(root)
    info = r.read(plan/'plan.json')
    if info.get('action')=='direct-migration':
        import bootstrap_routes
        return bootstrap_routes.verify(root,plan)
    r.require(info['uniform_manifest_sha256'] == r.sha((root/'uniform-manifest.json').read_bytes()), 'Changed kit binding')
    identity, banks = read_capture(plan/'capture')
    r.require(info['capture_manifest_sha256'] == r.sha((plan/'capture/capture.json').read_bytes()), 'Changed capture binding')
    r.require((info['board'], info['usb_serial']) == (identity['board'], identity['usb_serial']), 'Changed board binding')
    source, tx, data, expected = derive(root, manifest, banks, info['target_profile'])
    r.require(info['source_profile'] == source and info['source_sha256'] == r.hashes(banks) and
              info['expected_sha256'] == r.hashes(expected) and info['transaction'] == tx, 'Re-derived plan differs')
    if tx is None:
        r.require(info['action'] == 'already-current-no-write' and not (plan/'installer-model-only.s19').exists(), 'No-write plan contains an installer')
        return info
    r.require(info['action'] == 'direct-upgrade', 'Wrong action')
    r.require(info['installer_sha256'] == r.sha((plan/'installer-model-only.s19').read_bytes()), 'Changed installer hash binding')
    r.require(info['template_manifest_sha256'] == r.sha((root/'engine/template/manifest.json').read_bytes()), 'Changed template binding')
    import tempfile
    with tempfile.TemporaryDirectory(prefix='uniform-rederive-', dir=plan.parent) as tmp:
        check = Path(tmp)/'plan'
        r.compose(root/'engine/template', check, banks, tx, data, expected)
        for path in check.iterdir():
            if path.name != 'plan.json':
                r.require(path.read_bytes() == (plan/path.name).read_bytes(), 'Changed re-derived plan member: ' + path.name)
    return info


def restore(root, original_plan, current_capture, out):
    """Restore the immediate admitted source, never an unrelated old gen49 escrow."""
    original = verify(root, original_plan)
    r.require(original['transaction'] is not None, 'No-write operation needs no rollback')
    identity, _ = legacy.capture(current_capture)
    r.require((identity['board'], identity['usb_serial']) == (original['board'], original['usb_serial']), 'Escrow belongs to another board')
    return prepare(root, current_capture, out, target=original['source_profile'])


def boundary_states(root, plan):
    """Enumerate exact interrupted erase/commit boundaries; no guessed repair."""
    info = verify(root, plan)
    r.require(info['transaction'] is not None, 'No transaction to recover')
    _, banks = legacy.capture(Path(plan)/'capture')
    state = list(map(bytearray, banks))
    yield 'before-reservation', list(map(bytes, state))
    for index, op in enumerate(info['transaction']['operations']):
        bank, offset = op['bank'], op['address']-0x8000
        if index == 0:
            tx=info['transaction']
            body=r.record(bytes.fromhex(tx['source_config']), tx['reserved_counts'], tx['sequence_before']+1)
        else:
            body=bytearray((Path(plan)/f'transfer-{index-1:02d}.bin').read_bytes())
            if op['commit_address'] is not None:
                body[op['commit_address']-op['address']] = (Path(plan)/f'expected-b{bank}.bin').read_bytes()[op['commit_address']-0x8000]
            state[bank][offset:offset+4096] = b'\xff'*4096
            yield f'row-{index}-erased', list(map(bytes, state))
        state[bank][offset:offset+len(body)] = body
        if op['commit_address'] is not None:
            pending = list(map(bytearray,state))
            pending[bank][op['commit_address']-0x8000]=255
            yield f'row-{index}-before-commit', list(map(bytes,pending))
        yield f'row-{index}-complete', list(map(bytes,state))


def recover(root, original_plan, current_capture, out):
    """Forward recovery at exact attested boundaries, with fresh wear reservation.

Arbitrary partial programming and unknown states deliberately refuse. A board
without a working monitor transport needs programmer recovery from private
escrow; this is not a promise of power-loss atomic shared-F replacement.
"""
    root, original_plan, current_capture, out = map(Path,(root,original_plan,current_capture,out))
    original=verify(root,original_plan)
    if original.get('action')=='direct-migration':
        import bootstrap_routes
        kit,m,_=bootstrap_routes.modules(root)
        import recover as legacy_recover
        identity,_=m.capture(current_capture)
        r.require((identity['board'],identity.get('usb_serial'))==(original['board'],original['usb_serial']),'Wrong recovery board/USB')
        return legacy_recover.prepare_recovery('prepare-forward',kit,original_plan,current_capture,out)
    # A known precommit journal row is deliberately not a clean journal yet.
    # Validate every archived byte independently, then admit only a complete
    # exact transaction boundary before using attested_cut. Normal captures
    # continue to require clean_journal through legacy.capture.
    identity=r.read(current_capture/'capture.json')
    r.require(identity['schema']==1 and identity['repeat_verified'] is True, 'Repeated recovery capture required')
    for name,info in identity['files'].items():
        body=legacy.safe(current_capture,name).read_bytes()
        r.require(len(body)==info['bytes'] and r.sha(body)==info['sha256'], 'Changed recovery capture member: '+name)
    current=[]
    for n in range(4):
        r.require(all(f'b{n}{suffix}.bin' in identity['files'] for suffix in ('','-repeat')), 'Missing repeated recovery bank')
        bank=(current_capture/f'b{n}.bin').read_bytes()
        r.require(len(bank)==32768 and bank==(current_capture/f'b{n}-repeat.bin').read_bytes(), 'Recovery bank differs')
        current.append(bank)
    r.require(all(name in identity['files'] for name in ('application-ram.bin','restore-application-ram.s19')), 'Missing recovery RAM escrow')
    ram=(current_capture/'application-ram.bin').read_bytes()
    r.require(len(ram) in (0x6300,0x6500) and (current_capture/'restore-application-ram.s19').read_bytes()==r.migration.s19(dict(enumerate(ram,0x200)),0x200), 'Invalid recovery RAM escrow')
    r.require((identity['board'],identity['usb_serial'])==(original['board'],original['usb_serial']), 'Recovery board/USB mismatch')
    matches=[name for name,banks in boundary_states(root,original_plan) if banks==current]
    r.require(matches, 'Unknown partial state; preserve escrow for diagnosis, never force repair')
    expected=[(original_plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    if current==expected:
        result=prepare(root,current_capture,out,target=original['target_profile'])
        r.require(result['transaction'] is None, 'Completed recovery must not rewrite flash')
        return result
    tx,data,final=r.transaction(current,expected,bytes.fromhex(original['transaction']['target_config']), 'attested uniform forward recovery',attested_cut=True)
    info=r.compose(root/'engine/template',out,current,tx,data,final)
    info.update(schema=1,action='attested-forward-recovery',board=identity['board'],usb_serial=identity['usb_serial'],
                original_plan_sha256=r.sha((original_plan/'plan.json').read_bytes()),matched_boundaries=matches,
                native_debugging=False,RTC_drift_in_release_qualification=False)
    legacy.save(out/'plan.json',info);(out/'.gitignore').write_text('*\n')
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation', choices=('inspect', 'prepare', 'verify', 'restore', 'recover'))
    ap.add_argument('--package', type=Path, default=HERE)
    ap.add_argument('--capture', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--plan', type=Path)
    ap.add_argument('--original-plan', type=Path)
    ap.add_argument('--accept-unknown-wear-history',action='store_true')
    ap.add_argument('--history',type=Path)
    ap.add_argument('--metadata-escrow',type=Path)
    args = ap.parse_args()
    if args.operation == 'verify':
        r.require(args.plan, '--plan required'); info = verify(args.package, args.plan)
    elif args.operation == 'inspect':
        r.require(args.capture, '--capture required'); _, banks = read_capture(args.capture)
        try: source=identify(args.package, package(args.package), banks)
        except ValueError:
            import bootstrap_routes
            source=bootstrap_routes.identify(args.package,banks)
        info = dict(source_profile=source,board_access=False)
    elif args.operation in ('restore','recover'):
        r.require(args.original_plan and args.capture and args.out, '--original-plan, --capture and --out required')
        info = (restore if args.operation=='restore' else recover)(args.package,args.original_plan,args.capture,args.out)
    else:
        r.require(args.capture and args.out, '--capture and --out required')
        info = prepare(args.package, args.capture, args.out,accept_unknown_wear_history=args.accept_unknown_wear_history,history=args.history,metadata_escrow=args.metadata_escrow)
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    try: main()
    except (ValueError, KeyError, OSError) as error: raise SystemExit('REFUSED: ' + str(error))
