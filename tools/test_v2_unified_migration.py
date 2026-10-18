"""Exact installer rehearsal, including both commit types and fallback isolation."""
import argparse,json,sys
from pathlib import Path
import test_v2_rtc_upgrade as t

def main(root):
    info=json.loads((root/'upgrade/plan.json').read_text());build=t.ROOT/info['target_build']
    t.MANIFEST=json.loads((build/'migrator/manifest.json').read_text());t.S=t.MANIFEST['symbols'];t.kernel.fw.OUT=build
    expected=(root/'upgrade/expected-b3.bin').read_bytes();page=info.get('fallback_page',info['source']['active_page']);updated=info.get('target_page',info['source']['inactive_page']);instances=[];Base=t.Memory
    class Memory(Base):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);self.monitor_commit=False;instances.append(self)
        def mutated(self,kind,address,value):
            assert not(self.bank==3 and page<<8<=address<(page<<8)+4096),'Fallback monitor mutated'
            if info.get('layout_conversion') and self.bank==3 and 0x8000<=address<0xA000:
                maint=(build/json.loads((build/'build.json').read_text())['maintenance_storage_file']).read_bytes()
                assert bytes(self.banks[1][:len(maint)])==maint, 'b4 MAINT removed before complete relocated copy committed'
            if self.bank==3 and address==(updated<<8)+31 and value==0:
                i=(updated-0x80)*256
                assert kind=='program' and bytes(self.banks[3][i:i+4096])==expected[i:i+4096]
                self.monitor_commit=True
            super().mutated(kind,address,value)
    t.Memory=Memory;sys.argv=['rehearse','--root',str(root)];t.main()
    assert instances[0].monitor_commit and instances[0].events[-1]==('program',3,(updated<<8)+31,0)
    p=root/'upgrade/model-check.json';r=json.loads(p.read_text());r.update(fallback_unchanged=True,monitor_commit_verified_last=True)
    p.write_text(json.dumps(r,indent=2)+'\n');print('PASS fallback isolated; complete MAINT and monitor committed only after verification',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();main(a.root)
