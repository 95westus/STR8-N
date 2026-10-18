"""Add the qualified uchess.a session to the single complete release; retain payload bytes."""
import hashlib,json,posixpath,re,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/bf1-complete-release-2026-10-18-r2';sha=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def main():
    assert not OUT.exists();OUT.mkdir(parents=True);original=Q/'bf1-published-zip-audit-2026-10-18-r1/published-release.zip';audit=Q/'bf1-published-zip-content-audit-2026-10-18-r1/report.json';session=Q/'bf1-uchess-asm-session-2026-10-18-r1/report.json'
    assert read(audit)['passed'] and read(session)['passed'] and len(read(session)['checks'])==2
    workflows={}
    for platform in ('windows','linux'):
        path=Q/f'bf1-published-zip-{platform}-workflows-2026-10-18-r1.json';assert read(path)['passed'];workflows[platform]=sha(path.read_bytes())
    with zipfile.ZipFile(original) as z:files={n.split('/',1)[1]:z.read(n) for n in z.namelist()}
    prior=read(Q/'bf1-published-zip-audit-2026-10-18-r1/download.json');assert sha(original.read_bytes())==prior['sha256'];old_manifest=json.loads(files.pop('release-manifest.json'));files.pop('SHA256SUMS.txt')
    source=files['uchess-source/microchess.asm'];assert all(c['source_sha256']==sha(source) for c in read(session)['checks']);files['uchess-source/uchess.a']=source
    canonical=ROOT/'release/bf1-examples';canonical.mkdir(exist_ok=True);(canonical/'uchess.a').write_bytes(source);(canonical/'LICENSE.txt').write_bytes(files['uchess-source/LICENSE.txt'])
    text=(ROOT/'docs/bf1/UCHESS_ASM_SESSION.md').read_text(encoding='utf-8').replace('../../release/bf1-examples/uchess.a','../uchess-source/uchess.a').replace('../../release/bf1-examples/LICENSE.txt','../uchess-source/LICENSE.txt');files['docs/UCHESS_ASM_SESSION.md']=text.encode()
    files['docs/ASM_GUIDE.md']+=b'\n\n## Complete uChess source session\n\nSee [uchess.a: ASM 0.5 and S/T/R walkthrough](UCHESS_ASM_SESSION.md) for the\nqualified full-game PASTE/assembly, Store, Table, load-only Restore and run example.\n'
    files['docs/README.md']+=b'\n\n[uChess ASM source session and S/T/R example](UCHESS_ASM_SESSION.md).\n'
    command=files['docs/COMMAND_REFERENCE.md'].decode();command=command.replace('`S bank flash start end [name]`','`S bank AUTO|flash start end [name]`').replace('`R [bank] name`','`R [bank] name [L]`');files['docs/COMMAND_REFERENCE.md']=command.encode()
    files['uchess-source/README.md']='''# uChess / Microchess source for bf1 ASM 0.5

Microchess is Copyright 1976–2005 Peter Jennings, www.benlo.com.
Daryl Rictor added the serial chessboard interface in August 2002; Bill
Forster corrected OCR errors in August 2005. The full original conditions and
disclaimer are in [LICENSE.txt](LICENSE.txt) and the credited original source
is retained in `Microchess6502-upstream.txt`.

`uchess.a` is the paste-ready compact source for the included bf1 ASM 0.5.
It is byte-identical to `microchess.asm`, originally adapted for ASM 0.4.
`microchess-readable.asm` is the descriptive reference source, and
`symbols.json` maps descriptive to compact names. Use the compact source
inside the board's limited source buffer. The assembled executable is 1,439
bytes at $0200–$079E; entry $0200. The game uses public PUTC/GETC/HOLD calls;
normal 65C816 runtime is emulation mode.

Follow [the complete ASM session and S/T/R walkthrough](../docs/UCHESS_ASM_SESSION.md).
It demonstrates source PASTE/assembly and stores the compiled game as UCHDEMO,
preserving the supplied UCHESS. Source assembly and Store/Table/Restore were
executed with the actual bf1 MON A and MON B instructions in the W65C02 model;
no physical board was opened. Keep this source, all notices and full license
together when redistributing. Peter Jennings's license remains applicable;
the repository license does not replace it.
'''.encode()
    files['examples/uchess-asm-session.txt']=b'''UCHESS.A / ASM 0.5 / STORE-TABLE-RESTORE SESSION
Read docs/UCHESS_ASM_SESSION.md first. Prompts and explanatory lines below
are not commands to paste as one file. Send only uchess-source/uchess.a
as plain text after PASTE, then type a single period on a separate line.

At B3>:
ASM

At ASM>:
NEW
PASTE
[send uchess-source/uchess.a as ordinary text]
.
ASM
[expect OK 1439 bytes, origin $0200, buffer $0200]
QUIT

At B3>, choose an unused name if UCHDEMO already exists:
T 1
S 1 AUTO 0200 079E UCHDEMO
T 1
R 1 UCHDEMO L
D 0200 020F
G 0200
[in the game, press Q without Enter to return]
R 1 UCHDEMO
[press Q without Enter again]

Optional load-only restore proof, before executing:
M 0200 EA
R 1 UCHDEMO L
D 0200 020F
[the first byte is restored to 78]

S stores the compiled executable/tables. Keep uchess.a on the host to
reopen/edit the source in ASM. The original bundled UCHESS is preserved.
'''
    readme=files['README.md'].decode();readme=readme.replace('## Package contents','## uChess source session\n\nUse [uchess-source/uchess.a](uchess-source/uchess.a) with the\n[complete ASM 0.5 and S/T/R walkthrough](docs/UCHESS_ASM_SESSION.md).\nA printable command transcript is in `examples/uchess-asm-session.txt`.\n\n## Package contents',1);files['README.md']=readme.encode()
    assert all(files[n]==(Q/'bf1-published-zip-content-audit-2026-10-18-r1/extracted'/n).read_bytes() for n in files if n.startswith(('migration/','firmware/')))
    for name,body in files.items():
        if name.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)',body.decode()):
                if re.match('[a-z]+:',link):continue
                target=posixpath.normpath((Path(name).parent/link.split('#')[0]).as_posix());assert target in files,(name,target)
    old_manifest.update(release_revision=2,uchess_source_session_verified=True,uchess_source_file='uchess-source/uchess.a',verified_ASM_version='0.5',session_qualification='Actual bf1 MON A and MON B instructions in W65C02 model; no physical board access',files={n:dict(bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())})
    files['release-manifest.json']=(json.dumps(old_manifest,indent=2)+'\n').encode();files['SHA256SUMS.txt']=''.join(sha(b)+'  '+n+'\n' for n,b in sorted(files.items())).encode()
    path=OUT/'str8n-2.0bf1-release-r2.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,body in sorted(files.items()):
            entry=zipfile.ZipInfo('str8n-2.0bf1/'+name,date_time=(2026,10,18,0,0,0));entry.create_system=3;entry.external_attr=((0o100755 if name.endswith('.sh') else 0o100644)<<16);entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,body)
    with zipfile.ZipFile(path) as z:assert all(z.read('str8n-2.0bf1/'+n)==b for n,b in files.items())
    report=dict(passed=True,path=str(path),filename=path.name,bytes=path.stat().st_size,sha256=sha(path.read_bytes()),files=len(files),base_published_zip_sha256=prior['sha256'],base_audit_sha256=sha(audit.read_bytes()),uchess_session_sha256=sha(session.read_bytes()),platform_workflows=workflows,all_firmware_runtime_bytes_unchanged=True,credited_source_alias=True,original_zip_preserved=True,board_access=False)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS single complete release r2 with uchess.a and qualified ASM/S/T/R session:',len(files),'files')
if __name__=='__main__':main()
