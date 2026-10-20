"""Owner-stopped v1g soak with varied on-board ASM and four-hour drift checkpoints.

The frozen base_runner.py and all input cases live beside this copied runner.
No firmware, persistent settings, or native application mode is modified.
"""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import base_runner as base
import variants

def authorized_duration(auth):
    assert auth['owner_authorized'] and auth['run_until_owner_stop'] and auth['hours'] is None
    assert auth['boards']==list(base.BOARDS) and auth['final_drift_snapshot_authorized']
    assert auth['drift_interval_seconds']==14400
    assert auth['promotion_held'] and not auth['native_debugging'] and not auth['native_applications']
    assert auth['package_manifest_sha256']==base.KIT_SHA
    return float('inf')

def checkpoint_due(next_at,now):
    return now>=next_at

def next_checkpoint(start,number):
    return start+14400*number

def case_index(board,cycle,count):
    return (cycle+(13 if board=='2609' else 0))%count

def valid_snapshot(summary,auth):
    if not summary.get('passed') or any(summary.get(k,True) for k in ('clock_set','trim_changed','flash_written')):return False
    rows=summary.get('boards',[])
    if len(rows)!=2 or {x['board'] for x in rows}!=set(base.BOARDS):return False
    if any(Path(x.get('baseline_index','')).resolve()!=Path(auth['baseline_index']).resolve() or not x.get('application_ram_restored') for x in rows):return False
    row=next(x for x in rows if x['board']=='2609')
    return row.get('measurement_segment')==auth['measurement_segment_2609'] and row.get('original_baseline_replaced') is False

def verify_workload(run,auth):
    """Reject changed fixtures before importing cases or allowing any serial I/O."""
    run=Path(run).resolve();manifest=run/'workload-files.json'
    assert base.SHA(manifest)==auth['workload_manifest_sha256'],'Workload manifest changed'
    pins=base.READ(manifest)['files']
    for name,digest in pins.items():
        path=(run/name).resolve()
        assert path.is_relative_to(run),'Escaping workload fixture: '+name
        assert base.SHA(path)==digest,'Workload fixture changed: '+name
    return len(pins)

base.duration_seconds=authorized_duration
base.AUTHORIZED_HOURS=None

