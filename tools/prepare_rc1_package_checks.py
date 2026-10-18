"""Pin rc1 package inputs for the existing content and example auditors."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/releases/rc1-2026-10-18-r1'
def main():
    p=OUT/'image-report.json';r=json.loads(p.read_text());r['uchess_source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'base/uchess-source').iterdir() if p.is_file()};p.write_text(json.dumps(r,indent=2)+'\n')
    text=(ROOT/'tools/audit_bf1_published_zip.py').read_text(encoding='utf-8')
    text=text.replace("ROOT/'tmp/bf1-distribution-r18/migration'","ROOT/'output/releases/rc1-2026-10-18-r1/migration'")
    text=text.replace("Q/'bf1-app-image-2026-10-18-r1/report.json'","ROOT/'output/releases/rc1-2026-10-18-r1/image-report.json'")
    text=text.replace('str8n-2.0bf1','str8n-2.0rc1').replace("['bf1','wdcmonv2-to-bf1','beta4-to-bf1','bf1-recovery']","['rc1','wdcmonv2-to-rc1','beta4-to-rc1','rc1-recovery']")
    text=text.replace('f20b53793563acd5685cca1ed987f67118f7340fa8f1551955b135830f5e672a',r['sha256'])
    (ROOT/'tools/audit_rc1_zip.py').write_text(text,encoding='utf-8')
    print('Prepared actual-ZIP firmware/app/source/manual/privacy/vendor audits')
if __name__=='__main__':main()
