"""Direct-WDC plan admission/tamper checks; private fixtures never leave Q/tmp."""
import argparse,copy,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kit',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    kit=a.kit.resolve();assert not a.out.exists();sys.path.insert(0,str(kit))
    import factory_wdc as f;import runtime as r;import migrate as m
    prior=Q/'bf1-2609-windows-offline-2026-10-18-r1';checks=[]
    def passed(name,**more):checks.append(dict(name=name,passed=True,**more))
    def refuse(name,call):
        try:call()
        except (ValueError,OSError,KeyError):passed(name,refused=True)
        else:raise AssertionError('Invalid factory input admitted: '+name)
    def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='bf1-factory-bindings-',dir=ROOT/'tmp') as tmp:
        tmp=Path(tmp);plan_root=tmp/'bound-plan'
        info=f.prepare(prior/'model-only-WDC-capture',kit,plan_root,prior/'tracked-history.json',prior/'private-metadata-escrow.bin')
        plan,source,target=f.validate_plan(plan_root,kit)
        old=r.read(prior/'original-816-to-bf1/plan.json')
        assert info['transaction']==old['transaction'] and info['expected_sha256']==old['expected_sha256']
        assert (plan_root/'installer-model-only.s19').read_bytes()==(prior/'original-816-to-bf1/installer-model-only.s19').read_bytes()
        assert all((plan_root/f'transfer-{n:02d}.bin').read_bytes()==(prior/f'original-816-to-bf1/transfer-{n:02d}.bin').read_bytes() for n in range(len(plan['transaction']['operations'])))
        passed('Bound 816 plan re-derives exact prior CPU-executed installer, transaction, target and every transfer',fresh_CPU_execution=False)
        assert source[0]==target[0] and source[:3]!=target[:3]
        assert info['transaction']['no_lifetime_wear_claim']
        passed('Original B0 remains identical and tracked wear is not presented as lifetime history')
        original=copy.deepcopy(info)
        def altered(name,edit):
            changed=copy.deepcopy(original);edit(changed);save(plan_root/'plan.json',changed)
            try:refuse(name,lambda:f.validate_plan(plan_root,kit))
            finally:save(plan_root/'plan.json',original)
        for name,edit in [
            ('unbound schema',lambda x:x.update(binding_schema=0)),
            ('wrong route',lambda x:x.update(route='beta4-to-bf1')),
            ('changed board',lambda x:x.update(board='another-board')),
            ('wrong CPU entry',lambda x:x.update(source_cpu='65C02')),
            ('changed entry address',lambda x:x.update(entry=0x2000)),
            ('different kit',lambda x:x.update(kit_manifest_sha256='0'*64)),
            ('invented live qualification',lambda x:x.update(live_execution_qualified=True)),
            ('installation enabled flag',lambda x:x.update(installation_permitted=True)),
            ('escaping history path',lambda x:x['source_history'].update(file='../tracked-history.json')),
            ('escaping metadata path',lambda x:x['metadata_escrow'].update(file='../metadata.bin')),
            ('different factory template',lambda x:x.update(factory_template_manifest_sha256='0'*64)),
            ('different app record binding',lambda x:x.update(app_record_sha256='0'*64)),
            ('changed wear interpretation',lambda x:x.update(wear_baseline_origin='Lifetime erase counts')),
            ('changed target config',lambda x:x['transaction'].update(target_config='00'*16)),
            ('changed recorded counts',lambda x:x['transaction']['reserved_counts'].__setitem__(0,99)),
        ]:altered(name,edit)
        def corrupt(name,path):
            saved=path.read_bytes();changed=bytearray(saved);changed[len(changed)//2]^=1;path.write_bytes(changed)
            try:refuse(name,lambda:f.validate_plan(plan_root,kit))
            finally:path.write_bytes(saved)
        for name in ('source-capture.json','source-b0.bin','source-b3.bin','expected-b1.bin','source-history.json','metadata-escrow.bin','installer-model-only.s19','transfer-00.bin','transfer-01.bin'):
            corrupt('tampered '+name,plan_root/name)
        extra=plan_root/'transfer-99.bin';extra.write_bytes(bytes(4096))
        refuse('unexpected extra transfer',lambda:f.validate_plan(plan_root,kit));extra.unlink()
        body=(plan_root/'transfer-00.bin').read_bytes();(plan_root/'transfer-00.bin').unlink()
        refuse('missing transfer',lambda:f.validate_plan(plan_root,kit));(plan_root/'transfer-00.bin').write_bytes(body)
        # Explicit acknowledgement is required when no prior wear escrow exists.
        refuse('factory unknown history requires acknowledgement',lambda:f.prepare(prior/'model-only-WDC-capture',kit,tmp/'no-ack'))
        fresh=f.prepare(prior/'model-only-WDC-capture',kit,tmp/'fresh',accept_unknown_history=True)
        f.validate_plan(tmp/'fresh',kit)
        assert fresh['source_history'] is None and fresh['metadata_escrow'] is None
        assert fresh['transaction']['counts_before']==[0]*32 and fresh['transaction']['no_lifetime_wear_claim']
        assert 'previous physical erase history is unknown' in fresh['wear_baseline_origin']
        passed('No-escrow factory preparation uses an explicitly acknowledged new tracked baseline only')
        save(tmp/'another-history.json',dict(r.read(prior/'tracked-history.json'),board='another-board'))
        refuse('foreign-board history',lambda:f.prepare(prior/'model-only-WDC-capture',kit,tmp/'foreign',tmp/'another-history.json'))
        seed=r.read(prior/'tracked-history.json');seed['sequence']=-1;save(tmp/'bad-sequence.json',seed)
        refuse('negative history sequence',lambda:f.prepare(prior/'model-only-WDC-capture',kit,tmp/'negative',tmp/'bad-sequence.json'))
        command=[sys.executable,'-O',str(kit/'user_cli.py'),'verify-plan','--plan',str(plan_root)]
        result=subprocess.run(command,cwd=tmp,capture_output=True,text=True)
        assert result.returncode==0 and 'PASS bound offline plan' in result.stdout
        passed('Actual isolated-directory CLI verifies factory plan under Python -O without ports')
        bad=copy.deepcopy(original);bad['source_cpu']='65C02';save(plan_root/'plan.json',bad)
        result=subprocess.run(command,cwd=tmp,capture_output=True,text=True)
        assert result.returncode!=0 and 'CPU/profile mismatch' in result.stderr
        passed('Actual -O CLI refuses changed CPU/profile before any serial transport')
    # Non-factory runtime inputs must be byte-identical to the prior prototype.
    previous=ROOT/'tmp/bf1-distribution-r10/migration'
    before=r.read(previous/'kit-manifest.json');after=r.read(kit/'kit-manifest.json')
    differences=[n for n in set(before['files'])|set(after['files']) if before['files'].get(n)!=after['files'].get(n)]
    assert set(differences)=={'factory_wdc.py','user_cli.py'}
    passed('All prior payload/template/runtime/beta4/recovery inputs unchanged; only factory validation and CLI differ')
    a.out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,board_access=False,hardware_qualified=False,
        kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),test_sha256=r.sha(Path(__file__).read_bytes()),
        prior_CPU_proof=str(prior/'report.json'),prior_CPU_proof_sha256=r.sha((prior/'report.json').read_bytes()),
        reused_prior_CPU_execution_by_exact_installer_and_transfer_equality=True,changed_runtime_files=differences,
        live_execution_enabled=False,distribution_qualified=False),indent=2)+'\n')
    print('PASS',len(checks),'factory plan binding checks; no board access; prior CPU execution reused by exact bytes')

if __name__=='__main__':main()
