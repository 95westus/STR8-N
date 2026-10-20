"""Owner-stopped, RAM-preserving rc1 base/utility/ASM/DBG1 continuing soak.

Copied beside frozen continuing_runner.py, base_runner.py and qualified cases.
No firmware, persistent utility data, clock, trim or preference writes.
"""
import argparse
import hashlib
import importlib
from pathlib import Path
import re
import time
import continuing_runner as continuing
from continuing_runner import *


class Runner(continuing.Runner):
    def __init__(self,workspace,run):
        super().__init__(workspace,run)
        assert self.auth['broader_base_utilities'] and self.auth['all_builtin_BRK_each_unit']
        assert base.SHA(self.run/'continuing_runner.py')==self.auth['continuing_runner_sha256']
        self.units=importlib.import_module('full_units')
        assert base.SHA(self.run/'full_units.py')==self.auth['full_units_sha256']
        self.state.update(runner_sha256=base.SHA(__file__),continuing_runner_sha256=base.SHA(self.run/'continuing_runner.py'),
            workload='rc1 base commands, read-only utilities, varied ASM, DBG1 and all built-in BRK each unit',
            utility_mutations_permitted=False,all_builtin_BRK_each_unit=True)
        for value in self.state['boards'].values():
            value.update(base_command_units=0,utility_units=0,builtin_suite_units=0,base_status_reference=None)

    def recover_idle(self,link):
        self.drain(link);text=link.command('',b'> ')
        line=text.rsplit(b'\n',1)[-1].lstrip(b'\r')
        for prompt,command in ((b'DBG> ','X'),(b'ASM> ','QUIT'),(b'CLOCK> ','Q'),
                               (b'BM> ','Q'),(b'SRAM> ','Q'),(b'WORK> ','Q'),(b'EDU> ','Q')):
            if line==prompt:link.command(command);break
        else:
            if not re.fullmatch(rb'B[0-3]> ',line):
                raise RuntimeError('Unknown context; no reset or blind restoration')
        self.establish(link)

    def cycle(self,board):
        self.transport.plans.package(self.kit)
        continuing.verify_workload(self.run,self.auth)
        n=self.state['boards'][board]['passed_cycles']
        index=continuing.case_index(board,n,len(self.cases));case=self.cases[index]
        out=self.run/board/f'{n:06d}';out.mkdir(parents=True)
        self.status('running',current_board=board,current_unit='rc1/base/utilities/ASM/DBG1/built-in BRK')
        self.marker(board,'rc1-broader-soak-running',application_RAM_restore_pending=True)
        self.publish(self.run/f'{board}-restore-needed.json',dict(needed=True,archive=str(self.run/f'{board}-before'),
            RAM_sha256=hashlib.sha256(self.original[board]).hexdigest()))
        proof=dict(passed=False,board=board,slot=base.BOARDS[board][2],started_utc=base.NOW(),
            native_debugging=False,utility_mutations_permitted=False)
        self.publish(out/'report.json',proof)
        with self.connection(board,out/'serial.jsonl') as link:
            self.establish(link);proof['version']=self.guard(link,board);proof['mode_before']=self.mode(link,board)
            proof['base_utilities'],text=self.units.base_and_utilities(link,self.transport,n)
            (out/'base-utilities.txt').write_bytes(text)
            reference=proof['base_utilities']['base_status_sha256']
            assert set(reference)=={'C','P','W'},'Missing configuration/preference/wear preservation evidence'
            prior=self.state['boards'][board]['base_status_reference']
            assert prior is None or prior==reference,'Configuration/preference/wear status changed'
            proof['targeted']=base.targeted_unit(link,self.transport,self.run,n,*self.case_modules)
            proof['builtins'],text=self.units.builtins_unit(link,self.transport,self.cases,self.run/'builtin-images',n)
            (out/'builtin-BRK.txt').write_bytes(text)
            assert proof['builtins']['passed'] and set(proof['builtins']['services'])==set(range(0x80,0x85))
            proof['ASM'],text=variants.asm_unit(link,self.transport,case);(out/'asm.txt').write_bytes(text)
            proof['debugger']=base.debugger_unit(link,self.transport,self.kit)
            proof['mode_after']=self.mode(link,board);self.guard(link,board)
            proof['RTC'],text=self.clock(link,board);(out/'clock.txt').write_bytes(text)
            if time.monotonic()-self.last_flash[board]>=3600:proof['flash']=self.flash(link,board)
        proof.update(passed=True,finished_utc=base.NOW());self.publish(out/'report.json',proof)
        entry=self.state['boards'][board]
        entry.update(passed_cycles=n+1,breakpoint_hits=16*(n+1),registration_cases_passed=n+1,BRK82_84_cases_passed=n+1,
            latest_receipt=str(out/'report.json'),latest_pass_unix=time.time(),ASM_variants_passed=n+1,
            ASM_variant_indices=sorted(set(entry['ASM_variant_indices']+[index])),
            fixed_BRK_services_passed=list(range(0x80,0x85)),base_command_units=n+1,utility_units=n+1,
            builtin_suite_units=n+1,base_status_reference=reference)
        self.status('running',current_board=None,current_unit=None)
        print('PASS',board,n+1,'rc1 base/utilities/varied ASM/DBG1; all BRK80-84; 16 breakpoint hits',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    worker=Runner(args.workspace,args.run)
    if args.check_only:
        print('PASS broader exact owner authorization, fixture pins, indefinite scope and four-hour drift; no ports');return
    assert not (args.run/'status.json').exists(),'Never restart an existing workload'
    worker.execute()


if __name__=='__main__':main()
