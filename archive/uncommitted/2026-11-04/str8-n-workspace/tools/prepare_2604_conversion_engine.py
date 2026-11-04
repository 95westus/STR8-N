"""Serialize a review-only 2604 conversion using the unchanged qualified engine."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'release/str8nf-v0.2.0/migration-host')]
from installer.engine import runtime as r
from installer.engine.legacy_transport import read_s19,fnv
from nf_migrate import classify_journal,valid_snapshot

SCOPE=ROOT/'output/qualification/2604-foundation-rollout-scope-20261102-r1'
OUT=SCOPE/'conversion-engine-review'
TEMPLATE=ROOT/'tools/installer/engine/template'


def run():
    plan=json.loads((SCOPE/'plan.json').read_text())
    assert plan['board']=='2604' and plan['total_erases']==27 and plan['F_replacements']==1
    banks=[(SCOPE/f'B{n}-original.bin').read_bytes() for n in range(4)]
    state=list(map(bytearray,banks));ops=[];data=[]
    def append(kind,bank,address,body,commit):
        before=r.hashes(state);offset=address-0x8000
        state[bank][offset:offset+len(body)]=body
        ops.append(dict(kind=kind,bank=bank,address=address,commit_address=commit,
            source_sha256=before,after_sha256=r.hashes(state),data_sha256=r.sha(body)))
        data.append(body)
    address=int(plan['legacy_reservation_address'],16)
    row=(SCOPE/'legacy-reservation-128.bin').read_bytes();assert len(row)==128
    assert state[3][address-0x8000:address-0x8000+256]==b'\xff'*256
    append('reserve-old-WC-conversion-erases',3,address,row,address+127)
    for item in plan['conversion']:
        address=int(item['address'],16);body=(SCOPE/item['file']).read_bytes()
        assert r.sha(body)==item['sha256'] and r.sha(state[3][address-0x8000:address-0x8000+4096])==item['before_sha256']
        if address!=0xf000:assert valid_snapshot(body[:256]) and item['commit_address']==address+255
        else:assert r.sha(body)==plan['target_F_sha256'] and item['commit_address'] is None
        append('conversion-sector',3,address,body,item['commit_address'])
    final=classify_journal(state[3]);assert final['kind']=='valid-snbt' and final['default']=='S'
    assert final['sequence']==plan['source_inspection']['sequence']+3
    assert final['counts']==[int.from_bytes(row[24+3*i:27+3*i],'little') for i in range(32)]
    for i in range(3):assert bytes(state[i])==banks[i]
    assert state[3][:0x4000]==banks[3][:0x4000] and state[3][0x6000:0x7000]==banks[3][0x6000:0x7000]
    tx=dict(label='2604 exact rc1 g0034 WC-to-SNBT; review only',source_sha256=r.hashes(banks),
        expected_sha256=r.hashes(state),operations=ops,reservation_offset=int(plan['legacy_reservation_address'],16)-0x8000,
        counts_before=plan['source_inspection']['counts'],reserved_counts=final['counts'],
        sequence_before=plan['source_inspection']['sequence'],sequence_after=final['sequence'],
        model_only=True,installation_permitted=False)
    info=r.compose(TEMPLATE,OUT,banks,tx,data,list(map(bytes,state)))
    template,entry=read_s19(TEMPLATE/'integrated-template.s19')
    composed,after_entry=read_s19(OUT/'installer-model-only.s19')
    mf=json.loads((TEMPLATE/'manifest.json').read_text())
    assert entry==after_entry==0x2000 and set(template)==set(composed)
    allowed={mf['count'],mf['commit_after']}
    for key,length in [('banks',24),('commits',24),('commit_addresses',96),('commit_values',24),('table',216)]:
        allowed.update(range(mf[key],mf[key]+length))
    allowed.update(range(0x3500,0x3516));allowed.update(range(0x3600,0x3700))
    differences=[a for a in template if template[a]!=composed[a]]
    assert set(differences)<=allowed,'Unexpected executable/template change'
    assert composed[mf['count']]==3 and composed[mf['commit_after']]==0
    for n,op in enumerate(ops[1:]):
        transfer=(OUT/f'transfer-{n:02d}.bin').read_bytes()
        expected=bytearray(transfer);commit=op['commit_address']
        if commit is not None:
            assert transfer[255]==255 and composed[mf['commit_values']+n]==0
            assert bytes(composed[mf['commit_addresses']+n*4+i] for i in range(4))==commit.to_bytes(2,'little')+b'\0\0'
            expected[255]=0
        else:assert composed[mf['commits']+n]==0
        assert r.sha(expected)==op['data_sha256']
    # Independently reconstruct each source-bank guard from the saved state.
    check=list(map(bytearray,banks));check[3][tx['reservation_offset']:tx['reservation_offset']+128]=row
    for n,op in enumerate(ops[1:]):
        at=mf['table']+9*n;transfer=(OUT/f'transfer-{n:02d}.bin').read_bytes()
        table=bytes(composed[at+i] for i in range(9))
        assert table==bytes([op['address']>>8])+fnv(check[op['bank']]).to_bytes(4,'little')+fnv(transfer).to_bytes(4,'little')
        offset=op['address']-0x8000;check[op['bank']][offset:offset+4096]=data[n+1]
    assert check==state
    proof=dict(passed=True,kind='host serialization/static guard review; no CPU execution',board_access=False,
        firmware_builds=0,CPU_simulations=0,template_sha256=r.sha((TEMPLATE/'integrated-template.s19').read_bytes()),
        unchanged_executable_bytes=True,only_reviewed_plan_tables_and_WC_reservation_changed=True,
        changed_addresses=[f'{a:04X}' for a in differences],conversion_erases=3,
        initial_WC_reservation=f'B3:{int(plan["legacy_reservation_address"],16):04X}',
        erase_order=[f'B{op["bank"]}:{op["address"]:04X}' for op in ops[1:]],
        SNBT_commit_last=True,F_binary_exact=True,post_conversion_journal=final,
        installer_sha256=info['installer_sha256'],execution_authorized=False,
        limits='Legacy S19/G was live-tested; this exact conversion transaction has not run on hardware. Physical reset required after engine completion.')
    (OUT/'static-review.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:proof[k] for k in ('passed','kind','unchanged_executable_bytes','erase_order','installer_sha256','execution_authorized')},indent=2))


if __name__=='__main__':run()
