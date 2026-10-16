"""Promote the tested maintenance reminders to beta26, preserving the F ABI."""
import hashlib
import json
import shutil
from pathlib import Path

import build_v2_config as compiler
import build_v2_recovery as fw
from beta4_migration import crc, s19
import prepare_v2_battery as battery
from build_v2_spi_resident import assemble

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'BUILD/v2-battery'
OUT = ROOT/'BUILD/v2-beta26'
sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    battery.audit()
    meta = json.loads((BASE/'build.json').read_text())
    upgrade = json.loads((BASE/'battery-update-test-results.json').read_text())
    assert upgrade['passed'] and upgrade['battery_asset_sha256'] == meta['battery_asset_sha256']
    shutil.copytree(BASE, OUT, dirs_exist_ok=True)
    for p in OUT.glob('*test-results.json'):
        p.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    messages = json.loads((OUT/'source/str8n-v2-text.json').read_text())
    first = next(i for i, m in enumerate(messages) if m['name'] == 'V2_BAD_PREFIX')
    pool = bytearray()
    for i, message in enumerate(messages):
        raw = bytearray(message['text'].replace('{version}', '2.0b26').encode())
        if i < first:
            raw = raw[4:]
        raw[-1] |= 128
        pool.extend(raw)
    compiler.include_bytes(OUT/'asm/text-image.inc', pool)
    p = OUT/'asm/text-image.inc'
    p.write_text('V2_TEXT:\n'+p.read_text())
    compiler.OUT, compiler.SOURCE = OUT, OUT/'asm'
    fw.OUT = OUT
    slots, monitors = {}, {}
    for page in (0xA0, 0xB0):
        name = f'monitor-{page:02x}'
        cells, symbols = compiler.assemble(name, (page<<8)+128,
            shutil.which('wdc02as'), shutil.which('wdcln'), source_file=BASE/'asm'/(name+'.asm'))
        body = compiler.dense_image(cells, (page<<8)+128, symbols['V2_END'])
        prior = (BASE/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
        assert len(body) == 3967
        assert sum(a != b for a, b in zip(body, prior[128:128+len(body)])) == 1
        slot = bytearray(fw.slot_image(body, symbols, page, 38, meta['boot_compatibility']))
        slot[70:72] = symbols['V2_M_EDIT'].to_bytes(2, 'little')
        slot[18:20] = crc(slot[:18]+slot[32:]).to_bytes(2, 'little')
        stem = f'str8n-v2-recovery-slot-{page:02x}'
        (OUT/(stem+'.bin')).write_bytes(slot)
        (OUT/(stem+'.s19')).write_bytes(s19(dict(enumerate(slot, page<<8)), 0xF004))
        slots[page], monitors[f'{page:02x}'] = slot, symbols
    image = bytearray((BASE/'str8n-v2-recovery-a000-dfff.bin').read_bytes())
    image[:4096], image[4096:8192] = slots[0xA0], slots[0xB0]
    stem = 'str8n-v2-recovery-a000-dfff'
    (OUT/(stem+'.bin')).write_bytes(image)
    (OUT/(stem+'.s19')).write_bytes(s19(dict(enumerate(image, 0xA000)), 0xF004))

    # The new helper owns part of D, so AUTO must reserve the complete shared
    # sector, including erased padding. Keep storage operation 5 distinct from
    # VERSION (7); battery remains operation 6.
    stage = OUT/'storage-status/source'
    p = stage/'storage-services.inc'
    text = p.read_text()
    assert text.count('CMP #$D2') == text.count('LDA #$D2') == 1
    p.write_text(text.replace('CMP #$D2','CMP #$E0').replace('LDA #$D2','LDA #$E0'))
    body, status, _ = assemble(stage,'storage-status',0x6E00,'APP_END',0x6E07)
    assert len(body) == meta['status_code_bytes']
    original = (BASE/'boot-status/asset.bin').read_bytes()[:len(body)]
    assert sum(a != b for a,b in zip(body, original)) == 2
    asset = body+b'\xff'*(2558-len(body))
    asset += crc(asset).to_bytes(2,'big')
    (OUT/'boot-status/asset.bin').write_bytes(asset)
    stage = OUT/'loader/source'
    p = stage/'version-loader.asm'
    text = p.read_text()
    assert text.count('LDA #5') == 1 and text.count('CMP #5') == 2
    text = text.replace('LDA #5','LDA #7',1).replace('CMP #5','CMP #6',1)
    text = text.replace('CMP #5','CMP #7',1)
    p.write_text(text)
    body, loader, _ = assemble(stage,'version-loader',0xEF00,'AUX_END',0xEF0C)
    assert len(body) <= 254
    e = bytearray((BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes())
    e[0xF00:0xFFE] = body+b'\xff'*(254-len(body))
    e[-2:] = crc(e[:-2]).to_bytes(2,'big')
    assert crc(e) == 0 and crc(e[:0x800]) == 0
    stem = 'str8n-v2-recovery-e000-efff'
    (OUT/(stem+'.bin')).write_bytes(e)
    (OUT/(stem+'.s19')).write_bytes(s19(dict(enumerate(e,0xE000)),0xF004))
    meta.update(storage_reserved_end=0xE000,status_symbols=status,
        status_asset_sha256=sha(asset),version_loader_symbols=loader,
        version_loader_bytes=len(body),version_service_kind=7)

    # Reuse the existing per-step bank/address tables with the proven MI/SR
    # mixed commit selector: byte 31 -> 00, SR byte 3 -> 3F.
    folder = OUT/'migrator'
    p = folder/'rtc-migrator.asm'
    text = p.read_text()
    old = '                        LDA #$3F\n                        STA V2_FLASH_DATA\n                        JMP V2W_BYTE'
    assert text.count(old) == 1
    text = text.replace(old, '''                        LDA #$3F
                        LDY V2_FLASH_PTR
                        CPY #$1F
                        BNE MIG_COMMIT_VALUE_READY
                        LDA #$00
MIG_COMMIT_VALUE_READY:  STA V2_FLASH_DATA
                        JMP V2W_BYTE''')
    text = text.replace('STR8-N 2.0b24 RTC/I2C MIGRATOR', 'STR8-N 2.0b26 RTC/I2C MIGRATOR')
    p.write_text(text)
    compiler.OUT, compiler.SOURCE = folder, folder/'asm'
    cells, symbols = compiler.assemble('rtc-migrator', 0x2000,
        shutil.which('wdc02as'), shutil.which('wdcln'), source_file=p)
    data = s19(cells, 0x2000)
    (folder/'rtc-migrator-2000.s19').write_bytes(data)
    mm = json.loads((folder/'manifest.json').read_text())
    mm.update(symbols=symbols, sha256=sha(data), mixed_commit_values=True)
    for key, symbol in [('count','MIG_PLAN_COUNT'), ('commit_after','MIG_COMMIT_AFTER'),
        ('commits','MIG_COMMITS'), ('banks','MIG_BANKS'), ('table','MIG_TABLE'),
        ('commit_addresses','MIG_COMMIT_ADDRS')]:
        mm[key] = symbols[symbol]
    (folder/'manifest.json').write_text(json.dumps(mm, indent=2)+'\n')
    meta.update(version='2.0b26', generation=38, monitors=monitors,
        fallback_version='2.0b25', fallback_generation=37,
        battery_parent_build_sha256=sha((BASE/'build.json').read_bytes()),
        hardware_tested=False, board_access=False, boards_flashed=False)
    meta['artifacts'] = {name:sha((OUT/name).read_bytes()) for name in meta['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta, indent=2)+'\n')
    for name in ('str8n-v2-recovery-f000-ffff.bin',
                 'battery/asset.bin', 'clock/clock.bin'):
        assert (OUT/name).read_bytes() == (BASE/name).read_bytes(), name
    print('BETA26 generation 38; same F/ABI and qualified maintenance assets; monitor text changes one byte per slot')


if __name__ == '__main__':
    main()
