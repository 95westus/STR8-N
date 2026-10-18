"""Read-only firmware/app/ABI inventory for the expanded bf1 user package scope.

This is an audit, not a distribution qualification or hardware test.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    if a.out.exists():
        raise ValueError('Retain earlier audit: output already exists')
    image_path = ROOT/'output/qualification/bf1-str8n-only-image-2026-10-18-r1/str8n-2.0bf1-str8n-only.bin'
    image = image_path.read_bytes()
    ref_path = ROOT/'tmp/bfx5/build-report.json'
    ref = json.loads(ref_path.read_text(encoding='utf-8'))
    sr = next(v for v in ref['compiled'] if v['name'] == 'str8n-v2-sr')
    offset = 2*32768 + sr['start'] - 0x8000
    sr_data = image[offset:offset+sr['bytes']]
    if len(image) != 98304 or sha(sr_data) != sr['sha256']:
        raise ValueError('Pinned image size or S/R/T compiled bytes mismatch')
    if sr_data[:8] != bytes.fromhex('5352030118000000'):
        raise ValueError('S/R/T descriptor mismatch')
    inc_path = ROOT/'release/candidates/batchfix-r1/source/assembler/str8n-v2-public.inc'
    inc = inc_path.read_text(encoding='utf-8')
    entries = re.findall(r'^STR8V2_RAM_(\w+)\s+EQU\s+\$([0-9A-F]{4})', inc, re.M)
    entries = [(name, addr) for name, addr in entries if name != 'SIGNATURE']
    abi = (ROOT/'docs/bf1/ABI_REFERENCE.md').read_text(encoding='utf-8')
    if len(entries) != 13:
        raise ValueError('Unexpected public call count')
    for name, address in entries:
        if f'| {name} | `${address}` |' not in abi:
            raise ValueError('Missing source-correct ABI table row: '+name)
    chess_root = ROOT/'BUILD/microchess-asm04'
    chess = (chess_root/'microchess.bin').read_bytes()
    source_names = ['microchess.asm', 'microchess-readable.asm', 'symbols.json',
                    'Microchess6502-upstream.txt', 'LICENSE.txt', 'README.md']
    sources = {n: sha((chess_root/n).read_bytes()) for n in source_names}
    present = image.find(chess) >= 0
    result = dict(
        audit_completed=True, distribution_qualified=False,
        finished_utc=datetime.now(timezone.utc).isoformat(),
        image=dict(path=str(image_path), bytes=len(image), sha256=sha(image)),
        reference_sha256=sha(ref_path.read_bytes()),
        sr_table_code=dict(included=True, bytes=len(sr_data), bank=3,
                           address=sr['start'], sha256=sha(sr_data)),
        public_ABI_table=dict(source_sha256=sha(inc_path.read_bytes()),
                              source_matched_entries=len(entries)),
        uchess=dict(included_in_image=present, bytes=len(chess), sha256=sha(chess),
                    source_and_license_files=sources,
                    copyright='Kim-1 MicroChess (c) 1976-2005 Peter Jennings',
                    port_credits=['Daryl Rictor', 'Bill Forster']),
        app_complete_image=present,
        blockers=['UCHESS record/composition and bf1 source/execution qualification pending'] if not present else [],
        platform_package_qualification=dict(Windows='pending', Linux='pending'),
        board_access=False, firmware_modified=False, publication_permitted=False)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(audit_completed=True, public_ABI_entries=len(entries),
                         sr_table_code_included=True, uchess_included=present,
                         distribution_qualified=False)))


if __name__ == '__main__':
    main()
