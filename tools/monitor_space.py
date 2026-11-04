"""Verify existing F/monitor/WB1 binaries and report space; no build or board I/O."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(body):
    return hashlib.sha256(body).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked(path, length, expected_hash):
    body = path.read_bytes()
    require(len(body) == length, f'{path}: size mismatch')
    require(digest(body) == expected_hash, f'{path}: hash mismatch')
    return body


def erased(body, first, end):
    require(0 <= first <= end <= len(body), 'Invalid free-space boundaries')
    require(all(value == 255 for value in body[first:end]), 'Non-FF free-space tail')
    return end-first


def report(monitor_manifest=None, workbench_manifest=None):
    dependency = read_json(ROOT/'monitors/base1-dependency.json')
    freeze = read_json(ROOT/'F_FREEZE.json')
    f = checked(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin', 4096, freeze['sha256'])
    require(dependency['foundation']['F_sha256'] == digest(f), 'Foundation pin mismatch')
    for name, expected in freeze['sources'].items():
        require(digest((ROOT/name).read_bytes()) == expected, f'Frozen source changed: {name}')
    f_end = int(freeze['body_end'], 16)-0xF000
    f_free = erased(f, f_end, 0xFE0)
    require(f_free == freeze['usable_tail_bytes'], 'Frozen free-space metadata mismatch')
    rows = [dict(component='F (frozen)', total_bytes=4096, linked_bytes=f_end,
                 reserved_bytes=32, free_bytes=f_free, sha256=digest(f))]

    manifest_path = ROOT/(monitor_manifest or dependency['current_candidate_manifest'])
    monitor = read_json(manifest_path)
    require(monitor['F_sha256'] == digest(f), 'Monitor foundation mismatch')
    variants = set()
    for filename, item in monitor['artifacts'].items():
        body = checked(manifest_path.parent/filename, item['bytes'], item['sha256'])
        variant = item['variant']
        if variant not in ('A', 'B'):
            continue
        require(variant not in variants, 'Duplicate monitor variant')
        variants.add(variant)
        linked = item['linked_bytes']
        require(len(body) == 4096 and body[:3] == b'MI\x01', 'Not an MI/01 sector image')
        require(int.from_bytes(body[12:14], 'little') == linked, 'Header length mismatch')
        origin = 0xA080 if variant == 'A' else 0xB080
        require(int(item['linked_end'], 16) == origin+linked, 'Linked end mismatch')
        rows.append(dict(component=f'MON {variant} g{monitor["generation"]}',
                         total_bytes=4096, linked_bytes=linked, reserved_bytes=128,
                         free_bytes=erased(body, 128+linked, 4096), sha256=digest(body)))
    require(variants == {'A', 'B'}, 'Both monitor variants are required')

    wb_path = ROOT/(workbench_manifest or dependency['current_workbench_manifest'])
    workbench = read_json(wb_path)
    require(workbench['foundation_sha256'] == digest(f), 'WB1 foundation mismatch')
    artifact = workbench['artifact']
    loader = checked(wb_path.parent/artifact['filename'], artifact['bytes'], artifact['sha256'])
    module_info = workbench['module']
    origin = int(module_info['origin'], 16)
    filename = module_info.get('filename', 'WB1-module-5000.bin')
    module = checked(wb_path.parent/filename, module_info['bytes'], module_info['sha256'])
    version = {'WB1': 1, 'WB2': 2}[workbench['interface']]
    require(origin in (0x4000, 0x4800, 0x5000) and origin+len(module) == 0x6400,
            'Invalid module memory extent')
    require(module[:8] == b'MW'+bytes((version, len(module)//256))+b'PR05', 'Module header mismatch')
    require(binascii.crc_hqx(module, 0xffff) == 0, 'Module CRC mismatch')
    require(loader[256:] == module, 'Module load image mismatch')
    linked = module_info['linked_bytes']
    require(int(module_info['linked_end'], 16) == origin+linked, 'Module linked end mismatch')
    rows.append(dict(component=f'{workbench["interface"]} g{workbench["generation"]}', total_bytes=len(module),
                     linked_bytes=linked, reserved_bytes=2,
                     free_bytes=erased(module, linked, len(module)-2), sha256=digest(module)))

    service_sources = {}
    if (monitor_manifest is None and workbench_manifest is None
            and dependency.get('current_service_manifest')):
        service_path = ROOT/dependency['current_service_manifest']
        service = read_json(service_path)
        service_sources = service['source_sha256']
        require(service['F_sha256'] == digest(f), 'Service foundation mismatch')
        name, info = next((n, a) for n, a in service['artifacts'].items() if a['variant'] == 'E')
        extension = checked(service_path.parent/name, info['bytes'], info['sha256'])
        require(extension[:8] == b'MS\x01\x10PR05' and binascii.crc_hqx(extension, 0xffff) == 0,
                'Service header/CRC mismatch')
        rows.append(dict(component=f'E services g{service["generation"]}', total_bytes=len(extension),
                         linked_bytes=info['linked_bytes'], reserved_bytes=2,
                         free_bytes=erased(extension, info['linked_bytes'], len(extension)-2), sha256=digest(extension)))
        name, info = next((n, a) for n, a in service['artifacts'].items() if a['variant'] == 'B2 bundle')
        bundle = checked(service_path.parent/name, info['bytes'], info['sha256'])
        require(bundle[512:512+len(module)] == module, 'Installed bundle/module pair mismatch')

    changed = []
    for name, expected in {**monitor['source_sha256'], **workbench['sources'], **service_sources}.items():
        if digest((ROOT/name).read_bytes()) != expected:
            changed.append(name)
    return dict(basis='existing built binaries; not available owner storage', components=rows,
                source_changes_since_build=sorted(changed), build_performed=False,
                hardware_access=False, F_verified_unchanged=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--monitor-manifest', type=Path)
    parser.add_argument('--workbench-manifest', type=Path)
    args = parser.parse_args()
    print(json.dumps(report(args.monitor_manifest, args.workbench_manifest), indent=2))
