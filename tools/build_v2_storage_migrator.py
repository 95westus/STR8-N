"""Build RAM-only beta17 installer: 16 steps, two commit addresses per step."""
import hashlib,json,shutil
import build_v2_rtc_migrator as base
from build_bank_maint_v2 import long_branches
OUT=base.ROOT/'BUILD/v2-storage/migrator'
VERSION='2.0b17'

def main():
    base.OUT=OUT;base.VERSION=VERSION;base.MULTI_COMMIT=True;base.COMMIT_ADDRESS=0x8003;base.main()
    p=OUT/'rtc-migrator.asm';t=p.read_text().replace('MIG_COMMITS:           DS 10','MIG_COMMITS:           DS 16').replace('MIG_BANKS:             DS 10','MIG_BANKS:             DS 16').replace('CMP #$0B','CMP #$11')
    start=t.index('                        LDA #$03\n                        STA V2_FLASH_PTR',t.index('LDA MIG_COMMITS-1,X'))
    end=t.index('MIG_STORAGE_READY:',start)
    t=t[:start]+'''                        LDA MIG_INDEX
                        DEC A
                        ASL A
                        ASL A
                        STA $6230
                        TAX
                        JSR MIG_RECORD_COMMIT
                        BCC MIG_FAIL
                        LDA $6230
                        CLC
                        ADC #2
                        TAX
                        JSR MIG_RECORD_COMMIT
                        BCC MIG_FAIL
'''+t[end:]
    mark='MIG_IDENTIFY:'
    at=t.index(mark)
    t=t[:at]+'''MIG_RECORD_COMMIT:
                        LDA MIG_COMMIT_ADDRS+1,X
                        BEQ MIG_COMMIT_SKIP
                        STA V2_FLASH_PTR+1
                        LDA MIG_COMMIT_ADDRS,X
                        STA V2_FLASH_PTR
                        LDA #$3F
                        STA V2_FLASH_DATA
                        JMP V2W_BYTE
MIG_COMMIT_SKIP:        SEC
                        RTS
MIG_COMMIT_ADDRS:       DS 64
'''+t[at:]
    (OUT/'asm/migration-table.inc').write_text(' DB '+','.join('$FF' for _ in range(144))+'\n')
    p.write_text(long_branches(t).replace('BM_LONG_','STORE_MIG_LONG_'))
    link=base.base.link;link.OUT=OUT;link.SOURCE=OUT/'asm'
    cells,s=link.assemble('rtc-migrator',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=p)
    body=link.dense_image(cells,0x2000,s['MIG_END']);assert s['MIG_END']<0x4000
    from beta4_migration import s19
    data=s19(dict(enumerate(body,0x2000)),0x2000);(OUT/'rtc-migrator-2000.s19').write_bytes(data)
    m=json.loads((OUT/'manifest.json').read_text());m.update(symbols=s,entry=0x2000,count=s['MIG_PLAN_COUNT'],commit_after=s['MIG_COMMIT_AFTER'],commits=s['MIG_COMMITS'],commit_addresses=s['MIG_COMMIT_ADDRS'],banks=s['MIG_BANKS'],table=s['MIG_TABLE'],table_bytes=144,max_sectors=16,sha256=hashlib.sha256(data).hexdigest())
    (OUT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(VERSION,'RAM installer:',len(body),'bytes; 16 guarded sectors; two verified-record commits per step')

if __name__=='__main__':main()
