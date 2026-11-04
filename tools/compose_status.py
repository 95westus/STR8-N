"""Compose STATUS only into admitted spare extents of an existing B2 image.

The optional legacy-LT replacement must be named explicitly. No port access,
erase engine, F rebuild, vendor firmware, or inferred disposable image.
"""
import argparse,binascii,json
from pathlib import Path
from build_mona import sha

def compose(before,provider,out,replace_legacy_lt=False):
    before=Path(before);provider=Path(provider);out=Path(out)
    assert not out.exists()
    old=before.read_bytes();assert len(old)==32768
    manifest=json.loads((provider/'manifest.json').read_text())
    assert not manifest.get('RAM_trial',False)
    assert old[3:11]==b'WF\x03\x1cPR05'
    assert old[0x300:0x308]==b'MW\x02\x1cPR05'
    assert binascii.crc_hqx(old[0x300:0x1F00],65535)==0
    assert old[0x1F00:0x1F08]==b'SP\x01\x0dPR05'
    assert binascii.crc_hqx(old[0x1F00:0x2C00],65535)==0
    native=old[0x6000:0x6002]==b'RP'
    if native:
        assert not replace_legacy_lt
        assert binascii.crc_hqx(old[0x6000:],65535)==0
        assert old[0x6000:0x6008]==b'RP\x01\x01PR05'
        length=int.from_bytes(old[0x6008:0x600A],'little')
        # Admission is by actual RP body extent, never by an FF-looking tail.
        assert 0x6020+length<=0x7A50
    else:
        assert replace_legacy_lt and old[0x7000:0x7003]==b'LT\x01'
    image=bytearray(old);changes=[]
    for name,artifact in manifest['artifacts'].items():
        address=int(artifact['address'],16);start=address-0x8000
        part=(provider/name).read_bytes()
        assert len(part)==artifact['bytes'] and sha(part)==artifact['sha256']
        assert binascii.crc_hqx(part,65535)==0
        if address!=0xFA50 or native:
            assert old[start:start+len(part)]==b'\xff'*len(part),f'{address:04X} is occupied'
        image[start:start+len(part)]=part
        changes.append(dict(start=f'{address:04X}',bytes=len(part),sha256=sha(part)))
    if native:
        # RP admission covers its whole8K slot. Only its existing checksum changes.
        image[-2:]=binascii.crc_hqx(image[0x6000:-2],65535).to_bytes(2,'big')
        assert binascii.crc_hqx(image[0x6000:],65535)==0
        assert image[0x6000:0x7A50]==old[0x6000:0x7A50]
    else:
        # Do not leave an executable LT signature pointing at a replaced tail.
        # Retain the complete legacy sector in the review archive, not in firmware.
        image[0x7000:0x7A50]=b'\xff'*0xA50
    assert image[0x7FFA:0x7FFE]==old[0x7FFA:0x7FFE]
    assert image[0x300:0x2C00]==old[0x300:0x2C00]
    assert image[0x3000:0x7000]==old[0x3000:0x7000]
    out.mkdir(parents=True)
    (out/'B2-before.bin').write_bytes(old);(out/'B2-STATUS.bin').write_bytes(image)
    sectors=[]
    for n in range(8):
        a=n*4096
        if old[a:a+4096]!=image[a:a+4096]:
            name=f'B2-{8+n:X}-STATUS.bin';(out/name).write_bytes(image[a:a+4096])
            sectors.append(dict(sector=f'B2:{8+n:X}',file=name,old_sha256=sha(old[a:a+4096]),sha256=sha(image[a:a+4096])))
    assert [x['sector'] for x in sectors]==['B2:8','B2:A','B2:F']
    report=dict(status='COMPOSED_NOT_EXECUTION_QUALIFIED',before_sha256=sha(old),after_sha256=sha(image),
                provider_manifest_sha256=sha((provider/'manifest.json').read_bytes()),extents=changes,
                legacy_LT_replacement=replace_legacy_lt,sectors=sectors,F_writes=0,hardware_access=False)
    (out/'composition.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',required=True);p.add_argument('--provider',required=True)
    p.add_argument('--out',required=True);p.add_argument('--replace-legacy-lt',action='store_true');a=p.parse_args()
    compose(a.before,a.provider,a.out,a.replace_legacy_lt)
