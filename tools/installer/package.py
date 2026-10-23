"""Seal registered candidate images without a chain of earlier installer kits."""
from pathlib import Path
import shutil

from . import capture
from .common import HERE, REGISTRY, board_profile, inventory, safe, save
from .engine import runtime as r, legacy_transport as wire


def cleanup_policy(cap, board):
    identity,banks = capture.validate(cap,board); spec = REGISTRY['cleanup']
    r.require(identity['board']==spec['board'], 'Cleanup is restricted to its board profile')
    rows = []
    for address,name in zip(spec['source_addresses'],spec['source_names']):
        body = banks[0][address-0x8000:address-0x7000]
        r.require(body[:4]==b'SF\1?' and body[6]==1 and body[8:24].rstrip(b'\0')==name.encode(), 'Unexpected demo source')
        header = bytearray(body[:24]); header[3] = 255
        r.require(int.from_bytes(body[24:26],'little')==wire.crc(header), 'Invalid demo header CRC')
        n = int.from_bytes(body[4:6],'little'); data = body[32:32+n]
        r.require(data[:4]==b'AS\1\10' and int.from_bytes(data[4:6],'little')==n-8 and
                  int.from_bytes(data[6:8],'little')==wire.crc(data[8:]), 'Invalid source envelope')
        r.require(body[32+n:]==b'\xff'*(4096-32-n), 'Other owner data in demo sector')
        texts=[]; pos=8
        while pos<len(data):
            size=data[pos+2];texts.append(data[pos+4:pos+4+size].decode('ascii'));pos+=4+size
        r.require(pos==len(data) and any('BRK $01' in t for t in texts) and any('BRK $02' in t for t in texts)
                  and any('ORG $0200' in t for t in texts), 'Unexpected demo contents')
        rows.append(dict(bank=0,address=address,name=name,sha256=r.sha(body)))
    r.require(banks[0][0x4000:]==b'\xff'*0x4000, 'B0:C-F contains owner data')
    return dict(board=identity['board'],usb_serial=identity['usb_serial'],owner_erase=rows,
                all_B0_erased=True,erase_uchess=True,automatic_restore=False)


