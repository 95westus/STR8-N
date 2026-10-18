"""Rehearse the installer with explicit fallback and MI-commit instrumentation."""
import json,sys
import test_v2_rtc_upgrade as t
from deploy_v2_beta25 import BASE,BOARD
root=BASE/BOARD;expected=(root/'upgrade/expected-b3.bin').read_bytes();instances=[]
Base=t.Memory
class Memory(Base):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.monitor_commit=False;instances.append(self)
    def mutated(self,kind,address,value):
        assert not(self.bank==3 and 0xA000<=address<0xB000),'Fallback MON A mutated'
        if self.bank==3 and address==0xB01F and value==0:
            assert kind=='program' and bytes(self.banks[3][0x3000:0x4000])==expected[0x3000:0x4000]
            self.monitor_commit=True
        super().mutated(kind,address,value)
t.Memory=Memory
if __name__=='__main__':
    sys.argv=['rehearse','--root',str(root)];t.main()
    assert instances[0].monitor_commit and instances[0].events[-1]==('program',3,0xB01F,0)
    p=root/'upgrade/model-check.json';r=json.loads(p.read_text());r.update(fallback_unchanged=True,monitor_commit_verified_last=True)
    p.write_text(json.dumps(r,indent=2)+'\n');print('PASS exact installer never touches A; fully verified B commit is the final mutation',flush=True)
