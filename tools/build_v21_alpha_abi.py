"""Build the offline uniform ABI module; no board access or beta32 mutation."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
import build_v2_config as compiler
from build_bank_maint_v2 import long_branches

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/v2.1-alpha'
OUT=ROOT/'BUILD/v2.1-alpha/abi'
sha=lambda data:hashlib.sha256(data).hexdigest()

def registry(path=SOURCE/'abi-services.json'):
    data=json.loads(path.read_text());services=data['services'];names=set()
    core=(ROOT/'src/v2-beta4/str8n-v2-public.inc').read_text()
    call_targets={int(value,16) for name,value in re.findall(r'^(STR8V2_RAM_\w+)\s+EQU\s+\$([0-9A-F]{4})\s*$',core,re.M) if name!='STR8V2_RAM_SIGNATURE'}
    call_targets.update([0x5003,0x6504,0x6507,0x650A,0x650D,0x6514,0x664A,0x66A6])
    if data['format']!=1 or not 1<=len(services)<=31:raise ValueError('Unsupported directory format/count')
    for n,s in enumerate(services,1):
        if s['id']!=n or s['name'] in names:raise ValueError('Service IDs must be dense; names unique')
        names.add(s['name'])
        if not 1<=s['version']<=255 or s['sv_mask'] not in (0,1,2,4,8) or s['kind'] not in ('call','data'):raise ValueError('Invalid service contract')
        ops=s['operations'];seen=set()
        if not 1<=len(ops)<=127:raise ValueError('Invalid operation count')
        for i,op in enumerate(ops,1):
            if op['id']!=i or op['name'] in seen:raise ValueError('Operation IDs must be dense; names unique')
            seen.add(op['name']);target=op['target']
            if target=='ABI_SYSTEM_QUERY':
                if s['kind']!='call':raise ValueError('Query must be callable')
            elif int(target,0) not in ({0x7E00,0x7E10} if s['kind']=='data' else call_targets):raise ValueError('Target is not an audited public interface')
        signature=s.get('signature')
        if s['sv_mask'] and not signature:raise ValueError('Optional service needs a signature')
        if signature and (len(bytes.fromhex(signature['hex']))!=4 or not 0x0200<=int(signature['address'],0)<=0x7EFC):raise ValueError('Invalid signature')
    return data

def build(base=0x2000,out=OUT):
    if not 0x0200<=base<=0x6000:raise ValueError('Offline test origin outside application RAM')
    data=registry();out.mkdir(parents=True,exist_ok=True);stage=out/'source';stage.mkdir(exist_ok=True);(out/'asm').mkdir(exist_ok=True)
    for name in ['build.json','test-results.json','abi-directory.bin']:(out/name).unlink(missing_ok=True)
    text=long_branches((SOURCE/'abi-directory.asm').read_text())
    (stage/'abi-directory.asm').write_text(text)
    signatures=[];rows=[];ops=[];public=['; Generated alpha IDs; not yet a frozen public release.']
    for s in data['services']:
        signature=s.get('signature');index=0
        if signature:signatures.append(signature);index=len(signatures)
        rows += [f'        DB {s["version"]},{s["sv_mask"]},{index},{int(s["kind"]=="data")},{len(s["operations"])},0',f'        DW ABI_OPS_{s["id"]}']
        ops.append(f'ABI_OPS_{s["id"]}:')
        public.append(f'ABI_SERVICE_{s["name"]} EQU ${s["id"]:02X}')
        for op in s['operations']:
            target=op['target'];ops.append('        DW '+(target if target=='ABI_SYSTEM_QUERY' else f'${int(target,0):04X}'))
            public.append(f'ABI_{s["name"]}_{op["name"]} EQU ${op["id"]:02X}')
    lines=[f'ABI_SERVICE_COUNT EQU {len(data["services"])}','ABI_RECORDS:']+rows+ops+['ABI_SIGNATURES:']
    for sig in signatures:lines += [f'        DW ${int(sig["address"],0):04X}','        DB '+','.join('$'+sig['hex'][i:i+2] for i in range(0,8,2))]
    (stage/'abi-records.inc').write_text('\n'.join(lines)+'\n');(out/'abi-ids.inc').write_text('\n'.join(public)+'\n')
    compiler.OUT=out;compiler.SOURCE=stage
    cells,symbols=compiler.assemble('abi-directory',base,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    end=symbols['ABI_END'];body=compiler.dense_image(cells,base,end)
    assert end<=0x6500 and symbols['ABI_HEADER']==base and len(body)<=1024
    (out/'abi-directory.bin').write_bytes(body)
    metadata=dict(version='2.1a1-abi-foundation',base=base,end=end,bytes=len(body),sha256=sha(body),symbols=symbols,
        header_bytes=16,records_bytes=len(data['services'])*8,operation_bytes=sum(len(s['operations'])*2 for s in data['services']),signature_bytes=6*len(signatures),
        scratch_zero_page_start=0xD0,scratch_zero_page_bytes=8,result_bytes=24,additional_persistent_ram_bytes=0,
        offline_test_image_ram_bytes=len(body),permanent_anchor_assigned=False,resident_integration=False,hardware_tested=False,
        registry_sha256=sha((SOURCE/'abi-services.json').read_bytes()),source_sha256=sha((SOURCE/'abi-directory.asm').read_bytes()))
    (out/'build.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f'BUILT offline ABI foundation: {len(body)} bytes; 8 scratch ZP bytes; 24 caller-owned result bytes; no permanent anchor or flash image')
    return metadata

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=lambda s:int(s,0),default=0x2000);p.add_argument('--out',type=Path,default=OUT);a=p.parse_args();build(a.base,a.out)
