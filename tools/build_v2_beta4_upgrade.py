"""Retain qualified beta25 ROMs; enlarge its RAM migration table to 24 rows."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_config as compiler
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1]

def main():
    source=ROOT/'BUILD/v2-beta25-b23';out=ROOT/'BUILD/v2-beta25-b4-unified'
    assert not any(out.glob('hardware-qualification-*.json')), 'Qualified package is frozen'
    if out.exists():assert (out/'build.json').read_bytes()==(source/'build.json').read_bytes()
    shutil.copytree(source,out,dirs_exist_ok=True,ignore=shutil.ignore_patterns('hardware-qualification-*.json'))
    mig=out/'migrator';path=mig/'rtc-migrator.asm';text=path.read_text()
    for before,after in (('MIG_COMMITS:           DS 16','MIG_COMMITS:           DS 24'),('MIG_BANKS:             DS 16','MIG_BANKS:             DS 24'),('MIG_COMMIT_ADDRS:       DS 64','MIG_COMMIT_ADDRS:       DS 96'),('CMP #$11','CMP #$19')):
        assert text.count(before)==1,before;text=text.replace(before,after)
    path.write_text(text);(mig/'asm/migration-table.inc').write_text(' DB '+','.join('$FF' for _ in range(216))+'\n')
    compiler.OUT=mig;compiler.SOURCE=mig/'asm'
    cells,symbols=compiler.assemble('rtc-migrator',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=path)
    assert max(cells)<0x4000
    data=s19(cells,0x2000);(mig/'rtc-migrator-2000.s19').write_bytes(data)
    meta=json.loads((mig/'manifest.json').read_text());meta.update(symbols=symbols,sha256=hashlib.sha256(data).hexdigest(),max_sectors=24,table_bytes=216)
    for key,name in (('count','MIG_PLAN_COUNT'),('commit_after','MIG_COMMIT_AFTER'),('commits','MIG_COMMITS'),('banks','MIG_BANKS'),('table','MIG_TABLE'),('commit_addresses','MIG_COMMIT_ADDRS')):meta[key]=symbols[name]
    (mig/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    for name in json.loads((source/'build.json').read_text())['artifacts']:
        assert (out/name).read_bytes()==(source/name).read_bytes()
    print('PASS beta25 ROM artifacts unchanged; RAM installer enlarged to 24 guarded sectors')

if __name__=='__main__':main()
