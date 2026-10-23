"""Capture ASM 0.5 pass-two listings/symbols in CPU models, never board ports."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

from test_rc1_source_store import Harness, ROOT, OUT, packed

DEST = ROOT/'BUILD/rc1-dev-samples/listings'
SAMPLES = ('sxb-cs-patterns', 'edu-led31')
SHA = lambda b: hashlib.sha256(b).hexdigest()


def trace_assembly(h, lines):
    records = []; current = None
    m = h.m; sy = h.asm
    def word(address): return int.from_bytes(m.ram[address:address+2],'little')
    original = h.cpu.step
    def close():
        if current is not None:
            end = word(sy['OUTPTR'])
            current['bytes'] = bytes(m.ram[current['output_start']:end]).hex(' ').upper()
            current['length'] = end-current['output_start']
    def observe():
        nonlocal current
        if h.cpu.pc == sy['ASSEMBLE_LINE'] and m.ram[sy['PASS']] == 2:
            close()
            number = word(sy['LINENO'])
            current = dict(line=number, address=word(sy['PC']), output_start=word(sy['OUTPTR']),
                           source=lines[number//10-1])
            records.append(current)
        return original()
    h.set_source(packed([(10*(i+1),text) for i,text in enumerate(lines)]))
    h.cpu.step = observe
    try: answer = h.command('ASM',contains='OK ')
    finally: h.cpu.step = original
    close()
    n = word(sy['RESULT_LEN']); origin = word(sy['RESULT_ORIGIN'])
    image = bytes(m.ram[0x200:0x200+n])
    assert len(records) == len(lines) and [r['line'] for r in records] == list(range(10,10*(len(lines)+1),10))
    assert b''.join(bytes.fromhex(r['bytes']) for r in records) == image
    for record in records:
        if record['length']:
            assert record['address'] == origin+record['output_start']-0x200
    symbols = []
    for address in range(sy['SYMBOL_START'],word(sy['SYMTOP']),20):
        raw = bytes(m.ram[address:address+20]); assert raw[18] & 1
        name = raw[:16].split(b'\0')[0].decode('ascii')
        match = next((r for r in records if r['source'].upper().startswith(name+':')),None)
        if match is None:continue  # Constant definitions emit no instructions.
        symbols.append(dict(name=name, address=int.from_bytes(raw[16:18],'little'), line=match['line']))
    symbols.sort(key=lambda r:(r['address'],r['name']))
    return dict(origin=origin,end=origin+n-1,code_bytes=n,image_sha256=SHA(image),
                records=records,symbols=symbols,assembler_output=answer), image


def listing(report):
    text = ['LINE ADDR MACHINE CODE             SOURCE',
            '---- ---- -----------------------  ------']
    for row in report['records']:
        address = f'{row["address"]:04X}' if not row['source'].lstrip().startswith(';') else '----'
        text.append(f'{row["line"]:4d} {address} {row["bytes"]:<23}  {row["source"]}')
    return '\n'.join(text)+'\n'


def hexdump(image, origin=0x200):
    lines = []
    for offset in range(0,len(image),16):
        chunk = image[offset:offset+16]
        ascii_text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f'{origin+offset:04X}: {chunk.hex(" ").upper():<47}  {ascii_text}')
    return '\n'.join(lines)+'\n'


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    qualification = json.loads((DEST.parent/'development-status.json').read_text())
    assert qualification['passed'] and qualification['firmware_sha256'] == SHA((OUT/'firmware.bin').read_bytes())
    results = {}
    for cpu in ('65c02','65c816-e'):
        h = Harness(cpu,'A',edu=False); h.open()
        for stem in SAMPLES:
            source = ROOT/'examples/source-cycle'/(stem+'.asm')
            lines = source.read_text().splitlines()
            report, image = trace_assembly(h,lines)
            assert SHA(image) == qualification['samples'][stem]['code_sha256']
            for profile in ('65c02','65c816-e'):
                for slot in ('A','B'):
                    for edu in (0,1):
                        assert image == (DEST.parent/f'{stem}-{profile}-{slot}-{edu}.bin').read_bytes()
            target = 'DWELL_OUTER = $FF' if stem == 'edu-led31' else 'BURST_BATCHES = $40'
            replacement = 'DWELL_OUTER = $80' if stem == 'edu-led31' else 'BURST_BATCHES = $20'
            modified = [replacement if line == target else line for line in lines]
            revised, edited = trace_assembly(h,modified)
            diffs = [dict(address=0x200+i,before=old,after=new)
                     for i,(old,new) in enumerate(zip(image,edited)) if old != new]
            assert len(image) == len(edited) and len(diffs) == 1
            assert report['symbols'] == revised['symbols']
            assert [(r['line'],r['address'],r['length']) for r in report['records']] == [
                (r['line'],r['address'],r['length']) for r in revised['records']]
            edit_row = next(r for r in report['records'] if r['length'] and r['address']+1 == diffs[0]['address'])
            assert diffs[0]['address'] == edit_row['address']+1
            report.update(edited_line=edit_row['line'],edit_delta=diffs,
                edited_sha256=SHA(edited),source_sha256=SHA(source.read_bytes()))
            revised.update(source_sha256=SHA('\n'.join(modified).encode()))
            if stem in results:
                assert report == results[stem]['report'] and revised == results[stem]['revised']
            else: results[stem] = dict(report=report,revised=revised,image=image,edited=edited)
            print('PASS',cpu,stem,'actual pass-two addresses/bytes, symbols, one-byte edit; matches all 8 qualified binaries',flush=True)
    for stem,result in results.items():
        report = result['report']
        (DEST/(stem+'.lst')).write_text(listing(report))
        (DEST/(stem+'-edited.lst')).write_text(listing(result['revised']))
        (DEST/(stem+'.json')).write_text(json.dumps(report,indent=2)+'\n')
        (DEST/(stem+'.bin')).write_bytes(result['image'])
        (DEST/(stem+'-edited.bin')).write_bytes(result['edited'])
        (DEST/(stem+'.hex.txt')).write_text(hexdump(result['image']))
        (DEST/(stem+'.sym.txt')).write_text('SYMBOL           ADDR LINE\n'+''.join(
            f'{s["name"]:<16} {s["address"]:04X} {s["line"]:4d}\n' for s in report['symbols']))
        (DEST/(stem+'.s19')).write_bytes((DEST.parent/(stem+'.s19')).read_bytes())
    receipt = dict(passed=True,board_access=False,method='Observed linked ASM 0.5 ASSEMBLE_LINE during pass 2; symbols read from its RAM table',
        firmware_sha256=qualification['firmware_sha256'],cpu_profiles=['65c02','65c816-e'],
        assembly_runs=8,all_16_qualified_binaries_match=True,edited_variants_keep_all_addresses=True,
        observer_sha256=SHA(Path(__file__).read_bytes()),
        files={p.name:SHA(p.read_bytes()) for p in sorted(DEST.iterdir()) if p.is_file() and p.name!='listing-report.json'})
    (DEST/'listing-report.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (DEST/'README.txt').write_text(
        'STR8-N source debugger listings - offline only\n'
        'Base .lst files match the workbook source. -edited.lst/.bin use the dwell edit.\n'
        'LINE is the decimal editor number; ADDR and machine-code bytes are hexadecimal.\n'
        'Comments emit no bytes. Labels/directives show the current logical address.\n'
        'BRK is two bytes: the debugger PC is the address AFTER its signature byte.\n'
        'Use .numbered.txt for editor input; .lst contains extra report columns.\n'
        'No boards accessed or flashed. See listing-report.json for provenance.\n')
    archive = ROOT/'output/pdf/STR8N-Source-Debug-Listings.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(DEST.iterdir()):
            if p.is_file(): z.write(p,'listings/'+p.name)
        for stem in SAMPLES:
            for suffix in ('.asm','.numbered.txt','.paste.txt'):
                p = ROOT/'examples/source-cycle'/(stem+suffix); z.write(p,'source/'+p.name)
        for name in ('development-status.json','test-65c02.json','test-65c816-e.json'):
            z.write(DEST.parent/name,'qualification/'+name)
    print('PASS listing report:',DEST/'listing-report.json',flush=True)
    print('PASS report archive:',archive,flush=True)


if __name__ == '__main__': main()
