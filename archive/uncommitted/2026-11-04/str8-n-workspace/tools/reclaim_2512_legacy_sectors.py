"""Reclaim only owner-selected B0:E/F and B1:E/F; retain current ASM/DBG."""
import argparse
import json
from pathlib import Path
import devtools_2512_session as ds
import nf_opaque as opaque
from journal_rotation_plan import reserve

t=ds.t;Q=ds.Q;ROOT=t.ROOT
MARK=Q/'device-operations/2512.json'
TARGETS=((0,0xe0),(0,0xf0),(1,0xe0),(1,0xf0))
SOURCE_BYTES=Path(__file__).read_bytes()


def plan(out):
    marker=json.loads(MARK.read_text())
    baseline=Q/'2512-utility-retired-20261102-r2'
    before={b:(baseline/f'B{b}-after.bin').read_bytes() for b in range(4)}
    assert {f'B{b}':t.sha(v) for b,v in before.items()}==marker['current_physical_bank_sha256']
    assert not marker['block_snapshot'] and marker['application_ram_restored']
    assert before[0][0x6000:0x7000]==bytes(4096)
    assert before[1][0x6000:0x6004]==b'AP\x01\x01'
    assert b'STR8-N ASM 0.5' in before[1][0x6000:]
    assert before[0][0x2000:0x2008]==before[0][0x4000:0x4008]==b'AP\x02 PR05'
    assert before[0][0x2010:0x2013]==b'ASM' and before[0][0x4010:0x4013]==b'DBG'
    after={b:bytearray(v) for b,v in before.items()};state=before[3];targets=[];operations=[]
    out.mkdir();(out/'.gitignore').write_text('*\n')
    for bank,page in TARGETS:
        off=(page-0x80)*256;old=before[bank][off:off+4096];new=b'\xff'*4096
        assert old!=new
        after[bank][off:off+4096]=new
        state,op=reserve(state,bank*8+(page-0x80)//16)
        assert not op['journal_sector_erases'];operations.append(op)
        name=f'B{bank}-{page:02X}-target.bin';(out/name).write_bytes(new)
        targets.append(dict(bank=bank,page=page,file=name,address=f'B{bank}:{page:02X}00',before_sha256=t.sha(old),sha256=t.sha(new)))
    after[3]=bytearray(state)
    assert after[0][0x2000:0x6000]==before[0][0x2000:0x6000]
    assert after[2]==before[2]
    j0=t.classify_journal(before[3]);j1=t.classify_journal(state)
    for key in ('default','enabled_mask','entries','unknown_mask'):assert j0[key]==j1[key]
    for b,v in before.items():opaque.durable_file(out/f'B{b}-before.bin',v)
    for b,v in after.items():opaque.durable_file(out/f'B{b}-target.bin',v)
    p=dict(board='2512',authorization='remove the older ASM in B1:E/F and reclaim B0:E/F on 2512 too. keep the current ASM and DBG.',
           targets=targets,operations=operations,component_erases=4,journal_erases=0,
           before_bank_sha256={f'B{b}':t.sha(v) for b,v in before.items()},
           after_bank_sha256={f'B{b}':t.sha(v) for b,v in after.items()},journal_before=j0,journal_after=j1,
           current_ASM_sha256=t.sha(before[0][0x2000:0x4000]),current_DBG_sha256=t.sha(before[0][0x4000:0x6000]),
           new_free_bytes=16384,total_erased_bytes=36864,F_writes=0,MON_writes=0,SPI_writes=0)
    t.save(out/'plan.json',p)
    print(f'PASS plan: four erases, no journal erase; sequence {j0["sequence"]}->{j1["sequence"]}; 36 KB erased total',flush=True)


def run(out,scope):
    p=json.loads((scope/'plan.json').read_text())
    assert tuple((v['bank'],v['page']) for v in p['targets'])==TARGETS
    assert p['component_erases']==4 and p['journal_erases']==0
    r=dict(board='2512',passed=False,completed=[],checks=[],erase_requests=0,journal_erases=0,
           automatic_retries=0,F_writes=0,MON_writes=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
           plan_sha256=t.sha((scope/'plan.json').read_bytes()))
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    started=False
    try:
      with ds.escrow(out,r,'2512-owner-selected-legacy-sector-reclamation',window=240,cache_first=0x6b00,cache_end=0x77ff,lease_timeout=300) as x:
        s=x.s
        assert not x.original['block_snapshot']
        assert x.original['current_physical_bank_sha256']==p['before_bank_sha256']
        (out/'driver-as-executed.py').write_bytes(SOURCE_BYTES);t.save(out/'plan.json',p)
        for b in range(4):
            data=s.client.flash(b);assert t.sha(data)==p['before_bank_sha256'][f'B{b}']
            opaque.durable_file(out/f'B{b}-before.bin',data)
        r['checks'].append('fresh-all-bank-preimages-current-ASM-DBG-and-targets-admitted');x.save()
        started=True;x.mark(legacy_reclaim_pending=True,legacy_reclaim_write_worker_active=True)
        x.rec();s.load(writer,t.sha(writer),opaque.PROMPT)
        wire=opaque.Wire(s.link.serial,timeout=90,progress=lambda line:print(line,flush=True))
        for target in p['targets']:
            bank,page=target['bank'],target['page'];old=wire.read_sector(bank,page)
            assert t.sha(old)==target['before_sha256']
            body=(scope/target['file']).read_bytes();assert t.sha(body)==target['sha256'] and body==b'\xff'*4096
            r['erase_requests']+=1;x.save();s.context=None
            assert not wire.replace_sector(bank,page,old,body)
            s.context=opaque.PROMPT;actual=wire.read_sector(bank,page);assert actual==body
            opaque.durable_file(out/f'B{bank}-{page:02X}-after.bin',actual)
            r['completed'].append(target['address']);x.save()
            print('VERIFIED erased '+target['address'],flush=True)
        x.rec();s.service(reader)
        for b in range(4):
            data=s.client.flash(b);assert t.sha(data)==p['after_bank_sha256'][f'B{b}']
            opaque.durable_file(out/f'B{b}-after.bin',data)
        final0=(out/'B0-after.bin').read_bytes()
        assert t.sha(final0[0x2000:0x4000])==p['current_ASM_sha256']
        assert t.sha(final0[0x4000:0x6000])==p['current_DBG_sha256']
        x.expected_b3_sha256=p['after_bank_sha256']['B3'];r['NVM_verified']=True
        r['checks'].append('all-four-targets-erased-current-ASM-DBG-exact-all-other-images-preserved')
        assert t.classify_journal((out/'B3-after.bin').read_bytes())==p['journal_after']
        r['checks'].append('four-durable-wear-reservations-no-journal-erase-settings-preserved')
        s.client.restore_owner(x.ram,x.zp);s.context=t.REC;x.mon()
        assert b'CPU: 65C02' in x.cmd('VERSION')
        apps=x.cmd('APPS');assert b'ASM B0:A000' in apps and b'DBG B0:C000' in apps
        x.cmd('M1');r['checks'].append('current-ASM-DBG-still-advertised-and-MON-functional')
        x.rec();s.service(reader)
        for b in range(4):assert t.sha(s.client.flash(b))==p['after_bank_sha256'][f'B{b}']
        s.client.restore_owner(x.ram,x.zp);s.context=t.REC
      r['passed']=len(r['checks'])==4 and r.get('NVM_verified') and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'))
      t.save(out/'report.json',r);assert r['passed']
    finally:
      if started:
        m=json.loads(MARK.read_text());m.update(legacy_reclaim_write_worker_active=False,legacy_reclaim_pending=not r['passed'],block_snapshot=not r['passed'])
        if r.get('NVM_verified'):
            counts=m['current_tracked_erase_counts'].copy()
            for i,value in enumerate(p['journal_after']['counts']):counts[f'B{i//8}:{i%8+8:X}']=value
            for name,i in zip('ABCDEF',range(26,32)):counts[name]=p['journal_after']['counts'][i]
            m.update(current_physical_bank_sha256=p['after_bank_sha256'],current_tracked_erase_counts=counts,
                     current_wear_counts=p['journal_after']['counts'],current_journal_sequence=p['journal_after']['sequence'],
                     current_journal_valid_records=p['journal_after']['valid_records'],current_valid_journal_records=p['journal_after']['valid_records'])
        if r['passed']:
            m.update(last_legacy_sector_reclamation=str(out/'report.json'),legacy_ASM_B1_E_F_present=False,
                     B0_legacy_E_F_reclaimed=True,total_erased_flash_bytes=36864,current_ASM_preserved=True,current_DBG_preserved=True)
        t.save(MARK,m)
    print('PASS four legacy sectors reclaimed; 36 KB erased total; current ASM/DBG exact; RAM/ZP/cache restored',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','run']);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--scope',type=Path);args=parser.parse_args()
    if args.action=='plan':plan(args.out.resolve())
    else:run(args.out.resolve(),args.scope.resolve())
