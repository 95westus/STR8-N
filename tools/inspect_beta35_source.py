"""Identify an archived source for beta35; never plans or performs writes.

Pure stdlib, local bytes only. Exact code fingerprints, slot CRCs and ABI/profile
agreement are required. A familiar compatibility token alone is insufficient.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'release/beta35-prerelease/source-catalog.json'
sha=lambda data:hashlib.sha256(data).hexdigest()


def require(condition,message):
    if not condition:raise ValueError(message)


def identify(banks,active,catalog):
    require(len(banks)==4 and all(len(b)==32768 for b in banks),'Four complete 32768-byte banks required')
    require(catalog['schema']==1 and catalog['execution_permitted'] is False,'Invalid inspection catalog')
    core=banks[3][0x7000:]
    common=dict(target_version='2.0b35',target_generation=47,source_inspection_only=True,
                execution_permitted=False,route_qualified=False,board_access=False,
                bank_sha256=[sha(b) for b in banks],core_sha256=sha(core))
    for legacy in catalog['legacy']:
        start=legacy['normalized_offset'];stop=start+legacy['normalized_bytes']
        normalized=core[:start]+b'\xff'*(stop-start)+core[stop:]
        if sha(normalized)==legacy['normalized_core_sha256']:
            require(active is None,'Legacy source has no A/B active-slot contract')
            return dict(common,source_version=legacy['version'],layout='legacy',
                disposition='legacy-conversion-required',bootable_legacy_fallback_in_AB_layout=False,
                missing_gate='Qualify beta1-to-beta35 layout conversion and full backup restoration')
    known=next((r for r in catalog['cores'] if r['sha256']==sha(core)),None)
    require(known is not None,'Unregistered or altered source core; refuse before planning')
    require(active in (0xA0,0xB0),'Explicit A/B active monitor required for this source')
    slots={}
    for page in (0xA0,0xB0):
        offset=(page-0x80)*256;data=banks[3][offset:offset+4096]
        if data==b'\xff'*4096:
            require(page!=active,'Active monitor is erased')
            slots[page]=None;continue
        require(data[:4]==b'MI\x01'+bytes([page]) and data[31]==0,'Invalid or uncommitted monitor slot')
        require(binascii.crc_hqx(data[:18]+data[32:],0xFFFF)==int.from_bytes(data[18:20],'little'),
                'Monitor checksum mismatch')
        monitor=next((r for r in catalog['monitors'] if r['sha256']==sha(data) and r['page']==page),None)
        require(monitor is not None,'Unregistered monitor code, even if its checksum is valid')
        require(monitor['abi_token']==known['abi_token'] and monitor['validator_address']==known['validator_address'],
                'Registered monitor/core ABI profile mismatch')
        slots[page]=monitor
    source=slots[active];inactive=active^0x10
    installed=any(s and s['version']=='2.0b35' for s in slots.values())
    disposition=('target-monitor-present-reconcile-assets' if installed else 'target-specific-planner-required')
    return dict(common,source_version=source['version'],source_generation=source['generation'],layout='AB',
        active_page=active,inactive_page=inactive,core_source_builds=known['source_builds'],
        validator_address=known['validator_address'],abi_token=known['abi_token'],
        monitors={f'{p:02X}':None if m is None else {k:m[k] for k in ('version','generation','sha256')} for p,m in slots.items()},
        target_monitor_present=installed,disposition=disposition,
        missing_gate='Target-owned preserving layout planner, both active slots, occupied-range refusal and restore qualification')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--banks-dir',required=True,type=Path)
    p.add_argument('--prefix',default='b')
    p.add_argument('--active',choices=['A','B'])
    p.add_argument('--catalog',type=Path,default=CATALOG)
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    require(not args.out.exists(),'Choose a new inspection report path')
    require('/' not in args.prefix and '\\' not in args.prefix and ':' not in args.prefix,'Prefix must be a file-name prefix')
    banks=[(args.banks_dir/f'{args.prefix}{i}.bin').read_bytes() for i in range(4)]
    catalog=json.loads(args.catalog.read_text())
    result=identify(banks,None if args.active is None else {'A':0xA0,'B':0xB0}[args.active],catalog)
    result['catalog_sha256']=sha(args.catalog.read_bytes())
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
