"""Model SAVE/RESTORE of CLOCK against a fresh complete board backup."""
import argparse
import hashlib
import json
from pathlib import Path

import test_v2_rtc_kernel as kernel
from beta4_migration import read_s19
from build_v2_clock import OUT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.root/'prior/manifest.json').read_text())
    assert manifest['repeat_verified']
    banks = [(args.root/f'prior/b{b}.bin').read_bytes() for b in range(4)]
    for bank,data in enumerate(banks):
        assert sha(data)==manifest['banks'][bank]['sha256']
        assert data==(args.root/f'prior/b{bank}-repeat.bin').read_bytes()
    assert banks[2]==bytes([255])*32768, 'B2 is occupied; no automatic allocation'
    meta = json.loads((OUT/'build.json').read_text())
    tests = json.loads((OUT/'test-results.json').read_text())
    assert tests['passed'] and tests['sha256']==meta['sha256']
    body = (OUT/'clock.bin').read_bytes()
    assert sha(body)==meta['sha256'] and len(body)+24<=4096
    cells,entry = read_s19(OUT/'clock.s19')
    assert entry==0x2000 and sha(bytes(cells.values()))==meta['sha256']
    out = args.root/'plan'
    out.mkdir(exist_ok=False)
    cpu,m = kernel.boot(banks)
    for a,v in cells.items():
        m.ram[a] = v
    command = f'S 2 8000 2000 {meta["end"]-1:04X} CLOCK'
    output = kernel.model.command(cpu,(command+'\r').encode(),16000000)
    (out/'model-save.txt').write_bytes(output)
    assert b'Done' in output
    expected_record = b'SR\x01\x3f'+entry.to_bytes(2,'little')+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body
    assert bytes(m.banks[2][:4096])==expected_record+bytes([255])*(4096-len(expected_record))
    assert bytes(m.banks[2][4096:])==banks[2][4096:]
    assert bytes(m.banks[0])==banks[0] and bytes(m.banks[1])==banks[1]
    assert bytes(m.banks[3][:0x4000])==banks[3][:0x4000]
    assert bytes(m.banks[3][0x6000:])==banks[3][0x6000:]
    # RESTORE must recover the original dense artifact, then launch by its label.
    m.ram[0x2000:meta['end']] = bytes(len(body))
    output = kernel.model.command(cpu,b'R 2 CLOCK L\r',16000000)
    assert b'Done' in output and bytes(m.ram[0x2000:meta['end']])==body
    output = kernel.model.command(cpu,b'R CLOCK\r',16000000)
    assert b'CLOCK 1.0' in output and b'CLOCK> ' in output
    kernel.model.command(cpu,b'Q\r',12000000)
    assert not m.bus.writes
    after = [bytes(b) for b in m.banks]
    for bank,data in enumerate(after):
        (out/f'expected-b{bank}.bin').write_bytes(data)
    report = dict(passed=True, board=manifest['board'], command=command,
        sha256=meta['sha256'], s19_sha256=meta['s19_sha256'], app_end=meta['end'],
        prior_hashes=[sha(b) for b in banks], expected_hashes=[sha(b) for b in after],
        save_restore_and_label_launch_passed=True, rtc_data_written=False,
        changed_regions=['B2 sector 8 CLOCK record']+
            (['B3 configuration/wear journal'] if after[3]!=banks[3] else []))
    (out/'model-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',manifest['board'],'exact-backup CLOCK SAVE/RESTORE/label launch; expected four-bank hashes bound')


if __name__=='__main__':
    main()
