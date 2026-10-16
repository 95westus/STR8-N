"""Unflashed generation 36: F-only no-erase slot bootstrap and RAM provisioning."""
import json,shutil,hashlib,sys
from beta4_migration import default_config,metadata,s19
import build_v2_startup_keys as build
from build_v2_spi_resident import assemble

ROOT=build.ROOT;OUT=ROOT/'BUILD/v2-fix005';OLD=ROOT/'BUILD/v2-fix004'

def patch(text):
    # Keep every earlier private F entry and J CRC address fixed. Reclaim the
    # redundant wear-report title at the end of F, after all J entry points.
    for folder in ('source','asm'):
        p=OUT/folder/'str8n-v2-journal.inc';s=p.read_text()
        old='''                        LDX #<BOOT_COUNT_TITLE
                        LDY #>BOOT_COUNT_TITLE
                        JSR BOOT_PRINT
'''
        assert s.count(old)==1;s=s.replace(old,'',1)
        old='BOOT_COUNT_TITLE:       DB "ERASE ATTEMPTS SINCE PROVISIONING",$0D,$0A,0\n'
        assert s.count(old)==1;s=s.replace(old,'',1)
        s=s.replace('JOURNAL INVALID; WRITES DISABLED','JOURNAL INVALID',1);p.write_text(s)
    old='''                        LDA #$01
                        STA V2_ERASE
                        STZ V2_SELF
                        JSR V2W_MUTATE'''
    assert text.count(old)==1
    text=text.replace(old,'                        JSR BOOT_UPDATE_WRITE\n'+ '                        NOP\n'*6,1)
    helper='''; A missing/invalid journal never permits an erase. Only completely blank
; C/D permits bootstrap programming of bytes which are FF or already equal.
; A torn matching upload resumes without programming any byte twice.
BOOT_UPDATE_WRITE:      JSR BOOT_META_READ
                        BCS BOOT_UPDATE_ACCOUNTED
                        STZ V2_PTR
                        LDA #$C0
                        STA V2_PTR+1
                        LDA #$E0
                        STA BOOT_END_PAGE
                        LDY #$00
                        JSR J_SECTOR_BYTE
                        BCC BOOT_BOOTSTRAP_REFUSE
                        JSR V2W_ANALYZE
                        LDA V2_ERASE
                        BNE BOOT_BOOTSTRAP_REFUSE
                        STZ V2_SELF
                        STZ V2_FLASH_ERROR
                        LDA #$01
                        STA V2_NMI_HOLD
                        JSR V2W_BEGIN
                        JMP V2W_PROGRAM
BOOT_UPDATE_ACCOUNTED:  LDA #$01
                        STA V2_ERASE
                        STZ V2_SELF
                        JMP V2W_MUTATE
BOOT_BOOTSTRAP_REFUSE:  SEC
                        RTS
'''
    marker='BOOT_WORKER_IMAGE:      INCLUDE "worker-image.inc"'
    assert text.count(marker)==1
    return text.replace(marker,helper+marker,1)

