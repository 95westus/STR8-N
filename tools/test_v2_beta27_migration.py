"""Rehearse the exact beta27 RAM installer and guard the MAINT source removal."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-beta27')
import argparse,json
from pathlib import Path
import test_v2_unified_migration as unified

def main(root):
    plan=json.loads((root/'upgrade/plan.json').read_text())
    target=(root/'upgrade/expected-b2.bin').read_bytes()[:0x3000]
    Base=unified.t.Memory
    class Memory(Base):
        def mutated(self,kind,address,value):
            if self.bank==1:
                assert bytes(self.banks[2][:0x3000])==target,'B1 MAINT removed before verified destination committed'
            super().mutated(kind,address,value)
    unified.t.Memory=Memory
    unified.main(root)
    p=root/'upgrade/model-check.json';r=json.loads(p.read_text())
    assert r['expected_hashes']==plan['expected_hashes']
    r['maint_committed_before_source_erase']=True
    p.write_text(json.dumps(r,indent=2)+'\n')
    print('PASS MAINT committed in B2 before first B1 mutation; SRAM/WORK full records verified before commit')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();main(a.root)
