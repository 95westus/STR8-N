"""Check local Markdown files and anchors without modifying sources or using ports."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]

def anchors(path):
    counts={};found=set();fenced=False
    for line in path.read_text(encoding='utf-8').splitlines():
        if re.match(r'^\s*(```|~~~)',line):fenced=not fenced
        if fenced:continue
        match=re.match(r'^#{1,6}\s+(.+?)\s*#*$',line)
        if match:
            slug=match[1].lower();slug=re.sub(r'<[^>]+>','',slug);slug=re.sub(r'[^\w\- ]','',slug);slug=slug.replace(' ','-')
            n=counts.get(slug,0);counts[slug]=n+1;found.add(slug+(f'-{n}' if n else ''))
        found.update(re.findall(r'<a\s+(?:id|name)=[\"\']([^\"\']+)',line))
    return found

def audit(root,paths):
    root=Path(root).resolve();errors=[];links=0
    for path in paths:
        body=path.read_text(encoding='utf-8')
        for ref in re.findall(r'\]\(([^)\s]+)\)',body):
            if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:',ref):continue
            name,_,anchor=unquote(ref).partition('#');target=(path.parent/name).resolve() if name else path.resolve()
            links+=1
            if not target.is_relative_to(root) or not target.is_file():errors.append(f'{path.relative_to(root)} -> {ref}: missing/outside file')
            elif anchor and target.suffix.lower()=='.md' and anchor not in anchors(target):errors.append(f'{path.relative_to(root)} -> {ref}: missing anchor')
    return dict(passed=not errors,board_access=False,native_debugging=False,files_checked=len(paths),links_and_anchors_checked=links,errors=errors,
        documentation={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)})

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    paths=list((ROOT/'docs/rc1').rglob('*.md'))+[ROOT/'release/candidates/rc1-debugger'/n for n in ('README.md','BOARD_TEST.md','BRK_ABI.md')]
    result=audit(ROOT,paths);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='documentation'},indent=2))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
