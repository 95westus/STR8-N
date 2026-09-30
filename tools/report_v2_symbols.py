"""Count a22 symbols and relocation expressions using the WDC object viewer."""
from pathlib import Path
from collections import Counter
import csv
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/v2a22-code-sizes'
MODULES = ['str8n-v2', 'str8n-v2-worker', 'str8n-v2-vectors', 'str8n-v2-sr']
BASES = dict(zip(MODULES, [0xF000, 0x7900, 0x7E20, 0xE800]))


def main():
    routines = list(csv.DictReader((OUT / 'by-category.csv').open()))
    categories = {r['category']: Counter() for r in routines}
    for r in routines:
        categories[r['category']]['bytes'] += int(r['bytes'])
    categories['Data labels, end markers and data relocations'] = Counter()
    module_rows = []
    for module in MODULES:
        dump = subprocess.check_output(['wdcobj', '-lr', str(ROOT / 'BUILD/v2-alpha22/asm' / (module + '.obj'))], text=True)
        (OUT / (module + '-object.txt')).write_text(dump)
        symbols = re.findall(r'^\s*CODE\s*:\s*([0-9A-F]+)\s*:\s*(REL|ABS)\s*:\s*([^:]*)\s*:\s*(\w+)\s*:\s*(\w+)\s*$', dump, re.M)
        relocs = re.findall(r'^\s*[0-9A-F]+\s+([0-9A-F]+)\s*:\s*expr:\s*(\d+)\s*:', dump, re.M)
        assert symbols and relocs
        exported = {name for _, _, _, flags, name in symbols if flags[0] == 'G'}
        source = (ROOT / 'src/v2a22' / (module + '.asm')).read_text()
        assert exported == set(re.findall(r'^\s*XDEF\s+(\w+)', source, re.M))
        assert not re.search(r'\bXREF\b', source)
        assert all(flags[1] == 'D' for _, _, _, flags, _ in symbols)
        counts = Counter(symbols=len(symbols), local=sum(s[3][0] == 'g' for s in symbols),
                         global_=len(exported), imports=0, exports=len(exported),
                         relocations=len(relocs), relocation_bytes=sum(int(n) for _, n in relocs),
                         absolute=sum(s[1] == 'ABS' for s in symbols),
                         relative=sum(s[1] == 'REL' for s in symbols))
        module_rows.append((module, counts))

        def category(offset):
            address = BASES[module] + int(offset, 16)
            matches = [r['category'] for r in routines if r['module'] == module
                       and int(r['start'][1:], 16) <= address <= int(r['end'][1:], 16)]
            assert len(matches) <= 1
            return matches[0] if matches else 'Data labels, end markers and data relocations'

        for address, kind, _, flags, _ in symbols:
            if kind == 'REL':
                c = categories[category(address)]
                c['symbols'] += 1
                c['global' if flags[0] == 'G' else 'local'] += 1
        for address, width in relocs:
            categories[category(address)]['relocations'] += 1

    total = sum((c for _, c in module_rows), Counter())
    assert sum(c['symbols'] for c in categories.values()) == total['relative']
    assert sum(c['relocations'] for c in categories.values()) == total['relocations']
    lines = ['# v2.0a22 symbols and relocations', '',
             'Measured with WDCOBJ -lr on the four firmware objects. Local/global means object symbol visibility '
             '(g/G flags), not branch-label naming. Globals are the XDEF exports; all symbols are defined. '
             'Relocations count object expression/fixup records, not affected bytes or already-resolved relative branches.', '',
             '## Object totals', '',
             '| Object | Symbols | Local | Global / exports | Imports | Relocs | Absolute symbols | Relocatable labels |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, c in module_rows + [('TOTAL (sum of object tables)', total)]:
        lines.append(f'| {name} | {c["symbols"]} | {c["local"]} | {c["global_"]} | {c["imports"]} | {c["relocations"]} | {c["absolute"]} | {c["relative"]} |')
    lines += ['', 'Repeated include constants are counted in each object. Cross-module addresses use absolute EQU definitions; '
              'zero linker imports does not mean zero cross-module calls. The final BIN/S19 images contain no symbol or relocation tables.', '',
              '## By functional category', '',
              'Counts below cover labels defined in each code range, including internal branch labels and aliases. '
              'Absolute constants/EQU aliases are excluded from category counts because they are not defined by a code range. '
              'Data labels and end markers have their own row. Exports equal the global column; imports are zero throughout.', '',
              '| Category | Code bytes | Labels | Local | Global / exports | Relocs |', '|---|---:|---:|---:|---:|---:|']
    for name, c in categories.items():
        lines.append(f'| {name} | {c["bytes"]} | {c["symbols"]} | {c["local"]} | {c["global"]} | {c["relocations"]} |')
    lines += ['', f'The {total["relocations"]} relocation records patch {total["relocation_bytes"]} bytes.']
    (OUT / 'symbols.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
