"""b10: unlimited pre-frame wait, Ctrl-C cancellation, bounded raw frame RX."""
import json
from pathlib import Path
import sys
import build_b08 as frozen


def b10_source(source):
    source = frozen.b08_source(source)
    source = frozen.previous.replace_once(source,
        'BOOT_STARTUP:\n        LDY #30', 'BOOT_STARTUP:\n        LDY #20')
    source = frozen.previous.replace_once(source,
        'RL_HEADER_BYTE:\n        JSR RL_GET', 'RL_HEADER_BYTE:\n        JSR B10_HEADER_GET')
    first, last = source.index('RL_GET:\n'), source.index('RL_ADVANCE:\n')
    # The old 30-byte timed reader contains three unnecessary long branches.
    # Compact them to reclaim nine bytes, then spend six on the header dispatch
    # and three NOPs on the empty poll path. The 65536-poll timeout remains.
    source = source[:first]+'''RL_GET:
        PHX
        PHY
        LDX #0
        LDY #0
RL_POLL:
        JSR V2W_RAW_POLL
        BCS RL_GOT
        NOP
        NOP
        NOP
        DEX
        BNE RL_POLL
        DEY
        BNE RL_POLL
        CLC
RL_GOT: PLY
        PLX
        RTS
B10_HEADER_GET:
        TYA
        BNE RL_GET
        JMP B10_WAIT_FIRST
''' + source[last:]
    return source+'''
; RAW_POLL preserves X/Y. Only header byte zero admits Ctrl-C as cancellation.
; Remaining header and all payload bytes use RL_GET without control decoding.
B10_WAIT_FIRST:
        JSR V2W_RAW_POLL
        BCC B10_WAIT_FIRST
        CMP #3
        BEQ B10_CANCEL_FIRST
        SEC
        RTS
B10_CANCEL_FIRST:
        PLA
        PLA
        JMP BOOT_MENU
'''


def main():
    source = Path(frozen.__file__).read_text()
    for before, after in (
        ('0x80000008','0x8000000A'),
        ('2.0proto b08','2.0proto b10'),
        ('BUILD/pr04-b07-startup','BUILD/pr04-b09-usb2'),
        ('b08_source(source+(HERE/','b10_source(source+(HERE/'),
        ('b08_source=b08_source','b10_source=b10_source'),
        ("source = original.read_text()", "source = original.read_text()\n    source = previous.replace_once(source, 'USB_wait_seconds=3', 'USB_wait_seconds=2')"),
        ("('BOOT_END', '_END_CODE')", "('BOOT_END', '_END_CODE', 'RL_GOT', 'P_LONG_63', 'P_LONG_64', 'P_LONG_65')"),
        ("report['f']['bytes'] == 4047 and report['f']['free'] == 17", "report['f']['bytes'] == 4063 and report['f']['free'] == 1"),
        ("previous_banner='2.0proto b07'", "previous_banner='2.0proto b09'"),
    ):
        assert before in source, before
        source = source.replace(before,after)
    namespace = dict(__file__=__file__, __name__='b10_frozen_builder',b10_source=b10_source)
    exec(compile(source,str(Path(frozen.__file__)),'exec'),namespace)
    namespace['main']()
    out = Path(sys.argv[sys.argv.index('--out')+1]).resolve()
    path = out/'prototype-report.json'; report = json.loads(path.read_bytes())
    patch = report.pop('b08_selection_patch')
    patch.update(existing_private_entry_addresses_unchanged=False,
        internal_symbol_exceptions=['RL_GOT','P_LONG_63','P_LONG_64','P_LONG_65'],
        public_ABI_and_external_private_entries_unchanged=True,
        binary_handlers_unchanged=False, payload_bytes_not_interpreted_as_controls=True,
        initial_frame_wait='indefinite; initiating-console Ctrl-C returns to REC without REFUSED',
        subsequent_frame_wait='bounded 65536 empty polls per byte; no control decoding',
        reclaimed_timed_RX_bytes=9, header_dispatch_bytes=6, empty_poll_NOPS=3,
        appended_first_byte_wait_bytes=16, USB_wait_seconds=2)
    report['b10_receive_patch'] = patch
    old = json.loads((frozen.ROOT/'BUILD/pr04-b09-usb2/symbols.json').read_bytes())['core/str8n-v2-boot']
    new = json.loads((out/'symbols.json').read_bytes())['core/str8n-v2-boot']
    for label in ('RL_GET','RL_POLL','RL_ADVANCE','RL_BODY','RL_HEADER_BYTE','J_CRC_INIT','J_CRC_BYTE','BOOT_STARTUP'):
        assert new[label] == old[label],label
    assert new['B10_HEADER_GET']+6 == new['RL_ADVANCE']
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS b10: F4063 +32 reserved,1 free; MON3830 +128 header,138 free',flush=True)


if __name__ == '__main__':
    main()
