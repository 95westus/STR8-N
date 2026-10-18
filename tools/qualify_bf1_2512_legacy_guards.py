"""Adversarial admission tests for the separately modeled 2512 legacy routes."""
import argparse,json
from pathlib import Path
import plan_bf1_2512_legacy as p

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plans',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists()
    prior=p.read(a.plans/'report.json');assert prior['passed'] and prior['planner_sha256']==p.sha(Path(p.__file__).read_bytes())
    checks=[]
    def refused(name,action):
        try:action()
        except (AssertionError,ValueError):checks.append(dict(name=name,passed=True,refused=True))
        else:raise AssertionError('Invalid input admitted: '+name)
    for kind,key in [('wdcmonv2','wdcmonv2'),('v2.0b4','v2-0b4')]:
        stage=a.plans/(key+'-stage-source');banks=[(stage/f'b{n}.bin').read_bytes() for n in range(4)];plan=p.read(a.plans/(key+'-convert')/'plan.json')
        assert p.hashes(banks)==plan['source_sha256'];desired=p.target_destination(banks);cfg=bytes.fromhex(plan['transaction']['target_config'])
        for offset,label in [(0x7123,'unknown-F'),(0x6123,'unknown-E'),(0x2123,'unknown-source-A')]:
            bad=list(map(bytearray,banks));bad[3][offset]^=1;refused(key+'-'+label,lambda:p.admit_source(kind,list(map(bytes,bad))))
        for bank,offset,label in [(1,0x3000,'occupied-CLOCK'),(2,0x100,'occupied-provider')]:
            bad=list(map(bytearray,banks));bad[bank][offset]=0;refused(key+'-'+label,lambda:p.admit_source(kind,list(map(bytes,bad))))
        seq,off,row,valid=p.latest(banks)
        bad=list(map(bytearray,banks));bad[3][off+120]^=1;refused(key+'-torn-WC',lambda:p.admit_source(kind,list(map(bytes,bad))))
        # Every transaction reserves an erase of the opposite journal sector.
        retained=off//4096+8;index=3*8+(25-retained)-8
        counts=list(plan['transaction']['counts_before']);counts[index]=0xffffff
        bad=list(map(bytearray,banks));bad[3][off:off+128]=p.record(row[8:24],counts,seq)
        refused(key+'-wear-exhausted',lambda:p.transaction(bad,desired,cfg,'must refuse'))
        counts=list(plan['transaction']['counts_before']);bad=list(map(bytearray,banks));bad[3][off:off+128]=p.record(row[8:24],counts,0xfffffffd)
        refused(key+'-sequence-exhausted',lambda:p.transaction(bad,desired,cfg,'must refuse'))
        bad=list(map(bytearray,banks));start=(retained-8)*4096
        for i in range(start,start+4096,128):bad[3][i:i+128]=row
        refused(key+'-no-reservation-space',lambda:p.transaction(bad,desired,cfg,'must refuse'))
        altered=list(map(bytearray,desired));altered[0][0]^=1
        refused(key+'-B0-replacement',lambda:p.transaction(banks,altered,cfg,'must refuse'))
        changed=bytearray(cfg);changed[2]^=1;changed[14:]=p.migration.config_sum(changed)
        refused(key+'-startup-setting-change',lambda:p.transaction(banks,desired,bytes(changed),'must refuse'))
        # Unowned user data is admitted, remains byte-identical in the proposed
        # target, and would receive its own all-bank preflight fingerprint.
        changed=list(map(bytearray,banks));changed[1][0x1234]^=1;changed[2][0x6c01]^=1;p.admit_source(kind,changed)
        proposed=p.target_destination(changed);assert proposed[1][:0x3000]==changed[1][:0x3000] and proposed[2][0x6c00:0x7000]==changed[2][0x6c00:0x7000]
        checks.append(dict(name=key+'-unowned-user-data-preserved',passed=True))
    result=dict(passed=True,cases=len(checks),checks=checks,CPU_qualification_report_sha256=p.sha((a.plans/'report.json').read_bytes()),planner_sha256=p.sha(Path(p.__file__).read_bytes()),test_source_sha256=p.sha(Path(__file__).read_bytes()),board_access=False,hardware_qualified=False,publication_permitted=False)
    a.out.write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'legacy admission and preservation guards')
if __name__=='__main__':main()
