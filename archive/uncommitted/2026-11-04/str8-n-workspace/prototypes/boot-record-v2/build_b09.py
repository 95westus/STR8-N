"""Offline b09: reduce b08's silent USB wait from three to two seconds."""
import json
from pathlib import Path

import build_b08 as previous


def b09_source(source):
    return previous.previous.replace_once(previous.b08_source(source),
        'BOOT_STARTUP:\n        LDY #30', 'BOOT_STARTUP:\n        LDY #20')


def main():
    source = Path(previous.__file__).read_text()
    replacements = (
        ('0x80000008', '0x80000009'),
        ('2.0proto b08', '2.0proto b09'),
        ('BUILD/pr04-b07-startup', 'BUILD/pr04-b08-six-second'),
        ('b08_source(source+(HERE/', 'b09_source(source+(HERE/'),
        ('b08_source=b08_source', 'b09_source=b09_source'),
        ('previous_banner=\'2.0proto b07\'', 'previous_banner=\'2.0proto b08\''),
        ("source = original.read_text()", "source = original.read_text()\n    source = previous.replace_once(source, 'USB_wait_seconds=3', 'USB_wait_seconds=2')"),
    )
    for before, after in replacements:
        assert before in source, before
        source = source.replace(before, after)
    namespace = dict(__file__=__file__, __name__='b09_frozen_builder', b09_source=b09_source)
    exec(compile(source, str(Path(previous.__file__)), 'exec'), namespace)
    namespace['main']()
    # Locate the output selected by the inherited CLI, and bind the exact
    # single instruction-operand change against the qualified b08 F sector.
    import sys
    out = Path(sys.argv[sys.argv.index('--out')+1]).resolve()
    report_path = out/'prototype-report.json'
    report = json.loads(report_path.read_bytes())
    report['b09_startup_patch'] = report.pop('b08_selection_patch')
    report['b09_startup_patch']['USB_wait_seconds'] = 2
    before = previous.ROOT/'BUILD/pr04-b08-six-second'
    old = (before/'payload/f-offline-component.bin').read_bytes()
    new = (out/'payload/f-offline-component.bin').read_bytes()
    differences = [i for i,(a,b) in enumerate(zip(old,new)) if a != b]
    symbols = json.loads((out/'symbols.json').read_bytes())['core/str8n-v2-boot']
    operand = symbols['BOOT_STARTUP']+1-0xf000
    assert differences == [operand], differences
    assert old[operand] == 30 and new[operand] == 20
    assert report['startup_sequence']['USB_wait_seconds'] == 2
    report['b09_startup_patch']['F_changes_from_b08'] = [dict(address=f'{operand+0xf000:04X}', old=30, new=20)]
    report['b09_startup_patch']['all_other_F_bytes_identical_to_b08'] = True
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print('PASS b09: only USB wait operand changed in F; two seconds, drain/countdown unchanged', flush=True)


if __name__ == '__main__':
    main()
