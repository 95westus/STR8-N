"""Finalize existing transfer candidates; no assembler, port or F operation."""
import argparse,binascii,json
from pathlib import Path
from build_mona import ROOT,sha
from status_extents import preserve_text


def pack(out,services,storage,overlay,status):
    out,services,storage,overlay,status=map(lambda p:Path(p).resolve(),(out,services,storage,overlay,status))
    if out.exists():raise ValueError('Fresh output directory required')
    sources={k:json.loads((p/'manifest.json').read_text()) for k,p in dict(services=services,storage=storage,overlay=overlay).items()}
    def artifact(k,where,name):
        body=(where/name).read_bytes();assert sha(body)==sources[k]['artifacts'][name]['sha256'];return body
    b2name=next(n for n,v in sources['services']['artifacts'].items() if v['variant']=='B2 bundle')
    bundle=artifact('services',services,b2name)
    bundle=bytearray(preserve_text(bundle,status))
    # The bootstrap is unchanged gC code; retain its code generation rather
    # than erase B2:8 only to change the grouping number. E is independently gD.
    bundle[11:15]=(12).to_bytes(4,'little');bundle=bytes(bundle)
    storage_name='STR8N-STORAGE-g00000002-flash.bin'
    bank=artifact('storage',storage,storage_name)
    extension=artifact('overlay',overlay,'S19-STORE-6B00.bin')
    assert bank[0x2900:0x2F00]==b'\xff'*1536
    assert int.from_bytes(bank[8:10],'little')+32<=0x2900
    packed=bytearray(bank);packed[0x2900:0x2F00]=extension
    packed[-2:]=binascii.crc_hqx(packed[:-2],65535).to_bytes(2,'big');packed=bytes(packed)
    assert binascii.crc_hqx(packed,65535)==0
    assert packed[:0x2000]==bank[:0x2000] and packed[:0x2900]==bank[:0x2900]
    ename=next(n for n,v in sources['services']['artifacts'].items() if v['variant']=='E')
    dispatcher=artifact('services',services,ename)
    out.mkdir(parents=True);artifacts={}
    for name,data in [('TRANSFER-SERVICES-E.bin',dispatcher),('TRANSFER-B2-8000.bin',bundle),('STORAGE-g2-transfer-r1.bin',packed)]:
        (out/name).write_bytes(data);artifacts[name]=dict(bytes=len(data),sha256=sha(data))
    report=dict(status='PREPARED_NOT_INSTALLED',F_rebuilt=False,CPU_simulations=0,build_passes=0,
        inputs={k:str(p/'manifest.json') for k,p in dict(services=services,storage=storage,overlay=overlay).items()},
        status_manifest=str(status),artifacts=artifacts,
        STATUS_text_extents_preserved=['8040-80FF','8240-82FF'],bootstrap_generation='0000000C',
        services_generation='0000000D',PROGRAM_generation='00000003',storage_library_generation='00000002',
        extension_flash='B1:D900-DEFF; existing RP padding; library code/header unchanged',
        required_image_changes=['B1:D','B2:9','B2:A (preserve STATUS AC00-AFFF)','B3:E'])
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('out','services','storage','overlay','status'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();pack(a.out,a.services,a.storage,a.overlay,a.status)
