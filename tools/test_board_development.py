"""Rehearse the Phase-12 source/edit/debug/host-handoff workflow offline."""
import argparse
import json
import os
from pathlib import Path
import shutil

from test_resident_contract import ATTEMPTS, sha
from test_resident_batch import files, refused
import board_development as workflow
import version_cached_candidate as candidate

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def listing(lane):
    return ('LIST\r\n' + ''.join(f'{i * 10} {line}\r\n'
             for i, line in enumerate(lane['lines'], 1)) + 'ASM> ').encode('ascii')


def export(lane):
    def record(kind, address, body):
        data = bytes([len(body) + 3]) + address.to_bytes(2, 'big') + body
        return 'S' + kind + (data + bytes([255 - (sum(data) & 255)])).hex().upper()
    rows = [record('1', lane['origin'] + i, lane['expected'][i:i + 16])
            for i in range(0, len(lane['expected']), 16)]
    rows.append(record('9', lane['origin'], b''))
    return ('S19\r\n' + '\r\n'.join(rows) + '\r\nASM> ').encode('ascii')


def host_checks(build, kitpath, kit, out):
    checks = []
    repeat = out / 'repeated-kit'
    workflow.build_kit(build, repeat)
    assert files(kitpath) == files(repeat)
    checks.append('deterministic-complete-kit')
    refused(lambda: workflow.build_kit(build, repeat))
    assert files(kitpath) == files(repeat)
    checks.append('existing-kit-refused-unchanged')
    scratch = out / 'tampered-kit'
    shutil.copytree(kitpath, scratch)
    for relative in ('hello-a/source.asm', 'hello-b/expected.bin',
                     'version-fast/records.bin', 'version-control/symbols.json',
                     'session-commands.json'):
        path = scratch / relative
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        refused(lambda: workflow.load_kit(scratch))
        path.write_bytes(raw)
        checks.append('tampered-kit-' + relative + '-refused')
    (scratch / 'unexpected.txt').write_bytes(b'unexpected')
    refused(lambda: workflow.load_kit(scratch))
    checks.append('extra-kit-file-refused')
    inputs = out / 'inputs'
    inputs.mkdir()
    pairs = {}
    for name, lane in kit['lanes'].items():
        lp, sp = inputs / (name + '.list.txt'), inputs / (name + '.s19.txt')
        lp.write_bytes(listing(lane))
        sp.write_bytes(export(lane))
        pairs[name] = (lp, sp)
        destination = out / ('known-' + name)
        workflow.collect(kitpath, name, lp, sp, destination, expect_name=name)
        before = files(destination)
        refused(lambda: workflow.collect(kitpath, name, lp, sp, destination, expect_name=name))
        assert files(destination) == before
        checks.append('known-source-and-binary-' + name + '-roundtrip-and-no-overwrite')
    lp, sp = pairs['hello-b']
    cross = workflow.collect(kitpath, 'hello-a', lp, sp, out / 'known-a-to-b', expect_name='hello-b')
    assert cross['source_complete_verified'] and cross['source_binary_equivalence']
    assert (out / 'known-a-to-b/source.diff').read_text(encoding='utf-8')
    checks.append('documented-base-a-expect-b-verified-edit-with-diff')
    draft = out / 'edited-draft'
    result = workflow.collect(kitpath, 'hello-a', lp, sp, draft)
    assert result['source_complete_verified'] is False
    assert result['source_binary_equivalence'] is False and result['review_required']
    assert (draft / 'source.diff').read_text(encoding='utf-8')
    checks.append('edited-source-retained-as-review-draft-with-diff')
    bigger = dict(kit['lanes']['hello-b'])
    bigger['lines'] = bigger['lines'][:-2] + ['NOP'] + bigger['lines'][-2:]
    bigger['expected'] = bigger['expected'][:-3] + b'\xea' + bigger['expected'][-3:]
    longer_l, longer_s = inputs / 'larger.list.txt', inputs / 'larger.s19.txt'
    longer_l.write_bytes(listing(bigger))
    longer_s.write_bytes(export(bigger))
    result = workflow.collect(kitpath, 'hello-a', longer_l, longer_s, out / 'larger-draft')
    assert not result['source_complete_verified'] and not result['source_binary_equivalence']
    assert result['review_required']
    assert (out / 'larger-draft/resident.bin').read_bytes() == bigger['expected']
    checks.append('size-changing-exploratory-edit-retained-as-unverified-draft')
    original_inputs = files(inputs)
    good_list, good_s19 = pairs['hello-a'][0].read_bytes(), pairs['hello-a'][1].read_bytes()
    rows = good_list.split(b'\r\n')
    corruptions = {
        'truncated-list-with-prompt': (b'\r\n'.join(rows[:5] + [b'ASM> ']), good_s19),
        'missing-list-prompt': (good_list.removesuffix(b'ASM> '), good_s19),
        'duplicate-source-record': (good_list.replace(b'20 PUTC', b'10 PUTC'), good_s19),
        'unsorted-source-record': (good_list.replace(b'20 PUTC', b'5 PUTC'), good_s19),
        'zero-source-record': (good_list.replace(b'10 BASE', b'0 BASE'), good_s19),
        'out-of-range-source-record': (good_list.replace(b'10 BASE', b'65536 BASE'), good_s19),
        'oversize-source-line': (good_list.replace(b'BASE EQU $0200', b';' + b'X' * 120), good_s19),
        'non-ascii-source': (good_list.replace(b'BASE', b'B\xffSE'), good_s19),
        'mixed-list-log': (good_list.replace(b'ASM> ', b'unsolicited output\r\nASM> '), good_s19),
        'missing-s19-prompt': (good_list, good_s19.removesuffix(b'ASM> ')),
        'bad-s19-checksum': (good_list, good_s19.replace(b'78D8', b'79D8', 1)),
        'missing-s9': (good_list, b'\r\n'.join(good_s19.split(b'\r\n')[:-2]) + b'\r\nASM> '),
        'duplicate-s1': (good_list, good_s19.replace(b'S19\r\n', b'S19\r\n' + good_s19.split(b'\r\n')[1] + b'\r\n')),
        'mismatched-known-source-body': (good_list, pairs['hello-b'][1].read_bytes()),
        'mismatched-known-source-records': (pairs['hello-b'][0].read_bytes(), good_s19),
        'wrong-origin-valid-checksum': (good_list, export({**kit['lanes']['hello-a'], 'origin': 0x300})),
        'wrong-s9-valid-checksum': (good_list, good_s19.replace(b'S9030200FA', b'S9030201F9')),
    }
    for name, (lr, sr) in corruptions.items():
        bad_l, bad_s = out / 'bad.list.txt', out / 'bad.s19.txt'
        bad_l.write_bytes(lr)
        bad_s.write_bytes(sr)
        destination = out / ('refused-' + name)
        refused(lambda: workflow.collect(kitpath, 'hello-a', bad_l, bad_s, destination, expect_name='hello-a'))
        assert not destination.exists(), name
        checks.append(name + '-refused-before-output')
    assert original_inputs == files(inputs)
    for protected in (ROOT / 'src/current/new-phase12', ROOT / 'tools/new-phase12',
                      ROOT / 'tests/baselines/new-phase12', build / 'new-phase12'):
        refused(lambda: workflow.build_kit(build, protected))
        assert not protected.exists()
    checks.append('source-tools-baselines-build-output-protected')
    assert not ATTEMPTS
    result = dict(passed=True, mode='host', check_count=len(checks), checks=checks,
                  board_access=False, serial_ports_opened=0, network_attempts=0,
                  attempts=ATTEMPTS)
    save(out / 'report.json', result)
    print('PASS host:', len(checks), 'workflow checks', flush=True)
    return result


