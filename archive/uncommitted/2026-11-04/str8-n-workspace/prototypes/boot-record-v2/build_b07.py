"""Build the b07 display patch through the unchanged, qualified b06 builder.

All prior PR04 entry addresses remain fixed. New text and a tail-call print
wrapper occupy the remaining F space; transfer and journal code is unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHOICES = 'S=Recovery  A/B=Monitor  0-3=Bank'


def replace_once(text, before, after):
    assert text.count(before) == 1, before
    return text.replace(before, after, 1)


def b07_source(source):
    source = replace_once(source,
        '        LDX #<BR_CHOICES\n        LDY #>BR_CHOICES\n        JSR BOOT_PRINT',
        '        LDX #<B07_CHOICES\n        LDY #>B07_CHOICES\n        JSR B07_PRINT_CHOICES')
    source = replace_once(source,
        'BOOT_CONSUMING: DB "Consuming input",13,10,0',
        'BOOT_CONSUMING: DB 13,10,"WAIT...",13,10,0')
    return source + '''
; b07 append-only display code: keep every prior PR04 private call fixed.
B07_PRINT_CHOICES:
        JSR BOOT_PRINT
        LDX #<B07_PREFIX
        LDY #>B07_PREFIX
        JMP BOOT_PRINT
B07_PREFIX: DB "Boot : ",0
B07_CHOICES: DB "S=Recovery  A/B=Monitor  0-3=Bank",13,10,0
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=ROOT / 'BUILD/rc1-r10p2-g0034')
    parser.add_argument('--previous', type=Path, default=ROOT / 'BUILD/pr04-b06-startup-r2')
    args = parser.parse_args()
    out = args.out.resolve()
    original = HERE / 'build.py'
    source = original.read_text()
    source = replace_once(source, 'generation=0x80000006 if args.startup_drain',
                                  'generation=0x80000007 if args.startup_drain')
    source = replace_once(source, "banner=b'2.0proto b06' if args.startup_drain",
                                  "banner=b'2.0proto b07' if args.startup_drain")
    source = replace_once(source,
        "    if args.startup_drain:source+=(HERE/'boot-startup.inc').read_text()+'\\n'",
        "    if args.startup_drain:source=b07_source(source+(HERE/'boot-startup.inc').read_text()+'\\n')")
    source = replace_once(source, "drain_message='Consuming input'", "drain_message='WAIT...'")
    source = replace_once(source, "display='3 2 1 0'", "display='Boot : 3 2 1 0'")
    namespace = dict(__file__=str(original), __name__='b07_frozen_builder', b07_source=b07_source)
    exec(compile(source, str(original), 'exec'), namespace)
    old_argv = sys.argv
    try:
        sys.argv = [str(original), '--base', str(args.base.resolve()), '--out', str(out),
                    '--bench-core', '--startup-drain']
        namespace['main']()
    finally:
        sys.argv = old_argv
    report_path = out / 'prototype-report.json'
    report = json.loads(report_path.read_text())
    report['startup_sequence'].update(drain_message_bytes_hex=b'\r\nWAIT...\r\n'.hex(),
                                      choice_labels=CHOICES, countdown_prefix='Boot : ')
    old = json.loads((args.previous / 'symbols.json').read_text())
    new = json.loads((out / 'symbols.json').read_text())
    moved = {module: {label: [value, new[module].get(label)]
                      for label, value in labels.items()
                      if label not in ('BOOT_END', '_END_CODE') and new[module].get(label) != value}
             for module, labels in old.items()}
    moved = {module: labels for module, labels in moved.items() if labels}
    assert not moved, moved
    unchanged = {}
    for name in ('ram-config-offline.bin', 'ram-installer-offline.bin', 'ram-installer-offline.rlp1'):
        assert (out / 'payload' / name).read_bytes() == (args.previous / 'payload' / name).read_bytes()
        unchanged[name] = sha(out / 'payload' / name)
    for label, count in (('BOOT_WORKER_IMAGE', report['f']['worker_bytes']),
                         ('BOOT_VECTOR_IMAGE', report['f']['vectors_bytes'])):
        offset = old['core/str8n-v2-boot'][label] - 0xf000
        before = (args.previous / 'payload/f-offline-component.bin').read_bytes()[offset:offset+count]
        after = (out / 'payload/f-offline-component.bin').read_bytes()[offset:offset+count]
        assert before == after
        unchanged[label] = hashlib.sha256(after).hexdigest()
    report['b07_display_patch'] = dict(previous_banner='2.0proto b06',
        previous_symbols_sha256=sha(args.previous / 'symbols.json'),
        frozen_builder_sha256=sha(original), display_builder_sha256=sha(Path(__file__)),
        existing_private_entries_unchanged=True, changed_existing_symbols=['BOOT_END', '_END_CODE'],
        unchanged_runtime_sha256=unchanged,
        patch='Existing chooser pointer and JSR operands only; appended display wrapper/text; shorter final WAIT string')
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print('PASS b07 PR04 addresses and unchanged RAM tools/worker/vectors', flush=True)


if __name__ == '__main__':
    main()
