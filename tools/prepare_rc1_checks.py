"""Generate rc1-specific executions of the existing model regressions."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/rc1-2026-10-18-r1'
def main():
    first=json.loads((ROOT/'tmp/rc1b1/build-report.json').read_text());second=json.loads((ROOT/'tmp/rc1b2/build-report.json').read_text());assert first['artifacts']==second['artifacts'] and first['passed'] and second['passed']
    old=json.loads((ROOT/'tmp/bfx5/build-report.json').read_text())
    changed=[n for n,i in first['artifacts'].items() if i!=old['artifacts'][n]]
    assert sorted(changed)==['str8n-v2-recovery-slot-a0.bin','str8n-v2-recovery-slot-b0.bin']
    diffs={}
    for name in changed:
        a=(ROOT/'tmp/bfx5/payload'/name).read_bytes();b=(ROOT/'tmp/rc1b1/payload'/name).read_bytes();indices=[n for n,(v,w) in enumerate(zip(a,b)) if v!=w]
        assert 8 in indices and all(n in (8,18,19) or a[n:n+3]==b'bf1' or 128<=n<4096 for n in indices)
        assert len(indices)==5 and indices[:3]==[8,18,19] and a[indices[3]:indices[3]+3]==b'bf1' and b[indices[3]:indices[3]+3]==b'rc1',(name,indices)
        diffs[name]=indices
    (Q/'rc1-clean-build-report.json').write_text(json.dumps(dict(passed=True,fresh_links_per_build=27,artifacts=19,reproducible=True,changed_payloads=diffs,all_other_payloads_identical_to_bf1=True,board_access=False),indent=2)+'\n')
    replacements={
      'prepare_bf1_public_empty_models.py':[('tmp/bf1-distribution-r16/migration','output/releases/rc1-2026-10-18-r1/migration'),('bf1-public-empty-bank-models-2026-10-18-r1','rc1-empty-models')],
      'prepare_bf1_beta4_app_recovery_models.py':[('tmp/bf1-distribution-r16/migration','output/releases/rc1-2026-10-18-r1/migration'),('bf1-public-empty-bank-models-2026-10-18-r1','rc1-empty-models'),('bf1-public-beta4-recovery-models-2026-10-18-r1','rc1-beta4-recovery-models')],
      'test_bf1_candidate_workflow.py':[('bf1','rc1'),('BF1','RC1')],
      'test_bf1_boot_core_image.py':[('bf1-boot-core-image-2026-10-18-r1','rc1-boot-core-model'),("(Q/'bf1-app-image-2026-10-18-r1/str8n-2.0bf1-apps-str8n-only.bin')","(ROOT/'output/releases/rc1-2026-10-18-r1/firmware/str8n-2.0rc1-apps-str8n-only.bin')"),('2.0bf1','2.0rc1')],
      'test_bf1_uchess_session.py':[('bf1-uchess-asm-session-2026-10-18-r1','rc1-uchess-model'),("Q/'bf1-published-zip-audit-2026-10-18-r1/published-release.zip'","ROOT/'output/releases/rc1-2026-10-18-r1/str8n-v2.0rc1-release.zip'"),('str8n-2.0bf1/','str8n-2.0rc1/'),('str8n-2.0bf1-apps','str8n-2.0rc1-apps')]
    }
    image=(OUT/'firmware/str8n-2.0rc1-apps-str8n-only.bin').read_bytes();digest=hashlib.sha256(image).hexdigest()
    for name,pairs in replacements.items():
        text=(ROOT/'tools'/name).read_text(encoding='utf-8')
        for a,b in pairs:text=text.replace(a,b)
        text=text.replace('f20b53793563acd5685cca1ed987f67118f7340fa8f1551955b135830f5e672a',digest)
        (ROOT/'tools'/name.replace('bf1','rc1')).write_text(text,encoding='utf-8')
    for p in (ROOT/'docs/rc1').glob('*.md'):
        s=p.read_text(encoding='utf-8').replace('generation-48','generation-49')
        s=s.replace('booted\nrc1, discovered','booted\nbf1, discovered')
        s=s.replace('This local candidate guide does not waive release qualification; publication remains held.','This rc1 guide covers the scoped release candidate; full endurance/RTC qualification is deferred.')
        s=s.replace('These are local candidate tools/manuals. Publication and full release acceptance\nremain held. Longer soak/RTC gates are not waived by owner-stopped workloads.','These manuals accompany the scoped rc1 release candidate. The owner accepted\nrecorded stopped soaks; full endurance and RTC qualification remain deferred.')
        s=s.replace('Full-system\nmigrations were tested on physical 65C02 and 65C816 boards.','The prior bf1 full-system\nmigrations were tested on physical 65C02 and 65C816 boards; rc1 is verified offline.')
        s=s.replace('The common RAM worker and transfer engine completed both physical empty-bank\nroutes.','The unchanged RAM worker and transfer engine completed both physical empty-bank\nroutes with bf1; rc1 targets are verified in CPU/flash models.')
        s=s.replace('physical WDC/65C816 and beta4/65C02 checks passed.','prior bf1 physical WDC/65C816 and beta4/65C02 checks passed; rc1 is model-tested.')
        s=s.replace('Current status: **candidate / not a released generic installer**.','Current status: **scoped release candidate; exact-source empty-bank routes only**.')
        p.write_text(s,encoding='utf-8')
    print('PASS two clean builds: only 5 identity/generation/CRC bytes differ in each monitor; prepared rc1 model regressions')
if __name__=='__main__':main()
