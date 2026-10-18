"""Build a VERSION command in existing reserved shared firmware space."""
import hashlib
import json
import shutil
from pathlib import Path
from beta4_migration import crc, s19
from build_v2_spi_resident import assemble
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'BUILD/v2-clock-summary'
OUT = ROOT/'BUILD/v2-version'
sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    shutil.copytree(BASE, OUT, dirs_exist_ok=True)
    for p in OUT.glob('*test-results.json'):
        p.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    meta = json.loads((BASE/'build.json').read_text())
    source = OUT/'version/source'
    source.mkdir(parents=True, exist_ok=True)
    boot = meta['boot']
    names = ('BOOT_ACTIVE', 'BOOT_DEST', 'BOOT_BEST')
    eq = {'BOOT_ACTIVE':0x7D30, 'BOOT_DEST':0x7D31, 'BOOT_BEST':0x7DF5}
    eq.update({n:boot[n] for n in ('BOOT_SLOT_CHECK', 'BOOT_SELECT', 'BOOT_CHOICE_SLOT')})
    (source/'version-links.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n, v in eq.items()))
    local = (ROOT/'tools/v2-rtc/local-time.inc').read_text()
    crc_code = local[local.index('TZ_CRC:\n'):local.index('TZ_ABS:\n')]
    text = crc_code+(ROOT/'tools/v2-rtc/board-name.inc').read_text()
    (source/'version-board.inc').write_text(long_branches(text).replace('BM_LONG_', 'VB_LONG_'))
    (source/'version.asm').write_text(long_branches((ROOT/'tools/v2-spi/version.asm').read_text()).replace('BM_LONG_', 'VER_LONG_'))
    body, symbols, _ = assemble(source, 'version', 0x6E00, 'APP_END', 0x6E07)
    assert len(body) <= 2046
    asset = body+b'\xff'*(2046-len(body))
    asset += crc(asset).to_bytes(2, 'big')
    assert crc(asset) == 0
    (OUT/'version/asset.bin').write_bytes(asset)
    source = OUT/'loader/source'
    shutil.copytree(BASE/'storage-status-loader/source', source, dirs_exist_ok=True)
    (source/'version-loader.asm').write_text((ROOT/'tools/v2-spi/version-loader.asm').read_text())
    loader, ls, _ = assemble(source, 'version-loader', 0xEF00, 'AUX_END', 0xEF0C)
    assert len(loader) <= 254, len(loader)
    e = bytearray((BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes())
    e[0xF00:0xFFE] = loader+b'\xff'*(254-len(loader))
    e[-2:] = crc(e[:-2]).to_bytes(2, 'big')
    assert crc(e) == 0 and crc(e[:0x800]) == 0
    name = 'str8n-v2-recovery-e000-efff'
    (OUT/(name+'.bin')).write_bytes(e)
    (OUT/(name+'.s19')).write_bytes(s19(dict(enumerate(e, 0xE000)), 0xF004))
    for n in meta['artifacts']:
        if n != name+'.bin':
            assert (OUT/n).read_bytes() == (BASE/n).read_bytes(), n
    for n in ('clock/clock.bin', 'boot-status/asset.bin', 'local-display/asset.bin'):
        assert (OUT/n).read_bytes() == (BASE/n).read_bytes(), n
    meta.update(version_command=True, version_symbols=symbols, version_code_bytes=len(body),
        version_asset_address=0xE800, version_asset_bytes=len(asset), version_asset_sha256=sha(asset),
        version_loader_bytes=len(loader), version_loader_symbols=ls,
        version_flash_allocation='B2:E800-EFFF, reserved local-display sector tail',
        version_ram='6E00-75FF borrowed monitor staging; application RAM untouched',
        hardware_tested=False, board_access=False, boards_flashed=False)
    meta['artifacts'] = {n:sha((OUT/n).read_bytes()) for n in meta['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta, indent=2)+'\n')
    print('UNFLASHED VERSION:', len(body), 'helper bytes;', len(loader),
          'resident loader bytes (was 250); no added flash sector; F/A/B unchanged')


if __name__ == '__main__':
    main()