class Runner(base.Runner):
    def __init__(self,workspace,run):
        verify_workload(run,base.READ(Path(run)/'owner-authorization.json'))
        super().__init__(workspace,run)
        self.cases=base.READ(self.run/'asm-cases.json')
        assert len(self.cases)==40 and {s for c in self.cases for s in c['services'] if 0x80<=s<=0x84}==set(range(0x80,0x85))
        assert len({c['name'] for c in self.cases})==len(self.cases)
        assert base.SHA(self.run/'base_runner.py')==self.auth['base_runner_sha256']
        assert base.SHA(self.run/'variants.py')==self.auth['variants_sha256']
        assert base.SHA(self.run/'asm-cases.json')==self.auth['asm_cases_sha256']
        self.state.update(runner_sha256=base.SHA(__file__),base_runner_sha256=base.SHA(self.run/'base_runner.py'),
                          run_until_owner_stop=True,drift_interval_seconds=14400,
                          ASM_sources=40,stop_policy='owner STOP or failure; no automatic restart',checkpoints=[])
        for v in self.state['boards'].values():v.update(ASM_variants_passed=0,ASM_variant_indices=[],fixed_BRK_services_passed=[])

    def cycle(self,board):
        n=self.state['boards'][board]['passed_cycles'];index=case_index(board,n,len(self.cases));case=self.cases[index]
        base.asm_unit=lambda link,transport,kit:variants.asm_unit(link,transport,case)
        super().cycle(board)
        item=self.state['boards'][board]
        item['ASM_variants_passed']+=1
        item['ASM_variant_indices']=sorted(set(item['ASM_variant_indices']+[index]))
        item['fixed_BRK_services_passed']=sorted(set(item['fixed_BRK_services_passed']+[s for s in case['services'] if 0x80<=s<=0x84]))
        self.status('running')

    def checkpoint(self,label,collect=True):
        out=self.run/'checkpoints'/label;out.mkdir(parents=True,exist_ok=False)
        proof=dict(passed=False,label=label,started_utc=base.NOW(),boards={},drift=dict(passed=False),errors=[])
        self.status('checkpoint-restoring',current_checkpoint=label)
        final=base.restore_all(self.original,self.restore);proof['boards']=final
        for board,value in final.items():self.publish(out/(board+'-restoration.json'),value)
        if set(final)==set(base.BOARDS) and all(x['passed'] for x in final.values()):
            if collect:
                try:
                    for name,digest in self.source_pins.items():assert base.SHA(name)==digest,'Snapshot source changed: '+name
                    self.status('checkpoint-drift',current_checkpoint=label)
                    result=subprocess.run([sys.executable,str(self.root/'tools/snapshot_rtc_campaign.py'),'--board','2604','--board','2609'],
                                          cwd=self.root,capture_output=True,text=True)
                    (out/'drift.log').write_text(result.stdout+result.stderr)
                    match=re.search(r'^SNAPSHOT (.+)$',result.stdout,re.M)
                    path=Path(match[1].strip())/'summary.json' if match else None
                    drift=dict(passed=False,returncode=result.returncode,summary=str(path) if path else None)
                    if path and path.exists():
                        summary=base.READ(path)
                        drift.update(passed=result.returncode==0 and valid_snapshot(summary,self.auth),
                                     summary_sha256=base.SHA(path),boards=summary['boards'])
                    proof['drift']=drift
                except BaseException:proof['errors'].append(traceback.format_exc())
                self.publish(out/'drift.json',proof['drift'])
            for board in base.BOARDS:
                try:
                    with self.connection(board,out/(board+'-post-drift.jsonl')) as link:
                        self.establish(link);self.guard(link,board)
                        assert self.transport.read_range(link,0x200,0x200+len(self.original[board])-1)==self.original[board]
                    final[board]['RAM_verified_after_snapshot']=True
                except BaseException:
                    final[board].update(passed=False,RAM_verified_after_snapshot=False)
                    final[board]['errors'].append(traceback.format_exc())
                    self.marker(board,'inspection-required',blocked=True,application_RAM_restore_pending=True)
                    self.publish(self.run/f'{board}-restore-needed.json',dict(needed=True,reason='checkpoint RAM verification failed',archive=str(self.run/f'{board}-before')))
                self.publish(out/(board+'-restoration.json'),final[board]);self.publish(self.run/(board+'-final.json'),final[board])
        proof.update(passed=not proof['errors'] and (not collect or proof['drift']['passed']) and set(final)==set(base.BOARDS)
                     and all(x.get('passed') and x.get('RAM_verified_after_snapshot') for x in final.values()),finished_utc=base.NOW())
        self.publish(out/'report.json',proof)
        self.state['checkpoints'].append(dict(label=label,passed=proof['passed'],receipt=str(out/'report.json'),sha256=base.SHA(out/'report.json')))
        if label=='final':self.publish(self.run/'final-drift-snapshot.json',proof['drift'])
        return proof

    def execute(self):
        self.status('validating-fresh-backups');error=None;started=None;pause_seconds=0;final=None
        assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            for board in base.BOARDS:
                cap=self.run/f'{board}-before';identity,banks=self.transport.plans.capture(cap)
                assert identity['board']==board and identity['usb_serial']==base.BOARDS[board][1] and base.READ(cap/'report.json')['passed']
                self.original[board]=(cap/'application-ram.bin').read_bytes()
                self.flash_hashes[board]=[hashlib.sha256(b).hexdigest() for b in banks];self.last_flash[board]=time.monotonic()
                for sector in base.READ(self.kit/'board-test-manifest.json')['sectors']:
                    offset=sector['address']-0x8000
                    assert banks[sector['bank']][offset:offset+4096]==(self.kit/sector['target']).read_bytes()
            started=time.monotonic();started_unix=time.time();number=1
            self.status('running',started_utc=base.NOW(),started_unix=started_unix,deadline_unix=None,
                        next_drift_unix=started_unix+14400,monitored_seconds=0)
            self.campaign(True)
            while not (self.run/'STOP').exists():
                if checkpoint_due(next_checkpoint(started,number),time.monotonic()):
                    pause_start=time.monotonic();proof=self.checkpoint(f'periodic-{number:06d}')
                    pause_seconds+=time.monotonic()-pause_start
                    if not proof['passed']:raise RuntimeError('Four-hour restoration/drift checkpoint failed; workload stopped')
                    number+=1
                    self.status('running',current_checkpoint=None,next_drift_unix=started_unix+14400*number)
                    self.campaign(True)
                    continue
                for board in base.BOARDS:
                    if (self.run/'STOP').exists() or checkpoint_due(next_checkpoint(started,number),time.monotonic()):break
                    assert base.SHA(self.auth['baseline_index'])==self.auth['baseline_index_sha256']
                    assert base.SHA(self.kit/'board-test-manifest.json')==base.KIT_SHA
                    self.cycle(board)
                    self.state['monitored_seconds']=time.monotonic()-started
                for _ in range(5):
                    if (self.run/'STOP').exists() or checkpoint_due(next_checkpoint(started,number),time.monotonic()):break
                    time.sleep(1)
            self.state['owner_stop_observed']=True
        except BaseException:
            error=traceback.format_exc();self.state['workload_failure']=error;print(error,flush=True)
        finally:
            self.state['monitored_seconds']=0 if started is None else time.monotonic()-started
            self.state['active_workload_seconds']=max(0,self.state['monitored_seconds']-pause_seconds)
            self.state['periodic_checkpoint_seconds']=pause_seconds
            try:final=self.checkpoint('final',collect=not bool(error and self.state['checkpoints'] and not self.state['checkpoints'][-1]['passed']))
            except BaseException:
                self.state['final_checkpoint_failure']=traceback.format_exc()
                fallback=base.restore_all(self.original,self.restore)
                self.state['emergency_restoration']=fallback
            passed=not error and bool(self.state.get('owner_stop_observed')) and final is not None and final['passed']
            self.status('stopped-cleanly' if passed else 'stopped-needs-review',passed=passed,final=final,finished_utc=base.NOW(),next_drift_unix=None)
            self.publish(self.run/'report.json',self.state);self.campaign(False)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            print('END',self.state['state'],self.run/'report.json',flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    runner=Runner(args.workspace,args.run)
    if args.check_only:print('PASS exact indefinite owner authorization, model-qualified sources and four-hour drift policy; no ports');return
    assert not (args.run/'status.json').exists(),'Never restart an existing workload'
    runner.execute()

if __name__=='__main__':main()
