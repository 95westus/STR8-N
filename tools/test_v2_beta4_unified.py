"""Published b4 A/B conversion fixtures and pre-write collision refusals."""
import argparse,json,shutil
from pathlib import Path
import migrate_v2 as u
from migrate_v2_beta4 import record

def fixture(root,page):
    kit=u.ROOT/'BUILD/v2-beta4/kit';u.m.validate_kit(kit)
    banks=[bytearray(b'\xff'*32768) for _ in range(4)]
    banks[3][:8192]=u.m.maintenance_storage(kit)
    for offset,name in ((0x2000,'slot-a'),(0x3000,'slot-b'),(0x6000,'e000-efff'),(0x7000,'f000-ffff')):
        banks[3][offset:offset+4096]=(kit/f'str8n-v2-b4-{name}.bin').read_bytes()
    cfg=bytearray(u.m.default_config());cfg[2]=2;cfg[5]=23
    cfg[7:13]=b'P'+bytes((page,))+(13).to_bytes(4,'little');cfg[14:]=u.m.config_sum(cfg)
    counts=list(range(32));banks[3][0x4000:0x4080]=u.m.metadata(cfg,counts,19)
    banks[3][0x5000:0x5080]=u.m.metadata(cfg,counts,18)
    for bank,offset,name in ((0,0x1000,'MYAPP'),(1,0x6000,'MYDATA'),(2,0x1000,'USER')):
        data=record(b'\x60'+bytes(range(96)),name,0x2000);banks[bank][offset:offset+len(data)]=data
    save(root,banks,page);return banks

def save(root,banks,page):
    p=root/'prior-verified';p.mkdir(parents=True)
    for i,b in enumerate(banks):
        (p/f'b{i}.bin').write_bytes(b);(p/f'b{i}-repeat.bin').write_bytes(b)
    (p/'manifest.json').write_text(json.dumps(dict(board='2604',repeat_verified=True,banks=[dict(sha256=u.sha(b)) for b in banks])))
    (root/'initial-state.json').write_text(json.dumps(dict(active_page=page)))

def main(out):
    out.mkdir(parents=True,exist_ok=False);checks=[]
    for page in (0xA0,0xB0):
        root=out/('active-'+chr(page//16-10+65));banks=fixture(root,page);u.prepare(root,'2604',None)
        plan=u.read(root/'upgrade/plan.json');final=[(root/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
        assert len(plan['steps'])<=24 and plan['source']['version']=='2.0b4'
        assert final[0]==banks[0] and final[1][0x6000:]==banks[1][0x6000:] and final[2][:0x2000]==banks[2][:0x2000]
        assert final[3][0x5000:0x6000]==banks[3][0x5000:0x6000]
        cfg=u.m.journal(final[3])[8:24];assert cfg[:7]==u.m.journal(banks[3])[8:15]
        for b,s in [(r['bank'],r['sector']) for r in plan['steps']]:
            idx=b*8+s-8;assert plan['counts_after'][idx]==plan['counts_before'][idx]+1
        checks.append('Published b4 active '+chr(page//16-10+65)+': inactive-only plan, user records, settings, D journal and counts preserved')
        current=out/('already-current-fallback-'+chr(page//16-10+65));save(current,final,page)
        try:u.prepare(current,'2604',None)
        except ValueError as exc:assert 'Target already installed' in str(exc),str(exc)
        else:raise AssertionError('Already-installed beta25 rewrite accepted')
        assert not (current/'upgrade').exists()
        checks.append('Selected b4 fallback retains the already-installed beta25 target without writes')
    base=[bytearray(b) for b in banks]
    cases=['occupied MAINT','crossing FF record','duplicate CLOCK','modified old MAINT','custom E','autostart service RAM','invalid startup configuration']
    for idx,name in enumerate(cases):
        banks=[bytearray(b) for b in base]
        if idx==0:banks[1][0]=0
        elif idx==1:
            data=record(b'\xff'*200,'CROSS',0x2000);banks[2][0x1FE0:0x1FE0+len(data)]=data
        elif idx==2:
            data=record(b'\x60','CLOCK',0x2000);banks[0][:len(data)]=data
        elif idx==3:banks[3][100]^=1
        elif idx==4:banks[3][0x6100]^=1
        elif idx==5:
            r=u.m.journal(banks[3]);cfg=bytearray(r[8:24]);cfg[1]=1;cfg[3:5]=b'\x00\x65';cfg[14:]=u.m.config_sum(cfg);banks[3][0x4000:0x4080]=u.m.metadata(cfg,list(range(32)),20)
        else:
            r=u.m.journal(banks[3]);cfg=bytearray(r[8:24]);cfg[0]=2;cfg[14:]=u.m.config_sum(cfg);banks[3][0x4000:0x4080]=u.m.metadata(cfg,list(range(32)),20)
        root=out/f'refusal-{idx}';save(root,banks,0xB0)
        try:u.prepare(root,'2604',None)
        except (ValueError,AssertionError):pass
        else:raise AssertionError('Missing refusal: '+name)
        assert not (root/'upgrade').exists();checks.append('No-write refusal: '+name)
    (out/'planning-tests.json').write_text(json.dumps(dict(passed=True,checks=checks,board_access=False),indent=2)+'\n')
    print('\n'.join('PASS '+s for s in checks),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();main(a.out)
