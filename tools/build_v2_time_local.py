"""Unflashed asset-only TIME candidate based on qualified generation 35."""
import hashlib,json,shutil
from pathlib import Path
from build_v2_spi_resident import assemble
from beta4_migration import crc

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'BUILD/v2-startup-fifo';OUT=ROOT/'BUILD/v2-time-local'

def main():
    shutil.copytree(OLD,OUT,dirs_exist_ok=True)
    path=OUT/'local-display/source/local-display.asm';text=path.read_text()
    before='        LDA KIND\n                        BEQ LOCAL_BOOT_DISPLAY\n        JSR TRIM_DISPLAY'
    assert text.count(before)==1
    text=text.replace(before,'        LDA KIND\n        CMP #1\n        BNE LOCAL_BOOT_DISPLAY\n        JSR TRIM_DISPLAY',1)
    before='TZ_RENDER:\n        JSR $7E7F\n        LDA KIND\n'
    assert text.count(before)==1
    text=text.replace(before,before+'        CMP #2\n        BEQ TZ_DATE_ONLY\n        LDA KIND\n',1)
    text=text.replace('TZ_PREFIX_READY:\n        JSR TZ_PRINT\n','TZ_PREFIX_READY:\n        JSR TZ_PRINT\nTZ_DATE_ONLY:\n',1)
    path.write_text(text)
    body,local,_=assemble(path.parent,'local-display',0x6700,'APP_END',0x6707)
    assert len(body)<=1790
    asset=body+b'\xff'*(1790-len(body));asset+=crc(asset).to_bytes(2,'big');assert crc(asset)==0
    (OUT/'local-display/asset.bin').write_bytes(asset)

    path=OUT/'storage-status/source/storage-status.asm';text=path.read_text()
    before='TIME_ONLY:\n        JSR CLOCK\n        SEC\n        RTS\n'
    after='''TIME_ONLY:
        LDA $7D2A
        BEQ TIME_UNAVAILABLE
        JSR $6504
        BCC TIME_UNAVAILABLE
        JSR LOCAL_DISPLAY
        SEC
        RTS
TIME_UNAVAILABLE:
        LDX #<CLOCK_UNAVAILABLE
        LDY #>CLOCK_UNAVAILABLE
        JSR PRINT
        SEC
        RTS
'''
    assert text.count(before)==1;text=text.replace(before,after,1)
    # Share the handled-error tail with TIME, without changing cold boot errors.
    before='CLOCK_ABSENT:\n        JSR LOCAL_DISPLAY\n        LDX #<CLOCK_UNAVAILABLE\n        LDY #>CLOCK_UNAVAILABLE\n        JMP PRINT'
    assert text.count(before)==1
    text=text.replace(before,'CLOCK_ABSENT:\n        JSR LOCAL_DISPLAY\n        BRA TIME_UNAVAILABLE',1)
    # This helper returns C=1 for a handled TIME, including an unavailable RTC.
    # Reclaim a repeated context prefix; CLOCK's own EUI command is unchanged.
    text=text.replace('EUI_UNAVAILABLE DB 13,10,"RTCC: EUI unavailable",0','EUI_UNAVAILABLE DB 13,10,"EUI unknown",0',1)
    path.write_text(text)
    body,status,_=assemble(path.parent,'storage-status',0x6E00,'APP_END',0x6E07)
    assert len(body)<=2558,('status capacity',len(body))
    asset=body+b'\xff'*(2558-len(body));asset+=crc(asset).to_bytes(2,'big');assert crc(asset)==0
    (OUT/'boot-status/asset.bin').write_bytes(asset)
    meta=json.loads((OUT/'build.json').read_text())
    meta.update(time_local_only=True,detailed_time_unchanged=False,clock_details_unchanged=True,
        asset_only_candidate=True,hardware_tested=False,
        time_format='Ddd YYYY-MM-DD HH:MM:SS (+/-HH:MM)',
        local_symbols=local,local_code_bytes=local['APP_END']-0x6700,
        local_asset_sha256=hashlib.sha256((OUT/'local-display/asset.bin').read_bytes()).hexdigest(),
        status_symbols=status,status_code_bytes=len(body),status_asset_sha256=hashlib.sha256(asset).hexdigest())
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    for name in meta['artifacts']:assert (OUT/name).read_bytes()==(OLD/name).read_bytes(),name
    for name in ('clock/clock.bin','clock/source/clock.asm','maint/board-name.bin'):
        assert (OUT/name).read_bytes()==(OLD/name).read_bytes(),name
    print('UNFLASHED TIME local-only; local helper',meta['local_code_bytes'],'/1790; status',len(body),'/2558; CLOCK and firmware core unchanged',flush=True)

if __name__=='__main__':main()
