"""Rehearse a recovery fixture with an immutable F and other-bank guard."""
import argparse,json,sys
import test_v2_rtc_upgrade as t

def main(root):
    p=json.loads((root/'upgrade/plan.json').read_text());build=t.ROOT/p['target_build'];t.MANIFEST=json.loads((build/'migrator/manifest.json').read_text());t.S=t.MANIFEST['symbols'];t.kernel.fw.OUT=build
    expected=(root/'upgrade/expected-b3.bin').read_bytes()
    Base=t.Memory
    class Memory(Base):
        def mutated(self,kind,address,value):
            assert self.bank==3 and address<0xF000,'F or other bank mutated'
            if kind=='program' and address in (0xA01F,0xB01F) and value==0:
                start=(address&0xF000)-0x8000
                assert bytes(self.banks[3][start:start+4096])==expected[start:start+4096],'Monitor committed before full verified restoration'
            super().mutated(kind,address,value)
    t.Memory=Memory;sys.argv=['rehearse','--root',str(root)];t.main()
    out=root/'upgrade/model-check.json';r=json.loads(out.read_text());r['fixed_f_and_other_banks_preserved']=True;out.write_text(json.dumps(r,indent=2)+'\n')
    print('PASS actual RAM fixture instructions preserve F and B0/B1/B2; pinned guards and sector comparison pass',flush=True)

if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();main(a.root)
