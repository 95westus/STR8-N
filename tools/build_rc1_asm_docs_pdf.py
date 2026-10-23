"""Render current onboarding/ASM/save-store Markdown with the existing print style."""
import json
import hashlib
from build_rc1_source_pdfs import ROOT,OUTPUT,Renderer,fonts,footer,SimpleDocTemplate,letter,DOCUMENTS
from reportlab.platypus import Preformatted,KeepTogether

DOCS={
    'QUICK_START.md':'STR8N-RC1-Onboarding.pdf',
    'ASM_GUIDE.md':'STR8N-ASM-User-Guide.pdf',
    'ASM_SAVE_STORE.md':'STR8N-ASM-Save-Store.pdf',
    'ASM_DEVELOPMENT.md':'STR8N-ASM-Development.pdf',
}

def main():
    fonts();OUTPUT.mkdir(exist_ok=True,parents=True);DOCUMENTS.update(DOCS)
    records=[]
    for source_name,output_name in DOCS.items():
        source=ROOT/'docs/rc1'/source_name;target=OUTPUT/output_name
        doc=SimpleDocTemplate(str(target),pagesize=letter,leftMargin=48,rightMargin=48,
            topMargin=43,bottomMargin=54,title=source.read_text(encoding='utf-8').splitlines()[0][2:],author='STR8-N')
        story=Renderer(source).story()
        # Keep short source sessions and their expected error outputs intact.
        story=[KeepTogether([item]) if isinstance(item,Preformatted) and len(item.lines)<=30 else item for item in story]
        doc.build(story,onFirstPage=footer,onLaterPages=footer)
        records.append(dict(source=str(source),pdf=str(target),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            pdf_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        print(target,flush=True)
    (OUTPUT/'asm-development-pdfs.json').write_text(json.dumps(records,indent=2)+'\n')

if __name__=='__main__':main()
