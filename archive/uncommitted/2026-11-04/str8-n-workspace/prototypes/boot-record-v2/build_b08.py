"""Offline b08: separate selection output and allow guarded recovery bank jumps.

Reuse the unused old chooser string for the recovery digit dispatcher. All
existing private entry addresses, RAM tools, worker and vectors stay fixed.
"""
import argparse
import json
from pathlib import Path
import sys

import build_b07 as previous

HERE, ROOT = previous.HERE, previous.ROOT
RECOVERY = 'Recovery L/R/D/V A/B 0-3 C1/2/3'


def b08_source(source):
    source = previous.b07_source(source)
    source = previous.replace_once(source,
        '        LDA #3\n        STA BR_TICKS\nBR_COUNTDOWN:',
        '        LDA #6\n        STA BR_TICKS\nBR_COUNTDOWN:')
    old = 'BR_CHOICES: DB 13,10,"OFFLINE PROTOTYPE S A B 0 1 2 3",13,10,0'
    assert source.count('BR_CHOICES') == 1, 'Old chooser must have no callers'
    # 35 instruction bytes plus one pad byte replace the unused 36-byte text.
    source = previous.replace_once(source, old, '''BR_CHOICES:
BOOT_B08_READ_LINE:
        JSR BOOT_READ_LINE
        BCC B08_READ_DONE
        LDA V2_LINE+1
        BNE B08_READ_VALID
        LDA V2_LINE
        CMP #'0'
        BCC B08_READ_VALID
        CMP #'4'
        BCS B08_READ_VALID
        PHA
        JSR BOOT_SELECT
        PLA
        TAX
        PLA
        PLA
        TXA
        JMP BR_DISPATCH
B08_READ_VALID: SEC
B08_READ_DONE: RTS
        DB $EA''')
    start, end = source.index('BOOT_MENU:'), source.index('BR_SYNTAX:')
    menu = previous.replace_once(source[start:end], 'JSR BOOT_READ_LINE', 'JSR BOOT_B08_READ_LINE')
    source = source[:start] + menu + source[end:]
    start, end = source.index('BOOT_RECOVERY:'), source.index('BOOT_MENU:')
    recovery = previous.replace_once(source[start:end], 'JSR V2W_RX_RESET', 'JSR B08_RECOVERY_LINE')
    source = source[:start] + recovery + source[end:]
    start, end = source.index('BR_MASK_READY:'), source.index('BR_A:')
    handoff = previous.replace_once(source[start:end], 'JMP V2W_EXECUTE', 'JMP B08_BANK_LINE')
    source = source[:start] + handoff + source[end:]
    old_text = 'RAM recovery L/R/D/V A/B C1/2/3'
    assert len(old_text) == len(RECOVERY)
    source = previous.replace_once(source, 'DB "' + old_text + '"', 'DB "' + RECOVERY + '"')
    return source + '''
; Twelve append-only bytes. Existing monitor banner already starts with CRLF.
B08_RECOVERY_LINE:
        JSR V2W_RX_RESET
        JMP V2V_RAM_NEWLINE
B08_BANK_LINE:
        JSR V2V_RAM_NEWLINE
        JMP V2W_EXECUTE
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=ROOT / 'BUILD/rc1-r10p2-g0034')
    parser.add_argument('--previous', type=Path, default=ROOT / 'BUILD/pr04-b07-startup')
    args = parser.parse_args(); out = args.out.resolve()
    original = HERE / 'build.py'; source = original.read_text()
    source = previous.replace_once(source, 'generation=0x80000006 if args.startup_drain',
                                   'generation=0x80000008 if args.startup_drain')
    source = previous.replace_once(source, "banner=b'2.0proto b06' if args.startup_drain",
                                   "banner=b'2.0proto b08' if args.startup_drain")
    source = previous.replace_once(source,
        "    if args.startup_drain:source+=(HERE/'boot-startup.inc').read_text()+'\\n'",
        "    if args.startup_drain:source=b08_source(source+(HERE/'boot-startup.inc').read_text()+'\\n')")
    source = previous.replace_once(source, "drain_message='Consuming input'", "drain_message='WAIT...'")
    source = previous.replace_once(source, "display='3 2 1 0'", "display='Boot : 6 5 4 3 2 1 0'")
    source = previous.replace_once(source, 'countdown_seconds=3', 'countdown_seconds=6')
    source = previous.replace_once(source, 'seconds_at_8MHz=3', 'seconds_at_8MHz=6')
    source = previous.replace_once(source, 'Fixed three seconds; saved target honored',
                                   'Fixed six seconds; saved target honored')
    namespace = dict(__file__=str(original), __name__='b08_frozen_builder', b08_source=b08_source)
    exec(compile(source, str(original), 'exec'), namespace)
    old_argv = sys.argv
    try:
        sys.argv = [str(original), '--base', str(args.base.resolve()), '--out', str(out),
                    '--bench-core', '--startup-drain']
        namespace['main']()
    finally:
        sys.argv = old_argv
    old = json.loads((args.previous / 'symbols.json').read_bytes())
    new = json.loads((out / 'symbols.json').read_bytes())
    for module, labels in old.items():
        for label, value in labels.items():
            if label not in ('BOOT_END', '_END_CODE'):
                assert new[module].get(label) == value, (module, label)
    report_path = out / 'prototype-report.json'
    report = json.loads(report_path.read_bytes())
    assert report['f']['bytes'] == 4047 and report['f']['free'] == 17
    assert new['core/str8n-v2-boot']['B08_READ_DONE'] + 2 == old['core/str8n-v2-boot']['BR_RECOVERY']
    unchanged = {}
    for name in ('ram-config-offline.bin', 'ram-installer-offline.bin', 'ram-installer-offline.rlp1'):
        assert (out / 'payload' / name).read_bytes() == (args.previous / 'payload' / name).read_bytes()
        unchanged[name] = previous.sha(out / 'payload' / name)
    for label, count in (('BOOT_WORKER_IMAGE', report['f']['worker_bytes']),
                         ('BOOT_VECTOR_IMAGE', report['f']['vectors_bytes'])):
        offset = old['core/str8n-v2-boot'][label] - 0xf000
        assert (out / 'payload/f-offline-component.bin').read_bytes()[offset:offset+count] == (
            args.previous / 'payload/f-offline-component.bin').read_bytes()[offset:offset+count]
    report['startup_sequence'].update(drain_message_bytes_hex=b'\r\nWAIT...\r\n'.hex(),
        choice_labels=previous.CHOICES, countdown_prefix='Boot : ')
    report['b08_selection_patch'] = dict(previous_banner='2.0proto b07',
        frozen_builder_sha256=previous.sha(original), builder_sha256=previous.sha(Path(__file__)),
        previous_symbols_sha256=previous.sha(args.previous / 'symbols.json'),
        existing_private_entry_addresses_unchanged=True, reclaimed_unused_chooser_bytes=36,
        recovery_dispatch_bytes=35, internal_padding_bytes=1, appended_bytes=12,
        recovery_banner=RECOVERY, recovery_bank_commands='0/1/2/3, exact one-character lines',
        countdown_seconds=6, countdown_display='Boot : 6 5 4 3 2 1 0',
        refresh_boot_record_before_recovery_bank_handoff=True,
        reused_bank_validation=True, binary_handlers_unchanged=True,
        unchanged_RAM_tools_sha256=unchanged, board_access=False)
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print('PASS b08: F4047 +32 reserved,17 free; existing entries and RAM tools unchanged', flush=True)


if __name__ == '__main__':
    main()
