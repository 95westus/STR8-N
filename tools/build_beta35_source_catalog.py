"""Export project-firmware fingerprints for offline beta35 source inspection.

No firmware bytes, board data, vendor image, installer or serial code is exported.
Recognition never authorizes an installation or declares a migration route passed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    assert not args.out.exists()
    catalog={'schema':1,'target_version':'2.0b35','target_generation':47,
             'execution_permitted':False,'source_inspection_only':True,
             'cores':[],'monitors':[],'legacy':[],'provenance':[]}
    seen_core={};seen_monitor={}
    for name in ['v2-beta4','v2-beta28','v2-beta28-b23','v2-beta34-candidate','v2-beta35-candidate']:
        folder=ROOT/'BUILD'/name;meta=json.loads((folder/'build.json').read_text())
        if name=='v2-beta35-candidate':assert sha((folder/'build.json').read_bytes())=='2f5319ab1d7bc751d61bc4b00af225466d83b983bc7e5806a33417940be68365'
        if name=='v2-beta34-candidate':assert sha((folder/'build.json').read_bytes())=='2381688f48a5aa2f0da4c8b8f8fd21cdb2087d521861db813ad0d61c936938b1'
        if name=='v2-beta4':assert sha((folder/'build.json').read_bytes())=='6a354c04e78692099fc52412592bfcb9959d28c18eec76d24919acec60942394'
        core_name='str8n-v2-recovery-f000-ffff.bin';core=(folder/core_name).read_bytes()
        assert len(core)==4096 and sha(core)==meta['artifacts'][core_name]
        core_hash=sha(core);abi=meta['boot_compatibility'];validator=meta['boot']['BOOT_SLOT_CHECK']
        if core_hash not in seen_core:
            row=dict(sha256=core_hash,abi_token=abi,validator_address=validator,source_builds=[])
            seen_core[core_hash]=row;catalog['cores'].append(row)
        seen_core[core_hash]['source_builds'].append(name)
        for page in (0xA0,0xB0):
            filename=f'str8n-v2-recovery-slot-{page:02x}.bin';data=(folder/filename).read_bytes()
            assert sha(data)==meta['artifacts'][filename]
            generation=int.from_bytes(data[8:12],'little');version={13:'2.0b4',40:'2.0b28',46:'2.0b34',47:'2.0b35'}[generation]
            digest=sha(data)
            if digest not in seen_monitor:
                row=dict(sha256=digest,page=page,generation=generation,version=version,
                         abi_token=int.from_bytes(data[20:24],'little'),validator_address=validator,
                         source_builds=[])
                assert row['abi_token']==abi
                seen_monitor[digest]=row;catalog['monitors'].append(row)
            seen_monitor[digest]['source_builds'].append(name)
        catalog['provenance'].append(dict(build=name,metadata_sha256=sha((folder/'build.json').read_bytes())))
    # Bind the published b4 project's core and slots to the actual local release ZIP.
    published=ROOT/'output/release/str8n-v2-b4.zip'
    with zipfile.ZipFile(published) as archive:
        for member,filename in [('str8n-v2-b4-f000-ffff.bin','str8n-v2-recovery-f000-ffff.bin'),
                                ('str8n-v2-b4-slot-a.bin','str8n-v2-recovery-slot-a0.bin'),
                                ('str8n-v2-b4-slot-b.bin','str8n-v2-recovery-slot-b0.bin')]:
            assert archive.read(member)==(ROOT/'BUILD/v2-beta4'/filename).read_bytes()
    catalog['published_b4_zip_sha256']=sha(published.read_bytes())
    legacy=(ROOT/'BUILD/v2-a24c1/str8n-v2-a24c1-f000-ffff.bin').read_bytes()
    assert sha(legacy)=='231fbec1b0e6a1e80f4a956009aa74f6259e4f0dfcf761f09f16755832aece36'
    catalog['legacy'].append(dict(version='beta1/a24c1',normalized_core_sha256=sha(legacy),
                                 normalized_offset=0xFD0,normalized_bytes=16))
    catalog['provenance'].append(dict(build='v2-a24c1',core_sha256=sha(legacy)))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(catalog,indent=2)+'\n')
    print('Exported',len(catalog['cores']),'exact cores,',len(catalog['monitors']),'exact monitors; inspection only')


if __name__=='__main__':main()
