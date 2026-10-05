"""Collect existing matching host receipts; never build, test or program a board."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'BUILD'
OUT = BUILD/'v2-b2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = json.loads((OUT/'build.json').read_text())
    ef = OUT/'str8n-v2-b2-e000-ffff.bin'
    backing = OUT/'str8n-v2-b2-b000-bfff.bin'
    hx = BUILD/'v2-b2-command-example/str8n-v2-b2-h-x-c000-cfff.bin'
    help_bin = BUILD/'v2-b2-help-flash/str8n-v2-b2-help-c000-cfff.bin'
    help_s19 = help_bin.with_suffix('.s19')
    ram_s19 = BUILD/'v2-b2-help/str8n-v2-b2-help-2000.s19'
    ef_hash = sha(ef)
    expected = [
        (OUT/'manager-rts-tests.json',9,{'image_sha256':ef_hash}),
        (OUT/'extended-config-tests.json',8,{'image_sha256':ef_hash}),
        (OUT/'service-registration-tests.json',3,
            {'ef_sha256':ef_hash,'manager_storage_sha256':sha(backing)}),
        (OUT/'autoload-tests.json',5,
            {'firmware_sha256':ef_hash,'provider_sha256':sha(hx)}),
        (OUT/'autoload-headless-tests.json',1,
            {'firmware_sha256':ef_hash,'manager_storage_sha256':sha(backing),
             'provider_sha256':sha(hx)}),
        (OUT/'named-command-tests.json',4,
            {'firmware_sha256':ef_hash,'provider_sha256':sha(hx)}),
        (BUILD/'v2-b2-help-flash/help-flash-tests.json',4,
            {'firmware_sha256':ef_hash,'module_sha256':sha(help_bin),
             's19_sha256':sha(help_s19)}),
        (BUILD/'v2-b2-command-example/command-example-tests.json',3,
            {'firmware_sha256':ef_hash,'module_sha256':sha(hx)}),
        (BUILD/'v2-b2-help/help-tests.json',4,
            {'firmware_sha256':ef_hash,'module_sha256':sha(ram_s19)}),
    ]
    receipts = []
    for path,count,hashes in expected:
        receipt = json.loads(path.read_text())
        if len(receipt['passed']) != count or receipt['physical_hardware_tested']:
            raise ValueError(f'Unexpected host receipt: {path}')
        for field,value in hashes.items():
            if receipt.get(field) != value:
                raise ValueError(f'Stale receipt {path}: {field}')
        receipts.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path),
                             passed=receipt['passed']))
    if report['resident_bytes'] != 4039 or report['autoload_bytes'] != 2206 or report['named_command_bytes'] != 666:
        raise ValueError('Unexpected autoload candidate sizes')
    code_paths = [ef, backing, hx, help_bin, help_s19, ram_s19,
                  OUT/'str8n-v2-b2-e000-ffff.s19',OUT/'str8n-v2-b2-b000-bfff.s19',
                  hx.with_suffix('.s19')]
    result = dict(milestone='b2-named-commands',host_check_groups=41,
        board_installed=False,physical_hardware_tested=False,
        core_bytes=4039,core_free=9,core_increase=55,
        code_text_increase=3473,autoload_ram_bytes=79,config_block_bytes=64,
        named_command_ram_bytes=34,manager_ram_increase=34,
        application_ram_bytes=22016,overlay_ram_bytes=2048,
        images={str(p.relative_to(ROOT)):sha(p) for p in code_paths},receipts=receipts)
    target = OUT/'autoload-qualification.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {len(receipts)} matching receipts, 41 host check groups; no board programming')
    print(target)


if __name__ == '__main__':
    main()