def main():
    build.OLD=OLD;build.OUT=OUT;build.GENERATION=36;build.patch=patch;build.main()
    for p in OUT.glob('*test-results.json'):p.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    meta=json.loads((OUT/'build.json').read_text())
    stage=OUT/'bootstrap/source';stage.mkdir(parents=True,exist_ok=True)
    for name in ('str8n-v2-eq.inc','str8n-v2-public.inc','service-eq.inc'):
        shutil.copyfile(OUT/'asm'/name,stage/name)
    (stage/'bootstrap-symbols.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in meta['worker'].items() if k.startswith('V2W_'))+
        f"BOOT_COMPAT EQU ${meta['boot']['BOOT_COMPAT_DATA']:04X}\n"+
        'EXPECTED_CORE: DB '+','.join(f'${b:02X}' for b in meta['boot_compatibility'].to_bytes(4,'little'))+'\n')
    record=metadata(default_config(),[0]*32,1)
    (stage/'initial-record.inc').write_text('INITIAL_RECORD:\n'+''.join(' DB '+','.join(f'${b:02X}' for b in record[i:i+16])+'\n' for i in range(0,128,16)))
    (stage/'bootstrap-journal.asm').write_text(build.long_branches((ROOT/'tools/v2-rtc/bootstrap-journal.asm').read_text()))
    body,symbols,_=assemble(stage,'bootstrap-journal',0x2000,'APP_END',0x2000)
    (OUT/'bootstrap/bootstrap-journal.bin').write_bytes(body)
    (OUT/'bootstrap/bootstrap-journal.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    meta.update(f_only_bootstrap=True,bootstrap_erases=False,bootstrap_journal_guard='C/D entirely FF',
        bootstrap_resume='matching FF/equal slot bytes only',hardware_tested=False,board_access=False,boards_flashed=False,
        fixes=sorted(set(meta.get('fixes',[])+['STR8N-005'])),bootstrap_symbols=symbols,
        bootstrap_utility_sha256=hashlib.sha256(body).hexdigest())
    # Publish matching download encodings for every changed firmware container.
    for name,origin in (('str8n-v2-recovery-f000-ffff',0xF000),('str8n-v2-recovery-e000-efff',0xE000),
        ('str8n-v2-recovery-slot-a0',0xA000),('str8n-v2-recovery-slot-b0',0xB000),('str8n-v2-recovery-a000-dfff',0xA000)):
        data=(OUT/(name+'.bin')).read_bytes();(OUT/(name+'.s19')).write_bytes(s19(dict(enumerate(data,origin)),0xF004))
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('UNFLASHED F-only bootstrap; journal utility',len(body),'bytes; 004/TIME retained',flush=True)

def audit():
    meta=json.loads((OUT/'build.json').read_text());receipts={}
    for name,digest in meta['artifacts'].items():
        assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest,name
    for prefix,folder in (('local','local-display'),('status','boot-status')):
        assert hashlib.sha256((OUT/folder/'asset.bin').read_bytes()).hexdigest()==meta[prefix+'_asset_sha256']
    assert hashlib.sha256((OUT/'bootstrap/bootstrap-journal.bin').read_bytes()).hexdigest()==meta['bootstrap_utility_sha256']
    for name in ('f-only-bootstrap','f-only-fault','apps','time-local','startup-fifo','storage-transfer'):
        p=OUT/(name+'-test-results.json');r=json.loads(p.read_text())
        assert r['passed'] and r['artifacts']==meta['artifacts'],name
        for field in ('local_asset_sha256','status_asset_sha256','bootstrap_utility_sha256'):
            if field in r:assert r[field]==meta[field],(name,field)
        receipts[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    parent=json.loads((OLD/'build.json').read_text())
    assert meta['worker']==parent['worker'] and meta['boot']['BOOT_SR_ROUTE']==parent['boot']['BOOT_SR_ROUTE']
    assert all(meta['boot'][k]==v for k,v in parent['boot'].items() if k.startswith('J_') and v>=0xF000)
    for name in ('str8n-v2-recovery-e000-efff.bin','clock/clock.bin','local-display/asset.bin','boot-status/asset.bin'):
        assert (OUT/name).read_bytes()==(OLD/name).read_bytes(),name
    summary=dict(passed=True,artifacts=meta['artifacts'],receipts=receipts,
        bootstrap_utility_sha256=meta['bootstrap_utility_sha256'],
        local_asset_sha256=meta['local_asset_sha256'],status_asset_sha256=meta['status_asset_sha256'],
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            ROOT/'tools/build_v2_fix005.py',ROOT/'tools/test_v2_fix005.py',ROOT/'tools/test_v2_fix005_faults.py',
            ROOT/'tools/v2-rtc/bootstrap-journal.asm',OUT/'inputs/str8n-v2-boot.asm',OUT/'source/str8n-v2-journal.inc')},
        board_access=False,boards_flashed=False,hardware_tested=False)
    (OUT/'qualification-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PASS six exact-image suites, private ABI, unchanged 004/TIME assets and utility hash; no physical qualification claimed',flush=True)

if __name__=='__main__':audit() if '--audit' in sys.argv else main()