def runtime_checks(build, kitpath, kit, out, cpus):
    os.environ['STR8_SOURCE_BUILD'] = str(build)
    from test_rc1_source_store import Harness
    from test_board_development_runtime import rehearsal
    rows = []
    for cpu in cpus:
        for slot in ('A', 'B'):
            for edu in (False, True):
                profile = f'{cpu}-{slot}-' + ('edu' if edu else 'bare')
                dest = out / profile
                result = rehearsal(Harness, cpu, slot, edu, kit, dest)
                captures = {}
                for name in kit['lanes']:
                    lp, sp = dest / (name + '.list.txt'), dest / (name + '.s19.txt')
                    receipt = workflow.collect(kitpath, name, lp, sp, dest / ('host-' + name), expect_name=name)
                    assert receipt['source_complete_verified'] and receipt['source_binary_equivalence']
                    captures[name] = dict(list_sha256=sha(lp.read_bytes()), s19_sha256=sha(sp.read_bytes()),
                                          host_capture_verified=True)
                row = dict(cpu=cpu, slot=slot, edu=edu, passed=True, rehearsal=result, captures=captures)
                rows.append(row)
                save(out / 'progress.json', dict(cases=rows, attempts=ATTEMPTS))
                print('PASS', profile, 'editor/debugger/VERSION/host roundtrip', flush=True)
    assert not ATTEMPTS
    result = dict(passed=True, mode='runtime', profiles=len(rows), cases=rows,
                  board_access=False, serial_ports_opened=0, network_attempts=0,
                  hardware_qualified=False, attempts=ATTEMPTS,
                  scope='Actual linked editor, assembler, monitor and debugger instructions in the existing CPU model; no physical board claim')
    save(out / 'report.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'kit', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=('host', 'runtime'), required=True)
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), action='append')
    args = parser.parse_args()
    build, kitpath, out = args.build.resolve(), args.kit.resolve(), args.out.resolve()
    candidate.validate_out(build, out)
    assert not (out.is_relative_to(kitpath) or kitpath.is_relative_to(out))
    kit = workflow.load_kit(kitpath)
    out.mkdir(parents=True)
    if args.mode == 'host':
        host_checks(build, kitpath, kit, out)
    else:
        runtime_checks(build, kitpath, kit, out, args.cpu or ('65c02', '65c816-e'))


if __name__ == '__main__':
    main()
