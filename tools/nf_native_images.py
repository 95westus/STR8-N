"""Prepare reviewed native-utility sectors, retaining target RTC metadata.

Run from the extracted native candidate. This preparer never opens a port.
"""
import argparse
import hashlib
import json
from pathlib import Path

sha = lambda b: hashlib.sha256(b).hexdigest()


def prepare(root, current_b3, out, current_b2=None):
    root, out = Path(root).resolve(), Path(out).resolve()
    catalog = json.loads((root/'NATIVE-COMPONENTS.json').read_text())
    b3 = Path(current_b3).read_bytes()
    b2 = Path(current_b2).read_bytes() if current_b2 else None
    if len(b3) != 32768 or b2 is not None and len(b2) != 32768:
        raise ValueError('Each supplied bank capture must contain exactly 32768 bytes')
    if sha(b3[0x7000:]) != catalog['F_sha256']:
        raise ValueError('Captured B3 does not contain frozen Foundation BASE1/PR05')
    prepared = []
    for item in catalog['targets']:
        bank, address = item['bank'], int(item['address'], 16)
        if bank not in (2, 3) or bank == 3 and address not in (0x8000,0x9000,0xA000,0xB000,0xE000):
            raise ValueError('Catalog contains a protected or invalid target')
        member = (root/item['file']).resolve()
        if not member.is_relative_to(root):
            raise ValueError('Catalog path escapes extracted kit')
        body = member.read_bytes()
        if sha(body) != item['sha256']:
            raise ValueError('Changed candidate component: '+item['file'])
        if item.get('preserve_RTC_metadata'):
            if bank != 3 or address != 0x9000 or len(body) != 3072:
                raise ValueError('Invalid history-code allocation')
            body += b3[0x1C00:0x2000]
        if len(body) != 4096 or address & 4095 or not 0x8000 <= address <= 0xF000:
            raise ValueError('Prepared target is not one aligned 4K sector')
        old = b3[address-0x8000:address-0x7000] if bank == 3 else b2[address-0x8000:address-0x7000] if b2 else None
        prepared.append((item, body, old))
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    (out/'retained-CD-history.bin').write_bytes(b3[0x4000:0x6000])
    plan = dict(status='PREPARED_NO_DEVICE_ACCESS', F_writes=0, direct_C_D_writes=0,
        native_journal_rotations='Possible during admitted replacements; their erase counts are reserved first',
        source_B3_sha256=sha(b3),source_B2_sha256=sha(b2) if b2 else None,
        source_rule='Keep the board idle; recapture/reprepare if its settings, journal or RTC metadata change',
        targets=[])
    for item, body, old in prepared:
        name=f'B{item["bank"]}-{item["address"]}.bin'
        (out/name).write_bytes(body)
        plan['targets'].append(dict(bank=item['bank'],address=item['address'],image=name,
            sha256=sha(body),original_sha256=sha(old) if old is not None else None,
            identical_to_capture=old == body if old is not None else None))
    (out/'install-plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    print('Prepared',out/'install-plan.json','; no port opened, F/C/D are not image targets.')
    return plan


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--current-b3',type=Path,required=True)
    parser.add_argument('--current-b2',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    prepare(args.root,args.current_b3,args.out,args.current_b2)
