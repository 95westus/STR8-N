"""Create a separate source-versioned rc1 candidate; no serial or Git mutation."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    old=ROOT/'release/candidates/batchfix-r1';new=ROOT/'release/candidates/rc1'
    assert not new.exists();shutil.copytree(old,new)
    meta=json.loads((new/'release.json').read_text());prior=json.loads((ROOT/'tmp/bfx5/build-report.json').read_text())
    meta.update(version='2.0rc1',generation=49,candidate_id='rc1',deferred=['RTC qualification','native 816 applications/tests','ACIA','crypto'])
    meta['baseline_expected']={n:i for n,i in prior['artifacts'].items() if n!='str8n-v2-recovery-slot-a0.bin'}
    meta['expected_changed']=['str8n-v2-recovery-slot-b0.bin']
    meta['baseline_candidate_build_sha256']=sha((ROOT/'tmp/bfx5/build-report.json').read_bytes())
    (new/'release.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    text=(new/'build.py').read_text();text=text.replace('experimental batchfix-r1','STR8-N 2.0rc1 generation 49').replace('unmodified outputs match beta35','unmodified outputs match bf1; monitor identity is rc1 generation 49')
    (new/'build.py').write_text(text,encoding='utf-8')
    for name in ('candidate-state.json','derivation.json'):(new/name).unlink()
    (new/'README.md').write_text('''# STR8-N 2.0rc1 source build

Build from this directory alone with Python 3.10+, WDC02AS and WDCLN:

```text
python build.py --out C:\\tmp\\rc1build
```

Use a fresh short output path. This candidate advances the monitor banner to
2.0rc1 and both monitor descriptors to generation 49. All other linked payloads
must match the source-built bf1 baseline. No board access is performed.
The release ZIP contains the complete firmware and user tools; this source
directory is for reproducibility. RTC, native 816 apps/tests, ACIA and crypto
are deferred. The startup CPU detector exception is retained.
''',encoding='utf-8')
    (new/'derivation.json').write_text(json.dumps(dict(parent='v2.0bf1',parent_candidate='batchfix-r1',version='2.0rc1',generation=49,source_code_unchanged=True,changes=['monitor banner version','monitor descriptor generation and dependent CRCs'],board_access=False),indent=2)+'\n')
    target=ROOT/'release/rc1-migration-r1';assert not target.exists();target.mkdir()
    for src in (ROOT/'release/bf1-migration-r1').glob('*.py'):
        s=src.read_text(encoding='utf-8').replace('2.0bf1','2.0rc1').replace('batchfix-r1','rc1').replace('BF1','RC1').replace('bf1','rc1')
        s=s.replace('==48','==49').replace(',48)',',49)')
        if src.name=='workflow.py':
            s=s.replace("qualification['empty_bank_routes_hardware_passed'] and qualification['portable_transport_tests_passed']","qualification['prior_engine_hardware_passed'] and qualification['target_model_passed'] and qualification['portable_transport_tests_passed']")
        (target/src.name).write_text(s,encoding='utf-8')
    print('Created separate rc1 source and portable runtime; bf1 preserved')
if __name__=='__main__':main()
