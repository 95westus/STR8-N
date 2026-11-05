"""Build STR8-N's named BASE1 components offline; no board access or publication.

The accepted candidate is an immutable input, not edited in place. Output
contains canonical filenames, actual named banners and a rewritten component
catalog. Commands, prompts, AP identifiers, ABI and Foundation bytes survive.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'components/inputs/accepted-base1'
NAMES = json.loads((ROOT/'tools/product_names.json').read_text())
PRODUCTS = NAMES['components']
COPYRIGHT = NAMES['copyright']
COMPACT_COPYRIGHT = NAMES['copyright_compact']
sha = lambda data: hashlib.sha256(data).hexdigest()
crc = lambda data: binascii.crc_hqx(data, 65535)


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def copy_documentation(out):
    """Include public guides; point source-only links back to the repository."""
    destination = out/'docs'
    destination.mkdir(exist_ok=True)
    sources = sorted((ROOT/'docs').glob('*.md'))
    bundled = {path.resolve() for path in sources}
    for source in sources:
        def target(match):
            link = match.group(1)
            if '://' in link or link.startswith('#'):
                return link
            path, separator, fragment = link.partition('#')
            origin = (source.parent/path).resolve()
            if origin in bundled or (destination/path).exists():
                return link
            if origin.exists() and origin.is_relative_to(ROOT):
                kind = 'tree' if origin.is_dir() else 'blob'
                return ('https://github.com/95westus/STR8-N/'+kind+'/main/'
                        +origin.relative_to(ROOT).as_posix()+separator+fragment)
            return link
        text = re.sub(r'(?<=\]\()([^\s)]+)(?=\))', target,
                      source.read_text(encoding='utf-8'))
        (destination/source.name).write_text(text, encoding='utf-8', newline='\n')


def replace_text(body, old, new, minimum=1):
    old, new = old.encode('ascii'), new.encode('ascii')
    if len(new) > len(old) or body.count(old) < minimum:
        raise ValueError('Unexpected/too-small text field: '+repr(old))
    return body.replace(old, new.ljust(len(old)))


def config_titles(body):
    return replace_text(body,
        'STR8N-F CONFIG 0.3.0 / BASE1 / PR05 / settings writes are immediate',
        'STR8-N UTIL CONFIG 0.3.0 / BASE1/PR05; saves immediately')


def identity_notice(body, old, base=0x200):
    """Relocate an identity string; keep its original code/data addresses."""
    marker = old.encode('ascii')+b'\0'
    if body.count(marker)!=1:
        raise ValueError('Identity field is not unique: '+old)
    address = base+body.index(marker)
    target = base+len(body)
    pattern = bytes((0xa2,address&255,0xa0,address>>8))
    if body.count(pattern)<1:
        raise ValueError('Identity pointer not found')
    result = body.replace(pattern,bytes((0xa2,target&255,0xa0,target>>8)))
    return result+old.encode('ascii')+COPYRIGHT.encode()+b'\r\n\0'


def notice_identity(body, prefix, leading=False):
    start = body.index(prefix.encode())-(2 if leading else 0)
    end = body.index(b'\0',start)
    return identity_notice(body,body[start:end].decode('ascii'))


def symbols(path):
    return {n: int(v, 16) for v, n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', path.read_text(), re.M)}


def s19(path):
    memory = {}
    for row in path.read_text().splitlines():
        if row.startswith('S1'):
            data = bytes.fromhex(row[2:])
            if len(data) != data[0]+1 or sum(data)&255 != 255:
                raise ValueError('Invalid assembler output')
            memory.update(enumerate(data[3:-1], int.from_bytes(data[1:3], 'big')))
    return bytes(memory[a] for a in range(min(memory), max(memory)+1))


def assemble(stage, name, origin):
    logs = []
    for command in ([shutil.which('wdc02as'), '-G', '-L', '-S', '-W', name+'.asm'],
                    [shutil.which('wdcln'), '-g', '-s', '-t', f'-c{origin:04X}', '-hm19', '-j',
                     '-o', name+'.s19', name+'.obj']):
        if not command[0]:
            raise RuntimeError('WDC tools must be on PATH')
        result = subprocess.run(command, cwd=stage, capture_output=True, text=True)
        logs.append(dict(command=command, code=result.returncode, stdout=result.stdout, stderr=result.stderr))
        save(stage/(name+'-build.json'), logs)
        if result.returncode:
            raise RuntimeError('Assembly failed: '+str(stage/(name+'-build.json')))
    return s19(stage/(name+'.s19'))


def build_clock(original, stage, source):
    stage.mkdir()
    for file in source.iterdir():
        if file.suffix == '.inc' or file.name == 'clock.asm':
            shutil.copyfile(file, stage/file.name)
    size = int.from_bytes(original[8:10], 'little')
    unchanged = assemble(stage, 'clock', 0x2000)
    if unchanged != original[32:32+size]:
        raise ValueError('CLOCK source does not reproduce the accepted body')
    text = (stage/'clock.asm').read_text()
    if text.count('CLOCK 1.10 / BASE1 g1') != 1:
        raise ValueError('CLOCK title changed')
    text = text.replace('CLOCK 1.10 / BASE1 g1', 'STR8-N UTIL CLOCK 1.10')
    # Three identical readonly month tables can share one copy (24 bytes).
    table = 'DB 31,28,31,30,31,30,31,31,30,31,30,31'
    for name in ('TZ_MONTHS','BT_MONTH_LENGTH'):
        old = name+': '+table
        if text.count(old)!=1:
            raise ValueError('Readonly month table changed')
        text = text.replace(old,'; identical readonly table shared with MONTH_DAYS')
        text = re.sub(r'\b'+name+r'\b','MONTH_DAYS',text)
    text = text.replace('TITLE: DB "STR8-N UTIL CLOCK 1.10",13,10,0',
        'TITLE: DB "STR8-N UTIL CLOCK 1.10",13,10,"'+COMPACT_COPYRIGHT+'",13,10,0')
    (stage/'clock.asm').write_text(text)
    body = assemble(stage, 'clock', 0x2000)
    header = bytearray(original[:32])
    header[8:10] = len(body).to_bytes(2, 'little')
    data = bytes(header)+body
    if len(data) > len(original)-2:
        raise ValueError('Named CLOCK exceeds its existing allocation')
    data = data.ljust(len(original)-2, b'\xff')
    return data+crc(data).to_bytes(2, 'big')


def rebuild_asm(original, named_ram, stage, template):
    sys.path.insert(0, str(ROOT/'tools'))
    from storage_compact import compact
    stage.mkdir()
    text = Path(template).read_text()
    text = text[:text.index('DT_PACKED:\n')]
    raw = named_ram[0x3e00:]
    checksum = crc(raw)
    for address, value in ((0x670d, checksum&255), (0x670e, checksum>>8)):
        text, count = re.subn(r' LDA #\$[0-9A-Fa-f]{2}\n STA \$'+f'{address:04X}'+r'\n',
                              f' LDA #${value:02X}\n STA ${address:04X}\n', text)
        if count != 1:
            raise ValueError('ASM expanded CRC field changed')
    for address,value in ((0x6709,(0x4000+len(raw))&255),(0x670a,(0x4000+len(raw))>>8)):
        text,count = re.subn(r' LDA #\$[0-9A-Fa-f]{2}\n STA \$'+f'{address:04X}'+r'\n',
                            f' LDA #${value:02X}\n STA ${address:04X}\n',text)
        if count!=1:
            raise ValueError('ASM expanded end field changed')
    packed = compact(raw)
    text += 'DT_PACKED:\n'+''.join(' DB '+','.join(f'${v:02X}' for v in packed[i:i+16])+'\n'
                                  for i in range(0, len(packed), 16))
    text += 'DT_PACKED_END:\nDT_END:\n ENDMOD\n END\n'
    (stage/'asm.asm').write_text(text)
    body = assemble(stage, 'asm', 0xa020)
    if len(body)+32 > 8192:
        raise ValueError('Named ASM exceeds AP allocation')
    header = bytearray(original[:32])
    header[8:10] = (len(body)+32).to_bytes(2, 'little')
    header[28:30] = crc(header[:28]).to_bytes(2, 'little')
    header[30:32] = crc(body).to_bytes(2, 'little')
    return (bytes(header)+body).ljust(8192, b'\xff')


def named_dbg_ram(original):
    # The standalone packet starts by setting the initial target, then arms
    # DBG. Add its identity before that existing entry; code/tables stay put.
    body = bytearray(original)
    address = 0x5100
    offset = address-0x200
    if any(body[offset:offset+128]):
        raise ValueError('DBG banner gap is not zero-filled')
    old = bytes(body[:13])
    banner = b'STR8-N DEV DBG g2\r\n'+COPYRIGHT.encode()+b'\r\n\0'
    # X is preserved by the public PUTC veneer; original entry then sets A.
    code = bytearray.fromhex('A2 00 BD 00 00 F0 06 20 6D 7E E8 80 F5')
    string_address = address+len(code)+len(old)
    code[3:5] = string_address.to_bytes(2, 'little')
    body[offset:offset+len(code)+len(old)+len(banner)] = code+old+banner
    body[:3] = b'\x4c'+address.to_bytes(2, 'little')
    return bytes(body)


def title_wrapper(original, display):
    # Preserve old self-checks and absolute addresses: restore the original
    # first three bytes before entering the exact original tool at 0200.
    address = 0x200+len(original)
    banner = (display+'\r\n'+COPYRIGHT+'\r\n').encode()+b'\0'
    code = bytearray.fromhex('78 D8 A2 00 BD 00 00 F0 06 20 6D 7E E8 80 F5')
    restore = b''.join(bytes((0xa9, byte, 0x8d, offset, 2)) for offset,byte in enumerate(original[:3]))
    restore += bytes.fromhex('4C 00 02')
    code[5:7] = (address+len(code)+len(restore)).to_bytes(2, 'little')
    result = bytearray(original)+code+restore+banner
    result[:3] = b'\x4c'+address.to_bytes(2, 'little')
    if len(result)>0x6300:
        raise ValueError('Named helper exceeds raw recovery load limit')
    return bytes(result)


def rebuild_dbg(original, stage, template):
    stage.mkdir()
    text = Path(template).read_text()
    old = 'DT_TEXT: DB "DBG RAM start 0200-3FFF; Q MON> ",0'
    if text.count(old)!=1:
        raise ValueError('DBG launch identity changed')
    text = text.replace(old,'DT_TEXT: DB "STR8-N DEV DBG g2",13,10,"'+COPYRIGHT+'",13,10,"0200-3FFF; Q MON> ",0')
    (stage/'dbg.asm').write_text(text)
    body = assemble(stage,'dbg',0xc020)
    if len(body)>0x1800-32:
        raise ValueError('DBG loader overlaps paired provider')
    image = bytearray(original)
    image[32:0x1800] = body.ljust(0x1800-32,b'\xff')
    image[30:32] = crc(image[32:]).to_bytes(2,'little')
    return bytes(image)


def build(out, base=BASE):
    out, base = Path(out).resolve(), Path(base).resolve()
    out.mkdir(parents=True, exist_ok=False)
    from verify_component_inputs import verify_inputs
    lock = verify_inputs()
    host_overrides = lock.get("host_source_overrides", {})
    inputs = json.loads((base/'CANDIDATE-MANIFEST.json').read_text())['files']
    from rebuild_component_inputs import rebuild
    reconstructed, clock_source, reconstruction = rebuild(out/'reconstructed-inputs')
    from rebuild_mon_services import rebuild as rebuild_services
    service_inputs, service_receipt = rebuild_services(out/'reconstructed-services', clock_source)
    reconstructed.update(service_inputs)
    reconstruction['inputs'] += service_receipt['inputs']
    reconstruction['runtime_service_sources'] = service_receipt['source_sha256']
    from rebuild_util_dev_inputs import rebuild as rebuild_util_dev
    utility_inputs, generated, utility_receipt = rebuild_util_dev(out/'reconstructed-util-dev', out/'reconstructed-services')
    reconstructed.update(utility_inputs)
    reconstruction['inputs'] += utility_receipt['inputs']
    reconstruction['utility_dev_sources'] = utility_receipt['source_sha256']
    reconstruction['all_non_foundation_inputs_rebuilt'] = True
    save(out/'UTIL-DEV-RECONSTRUCTION.json', utility_receipt)
    save(out/'MON-SERVICES-RECONSTRUCTION.json', service_receipt)
    consumed = {}
    def read(name):
        override = host_overrides.get(name)
        path = ROOT/override['path'] if override else reconstructed[name] if name in reconstructed else base/name
        data = path.read_bytes()
        expected = override['sha256'] if override else inputs[name]['sha256']
        if sha(data) != expected:
            raise ValueError('Accepted candidate input differs: '+name)
        consumed[name] = sha(data)
        return data
    entries = {}
    def put(component, suffix, data, **metadata):
        stem = PRODUCTS[component]['stem'] if component in PRODUCTS else 'str8n-util-'+component.lower()
        file = 'payload/'+stem+('-'+suffix if suffix else '')+'.bin'
        path = out/file
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        entries[file] = dict(component=component, display=PRODUCTS.get(component, {}).get('display', 'STR8-N UTIL '+component),
                             bytes=len(data), sha256=sha(data), license='MIT', license_file='LICENSE',
                             embedded_notice=(COPYRIGHT.encode() in data or COMPACT_COPYRIGHT.encode() in data), **metadata)
        return file
    foundation = read('F.bin')
    put('F', '', foundation, unchanged=True)
    config = title_wrapper(config_titles(read('foundation/firmware/payload/STR8N-F-CONFIG-RAM.bin')),PRODUCTS['CONFIG']['display'])
    presets = {'CONFIG': put('CONFIG', 'ram', config, load='0200', command='CONFIG')}
    for component in ('OPAQUE','MAP','READBACK','DEMO'):
        original = read(f'foundation/firmware/payload/STR8N-F-{component}-RAM.bin')
        body = title_wrapper(original, PRODUCTS[component]['display'])
        presets[component] = put(component, 'ram', body, load='0200', command=component)
    flash = replace_text(read('rec/FLASH.bin'),
        'STR8N-F CONFIG 0.3.0 / BASE1 / PR05 / settings writes are immediate',
        'STR8-N UTIL FLASH g2 / BASE1/PR05; settings save immediately')
    flash = replace_text(flash, 'FLASH g2 / N-F0.3.0 BASE1/PR05', 'STR8-N UTIL FLASH g2')
    flash = notice_identity(flash,'STR8-N UTIL FLASH g2')
    put('FLASH', 'ram', flash, load='0200', command='FLASH')
    maint = config_titles(read('rec/MAINT.bin'))
    maint = replace_text(maint, 'STR8-N BANK MAINT 2.4 / REC 0200 r1', 'STR8-N UTIL MAINT 2.4 / REC 0200')
    maint = notice_identity(maint,'STR8-N UTIL MAINT 2.4 / REC 0200',leading=True)
    # MAINT's adapter seals the core+adapter before its private CRC field.
    sy = symbols(generated['maint_map'])
    seal = sy['MA_IMAGE_CRC']-0x200
    maint = bytearray(maint)
    maint[seal:seal+2] = crc(maint[0x1e00:seal]).to_bytes(2, 'big')
    put('MAINT', 'ram', bytes(maint), load='0200', command='MAINT')
    asm = replace_text(read('developer/ASM-RAM.bin'), 'STR8-N ASM 0.6-dev g1 / BASE1 PR05 RAM',
                       'STR8-N DEV ASM 0.6-dev BASE1/PR05')
    asm = notice_identity(asm,'STR8-N DEV ASM 0.6-dev BASE1/PR05',leading=True)
    put('ASM', 'ram', asm, load='0200', command='ASM')
    dbg = named_dbg_ram(read('developer/DBG-RAM.bin'))
    put('DBG', 'ram', dbg, load='0200', command='DBG')
    old_catalog = json.loads(read('NATIVE-COMPONENTS.json'))
    data = {item['file']: read(item['file']) for item in old_catalog['targets'] if 'file' in item}
    clock_names = [f'native/payload/B2-{address:04X}.bin' for address in (0xb000, 0xc000, 0xd000)]
    clock = build_clock(b''.join(data[n] for n in clock_names), out/'clock-source', clock_source)
    for i, name in enumerate(clock_names):
        data[name] = clock[i*4096:(i+1)*4096]
    workbench_names = ['native/payload/B2-8000.bin', 'native/payload/B2-9000.bin']
    workbench = b''.join(data[n] for n in workbench_names)
    if crc(workbench[0x300:0x1f00]) != 0:
        raise ValueError('Accepted workbench seal boundary differs')
    workbench = replace_text(workbench, 'STR8-N WORKBENCH WB2 g0000000E', 'STR8-N UTIL MAINT WB2 gE')
    workbench = bytearray(workbench)
    workbench[0x1efe:0x1f00] = crc(workbench[0x300:0x1efe]).to_bytes(2, 'big')
    for i, name in enumerate(workbench_names):
        data[name] = bytes(workbench[i*4096:(i+1)*4096])
    catalog = json.loads(json.dumps(old_catalog))
    for item in catalog['targets']:
        bank, address = item['bank'], int(item['address'], 16)
        component = ('MON' if bank == 3 and address in (0xa000, 0xb000) else
                     'CLOCK' if bank == 2 and address in (0xb000, 0xc000, 0xd000) else
                     'ASM' if bank == 0 and address in (0xa000, 0xb000) else
                     'DBG' if bank == 0 and address in (0xc000, 0xd000) else 'SERVICES')
        if component == 'MON':
            suffix = 'slot-'+('a' if address == 0xa000 else 'b')
        else:
            suffix = f'b{bank}-{address:04x}'
        if 'variants' in item:
            for cpu, info in item['variants'].items():
                body = read(info['file'])
                if component == 'ASM':
                    second = data['native/payload/B0-B000.bin']
                    body = rebuild_asm(body+second, asm, out/('asm-'+cpu), generated['asm_template'])[:4096]
                else:
                    second = data['native/payload/B0-D000.bin']
                    body = rebuild_dbg(body+second,out/('dbg-'+cpu), generated['dbg_template'])[:4096]
                file = put(component, suffix+'-'+cpu, body, bank=bank, address=item['address'])
                info.update(file=file, sha256=sha(body))
        else:
            body = data[item['file']]
            if component == 'ASM':
                # Rebuilt wrapper's packed ASM stream extends through sector B.
                named = rebuild_asm(read('native/payload/B0-A000-65c02.bin')+body, asm, out/'asm-shared', generated['asm_template'])
                body = named[4096:]
            elif component == 'DBG':
                first = read('native/payload/B0-C000-65c02.bin')
                body = rebuild_dbg(first+body,out/'dbg-shared', generated['dbg_template'])[4096:]
            elif component == 'MON':
                body = replace_text(body,
                    'STR8-N F 0.3.0  Foundation  gen 00000001\r\nRecovery / opaque-image boot\r\n',
                    'STR8-N F 0.3.0 gen 00000001\r\n'+COMPACT_COPYRIGHT+'\r\n')
                body = bytearray(body)
                body[18:20] = crc(body[:18]+body[32:]).to_bytes(2,'little')
                body = bytes(body)
            file = put(component, suffix, body, bank=bank, address=item['address'], unchanged=body==read(item['file']))
            item.update(file=file, sha256=sha(body))
    erased = read('native/payload/ERASED-4096.bin')
    blank_file = put('ERASED', '4096', erased, unchanged=True)
    for item in catalog['retirement_targets']:
        item.update(file=blank_file, sha256=sha(erased))
    for key in ('MAINT', 'FLASH'):
        file = next(f for f,v in entries.items() if v['component']==key and v.get('load')=='0200')
        catalog['REC_utilities'][key].update(file=file, bytes=entries[file]['bytes'], sha256=entries[file]['sha256'])
    catalog['profile'] = 'STR8-N F / MON / UTIL / DEV naming candidate'
    save(out/'NATIVE-COMPONENTS.json', catalog)
    from build_memory_agent import build as memory_agent
    memory_agent(out/'memory-agent-build')
    agent_file = put('MEMORY', 'ram', (out/'memory-agent-build/memory-agent.bin').read_bytes(), load='0200', command='MEMORY')
    am = json.loads((out/'memory-agent-build/manifest.json').read_text())
    am['file'] = Path(agent_file).name
    (out/'memory-agent-build'/am['file']).write_bytes((out/agent_file).read_bytes())
    save(out/'memory-agent-build/manifest.json', am)
    (out/'memory-agent-build/memory-agent.bin').unlink()
    (out/'product-names.json').write_bytes((ROOT/'tools/product_names.json').read_bytes())
    shutil.copyfile(ROOT/'LICENSE',out/'LICENSE')
    shutil.copyfile(ROOT/'THIRD_PARTY_NOTICES.md',out/'THIRD_PARTY_NOTICES.md')
    shutil.copyfile(ROOT/'requirements-console.txt',out/'requirements-console.txt')
    (out/'firmware/memory-agent').mkdir(parents=True)
    shutil.copyfile(ROOT/'firmware/memory-agent/profile.example.json',
                    out/'firmware/memory-agent/profile.example.json')
    save(out/'preset-assets.json', presets)
    (out/'terminal').mkdir()
    console = read('terminal/nf_console.py').decode()
    old = "self.selected.set(str(self.kit/'firmware/payload'/f'STR8N-F-{PRESETS[key]}-RAM.bin'))"
    new = "self.selected.set(str(self.kit/json.loads((self.kit/'preset-assets.json').read_text())[PRESETS[key]]))"
    if console.count(old)!=1:
        raise ValueError('Console preset selection changed')
    console = console.replace(old,new).replace('STR8N-F Serial Console','STR8-N Terminal')
    console = console.replace("version='STR8-N Terminal '+VERSION", "version='STR8-N Terminal '+VERSION+'\\n"+COPYRIGHT+"'")
    (out/'terminal/nf_console.py').write_text(console, encoding='utf-8')
    (out/'terminal/console_core.py').write_bytes(read('terminal/console_core.py'))
    (out/'str8n-terminal.py').write_text('''"""Launch STR8-N Terminal with canonical component presets."""
from pathlib import Path
import runpy,sys
r=Path(__file__).resolve().parent
p=r/'terminal/nf_console.py'
sys.path.insert(0,str(p.parent))
sys.argv=[str(p),'--kit',str(r)]+sys.argv[1:]
runpy.run_path(str(p),run_name='__main__')
''', encoding='utf-8')
    (out/'tools/installer/engine').mkdir(parents=True)
    for name in ('memory_tool.py', 'serial_test_coordination.py'):
        shutil.copyfile(ROOT/'tools'/name, out/'tools'/name)
    for name in ('installer/__init__.py', 'installer/engine/__init__.py'):
        (out/'tools'/name).write_text('')
    shutil.copyfile(ROOT/'tools/installer/engine/legacy_transport.py', out/'tools/installer/engine/legacy_transport.py')
    (out/'str8n-util-memory.py').write_text('''"""STR8-N UTIL MEMORY â€” named component kit launcher."""
from pathlib import Path
import sys
r = Path(__file__).resolve().parent
sys.path.insert(0, str(r/'tools'))
from memory_tool import main
if len(sys.argv)>1 and sys.argv[1] in ('backup','verify','plan','restore','load','offload') and '--agent' not in sys.argv:
    sys.argv += ['--agent', str(r/'memory-agent-build')]
main()
''', encoding='utf-8')
    (out/'README.md').write_text(README, encoding='utf-8')
    copy_documentation(out)
    save(out/'COMPONENTS.json', dict(schema=1, family='STR8-N', status='NAMING_CANDIDATE_NOT_LIVE_QUALIFIED',
        board_access=False, commands_changed=False, copyright=COPYRIGHT, Foundation_sha256=sha(foundation),
        artifacts=entries, source_inputs=consumed, reconstructed_inputs=reconstruction['inputs']))
    save(out/'SOURCE-RECONSTRUCTION.json', reconstruction)
    print('Named components: '+str(out))


README = '''# STR8-N components

STR8-N F is Foundation (BASE1/PR05). STR8-N MON has slots A and B.
STR8-N UTIL contains CONFIG, FLASH, CLOCK, MAINT and MEMORY.
STR8-N DEV contains ASM and DBG. Each component retains its own version.

Start with [the documentation index](docs/README.md),
[component/source/releases](docs/COMPONENT_GUIDE.md) and
[BIN/S19/S29 formats](docs/FILE_FORMATS.md). UTIL also includes MAP, OPAQUE,
READBACK and DEMO. F remains 0.3.0 g00000001 / BASE1 / PR05; current named
MON/UTIL/DEV have no dedicated published release yet. Preserved downloads:
[Foundation 0.3.0](https://github.com/95westus/STR8-N/releases/tag/v0.3.0),
[MON preview](https://github.com/95westus/STR8-N/releases/tag/mon-g8-tools-preview1),
[release index](https://github.com/95westus/STR8-N/blob/main/RELEASE_INDEX.md).

Commands and prompts stay short: CONFIG, FLASH, CLOCK, MAINT, MEMORY, ASM,
DBG; R ASM / R DBG, C B, B bank entry, C bank, Q, ASM> and DBG> retain their
existing meanings. Names do not change entry addresses or make headers executable.

Launch python str8n-terminal.py for STR8-N Terminal. F5/F6/F7/F8 select the
canonical MAP/CONFIG/OPAQUE/DEMO files through preset-assets.json.
Launch python str8n-util-memory.py --help for the PC memory utility. Both
launchers open no board connection on --help or --version.
Install PC dependencies with python -m pip install -r requirements-console.txt;
Python 3.11+ with Tk is required for Terminal. Copy
firmware/memory-agent/profile.example.json to a private location and fill in
the actual device/layout before MEMORY serial operations. The template
contains placeholders and is not a detected or approved board configuration.

payload/ contains canonical lowercase product filenames. COMPONENTS.json maps
each file to its component, placement, size and SHA-256. NATIVE-COMPONENTS.json
retains the existing sector/CPU catalog format with the new filenames.
CLOCK's three sector files are installed together using the existing reviewed
native-loader workflow. They are not standalone raw recovery executables.

This is an offline naming candidate. New banner bytes and rebuilt wrappers
need their own live qualification before installation. Foundation's payload
stays frozen. Monitor VERSION includes the compact copyright notice.
LICENSE accompanies all binaries, including reused service/data sectors.
No board was opened or flashed by this build.
Existing releases, machine identities, wire markers and historical evidence
keep their original identifiers. Private board settings/images are not copied.
'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--base', type=Path, default=BASE)
    args = parser.parse_args()
    build(args.out, args.base)
