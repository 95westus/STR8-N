"""Host admission checks for the preserving unified-board workflow; no ports."""
import json
from pathlib import Path
import qualify_unified_boards as p


def main():
    profiles, symbols, artifacts = p.admit()
    checks = []
    def passed(name):
        checks.append(dict(passed=True, case=name))
    for board, directory, prefix in (
        ('2512', p.ROOT/'output/qualification/FLASH-LED-2512-20261027', 'final-full-flash-r1'),
        ('2609', p.ROOT/'output/qualification/2609-b15-onboarding-20261027T212009Z/step19-CONFIG-save-restore-live', 'final-r1')):
        banks = [(directory/f'{prefix}-b{n}.bin').read_bytes() for n in range(4)]
        profile = profiles['boards'][board]
        row = p.verify_components(banks, profile)
        text = p.settings_text(row)
        assert (b'DEFAULT=B' if board == '2512' else b'DEFAULT=S') in text
        assert (b'B0 ON  ENTRY=8000' if board == '2512' else b'B0 OFF ENTRY=8000') in text
        passed(board+' exact installed component and settings admission')
        for target, name in profile['installed_components'].items():
            bank, sector = int(target[1]), int(target[3], 16)
            corrupt = list(map(bytearray, banks))
            corrupt[bank][(sector-8)*4096+0x150] ^= 1
            try:
                p.verify_components(list(map(bytes, corrupt)), profile)
            except AssertionError:
                passed(board+' corrupt '+target+' rejected')
            else:
                raise AssertionError('Corrupt installed component admitted')
        for key in ('monitor-'+profile['monitor_flavor'].lower()+'-a0',
                    'monitor-'+profile['monitor_flavor'].lower()+'-b0'):
            assert symbols[key]['V2_PROMPT'] in (0xa160, 0xb160)
        passed(board+' admitted monitor prompt destinations')
    assert p.USB['2512'] != p.USB['2609'] and len(p.USB) == 2
    assert p.APP_COMMANDS['CONFIG'] == ('?', 'B', 'C', 'W')
    assert all(not c.startswith(('F ', 'I ', 'B ', 'C ')) for c in p.APP_COMMANDS['MAINT'])
    passed('unique board identities and inspection-only application commands')
    for name in ('STR8N-F-CONFIG-RAM.bin', 'STR8N-F-MAINT-RO-RAM.bin', 'STR8N-F-READBACK-RAM.bin'):
        assert artifacts[name]['address'] == artifacts[name]['entry'] == '0200'
    assert symbols['maint']['MA_IMM_END'] < 0x2000
    passed('fixed shared RAM tool load ranges')
    for name in ('CONFIG-?.txt', 'MAINT-0.txt', 'C1-before-tool.bin.txt'):
        assert not set(p.log_name(name)) & set('<>:"/\\|?*')
    assert p.log_name('CONFIG-?.txt') == 'CONFIG-_.txt'
    passed('Windows-safe command log filenames')
    result = dict(passed=True, hardware=False, serial_access=False, checks=len(checks), cases=checks,
                  helper_sha256=p.io.sha(Path(p.__file__).read_bytes()),
                  checker_sha256=p.io.sha(Path(__file__).read_bytes()))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
