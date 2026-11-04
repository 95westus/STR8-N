"""Read saved g0034 files and frozen BASE1 sources; never build or execute target code."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
digest = lambda body: hashlib.sha256(body).hexdigest()
read_json = lambda path: json.loads(path.read_text(encoding='utf-8'))


def symbols(path):
    text = path.read_text(encoding='utf-8')
    found = {name: int(value, 16) for value, name in re.findall(
        r'^\s*([0-9a-fA-F]{8})\s+(\w+)\s*$', text, re.M)}
    found.update({name: int(value, 16) for name, value in re.findall(
        r'^(\w+)\s+EQU\s+\$([0-9a-fA-F]+)', text, re.M)})
    return found


def sources(start, boundary):
    found = {}

    def visit(path):
        path = path.resolve()
        if path in found:
            return
        if not path.is_relative_to(boundary.resolve()):
            raise ValueError('Include outside saved source tree: '+str(path))
        text = path.read_text(encoding='utf-8')
        found[path] = text
        for include in re.findall(r'^\s*INCLUDE\s+"([^"]+)"', text, re.M | re.I):
            visit(path.parent/include)
    visit(start)
    return found


def s19_cells(path):
    cells = {}
    for line in path.read_text(encoding='ascii').splitlines():
        if not line.startswith('S'):
            continue
        kind = int(line[1])
        row = bytes.fromhex(line[2:])
        if len(row) != row[0]+1 or sum(row) & 255 != 255:
            raise ValueError('Invalid saved S-record')
        if kind not in (1, 2, 3):
            continue
        width = kind+1
        address = int.from_bytes(row[1:1+width], 'big')
        for offset, value in enumerate(row[1+width:-1]):
            assert address+offset not in cells
            cells[address+offset] = value
    return cells


def slot_header(body, page):
    length = int.from_bytes(body[12:14], 'little')
    failures = []
    checks = {
        'MI/format/slot/bank/ABI': body[:6] == b'MI\x01'+bytes((page, 3, 1)),
        'nonzero payload length within 0F80': 0 < length <= 0x0f80,
        'reset entry': int.from_bytes(body[14:16], 'little') == page*256+0x84,
        'prompt entry': int.from_bytes(body[16:18], 'little') == page*256+0x87,
        'reserved byte 1F': body[31] == 0,
        'SN signature': body[128:130] == b'SN',
        'PR05 private contract': body[20:24] == b'PR05',
        'header/payload CRC': binascii.crc_hqx(body[:18]+body[32:], 0xffff)
                              == int.from_bytes(body[18:20], 'little'),
    }
    failures = [name for name, accepted in checks.items() if not accepted]
    return dict(generation=f'{int.from_bytes(body[8:12], "little"):08X}',
                private_contract_hex=body[20:24].hex().upper(),
                private_contract_ascii=body[20:24].decode('ascii', errors='replace'),
                payload_bytes=length, BASE1_admitted=not failures, refusal_reasons=failures)


def review(build, fixture_path):
    build = Path(build).resolve()
    fixture = read_json(fixture_path)
    assert fixture['generation'] == 0x34 and fixture['boot_compatibility'] == 0x52313032
    frozen = read_json(ROOT/'F_FREEZE.json')
    f = (ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert len(f) == frozen['bytes'] == 4096 and digest(f) == frozen['sha256']
    for name, expected in frozen['sources'].items():
        assert digest((ROOT/name).read_bytes()) == expected, name
    core = build/'s/core'
    public = symbols(ROOT/'src/include/str8n-v2-public.inc')
    old_public = symbols(build/'s/include/str8n-v2-public.inc')
    public_names = [name for name in public if name.startswith('STR8V2_RAM_')
                    and name not in ('STR8V2_RAM_FORMAT', 'STR8V2_RAM_CALLS')]
    assert all(old_public[name] == public[name] for name in public_names)
    old_worker, new_worker = symbols(core/'worker-public-symbols.inc'), symbols(ROOT/'src/core/worker-public-symbols.inc')
    worker_changes = {name: dict(g0034=f'{old_worker[name]:04X}', BASE1=f'{value:04X}')
                      for name, value in new_worker.items()
                      if name in old_worker and value != old_worker[name]}
    old_boot, new_boot = symbols(core/'str8n-v2-boot.map'), symbols(ROOT/'src/core/boot-symbols.inc')
    crc_changes = {name: dict(g0034=f'{old_boot[name]:04X}', BASE1=f'{new_boot[name]:04X}')
                   for name in ('J_CRC_INIT', 'J_CRC_BYTE')}
    slots, all_sources, calls = {}, {}, []
    worker_end = new_worker['V2W_END']
    rom_public = {value for name, value in public.items()
                  if name in ('STR8V2_RESET', 'STR8V2_HOLD', 'STR8V2_CON_INIT', 'STR8V2_PUTC',
                              'STR8V2_GETC', 'STR8V2_RAW_POLL', 'STR8V2_CHECK_CANCEL',
                              'STR8V2_RX_RESET', 'STR8V2_HEX_OUT', 'STR8V2_NEWLINE',
                              'STR8V2_HEX_NIBBLE', 'STR8V2_CAPS_QUERY', 'STR8V2_BOARD_QUERY')}
    ram_public = {public[name] for name in public_names if name != 'STR8V2_RAM_SIGNATURE'}
    for slot in ('a0', 'b0'):
        page = int(slot, 16)
        artifact = f'str8n-v2-recovery-slot-{slot}.bin'
        body = (build/'payload'/artifact).read_bytes()
        expected = fixture['artifacts'][artifact]
        assert len(body) == expected['bytes'] == 4096 and digest(body) == expected['sha256']
        sy = symbols(core/f'monitor-{slot}.map')
        cells = s19_cells(core/f'monitor-{slot}.s19')
        assert min(cells) == page*256+128
        assert max(cells)+1 == sy['V2_END']
        assert all(body[address-page*256] == value for address, value in cells.items())
        header = slot_header(body, page)
        assert header['generation'] == '00000034'
        assert header['refusal_reasons'] == ['PR05 private contract']
        # The saved header's entry shim copies 15 bytes to 7B81 before the
        # linked monitor body runs. Match bytes directly; no CPU is emulated.
        assert body[0x48:0x53] == bytes((0xA2,0x0E,0xBD,0x6C,page,0x9D,0x81,0x7B,0xCA,0x10,0xF7))
        slots[slot] = dict(artifact=artifact, sha256=digest(body), **header,
                           linked_code_bytes=len(cells), linked_end=f'{sy["V2_END"]:04X}',
                           S19_matches_sector=True,
                           entry_shim=dict(address=f'{page*256+0x48:04X}', copy_bytes=15,
                                           destination='7B81-7B8F',
                                           overlaps_BASE1_worker=0x7800 <= 0x7B81 < worker_end))
        inputs = sources(core/f'monitor-{slot}.asm', build/'s')
        for path, text in inputs.items():
            rel = path.relative_to(build/'s').as_posix()
            all_sources[rel] = dict(sha256=digest(path.read_bytes()), lines=len(text.splitlines()))
            for line_no, line in enumerate(text.splitlines(), 1):
                code = line.split(';', 1)[0].strip()
                match = re.search(r'\b(JSR|JMP)\s+([^\s]+)', code, re.I)
                if not match:
                    continue
                op, operand = match.groups()
                if operand.startswith('('):
                    calls.append(dict(slot=slot, file=rel, line=line_no, operation=op,
                                      target=operand, classification='indirect; inspect guard/owner'))
                    continue
                if operand.startswith('$'):
                    value = int(operand[1:], 16)
                elif operand in sy:
                    value = sy[operand]
                elif re.fullmatch(r'V2_IMAGE_PAGE\*\$100\+\$[0-9A-Fa-f]+', operand):
                    value = page*256+int(operand.rsplit('$', 1)[1], 16)
                else:
                    calls.append(dict(slot=slot, file=rel, line=line_no, operation=op,
                                      target=operand, classification='unresolved expression'))
                    continue
                if page*256 <= value < (page+16)*256:
                    category = 'own ROM image'
                elif value in ram_public:
                    category = 'public RAM facade'
                elif 0x7800 <= value < 0x7f00:
                    category = 'private RAM worker/vector/gateway'
                elif value in rom_public:
                    category = 'public F facade; B3 visible required'
                elif value >= 0xf000:
                    category = 'private F entry/helper'
                elif 0xe000 <= value < 0xf000:
                    category = 'optional B3:E provider'
                else:
                    category = 'other absolute target'
                calls.append(dict(slot=slot, file=rel, line=line_no, operation=op,
                                  target=operand, address=f'{value:04X}', classification=category))
    counts = {}
    for call in calls:
        counts[call['classification']] = counts.get(call['classification'], 0)+1
    provider_inputs = {}
    for name in ('core/launcher.asm', 'core/service-kernel.inc', 'banner/rtc-banner.asm',
                 'xip/utilities.asm', 'xip/system.inc', 'xip/gate.asm', 'xip/work-stub.asm'):
        path = build/'s'/name
        provider_inputs[name] = dict(sha256=digest(path.read_bytes()), lines=len(path.read_text(encoding='utf-8').splitlines()))
    return dict(schema=1, review='MON A/B checkpoint 1: saved-file compatibility inventory',
                scope='Source/header/link-file inspection only; no target instructions executed',
                artifact_validation_passed=True, binary_compatible=False,
                g0034_fixture_sha256=digest(Path(fixture_path).read_bytes()),
                g0034_firmware_sha256=fixture['firmware_sha256'],
                foundation=dict(tag='v0.3.0', F_sha256=digest(f), profile='BASE1', contract='PR05'),
                g0034_contract='52313032 / little-endian bytes 32 30 31 52 (201R)',
                slots=slots, public_RAM_addresses_equal={name:f'{public[name]:04X}' for name in public_names},
                private_worker_symbols_changed=worker_changes, private_CRC_symbols=crc_changes,
                saved_source_files=all_sources, call_site_counts=counts, call_sites=calls,
                manually_reviewed_provider_sources=provider_inputs,
                RAM_conflicts=[dict(owner='g0034 header debugger hook', range='7B81-7B8F',
                                    BASE1_owner='RAM worker 7800-7BE7', observed='literal header copy loop'),
                               dict(owner='g0034 optional XIP utility gateway', range='7B90-7BD3',
                                    BASE1_owner='RAM worker 7800-7BE7', observed='saved gateway link address and code length')],
                call_inventory_limit='Textual JSR/JMP sites; DB-encoded RAM gateways and provider internals require manual review',
                recommendation='New BASE1 monitor core using public RAM facade; port selected g0034 logic, not its sector bytes',
                board_access=False, flashing=False, firmware_builds=0, CPU_simulations=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--g0034-build', type=Path, required=True)
    parser.add_argument('--g0034-fixture', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Use a fresh report path; existing evidence is preserved')
    result = review(args.g0034_build, args.g0034_fixture)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({key:result[key] for key in ('artifact_validation_passed', 'binary_compatible',
        'slots', 'private_CRC_symbols', 'call_site_counts', 'private_worker_symbols_changed')}, indent=2))