def create(out, candidate, images, *, board=None, cleanup_capture=None):
    out = Path(out).resolve(); r.require(not out.exists(), 'Fresh kit directory required')
    if board is not None:board_profile(board)
    cleanup = candidate==REGISTRY['cleanup']['candidate']
    base = REGISTRY['cleanup']['base'] if cleanup else candidate
    r.require(base in REGISTRY['candidates'] and base in images and len(images)>=2, 'Target and source images required')
    bodies = {}
    for name,path in images.items():
        r.require(name in REGISTRY['candidates'], 'Unregistered candidate image')
        body = Path(path).read_bytes(); expected = REGISTRY['candidates'][name]
        r.require(len(body)==expected['bytes'] and r.sha(body)==expected['firmware_sha256'], 'Candidate image differs: '+name)
        bodies[name] = body
    policy = cleanup_policy(cleanup_capture,board) if cleanup else None
    r.require(cleanup or cleanup_capture is None, 'Cleanup capture requires the explicit cleanup candidate')
    if policy:
        _,banks = capture.validate(cleanup_capture,board)
        chess = bodies[base][:4096]
        r.require(banks[1][:4096]==chess and chess[:4]==b'SR\1?' and chess[8:24].rstrip(b'\0')==b'UCHESS', 'Unexpected UCHESS sector')
        n=int.from_bytes(chess[6:8],'little');r.require(chess[24+n:]==b'\xff'*(4096-24-n), 'Other UCHESS-sector data')
    out.mkdir(parents=True); (out/'.gitignore').write_text('*\n')
    shutil.copytree(HERE,out/'installer',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (out/'install.py').write_text('from installer.cli import main\nif __name__ == "__main__": main()\n')
    (out/'images').mkdir(); profiles = {}
    owned = REGISTRY['owned_sectors']+([[1,0x8000]] if cleanup else [])
    for name,body in bodies.items():
        key = candidate if name==base else name
        image_file = f'images/{name}.bin'; (out/image_file).write_bytes(body)
        rows=[]
        for bank,address in owned:
            off=(bank-1)*32768+address-0x8000
            data=b'\xff'*4096 if cleanup and name==base and (bank,address)==(1,0x8000) else body[off:off+4096]
            file=f'profiles/{key}/b{bank}-{address:04x}.bin';p=out/file;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            rows.append(dict(bank=bank,address=address,file=file))
        profiles[key]=dict(reference=name,image_file=image_file,firmware_sha256=r.sha(body),sectors=rows,
                           erased_b0=cleanup and name==base)
    guard=REGISTRY['admission_slice'];off=(guard['bank']-1)*32768+guard['address']-0x8000
    prefix=bodies[base][off:off+guard['bytes']]
    r.require(all(body[off:off+guard['bytes']]==prefix for body in bodies.values()), 'RTC immutable code differs')
    (out/'rtc-code.bin').write_bytes(prefix)
    manifest=dict(schema=2,default_target=candidate,generation=REGISTRY['generation'],profiles=profiles,
        admission_slices=[dict(**guard,file='rtc-code.bin')],cleanup=policy,
        board=board,board_access=False,installation_permitted=False,hardware_qualified=False,files=inventory(out))
    save(out/'installer-manifest.json',manifest); validate(out)
    return manifest


def validate(root):
    root=Path(root).resolve();m=r.read(root/'installer-manifest.json')
    if m['board'] is not None:board_profile(m['board'])
    r.require(m['schema']==2 and m['installation_permitted'] is False and m['hardware_qualified'] is False, 'Wrong kit/admission state')
    r.require(inventory(root)==m['files'], 'Changed kit inventory')
    for name,info in inventory(HERE).items():
        r.require(m['files'].get('installer/'+name)==info, 'Installer implementation differs from sealed kit: '+name)
    r.require(m['generation']==50 and m['default_target'] in m['profiles'], 'Wrong target/generation')
    cleanup = m['default_target']==REGISTRY['cleanup']['candidate']
    r.require(bool(m['cleanup'])==cleanup, 'Unexpected owner erase policy')
    if cleanup:
        r.require(m['cleanup']['board']==m['board']==REGISTRY['cleanup']['board'] and
                  m['cleanup']['usb_serial']==REGISTRY['boards'][m['board']]['usb_serial'], 'Cleanup board differs')
        r.require([(x['bank'],x['address'],x['name']) for x in m['cleanup']['owner_erase']]==
                  [(0,a,n) for a,n in zip(REGISTRY['cleanup']['source_addresses'],REGISTRY['cleanup']['source_names'])], 'Cleanup scope differs')
    owned = {tuple(s) for s in REGISTRY['owned_sectors']} | ({(1,0x8000)} if cleanup else set())
    for key,profile in m['profiles'].items():
        ref=profile['reference'];r.require(ref in REGISTRY['candidates'], 'Unregistered firmware')
        r.require(key==ref or cleanup and key==m['default_target'] and ref==REGISTRY['cleanup']['base'], 'Wrong profile identity')
        r.require(profile['erased_b0']==(cleanup and key==m['default_target']), 'Wrong cleanup target')
        r.require({(s['bank'],s['address']) for s in profile['sectors']}==owned and len(profile['sectors'])==len(owned), 'Owned-sector scope differs')
        body=safe(root,profile['image_file']).read_bytes()
        r.require(r.sha(body)==profile['firmware_sha256']==REGISTRY['candidates'][ref]['firmware_sha256'], 'Changed reference image')
        for row in profile['sectors']:
            bank,address=row['bank'],row['address'];off=(bank-1)*32768+address-0x8000
            expected=b'\xff'*4096 if profile['erased_b0'] and (bank,address)==(1,0x8000) else body[off:off+4096]
            r.require(safe(root,row['file']).read_bytes()==expected, 'Changed candidate sector')
    r.require(len(m['admission_slices'])==1, 'RTC admission guard required')
    guard=m['admission_slices'][0]
    r.require({k:guard[k] for k in ('bank','address','bytes')}==REGISTRY['admission_slice'], 'Changed RTC guard scope')
    for profile in m['profiles'].values():
        off=(guard['bank']-1)*32768+guard['address']-0x8000
        r.require(safe(root,guard['file']).read_bytes()==safe(root,profile['image_file']).read_bytes()[off:off+guard['bytes']], 'Changed RTC guard bytes')
    return m
