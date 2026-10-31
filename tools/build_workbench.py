"""Build the WB2 RAM-only checkpoint once; never rebuild F or access hardware."""
import argparse
import binascii
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_mona import ROOT, cells, equs, sha
from mona_branches import conservative_branches


def build(out, generation=1, reuse_loader=None):
    if not 1 <= generation <= 0xffffffff:
        raise ValueError('Generation must be 1..FFFFFFFF')
    generation_text=f'{generation:08X}'
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh output directory; preserve earlier build results')
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise ValueError('WDC assembler/linker required')
    freeze = json.loads((ROOT/'F_FREEZE.json').read_text(encoding='utf-8'))
    f = (ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert len(f) == 4096 and sha(f) == freeze['sha256']
    for filename, digest in freeze['sources'].items():
        assert sha((ROOT/filename).read_bytes()) == digest, filename
    contract = equs(ROOT/'monitors/src/workbench-interface.inc')
    origin, pages = contract['WB_ORIGIN'], contract['WB_PAGES']
    module_bytes = pages*256
    assert origin+module_bytes == 0x6400
    bs = equs(ROOT/'src/core/boot-symbols.inc')
    ws = equs(ROOT/'src/core/worker-public-symbols.inc')
    crc = binascii.crc_hqx(f, 0xffff)
    private = dict(WB_F_READ=ws['V2W_READ'], WB_F_EXECUTE=ws['V2W_EXECUTE'],
                   WB_F_SELECT=ws['V2W_SELECT'], WB_F_BYTE=ws['V2W_BYTE']+2,
                   WB_F_RECOVERY=bs['BOOT_RECOVERY'],
                   WB_F_CRC_LO=crc & 255, WB_F_CRC_HI=crc >> 8)
    out.mkdir(parents=True)
    source_hashes = {}
    branch_layout = {}
    for filename in ('workbench.asm', 'workbench-loader.asm', 'workbench-interface.inc',
                     'workbench-layout.inc', 'workbench-sram.inc', 'workbench-store.inc',
                     'workbench-batch.inc', 'workbench-clock.inc', 'workbench-native.inc',
                     'workbench-program.inc', 'program-layout.inc',
                     'workbench-monitor-ui.inc', 'monitor-ui.inc', 'batch-interface.inc'):
        path = ROOT/'monitors/src'/filename
        body = path.read_text(encoding='utf-8')
        body = body.replace('WB_GENERATION_TEXT',generation_text)
        body = body.replace('"WB_GENERATION_BYTES"',','.join(f'${v:02X}' for v in generation.to_bytes(4,'little')))
        source_hashes[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
        if filename not in ('workbench-layout.inc','program-layout.inc'):
            body, info = conservative_branches(body, 'WB_LONG_'+re.sub(r'\W', '_', filename)+'_')
            branch_layout[filename] = info
        (out/filename).write_text(body, encoding='utf-8', newline='\n')
    shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc', out/'str8n-v2-public.inc')
    (out/'workbench-foundation.inc').write_text(
        ''.join(f'{name} EQU ${value:04X}\n' for name, value in private.items()),
        encoding='ascii', newline='\n')
    logs = []
    objects = {}
    components=[('workbench', origin, 'W_CODE_END')]
    if reuse_loader is None:
        components.append(('workbench-loader', 0x0200, 'WL_END'))
    else:
        old_path=Path(reuse_loader).resolve();old=json.loads(old_path.read_text(encoding='utf-8'))
        assert old['foundation_sha256']==sha(f) and old['private_adapter']==private
        for name in ('workbench-loader.asm','workbench-layout.inc','workbench-interface.inc'):
            key='monitors/src/'+name;assert source_hashes[key]==old['sources'][key],key
        old_image=(old_path.parent/old['artifact']['filename']).read_bytes()
        assert sha(old_image)==old['artifact']['sha256']
        objects['workbench-loader']=(old_image[:old['loader_bytes']],{})
    for stem, origin, end_symbol in components:
        for command in ([assembler, '-G', '-L', '-S', '-W', stem+'.asm'],
                        [linker, '-g', '-s', '-t', f'-c{origin:04X}', '-hm19', '-j',
                         '-o', stem+'.s19', stem+'.obj']):
            done = subprocess.run(command, cwd=out, capture_output=True,
                                  text=True, encoding='utf-8')
            logs.append(dict(command=command, returncode=done.returncode,
                             stdout=done.stdout, stderr=done.stderr))
            (out/'build-log.json').write_text(json.dumps(logs, indent=2)+'\n',
                                              encoding='utf-8', newline='\n')
            if done.returncode:
                raise RuntimeError('WDC build failed; inspect '+str(out/'build-log.json'))
        symbols = {name: int(value, 16) for value, name in re.findall(
            r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',
            (out/(stem+'.map')).read_text(encoding='utf-8'), re.M)}
        memory = cells(out/(stem+'.s19'))
        assert set(memory) == set(range(origin, symbols[end_symbol]))
        objects[stem] = (bytes(memory[a] for a in range(origin, symbols[end_symbol])), symbols)
    body, symbols = objects['workbench']
    loader, _ = objects['workbench-loader']
    contract = equs(ROOT/'monitors/src/workbench-interface.inc')
    assert contract['WB_ORIGIN'] == 0x4800 and pages == 28
    assert contract['WB_FORMAT'] == 2 and contract['WB_RESULT'] == 0x655F
    assert len(loader) <= 256, 'Loader overlaps source module at 0300'
    assert len(body) <= module_bytes-2, 'Module overlaps its CRC trailer at 63FE'
    assert body[:8] == b'MW'+bytes((2,pages))+b'PR05'
    assert body[17:23]==b'WG'+generation.to_bytes(4,'little')
    for offset, target in ((8, 'W_DISPATCH'), (11, 'W_SHELL'), (14, 'W_INIT')):
        assert body[offset:offset+3] == b'\x4c'+symbols[target].to_bytes(2, 'little')
    module = body+b'\xff'*(module_bytes-2-len(body))
    module += binascii.crc_hqx(module, 0xffff).to_bytes(2, 'big')
    assert len(module) == module_bytes and binascii.crc_hqx(module, 0xffff) == 0
    image = loader+b'\xff'*(256-len(loader))+module
    assert len(image) == 256+module_bytes and 0x0200+len(image) == 0x1F00
    filename = 'STR8N-WORKBENCH-WB2-g'+generation_text+'-RAM.bin'
    (out/filename).write_bytes(image)
    (out/'WB2-module-4800.bin').write_bytes(module)
    report = dict(schema=1, component='STR8-N RAM workbench', interface='WB2',
                  generation=generation_text, status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',
                  artifact=dict(filename=filename, bytes=len(image), sha256=sha(image)),
                  module=dict(origin='4800', filename='WB2-module-4800.bin', bytes=module_bytes, linked_bytes=len(body),
                              linked_end=f'{symbols["W_CODE_END"]:04X}',
                              sha256=sha(module), crc='CCITT FFFF; big-endian trailer; residue zero',
                              header='MW 02 1C PR05', command_entry='4808', shell_entry='480B', init_entry='480E'),
                  bridge_client_RAM_floor='6550: lowest destination page; RAM monitor declares code end rounded up',
                  command_result=dict(address='655F',values={'0':'OK','1':'syntax/unsupported','2':'refused','3':'canceled','4':'partial destination'}),
                  foundation_sha256=sha(f), private_adapter=private,
                  loader_bytes=len(loader), sources=source_hashes,
                  RAM_borrowed=['0200-1EFF transfer staging', '4800-63FF module', '6400-66FF state'],
                  application_RAM_while_loaded='0200-47FF', system_ZP=['E0-E1', 'E2-E3', 'E6-E7', 'EA'],
                  entry='REC> L or ROM monitor L raw RAM BIN; g8 uses the matching MS service dispatcher',
                  return_path='Q -> CRC-admitted UI/1 quiet MON return; intact legacy MON falls back to HOLD; invalid MI returns to recovery',
                  monitor_A_B_changed=False, F_rebuilt=False, hardware_access=False,
                  flash_writes='Explicit S into fully erased owner-declared B0/B1 AREA only; no erase',
                  journal_writes=False, SRAM_writes=False,
                  EDU='Explicit session OFF/ON; ON is a wiring selection, not presence proof',
                  monitor_UI=dict(requires='UI/1 count > operation: six original vectors; operation6 needs seven',
                    commands=['VERSION','V','TIME','quiet Q'],
                    peripheral_reader='WB TIME reuses MON RTC implementation/cache; native CLOCK has its own full provider',
                    cold_entry='Initializes selected bank to B3',
                    MAINT_entry='Preserves caller-selected bank through shell initialization',
                    Q='Validated quiet MON return preserves selected bank/cache; intact old MON falls back to HOLD; invalid MI returns to REC'),
                  SPI=dict(profile='EDU Rev D PB0 SCK/PB1 MOSI/PB2 SRAM CS/PB5 MISO; PB3 CS kept high',
                           opcodes=['05 RDMR', '03 READ'], automatic_probe=False,
                           layout='SS/01/08 primary fixed 64KiB zero-generation; SS/02/08 nonzero generation and labelled fallback; CRC/commit/reserved fields required',
                           PREP='Explicit disabled-CB flag acknowledgment; not automatic',
                           prior_input_pin_output_latch='Unreadable: sampled ORB restoration only'),
                  records=dict(format='SR/01; no payload checksum', scan='bytewise 8000-DFFF, selected bank',
                               table=True, restore=True, restore_names='unique within selected bank',
                               command_aliases={'STORE':'S','TABLE':'T','RESTORE':'R'},
                               store='S bank flash|AUTO RAMfirst RAMlast [name]; YES; commit last, per-byte readback; AREA window required',
                               AUTO='Flash append tail after complete/pending SR01 records; no gap reclaim; crossing/corrupt AREA refused; explicit start address retained',
                               run='Explicit R without L; old program ABI not thereby qualified'),
                  batch=dict(text_bytes=34,separator=';',empty_segments='refused before execution',
                             command_allowlist='checked when reached: returning WB commands, STORE/TABLE/RESTORE, guarded MON D/M, maps/W/APPS/APP, native menus and registered PROGRAM runs',
                             stop_on_error=True,cancel='Ctrl-C/ESC stops remainder; confirmations always use live input',
                             queue_is_console_input=False,nested_batch=False,
                             completion='resident queue resumes after native Q, AP/02 or PR05-registered PROGRAM HOLD; wide load-only must be final'),
                  companion_PROGRAM='SP/01 provider at6B00-77FF required for PROGRAM; full RAM packet supplied by services manifest',
                  native_apps='Reserved R CLOCK/R FLASH/R MAINT and BOOT route to the separately packaged RAM overlays; see native acceptance',
                  planned=['Large STORE-source staging', 'Remaining full-b35 management parity',
                           'Source/ASM/DEBUG', 'WORKSPACE allocation review and separate append-only messages'],
                  build_passes=1, assembler_linker_invocations=len(logs),
                  reused_loader_from=str(Path(reuse_loader).resolve().relative_to(ROOT)) if reuse_loader else None,
                  branch_layout=branch_layout, CPU_simulations=0)
    (out/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(filename=filename, bytes=len(image), linked_bytes=len(body),
                          free_module_bytes=module_bytes-2-len(body), sha256=sha(image),
                          status=report['status']), indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--generation', type=lambda value:int(value,0), default=1)
    parser.add_argument('--reuse-loader',type=Path)
    args=parser.parse_args()
    build(args.out,args.generation,args.reuse_loader)
