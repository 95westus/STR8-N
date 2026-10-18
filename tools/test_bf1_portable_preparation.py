"""Exercise extracted migration/recovery preparation with private local fixtures, never ports."""
import argparse,importlib,sys,json,hashlib,tempfile,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
def main():
    p=argparse.ArgumentParser();p.add_argument('--kit',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();kit=a.kit.resolve();sys.path.insert(0,str(kit));m=importlib.import_module('migrate');rec=importlib.import_module('recover');r=importlib.import_module('runtime');checks=[]
    def capture(root,banks):
        root.mkdir();files={}
        for n,b in enumerate(banks):
            for suffix in ('','-repeat'):
                name=f'b{n}{suffix}.bin';(root/name).write_bytes(b);files[name]=dict(bytes=len(b),sha256=r.sha(b))
        (root/'capture.json').write_text(json.dumps(dict(schema=1,board='local-test-profile',repeat_verified=True,files=files)))
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='bf1-portable-cli-') as temp:
        temp=Path(temp);phase=Q/'bf1-2512-legacy-offline-2026-10-17-r6/v2-0b4-convert';banks=[(phase/f'source-b{n}.bin').read_bytes() for n in range(4)];cap=temp/'beta4';capture(cap,banks)
        escrow=temp/'metadata.bin';escrow.write_bytes((Q/'bf1-2512-pre-migration-backup-2026-10-17-r2/b3.bin').read_bytes()[0x1c00:0x2000]);out=temp/'forward';info=m.prepare_beta4(cap,kit,out,escrow)
        assert info['expected_sha256']==json.loads((phase/'plan.json').read_text())['expected_sha256'];assert (out/'installer-model-only.s19').read_bytes()==(phase/'installer-model-only.s19').read_bytes();checks.append(dict(name='portable-beta4-preparation-identical-to-hardware-qualified-transaction',passed=True,fresh_CPU_execution=False))
        for cfg in (bytes(6),b'P\xb0\x0d\0\0\0'):
            b=list(map(bytearray,banks));_,offset,row,_=r.latest(b);config=bytearray(row[8:24]);config[7:13]=cfg;config[14:]=m.bridge.config_sum(config);counts=[int.from_bytes(row[24+i*3:27+i*3],'little') for i in range(32)];sequence=int.from_bytes(row[4:8],'little');b[3][offset:offset+128]=r.record(bytes(config),counts,sequence);m.admit_beta4(list(map(bytes,b)),kit);checks.append(dict(name='published-beta4-empty-or-B-preference-admission-'+cfg.hex(),passed=True,CPU_qualification_still_required=True))
        bad=list(map(bytearray,banks));bad[1][0x3000]=1
        try:m.admit_beta4(list(map(bytes,bad)),kit)
        except ValueError:checks.append(dict(name='occupied-user-provider-destination-refused',passed=True))
        else:raise AssertionError('Occupied provider accepted')
        bad=list(map(bytearray,banks));bad[3][0x7123]^=1
        try:m.admit_beta4(list(map(bytes,bad)),kit)
        except ValueError:checks.append(dict(name='unknown-source-core-refused',passed=True))
        else:raise AssertionError('Unknown core accepted')
        try:m.safe(cap,'../outside.bin')
        except ValueError:checks.append(dict(name='escaping-capture-path-refused',passed=True))
        else:raise AssertionError('Path escape accepted')
        cut=Q/'bf1-2512-legacy-offline-2026-10-17-r6/v2-0b4-convert-provider-erase-recover';current=[(cut/f'source-b{n}.bin').read_bytes() for n in range(4)];_,_,_,matches=rec.admit_boundary(out,current);assert matches;checks.append(dict(name='CPU-attested-provider-erase-recovery-admitted',passed=True,fresh_CPU_execution=False))
        bad=list(map(bytearray,current));bad[0][0x123]^=1
        try:rec.admit_boundary(out,list(map(bytes,bad)))
        except ValueError:checks.append(dict(name='unexplained-recovery-B0-change-refused',passed=True))
        else:raise AssertionError('Unexplained B0 accepted')
        vendor=(Q/'board-2512-layout-2026-09-24/b0-final.bin').read_bytes();stock=[vendor,b'\xff'*32768,b'\xff'*32768,vendor];stockcap=temp/'stock';capture(stockcap,stock);bridgeout=temp/'bridge';bridge=m.prepare_wdc_bridge(stockcap,kit,bridgeout);assert bridge['final_target']=='2.0bf1' and bridge['live_execution_qualified'] is False
        expected=[(bridgeout/f'expected-b{n}.bin').read_bytes() for n in range(4)];assert expected[:3]==stock[:3];m.admit_beta4(expected,kit);checks.append(dict(name='exact-factory-WDC-profile-prepares-published-beta4-bridge-preserving-B0-B2',passed=True,CPU_and_hardware_qualification_still_required=True))
        aftercap=temp/'after-bridge';capture(aftercap,expected);final=m.prepare_beta4(aftercap,kit,temp/'factory-to-bf1');assert final['route']=='beta4-to-bf1' and final['live_execution_qualified'] is False;checks.append(dict(name='WDC-bridge-to-bf1-offline-chain-prepares',passed=True,CPU_and_hardware_qualification_still_required=True))
        changed=list(stock);changed[3]=stock[3][:-1]+bytes([stock[3][-1]^1]);badcap=temp/'unknown-stock';capture(badcap,changed)
        try:m.prepare_wdc_bridge(badcap,kit,temp/'refused')
        except ValueError:checks.append(dict(name='unknown-vendor-WDC-image-refused',passed=True))
        else:raise AssertionError('Unknown vendor image admitted')
    report=dict(passed=True,cases=len(checks),checks=checks,kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),test_sha256=r.sha(Path(__file__).read_bytes()),board_access=False,distribution_qualified=False,live_execution_enabled=False,limits='Preparation and bounded recovery admission only; new factory-WDC two-hop route, fresh portable capture/serial workflow, CPU interruption tests, recovery execution and manuals remain pending')
    assert not a.out.exists();a.out.write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),'portable preparation/admission checks; no serial access')
if __name__=='__main__':main()
