"""Build an isolated beta5 RTC/I2C monitor profile; never access a board.

Keep the qualified beta4 fixed F byte-identical, retain E entry addresses, move
saved MAINT to B1:8/9, and allocate B3:8 to the optional service component.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import build_v2_beta4_launcher as apps
import build_v2_rtc_split as split
from build_bank_maint_v2 import long_branches

ROOT = apps.ROOT
OUT = ROOT / 'BUILD/v2-rtc-kernel'
PROFILE = ROOT / 'src/v2-rtc-kernel'
VERSION = '2.0b5'
GENERATION = 14
PROFILE_HOOK = None
COMPONENT_HOOK = None
LAUNCHER_EXTRA = None
TEMPLATE_BASE = None


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Profile source drift: {old[:70]!r}')
    return text.replace(old, new)


def main():
    split.main()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'build.json').unlink(missing_ok=True)
    (OUT / 'kernel-test-results.json').unlink(missing_ok=True)
    overlay = OUT / 'overlay'
    overlay.mkdir(exist_ok=True)
    help_text = json.loads((ROOT / 'src/v2-beta4-launcher/help.json').read_text())
    help_text['monitor'] = ('B0-3 D addr [end] M/F addr bytes G addr L\r\n'
        'M [1 grid|2 ranges|3 wear]\r\nI start end W U A|B\r\n'
        'S bank flash start end [label]\r\nR [bank] label|bank flash [L]\r\n'
        'T [bank|first-last]\r\nJ0-3 C [0|1 bank addr|V delay] P [A|B]')
    assert len(help_text['extension'].encode()) + 1 <= 254
    (overlay / 'help.json').write_text(json.dumps(help_text, indent=2) + '\n')
    hook = (ROOT / 'src/v2-beta4-launcher/monitor-hook.inc').read_text()
    hook = replace_once(hook, 'CMP #$E8', 'CMP #$F0')
    (overlay / 'monitor-hook.inc').write_text(hook)
    baseline = json.loads((ROOT / 'BUILD/v2-beta4-base/build.json').read_text())
    apps.OUT, apps.SOURCE = OUT, overlay
    apps.prepare(baseline)
    source = OUT / 'source'
    for path in PROFILE.glob('*.inc'):
        shutil.copyfile(path, source / path.name)
    smeta = json.loads((split.OUT / 'build.json').read_text())
    template = TEMPLATE_BASE or (0x8000 + smeta['provider_bytes'])
    with (source / 'service-eq.inc').open('a') as f:
        f.write(f'\nSVC_TEMPLATE EQU ${template:04X}\n')
    eq = source / 'str8n-v2-eq.inc'
    eq.write_text(eq.read_text() + '\n INCLUDE "service-eq.inc"\n')
    monitor = (source / 'str8n-v2.asm').read_text()
    monitor = replace_once(monitor, 'V2_WORKER_COPIED:\n', '''V2_WORKER_COPIED:
                        STZ SVC_DESC
                        JSR AP_CHECK
                        BCC SVC_BOOT_DONE
                        JSR $E014
SVC_BOOT_DONE:
''')
    (source / 'str8n-v2.asm').write_text(monitor)
    mi = source / 'str8n-v2-monitor.inc'
    text = mi.read_text()
    text = replace_once(text, '                        CMP     #$67\n                        BCC     V2_ADDRESS_YES',
        '                        CMP     #$67\n                        BCS     V2_ADDRESS_NO\n'
        '                        CMP     #$65\n                        BCC     V2_ADDRESS_YES\n'
        '                        BIT SVC_ACTIVE\n                        BNE V2_ADDRESS_NO\n'
        '                        BRA V2_ADDRESS_YES')
    mi.write_text(text)
    li = source / 'str8n-v2-load.inc'
    text = li.read_text()
    text = replace_once(text, '                        CMP     #$67\n                        BCS     V2_LOAD_RANGE',
        '                        CMP     #$67\n                        BCS     V2_LOAD_RANGE\n'
        '                        CMP     #$65\n                        BCC SVC_LOAD_OK\n'
        '                        BIT SVC_ACTIVE\n                        BNE V2_LOAD_RANGE\nSVC_LOAD_OK:')
    li.write_text(text)
    fi = source / 'str8n-v2-flash.inc'
    text = fi.read_text()
    text = replace_once(text, '                        CMP #$A0\n                        BCS V2_F_PROTECTED',
        '                        CMP #$A0\n                        BCS V2_F_PROTECTED\n'
        '                        CMP #$80\n                        BEQ V2_F_PROTECTED')
    text = replace_once(text, '                        CMP     #$A0\n                        BCS     V2_I_PROTECTED',
        '                        CMP     #$A0\n                        BCS     V2_I_PROTECTED\n'
        '                        LDA V2_ADDR+1\n                        CMP #$80\n'
        '                        BEQ V2_I_PROTECTED')
    fi.write_text(text)
    si = source / 'str8n-v2-sr.asm'
    text = si.read_text().replace('CMP     #$67', 'JSR SR_APPLICATION_LIMIT')
    text = replace_once(text, 'SR_VALID_NONRESIDENT:', '''                        LDA SR_BANK
                        CMP #3
                        BNE SR_VALID_NONRESIDENT
                        LDA SR_RECORD+1
                        CMP #$90
                        BCC SR_INVALID
SR_VALID_NONRESIDENT:''')
    text = replace_once(text, 'SR_END:', '''SR_APPLICATION_LIMIT:
                        BIT SVC_ACTIVE
                        BEQ SR_UNRESERVED
                        CMP #$65
                        RTS
SR_UNRESERVED:          CMP #$67
                        RTS
SR_END:''')
    si.write_text(text)
    if PROFILE_HOOK:
        PROFILE_HOOK(source)
    apps.configure()
    fw = apps.fw
    fw.VERSION = VERSION
    saved = sys.argv
    try:
        sys.argv = [saved[0], '--generation', str(GENERATION)]
        fw.main()
    finally:
        sys.argv = saved
    fixed_f = (OUT / (fw.STEM + '-f000-ffff.bin')).read_bytes()
    assert fixed_f == (ROOT / 'BUILD/v2-beta4-base' / (fw.STEM + '-f000-ffff.bin')).read_bytes()
    report = json.loads((OUT / 'build.json').read_text())
    (OUT / 'build.json').unlink()
    stage = OUT / 'asm'
    (stage / 'app-text-ids.inc').write_text(''.join(line for line in
        (stage / 'text-ids.inc').read_text().splitlines(True) if not line.startswith('V2_SR_ERROR_TEXT ')))
    legacy = (stage / 'app-legacy-dispatch.inc').read_text()
    (stage / 'app-legacy-dispatch.inc').write_text(long_branches(legacy).replace('BM_LONG_', 'AP_LEG_LONG_'))
    launcher = (ROOT / 'src/v2-beta4-launcher/launcher.asm').read_text()
    launcher = replace_once(launcher, '                       JMP AP_PROBE          ; E011: read-only slot probe',
        '                       JMP AP_PROBE          ; E011: read-only slot probe\n'
        '                       JMP SVC_INIT          ; E014: verified kernel startup')
    launcher = launcher.replace('                       INCLUDE "app-help.inc"', 'AP_HELP_TEXT EQU $EF00')
    launcher = replace_once(launcher, '                       CMP #$67\n                       BCS AP_VALIDATE_BAD',
        '                       CMP #$67\n                       BCS AP_VALIDATE_BAD\n'
        '                       CMP #$65\n                       BCC SVC_APP_RAM_OK\n'
        '                       BIT SVC_ACTIVE\n                       BNE AP_VALIDATE_BAD\nSVC_APP_RAM_OK:')
    # Bank-3 app images may use only the unowned sector 9, never the RTC sector.
    launcher = replace_once(launcher, '                       LDA AP_LIMIT+1\n                       CMP #$A0',
        '                       LDA AP_DESC+15\n                       CMP #$90\n'
        '                       BCC AP_VALIDATE_BAD\n                       LDA AP_LIMIT+1\n                       CMP #$A0')
    launcher = replace_once(launcher, 'AP_END:', '                       INCLUDE "service-kernel.inc"\nAP_END:')
    if LAUNCHER_EXTRA:launcher=LAUNCHER_EXTRA(launcher)
    path = OUT / 'launcher.asm'
    path.write_text(long_branches(launcher).replace('BM_LONG_', 'AP_LONG_'))
    memory, symbols = fw.link.assemble('launcher', 0xE000, shutil.which('wdc02as'), shutil.which('wdcln'), source_file=path)
    memory, symbols = fw.relax_branches(path, memory, symbols,
        lambda: fw.link.assemble('launcher', 0xE000, shutil.which('wdc02as'), shutil.which('wdcln'), source_file=path))
    code = fw.link.dense_image(memory, 0xE000, symbols['AP_END'])
    assert len(code) <= 0x6E0, ('Launcher/kernel exceeds allocation', len(code))
    e = bytearray((OUT / (fw.STEM + '-e000-efff.bin')).read_bytes())
    e[:0x800] = b'\xFF' * 2048
    e[:len(code)] = code
    e[0x6E0:0x6E8] = b'MP\x01\x08\x11\xe0\x90\x7d'
    e[0x6F0:0x6F4] = b'AT\x01\x08'
    e[0x7FE:0x800] = fw.crc(e[:0x7FE]).to_bytes(2, 'big')
    tail = help_text['extension'].encode() + b'\0'
    e[0xF00:0xF00+len(tail)] = tail
    e[-2:] = fw.crc(e[:-2]).to_bytes(2, 'big')
    assert fw.crc(e[:0x800]) == fw.crc(e) == 0
    fw.emit(fw.STEM + '-e000-efff', 0xE000, e, 0xF004)
    sector = bytearray(b'\xFF' * 4096)
    provider = (split.OUT / 'provider.bin').read_bytes()
    gateway = (split.OUT / 'gateway.bin').read_bytes()
    sector[:len(provider)] = provider
    sector[template-0x8000:template-0x8000+len(gateway)] = gateway
    if COMPONENT_HOOK:
        COMPONENT_HOOK(sector)
    sector[-2:] = fw.crc(sector[:-2]).to_bytes(2, 'big')
    assert fw.crc(sector) == 0
    fw.emit('str8n-rtc-component-8000-8fff', 0x8000, sector, 0xF004)
    report.update(version=VERSION, generation=GENERATION, launcher=symbols,
        launcher_bytes=len(code), service_component_bytes=len(provider)+len(gateway),
        service_template=template, service_discovery=0x7D04, service_ram='6500-66FF',
        fixed_f_unchanged=True, hardware_tested=False,
        artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.bin')})
    (OUT / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'RTC kernel {VERSION}: E code {len(code)}; component {len(provider)+len(gateway)} bytes; F unchanged')


if __name__ == '__main__':
    main()
