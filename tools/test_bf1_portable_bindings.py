"""Offline identity, route-replay and recovery refusal tests for a portable kit.

Private local captures are test inputs only and are never copied into the kit.
"""
import argparse
import copy
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'output/qualification'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();kit=a.kit.resolve()
    if a.out.exists():raise ValueError('Preserve earlier receipt')
    sys.path.insert(0,str(kit))
    m=importlib.import_module('migrate');rec=importlib.import_module('recover');r=importlib.import_module('runtime')
    checks=[]
    def passed(name,**kw):checks.append(dict(name=name,passed=True,**kw))
    def refuse(name,fn):
        try:fn()
        except ValueError as error:passed(name,refused=True,reason=str(error))
        else:raise AssertionError('Accepted invalid input: '+name)
    def write_json(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
    def capture(folder,banks,board='board-2512-fixture'):
        folder.mkdir();files={}
        for n,body in enumerate(banks):
            for suffix in ('','-repeat'):
                name=f'b{n}{suffix}.bin';(folder/name).write_bytes(body)
                files[name]=dict(bytes=len(body),sha256=r.sha(body))
        write_json(folder/'capture.json',dict(schema=1,board=board,repeat_verified=True,files=files))
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='bf1-bindings-') as temp:
        temp=Path(temp)
        prior=Q/'bf1-2512-legacy-offline-2026-10-17-r6/v2-0b4-convert'
        source=[(prior/f'source-b{n}.bin').read_bytes() for n in range(4)]
        cap=temp/'source';capture(cap,source)
        escrow=temp/'original-metadata.bin';escrow.write_bytes((Q/'bf1-2512-pre-migration-backup-2026-10-17-r2/b3.bin').read_bytes()[0x1c00:0x2000])
        plan_root=temp/'plan';info=m.prepare_beta4(cap,kit,plan_root,escrow)
        require_expected=json.loads((prior/'plan.json').read_text(encoding='utf-8'))['expected_sha256']
        assert info['expected_sha256']==require_expected
        assert (plan_root/'installer-model-only.s19').read_bytes()==(prior/'installer-model-only.s19').read_bytes()
        m.validate_beta4_plan(plan_root,kit)
        passed('new bound beta4 plan matches CPU-qualified installer and target',fresh_CPU_execution=False)
        target=[(plan_root/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        current=temp/'complete';capture(current,target)
        recovery=rec.prepare_recovery('prepare-forward',kit,plan_root,current,temp/'forward')
        assert recovery['board']=='board-2512-fixture' and recovery['current_capture_manifest_sha256']==r.sha((current/'capture.json').read_bytes())
        passed('completed forward recovery retains original-plan and current-capture bindings')
        assert recovery['write_required'] is False and recovery['transaction'] is None
        assert sorted(p.name for p in (temp/'forward').iterdir())==['.gitignore','plan.json']
        passed('already complete target emits receipt only with no installer or erase plan')
        restoration=rec.prepare_recovery('prepare-restore-beta4',kit,plan_root,current,temp/'restore')
        assert restoration['transaction']['reserved_counts']>=info['transaction']['reserved_counts']
        for n in range(3):assert (temp/f'restore/expected-b{n}.bin').read_bytes()==source[n]
        restored=(temp/'restore/expected-b3.bin').read_bytes()
        assert restored[:0x4000]==source[3][:0x4000] and restored[0x6000:]==source[3][0x6000:]
        passed('completed beta4 restoration preserves payloads and newer conservative wear')
        cut=Q/'bf1-2512-legacy-offline-2026-10-17-r6/v2-0b4-convert-provider-erase-recover'
        cut_banks=[(cut/f'source-b{n}.bin').read_bytes() for n in range(4)]
        cutcap=temp/'cut';capture(cutcap,cut_banks)
        recovered=rec.prepare_recovery('prepare-forward',kit,plan_root,cutcap,temp/'cut-forward')
        assert recovered['admitted_boundaries']
        passed('CPU-attested erased-provider state prepares bound forward recovery',fresh_CPU_execution=False)
        refuse('historical restoration of interrupted target refused',lambda:rec.prepare_recovery('prepare-restore-beta4',kit,plan_root,cutcap,temp/'refused-cut-restore'))
        other=temp/'other-board';capture(other,target,'another-board')
        refuse('cross-board current capture refused',lambda:rec.prepare_recovery('prepare-forward',kit,plan_root,other,temp/'refused-other'))
        partial=list(map(bytearray,cut_banks));partial[2][0x122]^=1
        partialcap=temp/'partial';capture(partialcap,list(map(bytes,partial)))
        refuse('unexplained partial programming refused',lambda:rec.prepare_recovery('prepare-forward',kit,plan_root,partialcap,temp/'refused-partial'))
        original=copy.deepcopy(info)
        def altered_plan(name,edit):
            new=copy.deepcopy(original);edit(new);write_json(plan_root/'plan.json',new)
            try:refuse(name,lambda:m.validate_beta4_plan(plan_root,kit))
            finally:write_json(plan_root/'plan.json',original)
        altered_plan('plan board identity change refused',lambda v:v.update(board='another-board'))
        altered_plan('old unbound plan refused',lambda v:v.update(binding_schema=0))
        altered_plan('alternate kit binding refused',lambda v:v.update(kit_manifest_sha256='0'*64))
        altered_plan('wrong route refused',lambda v:v.update(route='wdcmonv2-to-bf1'))
        altered_plan('unqualified live claim refused',lambda v:v.update(live_execution_qualified=True))
        altered_plan('escaping metadata path refused',lambda v:v['metadata_escrow'].update(file='../original-metadata.bin'))
        altered_plan('changed transaction target config refused',lambda v:v['transaction'].update(target_config='00'*16))
        def flip_file(name,test_name):
            path=plan_root/name;body=path.read_bytes();path.write_bytes(body[:-1]+bytes([body[-1]^1]))
            try:refuse(test_name,lambda:m.validate_beta4_plan(plan_root,kit))
            finally:path.write_bytes(body)
        flip_file('source-capture.json','changed original manifest refused')
        flip_file('metadata-escrow.bin','changed metadata escrow refused')
        flip_file('transfer-00.bin','changed sector transfer refused')
        flip_file('installer-model-only.s19','changed RAM installer refused')
        path=plan_root/'expected-b1.bin';body=path.read_bytes();path.write_bytes(body[:-1]+bytes([body[-1]^1]))
        new=copy.deepcopy(original);new['expected_sha256'][1]=r.sha(path.read_bytes());write_json(plan_root/'plan.json',new)
        try:refuse('self-rehashed altered target still refused by kit route replay',lambda:m.validate_beta4_plan(plan_root,kit))
        finally:path.write_bytes(body);write_json(plan_root/'plan.json',original)
        path=plan_root/'source-b0.bin';body=path.read_bytes();path.write_bytes(body[:-1])
        try:refuse('truncated original bank refused',lambda:m.validate_beta4_plan(plan_root,kit))
        finally:path.write_bytes(body)
        malformed=temp/'bad-board';capture(malformed,source,'../board')
        refuse('malformed explicit board identity refused',lambda:m.capture(malformed))
        no_fallback=list(map(bytearray,target));no_fallback[3][0x201f]=255;no_fallback[3][0x301f]=255
        refuse('cut recovery without valid monitor fallback refused',lambda:r.transaction(no_fallback,no_fallback,bytes.fromhex(info['transaction']['target_config']),'invalid',attested_cut=True))
        refuse('short journal configuration refused',lambda:r.record(b'\0', [0]*32,1))
        refuse('wrong wear-count vector refused',lambda:r.record(source[3][r.latest(source)[1]+8:r.latest(source)[1]+24],[0]*31,1))
        refuse('short bank collection refused',lambda:r.latest(source[:3]))
        command=[sys.executable,'-O',str(kit/'recover.py'),'prepare-forward','--kit',str(kit),'--plan',str(plan_root),'--capture',str(other),'--out',str(temp/'optimized-refusal')]
        result=subprocess.run(command,cwd=temp,capture_output=True,text=True)
        if not (result.returncode!=0 and 'another board' in result.stderr and not (temp/'optimized-refusal').exists()):
            a.out.write_text(json.dumps(dict(passed=False,checks=checks,command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
                board_access=False,scope='Failed optimized CLI test harness; retain evidence before correcting'),indent=2)+'\n',encoding='utf-8')
            raise AssertionError('Optimized CLI result did not reach expected refusal; see saved receipt')
        passed('optimized clean-directory recovery CLI refuses cross-board capture without output',refused=True)
    result=dict(passed=True,cases=len(checks),checks=checks,kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),test_sha256=r.sha(Path(__file__).read_bytes()),
                model_only=True,fresh_CPU_execution=False,live_execution_enabled=False,board_access=False,distribution_qualified=False,
                scope='Bound offline beta4 plan/recovery preparation and refusals, exact qualified forward byte reuse. Factory WDC, transport, recovery CPU execution and platform packages remain pending.')
    a.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS',len(checks),'portable binding/recovery checks; live execution remains disabled')


if __name__=='__main__':main()
