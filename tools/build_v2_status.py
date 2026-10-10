"""Build an isolated beta16 status candidate; no serial ports or flashing."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_spi_resident as spi
import build_v2_edu_mode as edu
from build_bank_maint_v2 import long_branches
from beta4_migration import s19,crc
ROOT=spi.ROOT;OUT=ROOT/'BUILD/v2-status'
VERSION='2.0b16';GENERATION=25
STORAGE=False
TRIM_DISPLAY=False
WEEKDAY_DISPLAY=False
LOCAL_TIME=False
SPI_STARTUP_ACK=False
COMPACT_BOOT_LOCAL=False
def profile(source):
    edu.profile(source)
    # The banner's existing CR/LF separates it from the recovery selector.
    p=source/'str8n-v2-text.json';messages=json.loads(p.read_text())
    header=next(m for m in messages if m['name']=='V2_BANNER')
    assert header['text'].startswith('\r\nSTR8-N ')
    p.write_text(json.dumps(messages,indent=2)+'\n')
    # V2_ENTER selects the same monitor bank before any use; avoid the
    # duplicate reset assignment to keep the entry guard inside the sector.
    p=source/'str8n-v2.asm';t=p.read_text()
    old='V2_RESET:\n                        LDA #V2_IMAGE_PAGE\n                        STA BOOT_ACTIVE\n'
    assert t.count(old)==1
    assert 'V2_ENTER:' in t and '                        STA BOOT_ACTIVE\nV2_WORKER_COPIED:' in t
    t=t.replace(old,'V2_RESET:\n',1)
    # Software monitor entry still restores workers, services and console,
    # but only cold entry prints the boot/status block. TIME remains explicit.
    marker='                        JSR     V2_CON_INIT\n                        LDX     #V2_BANNER\n'
    assert t.count(marker)==1
    # A/B selection also enters through HOLD with V2_AUTO clear. Capture the
    # reset-cleared EDU mode latch before service discovery sets it, so the
    # first entry always displays status regardless of the autostart choice.
    entry='V2_ENTER:\n'
    assert t.count(entry)==1
    t=t.replace(entry,entry+'                        LDA     $7D27\n                        PHA\n',1)
    t=t.replace(marker,'                        JSR     V2_CON_INIT\n                        PLA\n                        BNE     V2_PROMPT\n                        LDX     #V2_BANNER\n',1)
    # The delay label immediately follows; fall through to recover three
    # bytes needed by the quiet-entry guard in the sealed monitor sector.
    redundant='                        JMP     V2_BOOT_DELAY_DONE\nV2_BOOT_MONITOR:\nV2_BOOT_DELAY_DONE:\n'
    assert t.count(redundant)==1
    t=t.replace(redundant,'V2_BOOT_MONITOR:\nV2_BOOT_DELAY_DONE:\n',1)
    p.write_text(t)
    p=source/'service-eq.inc';p.write_text(p.read_text().replace('SVC_INIT EQU $EE98','SVC_INIT EQU $EE96'))
    p=source/'str8n-v2.asm';p.write_text(p.read_text().replace('JSR $EF53','JSR $EF03'))
    if STORAGE:
        p=source/'app-legacy-dispatch.inc';t=p.read_text();start=t.index('AP_LEGACY_SR:');end=t.index('AP_LEGACY_MAP:',start)
        p.write_text(t[:start]+'AP_LEGACY_SR:         LDA #4\n                       JMP $EF09\n\n'+t[end:])
        p=source/'service-kernel.inc';t=p.read_text();t+='\nSTORAGE_ASSET_FAIL:\n        LDA $7D2B\n        CMP #4\n        BNE STORAGE_CALLED\n        JMP V2_PROMPT\nSTORAGE_CALLED:\n        CMP #3\n        BCC STORAGE_HANDLED\n        LDA #$80\n        CLC\n        RTS\nSTORAGE_HANDLED:\n        SEC\n        RTS\n';p.write_text(t)
def banner(text):
    first=text.index('BANNER:\n');last=text.index('        JSR NL\n        JSR RTC_READ',first)
    text=text[:first]+'BANNER:\n'+text[last:]
    assert 'UTC_TEXT DB "UTC ",0' in text
    text=text.replace('UTC_TEXT DB "UTC ",0','UTC_TEXT DB "RTCC: UTC ",0')
    if WEEKDAY_DISPLAY:
        marker='SHOW_TIME:\n        LDX #<UTC_TEXT\n        LDY #>UTC_TEXT\n        JSR PRINT\n'
        assert text.count(marker)==1
        text=text.replace(marker,marker+'        JSR $6E07\n',1)
    if COMPACT_BOOT_LOCAL:
        # Keep RTC READ and outage/journal processing; omit only boot UTC text.
        marker='SHOW_TIME:\n'
        assert text.count(marker)==1 and 'SHOW_EVENT:' in text
        opening='BANNER:\n        JSR NL\n        JSR RTC_READ\n'
        assert text.count(opening)==1
        text=text.replace(opening,'BANNER:\n        JSR RTC_READ\n',1)
        text=text.replace(marker,marker+'        LDA TIME_MODE\n        BEQ SHOW_EVENT\n        JSR NL\n',1)
    return text
def stage(name,links,base,end,minimum):
    folder=OUT/name;source=folder/'source';source.mkdir(parents=True,exist_ok=True);(folder/'asm').mkdir(exist_ok=True)
    for p in (OUT/'source').glob('*.inc'):shutil.copyfile(p,source/p.name)
    spi.equs(source/'status-links.inc',links)
    path=ROOT/'tools/v2-spi'/f'{name}.asm'
    if name=='storage-status-loader':
        text=(ROOT/'tools/v2-spi/status-loader.asm').read_text().replace('EDU_FRAME:\n        LDA #1\n','EDU_FRAME:\n').replace('LDA #$C9','LDA #$C8').replace('CMP #$74','CMP #$78').replace('        SEC\n        RTS\nTIME_WORD','        JMP STORAGE_ASSET_FAIL\nTIME_WORD').replace('MAGIC DB "BS",1,1','MAGIC DB "BS",1,2')
        if TRIM_DISPLAY:
            text=text.replace('LDA #$70','LDA #$6E').replace('LDA $7000,X','LDA $6E00,X').replace('JMP $7004','JMP $6E04').replace('MAGIC DB "BS",1,2','MAGIC DB "BS",1,3')
    elif name=='storage-status':
        text=(ROOT/'tools/v2-spi/boot-status.asm').read_text().replace('        STA KIND\n        CMP #2','        STA KIND\n        CMP #3\n        BCC STORAGE_DISPLAY\n        JMP STORAGE\nSTORAGE_DISPLAY:\n        CMP #2',1)
        text=text.replace('DB "BS",1,1','DB "BS",1,2')
        if TRIM_DISPLAY:
            text=text.replace('DB "BS",1,2','DB "BS",1,3')
            text=text.replace('        JSR $8907\n','        JSR $8907\n        JSR TRIM_DISPLAY\n')
            text=text.replace('APP_END:\n','        INCLUDE "trim-display.inc"\nAPP_END:\n')
            (source/'trim-display.inc').write_text(long_branches((ROOT/'tools/v2-spi/trim-display.inc').read_text()).replace('BM_LONG_','TD_LONG_'))
        if LOCAL_TIME:
            text=text.replace('        JSR TRIM_DISPLAY\n','        JSR LOCAL_DISPLAY\n')
            text=text.replace('        INCLUDE "trim-display.inc"\n','        INCLUDE "local-loader.inc"\n')
            loader=(ROOT/'tools/v2-spi/local-loader.inc').read_text()
            if COMPACT_BOOT_LOCAL:loader=loader.replace('Local display unavailable','Local time unavailable')
            (source/'local-loader.inc').write_text(long_branches(loader).replace('BM_LONG_','LL_LONG_'))
        if COMPACT_BOOT_LOCAL:
            marker='        JSR CLOCK\n        LDA $7D2A\n'
            assert text.count(marker)==1
            text=text.replace(marker,'        JSR CLOCK\n        LDA KIND\n        BEQ EUI_DONE\n        LDA $7D2A\n',1)
            # Keep the active EDU line, then explicitly mark the saved target.
            text=text.replace('PENDING_TEXT DB "EDU after RESET: ",0','PENDING_TEXT DB "RESET required: ",0',1)
        if WEEKDAY_DISPLAY:
            assert TRIM_DISPLAY
            text=text.replace('        JMP DISPLAY\n','        JMP DISPLAY\n        JMP WEEKDAY\n',1)
            weekday='''WEEKDAY:
        LDA $66C6
        DEC A
        ASL A
        ASL A
        TAY
        LDX #4
WEEKDAY_CHAR:
        LDA WEEKDAYS,Y
        JSR $7E6D
        INY
        DEX
        BNE WEEKDAY_CHAR
        RTS
WEEKDAYS DB "Mon Tue Wed Thu Fri Sat Sun "
'''
            text=text.replace('APP_END:\n',weekday+'APP_END:\n',1)
        if SPI_STARTUP_ACK:
            marker='        BPL SM_HEADER\n        LDX #63\n'
            assert text.count(marker)==1
            text=text.replace(marker,'''        BPL SM_HEADER
        LDA KIND
        BNE SPI_STARTUP_DONE
        JSR SPI_STARTUP_GUARD
        BCC UNAVAILABLE
SPI_STARTUP_DONE:
        LDX #63
''',1)
            guard=(ROOT/'tools/v2-spi/spi-disabled-cb-guard.asm').read_text()
            guard=guard[guard.index('START:\n'):guard.index('APP_END:\n')]
            guard=guard.replace('START:', 'SPI_STARTUP_GUARD:').replace('REFUSE','SPI_STARTUP_REFUSE').replace('SAFE','SPI_STARTUP_SAFE')
            guard=guard.replace('        SEI\n','        SEI\n        LDA $6660\n        ORA $6669\n        BNE SPI_STARTUP_REFUSE\n',1)
            text=text.replace('APP_END:\n',guard+'APP_END:\n',1)
        text=text.replace('APP_END:\n','        INCLUDE "storage-services.inc"\nAPP_END:\n')
        inc=(ROOT/'tools/v2-spi/storage-services.inc').read_text();first=inc.index('FINALIZER:\n');last=inc.index('FINAL_END:\n',first)
        if TRIM_DISPLAY:
            inc=inc.replace('CMP #$D0','CMP #$D2').replace('LDA #$D0','LDA #$D2')
        final='        MODULE STORAGE_FINAL\n        XDEF FINAL_END\n        INCLUDE "str8n-v2-eq.inc"\n        INCLUDE "status-links.inc"\n        CODE\n'+inc[first:last]+'FINAL_END:\n        ENDMOD\n'
        (source/'storage-finalizer.asm').write_text(long_branches(final).replace('BM_LONG_','FINAL_LONG_'))
        fbody,fs,_=spi.assemble(source,'storage-finalizer',0x6B00,'FINAL_END',0x6B00);assert len(fbody)<=256
        (source/'storage-finalizer.bin.inc').write_text(''.join('        DB '+','.join(f'${v:02X}' for v in fbody[i:i+16])+'\n' for i in range(0,len(fbody),16)))
        inc=inc[:first]+'FINALIZER:\n        INCLUDE "storage-finalizer.bin.inc"\n'+inc[last:]
        (source/'storage-services.inc').write_text(long_branches(inc).replace('BM_LONG_','STOR_LONG_'))
    else:
        text=path.read_text()
        if STORAGE and name=='status-mode-init':text=text.replace('DB "ED",1,2','DB "ED",1,3')
    (source/f'{name}.asm').write_text(long_branches(text))
    return spi.assemble(source,name,base,end,minimum)
def main():
    spi.journal.banner.base.LAUNCHER_EXTRA=lambda text:text.replace('AP_HELP_TEXT EQU $EF00','AP_HELP_TEXT EQU $E7F4')
    spi.OUT=OUT;spi.VERSION=VERSION;spi.GENERATION=GENERATION;spi.PROFILE_EXTRA=profile;spi.BANNER_EXTRA=banner;spi.main()
    meta=json.loads((OUT/'build.json').read_text());links={k:meta['launcher'][k] for k in ('SVC_ENABLED','SVC_DONE','AP_CRC_INIT','AP_CRC_BYTE')}
    links.update({k:meta['boot'][k] for k in ('BOOT_API_READ',)});links['V2W_READ']=meta['worker']['V2W_READ']
    if STORAGE:links['STORAGE_ASSET_FAIL']=meta['launcher']['STORAGE_ASSET_FAIL']
    # Core's aliases already supply AP CRC symbols; include them once only.
    body,bs,_=stage('status-mode-init',links,0xEE92,'AUX_END',0xEE96);assert len(body)<=110,('mode helper',len(body))
    links['PRINT']=bs['PRINT']
    links['STATUS_PRINT']=bs['PRINT']
    loader_source=ROOT/'tools/v2-spi/status-loader.asm'
    hooks,hs,_=stage('storage-status-loader' if STORAGE else 'status-loader',links,0xEF00,'AUX_END',0xEF0C);assert len(hooks)<=254,('loader',len(hooks))
    e=bytearray((OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes());assert meta['sr_bytes']<=0x692 and e[0xE92:0xF00]==b'\xff'*110
    e[0xE92:0xE92+len(body)]=body;e[0xF00:0xFFE]=b'\xff'*254
    help_text=b'\r\nAPPS\r\n\0';assert len(help_text)<=10 and e[0x7F4:0x7FE]==b'\xff'*10
    e[0x7F4:0x7F4+len(help_text)]=help_text;e[0x7FE:0x800]=crc(e[:0x7FE]).to_bytes(2,'big')
    e[0xF00:0xF00+len(hooks)]=hooks;e[-2:]=crc(e[:-2]).to_bytes(2,'big')
    assert crc(e)==0 and crc(e[:0x800])==0
    (OUT/'str8n-v2-recovery-e000-efff.bin').write_bytes(e);(OUT/'str8n-v2-recovery-e000-efff.s19').write_bytes(s19(dict(enumerate(e,0xE000)),0xF004))
    links['SHOW_EUI']=json.loads((OUT/'banner/build.json').read_text())['symbols']['SHOW_EUI']
    if STORAGE:
        sm=json.loads((OUT/'store/build.json').read_text());links.update({k:sm[k] for k in ('core_bytes','bytes')})
        links.update(SRAM_CORE_BYTES=(sm['core_bytes']+255)//256*256,SRAM_IMAGE_BYTES=sm['bytes'],SRAM_CORE_SOURCE=0xA018+sm['core_offset'],SRAM_DATA_SOURCE=0xA018+sm['data_offset'],SRAM_AUX_SOURCE=0xA018+sm['aux_offset'],SRAM_EXT_SOURCE=0xA018+sm['ext_offset'])
        links.update(SRAM_LENGTH_LO_MASK=(sm['bytes']&255)^0x80,SRAM_LENGTH_HI_MASK=(sm['bytes']>>8)^0x80)
        for key in ('V2_HEX_WORD','V2_SKIP_SPACES','SR_CLI_SAVE','SR_CLI_RESTORE','SR_CLI_TABLE','SR_PARSE_BANK','SR_CLI_BAD'):links[key]=meta['sr'][key]
    status_base=0x6E00 if TRIM_DISPLAY else 0x7000
    status,s,_=stage('storage-status' if STORAGE else 'boot-status',{k:v for k,v in links.items() if k!='PRINT'},status_base,'APP_END',status_base+7);asset_size=2560 if TRIM_DISPLAY else (2048 if STORAGE else 1024)
    assert len(status)<=asset_size-2,('status size',len(status))
    if STORAGE:assert s['FINAL_END']-s['FINALIZER']<=256,('finalizer',s['FINAL_END']-s['FINALIZER'])
    asset=status+b'\xff'*(asset_size-2-len(status));asset+=crc(asset).to_bytes(2,'big');assert crc(asset)==0
    (OUT/'boot-status').mkdir(exist_ok=True)
    (OUT/'boot-status/asset.bin').write_bytes(asset)
    meta.update(status_banner=True,quiet_monitor_return=True,edu_mode=True,edu_magic_address=0xEE92,edu_magic='45440103' if STORAGE else '45440102',edu_config_entry=0xEF00,edu_status_entry=0xEF09,edu_ram_end_off=0x66FF,edu_ram_end_on=0x64FF,
        storage_services=STORAGE,status_asset_bank=2,status_asset_address=0xC800 if STORAGE else 0xC900,status_asset_bytes=asset_size,status_code_bytes=len(status),status_asset_sha256=hashlib.sha256(asset).hexdigest(),status_ram='7000-77FF temporary staging' if STORAGE else '7000-73FF temporary staging',status_symbols=s,edu_boot_bytes=len(body),edu_hook_bytes=len(hooks))
    if TRIM_DISPLAY:meta.update(trim_display=True,status_ram='6E00-77FF temporary monitor staging; journal/binding scratch retained',status_ram_base=status_base,trim_display_coarse='Explicit ON label; numerical correction unavailable')
    if WEEKDAY_DISPLAY:meta.update(weekday_display=True,weekday_entry=0x6E07)
    if LOCAL_TIME:meta.update(local_time=True,local_asset_bank=2,local_asset_address=0xE000,local_asset_bytes=1536,local_ram='6800-6DFF borrowed; 6B00-6BFF backed up/restored')
    if SPI_STARTUP_ACK:meta.update(spi_startup_disabled_cb_ack=True,spi_startup_ack_scope='cold boot only; active owners refused; resident SPI API unchanged')
    if COMPACT_BOOT_LOCAL:meta.update(compact_boot_local=True,compact_boot_format='RTCC: Ddd YYYY-MM-DD HH:MM:SS (+/-HH:MM)',boot_eui=False,boot_trim=False,detailed_time_unchanged=True)
    meta['artifacts']['str8n-v2-recovery-e000-efff.bin']=hashlib.sha256(e).hexdigest()
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    # Libraries/clients are unchanged. Copy their receipts as historical inputs;
    # new model receipts must bind to this candidate's resident hashes.
    if not STORAGE:
        for name in ('workspace','store','example','hardware-client'):shutil.copytree(ROOT/'BUILD/v2-spi-resident'/name,OUT/name,dirs_exist_ok=True)
    print(f'UNFLASHED {VERSION}:',len(body),'mode +',len(hooks),'loader;',len(status),'status/storage bytes; asset',f"B2:{meta['status_asset_address']:04X}-{meta['status_asset_address']+asset_size-1:04X}")
if __name__=='__main__':main()
