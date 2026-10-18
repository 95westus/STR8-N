"""Build a separate 24-row legacy conversion installer. Offline only."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path
import build_v2_storage_migrator as storage
from build_bank_maint_v2 import long_branches
from beta4_migration import read_s19,s19
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def linked_cells(path):
    cells={}
    for line in path.read_text().splitlines():
        assert re.fullmatch(r'S[019][0-9A-Fa-f]+',line)
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
        if line[1]=='1':
            address=int.from_bytes(raw[1:3],'big')
            for offset,value in enumerate(raw[3:-1],address):assert offset not in cells;cells[offset]=value
    assert cells and set(cells)==set(range(min(cells),max(cells)+1))
    return cells

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();assert not out.exists() and len(str(out))<60
    # Builders write only into this new candidate directory. No firmware or
    # running worker dependencies are edited or rebuilt in their original path.
    storage.OUT=out;storage.VERSION='2.0bf1 LEGACY CONVERSION';storage.main()
    source=out/'rtc-migrator.asm';text=source.read_text()
    for old,new in [('MIG_COMMITS:           DS 16','MIG_COMMITS:           DS 24'),('MIG_BANKS:             DS 16','MIG_BANKS:             DS 24'),('MIG_COMMIT_ADDRS:       DS 64','MIG_COMMIT_ADDRS:       DS 96'),('CMP #$11','CMP #$19')]:
        assert old in text,old;text=text.replace(old,new)
    needle='                        LDA #$3F\n                        STA V2_FLASH_DATA'
    assert text.count(needle)==1
    text=text.replace(needle,'                        LDY MIG_INDEX\n                        LDA MIG_COMMIT_VALUES-1,Y\n                        STA V2_FLASH_DATA')
    text=text.replace('MIG_COMMIT_ADDRS:       DS 96','MIG_COMMIT_VALUES:      DS 24\nMIG_COMMIT_ADDRS:       DS 96')
    (out/'asm/migration-table.inc').write_text(' DB '+','.join('$FF' for _ in range(216))+'\n')
    source.write_text(long_branches(text).replace('BM_LONG_','LEGACY_LONG_'))
    link=storage.base.base.link;link.OUT=out;link.SOURCE=out/'asm'
    cells,symbols=link.assemble('rtc-migrator',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=source)
    assert symbols['MIG_END']<0x3000
    original=s19(dict(enumerate(link.dense_image(cells,0x2000,symbols['MIG_END']),0x2000)),0x2000)
    (out/'legacy-template.s19').write_bytes(original)
    mf=json.loads((out/'manifest.json').read_text());mf.update(symbols=symbols,entry=0x2000,count=symbols['MIG_PLAN_COUNT'],commits=symbols['MIG_COMMITS'],commit_after=symbols['MIG_COMMIT_AFTER'],commit_addresses=symbols['MIG_COMMIT_ADDRS'],commit_values=symbols['MIG_COMMIT_VALUES'],banks=symbols['MIG_BANKS'],table=symbols['MIG_TABLE'],table_bytes=216,max_sectors=24,sha256=sha(original))
    # New helper source: legacy WDC has no monitor-slot preference. Permit only
    # an explicitly empty preference; retain the existing P/generation checks
    # for A/B sources. Checksums, CRC, erased record and all-bank guards remain.
    helper_source=ROOT/'release/candidates/batchfix-route-r1/source/reservation.asm'
    helper=helper_source.read_text();needle="        LDA R_RECORD+15\n        CMP #'P'"
    assert helper.count(needle)==1
    helper=helper.replace(needle,"        LDA R_RECORD+15\n        BEQ R_LEGACY_NO_PREFERENCE\n        CMP #'P'")
    at=helper.index('R_CONFIG_CHECKSUM:')
    helper=helper[:at]+'''        BRA R_CONFIG_CHECKSUM
R_LEGACY_NO_PREFERENCE:
        LDX #5
R_LEGACY_PREF_LOOP:
        LDA R_RECORD+15,X
        BNE R_CONFIG_BAD
        DEX
        BPL R_LEGACY_PREF_LOOP
'''+helper[at:]
    stage=out/'asm';(stage/'legacy-reservation.asm').write_text(helper)
    links={n:symbols.get(n,mf['worker'].get(n)) for n in ['MIG_HASH_RANGE','V2W_SELECT','V2W_BYTE','V2W_POLL','V2W_TIMEOUT']};assert all(v is not None for v in links.values())
    (stage/'reservation-links.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in links.items()))
    commands=[]
    def assemble(name,address):
        for cmd in [[shutil.which('wdc02as'),'-G','-L','-S','-W','-I',str(stage),name+'.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c'+address,'-hm19','-j','-o',name+'.s19',name+'.obj']]:
            r=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);commands.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));(out/'extra-build-log.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,(r.stdout,r.stderr)
        return linked_cells(stage/(name+'.s19'))
    helper_cells=assemble('legacy-reservation','3000');assert max(helper_cells)<0x3300
    wrapper=(ROOT/'release/beta35-prerelease/source/reservation-entry.asm').read_text()
    (stage/'reservation-entry.asm').write_text(wrapper)
    start=symbols['MIG_NEXT'];assert bytes(cells[i] for i in range(start,start+3))==b'\xae\0\x62'
    (stage/'transaction-links.inc').write_text(f'MIG_NEXT_CONTINUE EQU ${start+3:04X}\nMIG_FAIL EQU ${symbols["MIG_FAIL"]:04X}\n')
    wrapper_cells=assemble('reservation-entry','3300');assert max(wrapper_cells)<0x3500
    image=read_s19(out/'legacy-template.s19')[0];image.update(helper_cells);image.update(wrapper_cells);image.update(dict(enumerate(b'\x4c\0\x33',start)))
    image={i:image.get(i,0) for i in range(0x2000,0x3700)}
    (out/'integrated-template.s19').write_bytes(s19(image,0x2000))
    mf.update(integrated_sha256=sha((out/'integrated-template.s19').read_bytes()),helper_parent_sha256=sha(helper_source.read_bytes()),helper_source_sha256=sha((stage/'legacy-reservation.asm').read_bytes()),helper_bytes=len(helper_cells),wrapper_bytes=len(wrapper_cells),builder_sha256=sha(Path(__file__).read_bytes()),passed=True,model_qualified=False,hardware_qualified=False,board_access=False)
    (out/'manifest.json').write_text(json.dumps(mf,indent=2)+'\n');print('PASS separate 24-row template and legacy reservation helper built',flush=True)
if __name__=='__main__':main()
