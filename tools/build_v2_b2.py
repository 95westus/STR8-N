"""Build the separate 2.0b2 manager/RTS candidate; never program hardware."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import build_v2_config as host
from build_bank_maint_v2 import long_branches

ROOT = host.ROOT
VERSION = '2.0b2'
CONFIG_IN_F = True
STAGING_START = 0x6100
BOOT_WAITS = host.BOOT_WAITS
STEM = 'str8n-v2-b2'
OUT = ROOT / 'BUILD/v2-b2'
SOURCE = ROOT / 'src/v2-b2'
CONFIG_ADDRESS = host.CONFIG_ADDRESS
FT245_ONLY = True
# Expanded directory consumes the former E alignment gap and one tail byte.
CONFIG_ROM_START = 0xBB00
AUTOLOAD_ROM_START = 0xB240
MANAGER_STORAGE_START = 0xB008
SERVICE_ROM_START = 0xE180
PUBLIC_CALLS = host.PUBLIC_CALLS
RAM_PUBLIC_CALLS = host.RAM_PUBLIC_CALLS
RESIDENT_START = host.RESIDENT_START
read_s19, symbols, record = host.read_s19, host.symbols, host.record

SERVICES = (
    ('CONSOLE.PUTC', 'STR8V2_RAM_PUTC'), ('CONSOLE.HEXOUT', 'STR8V2_RAM_HEX_OUT'),
    ('CONSOLE.NEWLINE', 'STR8V2_RAM_NEWLINE'), ('CONSOLE.CANCEL', 'STR8V2_RAM_CHECK_CANCEL'),
    ('PARSE.HEXWORD', 'V2_HEX_WORD'), ('PARSE.HEXBYTE', 'V2_HEX_BYTE'),
    ('PARSE.SPACES', 'V2_SKIP_SPACES'), ('FLASH.READ', 'V2W_READ'),
    ('FLASH.SNAPSHOT', 'V2W_SNAPSHOT'), ('FLASH.MUTATE', 'V2W_MUTATE'),
)


def crc16(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xFFFF
    return value


def write_s19(path, start, data, entry):
    lines = [record('0', 0, ('STR8-N ' + VERSION).encode('ascii'))]
    lines += [record('1', start+i, data[i:i+32]) for i in range(0, len(data), 32)]
    lines.append(record('9', entry))
    path.write_text('\n'.join(lines) + '\n', encoding='ascii')


def main():
    # Reuse the qualified build machinery against a separate source/output tree.
    host.VERSION, host.STEM, host.OUT, host.SOURCE = VERSION, STEM, OUT, SOURCE
    assemble_base = host.assemble
    def assemble_b2(*args, **kwargs):
        if len(args) < 5:
            kwargs.setdefault('source', SOURCE)
        return assemble_base(*args, **kwargs)
    host.assemble = assemble_b2
    for receipt in ('manager-rts-tests.json', 'extended-config-tests.json',
                    'service-registration-tests.json', 'autoload-tests.json',
                    'autoload-headless-tests.json'):
        (OUT / receipt).unlink(missing_ok=True)
    for pattern in (f'{STEM}-rts*.bin', f'{STEM}-rts*.s19',
                    f'{STEM}-extended-config*.bin', f'{STEM}-extended-config*.s19'):
        for artifact in OUT.glob(pattern):
            artifact.unlink()
    host.main()
    report = json.loads((OUT / 'build.json').read_text())
    (OUT / 'build.json').unlink()
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    core_symbols = report['resident'] | report['worker'] | report['vectors']
    config_calls = ('V2_CONFIG_READ', 'V2_CONFIG_SUM', 'V2_HEX_BYTE',
                    'V2_SKIP_SPACES', 'V2_CONFIRM', 'V2_FLASH_MODE',
                    'V2W_READ', 'V2W_SNAPSHOT', 'V2W_ANALYZE', 'V2W_MUTATE')
    (OUT / 'asm/config-host-symbols.inc').write_text(''.join(
        f'{name:24} EQU ${core_symbols[name]:04X}\n' for name in config_calls), encoding='ascii')
    cfg_mem, cfg_sym = host.assemble('str8n-v2-extended-config', CONFIG_ROM_START, assembler, linker,
                                   include_dirs=(OUT / 'asm',))
    cfg = host.dense_image(cfg_mem, CONFIG_ROM_START, cfg_sym['CF_END'])
    if cfg_sym['CF_END'] > 0xC000:
        raise ValueError('Configuration exceeds B sector')
    rts_start = 0xE400
    (OUT / 'asm/config-module-symbols.inc').write_text(''.join(
        f'{name:24} EQU ${cfg_sym[name]:04X}\n' for name in ('CF_COMMAND', 'CF_LOCATE')), encoding='ascii')
    host_inc = ''.join(f'{name:24} EQU     ${core_symbols[name]:04X}\n'
                       for _, name in SERVICES)
    (OUT / 'asm/rts-host-symbols.inc').write_text(host_inc, encoding='ascii')
    rts_mem, rts_sym = host.assemble('str8n-v2-rts', rts_start, assembler, linker,
                                   include_dirs=(OUT / 'asm',))
    rts = host.dense_image(rts_mem, rts_start, rts_sym['SR_END'])
    if rts_sym['SR_END'] > 0xF000:
        raise ValueError(f'Configuration/RTS exceeds E sector: end {rts_sym["SR_END"]:04X}')
    names = list(SERVICES) + [('COMMAND.REGISTER', 'MG_REGISTER'),
                              ('SERVICE.REGISTER', 'MG_SERVICE_REGISTER_ROM'),
                              ('COMMAND.CORE', 'MG_CORE_META')]
    extra = [('RTS.SAVE', rts_sym['SR_API_SAVE'], 1),
             ('RTS.RESTORE', rts_sym['SR_API_RESTORE'], 1),
             ('STORAGE.POLICY', rts_sym['RTS_POLICY'], 0)]
    extra.append(('CONFIG.LOCATE', cfg_sym['CF_LOCATE'], 1))
    extra.append(('COMMAND.REGISTER', 0xED00, 1))
    table = [f'MG_SERVICE_COUNT EQU {len(names)+len(extra)}\n', 'MG_SERVICES:\n']
    for index, (_, target) in enumerate(names):
        address = target if target.startswith('MG_') else f'${core_symbols[target]:04X}'
        flags = 0 if target == 'MG_CORE_META' else 1
        table += [f'                        DW MG_NAME_{index}\n',
                  f'                        DB $01,${flags:02X}\n', f'                        DW {address}\n']
    for index, (_, address, flags) in enumerate(extra, len(names)):
        table += [f'                        DW MG_NAME_{index}\n',
                  f'                        DB ${2 if index==len(names)+len(extra)-1 else 1:02X},${flags:02X}\n', f'                        DW ${address:04X}\n']
    count = core_symbols['V2_COMMAND_TABLE']-core_symbols['V2_COMMAND_KEYS']
    table += ['MG_CORE_META:          DB $01,'+f'${count:02X}\n',
              f'                        DW ${core_symbols["V2_COMMAND_KEYS"]:04X}\n',
              f'                        DW ${core_symbols["V2_COMMAND_TABLE"]:04X}\n']
    for index, (name, *_) in enumerate(names + extra):
        table.append(f'MG_NAME_{index}:           DB "{name}",$00\n')
    (OUT / 'asm/manager-host-services.inc').write_text(''.join(table), encoding='ascii')
    mgr_mem, mgr_sym = host.assemble('str8n-v2-manager', 0x7100, assembler, linker,
                                   include_dirs=(OUT / 'asm',))
    mgr = host.dense_image(mgr_mem, 0x7100, mgr_sym['MG_END'])
    if mgr_sym['MG_END'] > 0x7400:
        raise ValueError(f'Manager overlaps pinned command stub reservation at 7400: {len(mgr)}')
    if MANAGER_STORAGE_START+len(mgr) > AUTOLOAD_ROM_START:
        raise ValueError('Stored manager overlaps autoload code')
    (OUT / 'asm/service-directory.inc').write_text(
        f'MG_STATIC_TABLE EQU ${mgr_sym["MG_SERVICES"]:04X}\n'
        f'MG_STATIC_BYTES EQU {6*(len(names)+len(extra))}\n', encoding='ascii')
    service_source = OUT / 'asm/services-expanded.asm'
    service_source.write_text(long_branches((SOURCE / 'str8n-v2-services.asm').read_text()), encoding='ascii')
    service_mem, service_sym = host.assemble('str8n-v2-services', SERVICE_ROM_START,
        assembler, linker, source_file=service_source, include_dirs=(SOURCE, OUT / 'asm'))
    service_code = host.dense_image(service_mem, SERVICE_ROM_START, service_sym['SERVICE_END'])
    if service_sym['SERVICE_END'] > rts_start:
        raise ValueError(f'Services overlap RTS: end {service_sym["SERVICE_END"]:04X}')
    (OUT / 'asm/named-host-symbols.inc').write_text(
        f'NAMED_CORE_KEYS EQU ${core_symbols["V2_COMMAND_KEYS"]:04X}\n',encoding='ascii')
    named_source=OUT/'asm/named-expanded.asm'
    named_source.write_text(long_branches((SOURCE/'str8n-v2-named.asm').read_text()),encoding='ascii')
    named_mem,named_sym=host.assemble('str8n-v2-named',0xED00,assembler,linker,
        source_file=named_source,include_dirs=(SOURCE,OUT/'asm'))
    named_code=host.dense_image(named_mem,0xED00,named_sym['NAMED_END'])
    if rts_sym['SR_END']>0xED00 or named_sym['NAMED_END']>0xF000:
        raise ValueError('Named commands overlap RTS or core')
    runtime_rts=rts+b'\xff'*(0xED00-rts_sym['SR_END'])+named_code
    al_symbols = {name: core_symbols[name] for name in config_calls + ('V2_HEX_WORD', 'V2_COMMAND_KEYS')}
    al_symbols.update({name: cfg_sym[name] for name in ('CF_LOCATE', 'CF_SUM')})
    al_symbols.update({name: rts_sym[name] for name in
        ('SR_COMMAND_SAVE', 'SR_COMMAND_RESTORE', 'SR_COMMAND_TABLE', 'RTS_REGISTER')})
    (OUT / 'asm/autoload-host-symbols.inc').write_text(''.join(
        f'{name:24} EQU ${address:04X}\n' for name,address in al_symbols.items()), encoding='ascii')
    al_source = OUT / 'asm/autoload-expanded.asm'
    al_source.write_text(long_branches((SOURCE / 'str8n-v2-autoload.asm').read_text()), encoding='ascii')
    al_mem, al_sym = host.assemble('str8n-v2-autoload', AUTOLOAD_ROM_START,
        assembler, linker, source_file=al_source, include_dirs=(SOURCE, OUT / 'asm'))
    al_code = host.dense_image(al_mem, AUTOLOAD_ROM_START, al_sym['AL_END'])
    if al_sym['AL_END'] > CONFIG_ROM_START:
        raise ValueError(f'Autoload overlaps config: end {al_sym["AL_END"]:04X}')
    top = (OUT / f'{STEM}-f000-ffff.bin').read_bytes()
    core_crc = crc16(top[:0xFD0] + top[0xFE0:])
    image_id = crc16(mgr + runtime_rts + cfg + service_code + al_code)
    for name, data in (('manager', mgr), ('rts', rts)):
        host.include_bytes(OUT / f'asm/{name}-image.inc', data)
    constants = dict(MG_SIZE=len(mgr), RTS_SIZE=len(runtime_rts), MG_CORE_CRC=core_crc,
                     MG_RUNTIME_ID=image_id, RTS_INIT=rts_sym['RTS_INIT'],
                     RTS_ROM_START=rts_start, CF_ROM_START=CONFIG_ROM_START,
                     CF_ROM_END=cfg_sym['CF_END'], CF_LOAD=cfg_sym['CF_LOAD'],
                     MG_STORAGE_START=MANAGER_STORAGE_START,
                     MG_SERVICE_ROM_END=service_sym['SERVICE_END'],
                     AL_APPLY_ENTRY=AUTOLOAD_ROM_START,
                     AL_ROM_START=AUTOLOAD_ROM_START, AL_ROM_END=al_sym['AL_END'])
    (OUT / 'asm/manager-build.inc').write_text(''.join(
        f'{name:24} EQU ${value:04X}\n' for name, value in constants.items()), encoding='ascii')
    copy = []
    for prefix, length, target in (('MG', len(mgr), 0x7100),):
        offsets = list(range(0, length-255, 256))
        if length % 256:
            offsets.append(max(0, length-256))
        copy += ['                        LDX #$00\n', f'{prefix}_COPY:\n']
        for offset in offsets:
            copy += [f'                        LDA {prefix}_IMAGE+${offset:04X},X\n',
                     f'                        STA ${target+offset:04X},X\n']
        copy += ['                        INX\n']
        if length < 256:
            copy += [f'                        CPX #${length:02X}\n']
        copy += [f'                        BNE {prefix}_COPY\n']
    (OUT / 'asm/manager-copy.inc').write_text(''.join(copy), encoding='ascii')
    rom_source = OUT / 'asm/manager-rom-expanded.asm'
    rom_source.write_text(long_branches((SOURCE / 'str8n-v2-manager-rom.asm').read_text()), encoding='ascii')
    rom_mem, rom_sym = host.assemble('str8n-v2-manager-rom', 0xE000, assembler, linker,
                                   source_file=rom_source, include_dirs=(SOURCE, OUT / 'asm'))
    e_code = host.dense_image(rom_mem, 0xE000, rom_sym['MG_ROM_END'])
    if len(e_code) > SERVICE_ROM_START-0xE000:
        raise ValueError(f'Manager boot overlaps services at {SERVICE_ROM_START:04X}: {len(e_code)}')
    e_sector = e_code + b'\xff' * (SERVICE_ROM_START-0xE000-len(e_code)) + service_code
    e_sector += b'\xff' * (rts_start-0xE000-len(e_sector)) + runtime_rts
    e_sector += b'\xff' * (4096-len(e_sector))
    image = e_sector + top
    manager_sector = bytearray(4096)
    manager_sector[:8+len(mgr)] = b'MB\x01\x01'+len(mgr).to_bytes(2,'little')+image_id.to_bytes(2,'little')+mgr
    manager_sector[AUTOLOAD_ROM_START-0xB000:al_sym['AL_END']-0xB000] = al_code
    manager_sector[CONFIG_ROM_START-0xB000:cfg_sym['CF_END']-0xB000] = cfg
    manager_sector = bytes(manager_sector)
    (OUT / f'{STEM}-b000-bfff.bin').write_bytes(manager_sector)
    write_s19(OUT / f'{STEM}-b000-bfff.s19', 0xB000, manager_sector, 0xB000)
    for name, start, data in (('e000-efff', 0xE000, e_sector),
                              ('e000-ffff', 0xE000, image)):
        (OUT / f'{STEM}-{name}.bin').write_bytes(data)
        write_s19(OUT / f'{STEM}-{name}.s19', start, data, report['resident']['START'])
    if '--full-bank' in sys.argv:
        full = b'\xff' * 0x3000 + manager_sector + b'\xff' * 0x2000 + image
        (OUT / f'{STEM}-8000-ffff.bin').write_bytes(full)
        write_s19(OUT / f'{STEM}-8000-ffff.s19', 0x8000, full, report['resident']['START'])
    for name, start, data in (('manager-7100', 0x7100, mgr), ('rts', rts_start, rts),
                              ('extended-config', CONFIG_ROM_START, cfg)):
        (OUT / f'{STEM}-{name}.bin').write_bytes(data)
        write_s19(OUT / f'{STEM}-{name}.s19', start, data, start+8)
    report.update(milestone='b2-manager-rts-config', manager_bytes=len(mgr), rts_bytes=len(rts),
                  named_command_bytes=len(named_code),named_command_symbols=named_sym,
                  manager=mgr_sym, rts=rts_sym, manager_rom=rom_sym,
                  manager_carrier_bytes=len(e_code), core_binding_crc16=core_crc,
                  service_code_bytes=len(service_code),services=service_sym,
                  manager_storage=[0xB000,0xBFFF], manager_storage_bytes=len(mgr)+8,
                  autoload=al_sym, autoload_bytes=len(al_code), autoload_state=[0x7640,0x768E],
                  dynamic_services=dict(capacity=8,table=0x7600,table_bytes=48,count=0x7DEB),
                  core_commands=dict(service='COMMAND.CORE',version=1,format=1,
                      descriptor=mgr_sym['MG_CORE_META'],count=count,
                      keys=core_symbols['V2_COMMAND_KEYS'],
                      targets=core_symbols['V2_COMMAND_TABLE'],callable=False),
                  rts_execution=f'resident-bank ROM {rts_start:04X}', rts_state=[0x7500, 0x7537],
                  extended_config=cfg_sym, extended_config_bytes=len(cfg),
                  config_state=[0x7540, 0x756A], persistent_storage_policy=True,
                  config_locator_offset=7, config_sector_default=None,
                  runtime_image_id=image_id, application_end=0x57FF,
                  staging_start=0x6100, overlays=[0x5800, 0x5FFF],
                  manager_reservation=[0x7100, 0x78FF],
                  named_records=True, automatic_placement=True,
                  manager_initialization='reset and lazy recovery; explicit configuration autoload',
                  storage_default_sector_masks=[0, 0, 0, 0], board_tested=False)
    report.pop('sr_bytes', None)
    report.pop('sr_symbols', None)
    report['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(OUT.iterdir()) if p.suffix in ('.bin', '.s19')}
    (OUT / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'2.0b2: manager {len(mgr)} RAM bytes, RTS {len(rts)} ROM bytes, '
          f'config {len(cfg)} ROM bytes, E carrier {len(e_code)}; no board programming')


if __name__ == '__main__':
    main()
