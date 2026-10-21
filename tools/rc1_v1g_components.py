"""Exact programmer slices of the tested v1g image, never board captures."""
import hashlib
import json
from pathlib import Path

IMAGE='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
STEM='str8n-2.0rc1-dbg1-gen50-'
SLICES=[('full-system',0,98304,'B1/B2/B3:$8000-$FFFF',0x8000),
        ('b3-bank-reference',0x10000,32768,'B3:$8000-$FFFF',0x18000),
        ('monitor-a',0x12000,4096,'B3:$A000-$AFFF',0x1a000),
        ('monitor-b',0x13000,4096,'B3:$B000-$BFFF',0x1b000),
        ('b3-f000-ffff',0x17000,4096,'B3:$F000-$FFFF',0x1f000),
        ('asm-e000-efff',0x6000,4096,'B1:$E000-$EFFF',0xe000),
        ('asm-f000-ffff',0x7000,4096,'B1:$F000-$FFFF',0xf000)]
SHA=lambda b:hashlib.sha256(b).hexdigest()


def emit(package,model):
    package=Path(package);firmware=package/'firmware'
    image=(firmware/(STEM+'reference.bin')).read_bytes();assert SHA(image)==IMAGE and len(image)==98304
    assert image[0x1000:0x2000]==b'\xff'*4096, 'B1:9 is not a free reference-image sector'
    files={}
    for kind,offset,size,cpu,device in SLICES:
        name=STEM+kind+'.bin';path=firmware/name;assert not path.exists()
        body=image[offset:offset+size];assert len(body)==size;path.write_bytes(body)
        files[name]=dict(bytes=size,sha256=SHA(body),source_offset=offset,CPU_destination=cpu,full_device_offset=device,
                         complete_full_system=kind=='full-system',preserving_update=False,
                         standalone_bank_launcher=False)
    assert model['passed'] and model['model_only'] and not model['board_access']
    value=dict(passed=True,firmware_sha256=IMAGE,source_reference=STEM+'reference.bin',files=files,
        B0_included=False,private_board_bytes_included=False,firmware_rebuilt=False,
        F_only_has_normal_monitor_or_Jn=False,B3_only_with_opaque_B1_B2_qualified=False,
        erase_only_DBG1_uninstall_supported=False,generic_component_uninstaller_qualified=False,
        component_models_hardware_removal_tested=False,model_checks=model['checks'],
        native_debugging=False,RTC_drift_in_release_qualification=False)
    (firmware/'components.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    verify(package)
    return value


def verify(package):
    firmware=Path(package)/'firmware';manifest=json.loads((firmware/'components.json').read_text())
    image=(firmware/manifest['source_reference']).read_bytes();assert SHA(image)==IMAGE
    assert set(manifest['files'])=={STEM+row[0]+'.bin' for row in SLICES}
    for kind,offset,size,cpu,device in SLICES:
        path=firmware/(STEM+kind+'.bin');body=path.read_bytes();info=manifest['files'][path.name]
        assert body==image[offset:offset+size] and len(body)==size and SHA(body)==info['sha256']
        assert info['CPU_destination']==cpu and info['full_device_offset']==device and info['source_offset']==offset
    assert not any(manifest[k] for k in ('B0_included','private_board_bytes_included','firmware_rebuilt',
        'F_only_has_normal_monitor_or_Jn','B3_only_with_opaque_B1_B2_qualified','erase_only_DBG1_uninstall_supported',
        'generic_component_uninstaller_qualified','component_models_hardware_removal_tested','native_debugging','RTC_drift_in_release_qualification'))
    return dict(passed=True,exact_slices_verified=len(SLICES),board_access=False)
