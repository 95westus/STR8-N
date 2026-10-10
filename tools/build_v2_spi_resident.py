"""Link a compact resident SPI candidate in existing sectors 8/9; no board I/O."""
import hashlib,json,re,shutil
from pathlib import Path
import build_v2_config as compiler
import build_v2_rtc_trim as trim
import build_v2_rtc_journal as journal
import build_bank_maint_rtc as maintenance
from build_bank_maint_v2 import long_branches
from build_v2_recovery import relax_branches
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-spi-resident'
VERSION='2.0b14'
GENERATION=23
PROFILE_EXTRA=None
BANNER_EXTRA=None
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())

def merge_identity_tail(prior,candidate):
    """Replace only a compatible, sealed immutable prefix; retain all EUI slots."""
    crc=journal.banner.base.apps.fw.crc
    assert len(prior)==len(candidate)==4096 and candidate[:4]==b'PJ\x06\x01' and crc(candidate[:3072])==0
    assert prior[:4] in (b'PJ\x04\x01',b'PJ\x05\x01',b'PJ\x06\x01') and crc(prior[:3072])==0
    return candidate[:3072]+prior[3072:]

def assemble(stage,name,base,end,minimum):
    folder=stage.parent;compiler.OUT=folder;compiler.SOURCE=stage;(folder/'asm').mkdir(exist_ok=True)
    def run():return compiler.assemble(name,base,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    cells,symbols=run()
    for _ in range(12):
        before=tuple(p.read_text() for p in sorted(stage.glob('*')) if p.suffix in ('.asm','.inc'))
        for p in sorted(stage.glob('*')):
            if p.suffix in ('.asm','.inc'):cells,symbols=relax_branches(p,cells,symbols,run)
        # Shrink ordinary local absolute tail jumps; retain fixed entry tables.
        for p in sorted(stage.glob('*')):
            if p.suffix not in ('.asm','.inc'):continue
            lines=p.read_text().splitlines();changed=False
            # Listing offsets identify instruction locations, including includes.
            listings=(folder/'asm'/f'{name}.lst').read_text(errors='replace').splitlines()
            available={}
            for row in listings:
                m=re.search(r'00:([0-9A-F]{4}): 4C [^\n]*?\bJMP\s+(\w+)\s*(?:;.*)?$',row)
                if m:available.setdefault(m[2],[]).append(base+int(m[1],16))
            for i,line in enumerate(lines):
                m=re.fullmatch(r'(\w+:)?\s*JMP\s+(\w+)\s*(?:;.*)?',line)
                if not m or m[2] not in symbols:continue
                if i and re.search(r'B[A-Z]{2}\s+\w*LONG_\d+',lines[i-1]):continue
                target=symbols[m[2]];positions=available.get(m[2],[])
                if len(positions)!=1:continue
                location=positions[0]
                if minimum<=location and base<=target<symbols[end] and -128<=target-location-2<=127:
                    lines[i]=line.replace('JMP','BRA',1);changed=True
            if changed:p.write_text('\n'.join(lines)+'\n');cells,symbols=run()
        after=tuple(p.read_text() for p in sorted(stage.glob('*')) if p.suffix in ('.asm','.inc'))
        if before==after:break
    return compiler.dense_image(cells,base,symbols[end]),symbols,cells

def profile(source):
    trim.profile(source)
    p=source/'service-kernel.inc';s=p.read_text().replace('DB "RC",2,5','DB "RC",3,7').replace('DB "BT",4,3','DB "BT",5,3');p.write_text(s)
    if PROFILE_EXTRA:PROFILE_EXTRA(source)

def source(stage,from_dir):
    stage.mkdir(parents=True,exist_ok=True)
    for p in from_dir.iterdir():
        if p.is_file():shutil.copyfile(p,stage/p.name)

def equs(path,symbols):path.write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in symbols.items()))

def main():
    journal.OUT=OUT;journal.VERSION=VERSION;journal.GENERATION=GENERATION
    journal.BANNER_SOURCE='rtc-trim-banner.asm';journal.JOURNAL_SOURCE='journal-trim.asm';journal.TRANSPORT_SOURCE='eeprom-trim-transfer.inc';journal.JOURNAL_CODE_END=0x9C00;journal.profile=profile;journal.main()
    original=(ROOT/'tools/v2-spi/spi-prototype.asm').read_text()
    names=set(re.findall(r'^(\w+)\s+EQU\b',original,re.M))|set(re.findall(r'^(\w+):',original,re.M))
    names|={'BUFFER','VALIDATE_SHAPE'}
    def pref(s):return re.sub(r'\b\w+\b',lambda m:'SP_'+m[0] if m[0] in names else m[0],s)
    constants=pref(original[original.index('R EQU'):original.index('START DB')]).replace('SP_MANAGED EQU $3DF0','SP_MANAGED EQU $66AE')
    main_code=original[original.index('DISPATCH:'):original.index('READ_MODE:')]+original[original.index('MEMORY_FRAME:'):original.index('NEXT_RX:')]
    main_code=main_code.replace('        LDA MANAGED\n        BNE DENIED','        BRA DENIED')
    helper_code=original[original.index('READ_MODE:'):original.index('MEMORY_FRAME:')]+original[original.index('INIT:'):original.index('CORE_END:')]
    pointer_code=original[original.index('NEXT_RX:'):original.index('INIT:')]
    bst=OUT/'resident-banner/source';source(bst,OUT/'banner-source')
    banner=(ROOT/'tools/v2-rtc/rtc-trim-banner.asm').read_text().replace('DB "BT",4,3','DB "BT",5,3').replace('DB "PJ",5,1','DB "PJ",6,1')
    banner=banner.replace('        STZ J_DESC\n','',1).replace('        LDX #3\nJ_HEADER_CHECK:',
        'SPI_VALIDATE:\n        LDA #3\n        STA $7D07\n        STZ J_DESC\n        LDX #3\nJ_HEADER_CHECK:')
    banner=banner.replace('BNE J_INSTALL_DONE','BNE SPI_BAD_FORMAT',1)
    banner=banner.replace('BNE J_INSTALL_DONE','BNE SPI_BAD_CRC')
    begin=banner.index('        LDA #$FF\n        STA $7D23')
    last=banner.index('        INY\n        BNE J_CRC_BYTE',begin)
    banner=banner[:begin]+'''        JSR KERNEL_CRC_INIT
        STZ TEXT
        LDA #$90
        STA TEXT+1
        LDY #0
J_CRC_BYTE:
        LDA (TEXT),Y
        JSR KERNEL_CRC_BYTE
'''+banner[last:]
    banner=banner.replace('LDA $7D23','LDA $7D38').replace('ORA $7D24','ORA $7D39')
    library=read(OUT/'build.json')['launcher']
    banner=banner.replace('        CODE','        INCLUDE "kernel-private.inc"\n        CODE',1)
    equs(bst/'kernel-private.inc',{'KERNEL_CRC_INIT':library['AP_CRC_INIT'],'KERNEL_CRC_BYTE':library['AP_CRC_BYTE']})
    banner=banner.replace('J_INSTALL_DONE:\n        RTS','''        LDA $7D07
        ORA #$0C
        STA $7D07
        LDA #0
        SEC
        RTS
SPI_BAD_FORMAT:
        LDA #$80
        CLC
        RTS
SPI_BAD_CRC:
        LDA #$81
        CLC
        RTS''')
    housekeeping='''SPI_PREP:
        STZ SP_CHANGED
        STZ SP_READY
        STZ SP_ERR
        RTS
SPI_REPAIR_MODE:
        LDA SP_OLDMODE
        JSR SP_WRITE_MODE
        JSR SP_READ_MODE
        CMP SP_OLDMODE
        BEQ SPI_MODE_OK
        LDA #7
        STA SP_ERR
SPI_MODE_OK:
        RTS
SPI_FINISH_PHASE:
        LDA SP_KIND
        BNE SPI_PHASE_DONE
        LDA SP_ERR
        BNE SPI_PHASE_DONE
        LDA #3
        STA SP_R+11
SPI_PHASE_DONE:
        RTS
'''
    banner=banner.replace('BANNER_END:',constants+'\n'+pref(helper_code)+housekeeping+'\nBANNER_END:')
    if BANNER_EXTRA:banner=BANNER_EXTRA(banner)
    (bst/'rtc-banner.asm').write_text(long_branches(banner).replace('BM_LONG_','BN_LONG_'))
    bbody,bs,_=assemble(bst,'rtc-banner',0x8900,'BANNER_END',0x890D)
    assert 0x8900+len(bbody)<=0x8DF0,('banner/helpers fit',len(bbody))
    pst=OUT/'resident-provider/source';source(pst,OUT/'split/source')
    provider=(pst/'rtc-provider.asm').read_text().replace('DB "RC",2,5','DB "RC",3,7')
    provider=provider.replace('        JMP PUBLIC_I2C\n','        JMP PUBLIC_I2C\n        JMP SPI_PUBLIC\n        JMP SRAM_PUBLIC\n')
    bridge='''SPI_PUBLIC:
        LDA #0
        BRA SPI_ENTER
SRAM_PUBLIC:
        LDA #1
SPI_ENTER:
        PHA
        LDA BUSY
        ORA $7D22
        BNE SPI_IN_USE
        INC BUSY
        PLA
        STA SP_KIND
        STA SP_OP
        STZ $6659
        STZ $665A
        STZ $665B
        LDA $6664
        AND #4
        BNE SPI_CALL
        JSR SPI_VALIDATE
        BCC SPI_REFUSED
        LDA $6664
        ORA #4
        STA $6664
SPI_CALL:
        INC $7D22
        JMP SPI_HANDLE
SPI_REFUSED:
        STZ BUSY
        RTS
SPI_IN_USE:
        PLA
        LDA #8
        RTS
'''
    provider=provider.replace('\nSERVICE_END',constants+'\n        INCLUDE "spi-links.inc"\n'+bridge+pref(pointer_code)+'\nSERVICE_END')
    (pst/'rtc-provider.asm').write_text(long_branches(provider).replace('BM_LONG_','PV_LONG_'))
    links={k:v for k,v in bs.items() if k.startswith(('SP_','SPI_')) and 0x8900<=v<0x8DF0};links['SPI_HANDLE']=0x9007;equs(pst/'spi-links.inc',links)
    pbody,ps,_=assemble(pst,'rtc-provider',0x8000,'SERVICE_END',0x8019)
    assert 0x8000+len(pbody)+2<=0x8900,('provider/bridge fit',len(pbody))
    jst=OUT/'resident-journal/source';source(jst,OUT/'journal-source')
    eq={'EE_TRANSFER':ps['EE_TRANSFER'],'TRIM_CONTROL':ps['TRIM_CONTROL'],'BIND_FLASH_BYTE':read(OUT/'build.json')['worker']['V2W_BYTE'],
        'SP_BUFFER':ps['BUFFER_VALID'],'SP_VALIDATE_SHAPE':ps['ADDRESS_OK']}
    equs(jst/'journal-transport.inc',eq)
    eq={k:v for k,v in links.items() if k!='SPI_HANDLE'};eq.update({k:ps[k] for k in ('SP_NEXT_RX','SP_NEXT_TX')});equs(jst/'spi-links.inc',eq)
    text=(ROOT/'tools/v2-rtc/journal-trim.asm').read_text().replace('DB "PJ",5,1','DB "PJ",6,1')
    handle='''SPI_HANDLE:
        JSR SPI_PREP
        JSR SP_DISPATCH
        STA SP_ERR
        LDA SP_READY
        BEQ SPI_DONE
        LDA SP_KIND
        BEQ SPI_RESTORE
        LDA SP_CHANGED
        BEQ SPI_RESTORE
        JSR SPI_REPAIR_MODE
SPI_RESTORE:
        JSR SP_RESTORE
SPI_DONE:
        JSR SPI_FINISH_PHASE
SPI_RETURN:
        STZ $7D22
        STZ $6669
        LDA SP_ERR
        RTS
'''
    text=text.replace('JOURNAL_END:',constants+'\n        INCLUDE "spi-links.inc"\n'+handle+pref(main_code)+'\nJOURNAL_END:')
    (jst/'journal.asm').write_text(long_branches(text).replace('BM_LONG_','JS_LONG_'))
    jbody,js,_=assemble(jst,'journal',0x9000,'JOURNAL_END',0x9007)
    assert len(jbody)<=3070,('journal/SPI fit',len(jbody))
    links['SPI_HANDLE']=js['SPI_HANDLE'];equs(pst/'spi-links.inc',links)
    pbody,final_ps,_=assemble(pst,'rtc-provider',0x8000,'SERVICE_END',0x8019)
    assert all(final_ps[k]==ps[k] for k in ('EE_TRANSFER','TRIM_CONTROL','BUFFER_VALID','ADDRESS_OK','SERVICE_END'))
    crc=journal.banner.base.apps.fw.crc;psealed=pbody+crc(pbody).to_bytes(2,'big')
    gst=OUT/'resident-gateway/source';source(gst,OUT/'split/source')
    gate=(gst/'rtc-gateway.asm').read_text()
    begin=gate.index('        LDA PROVIDER_BASE\n');last=gate.index('        JSR CHECK_CRC\n',begin)
    gate=gate[:begin]+'''        LDX #3
CHECK_HEADER:
        LDA PROVIDER_BASE,X
        CMP HEADER_MAGIC,X
        BNE UNAVAILABLE
        DEX
        BPL CHECK_HEADER
'''+gate[last:]
    gate=gate.replace('        STA RTC_RESULT','        CMP #8\n        BEQ GATE_RELEASE\n        STA RTC_RESULT',1).replace('        STZ G_BUSY\n        PLP','GATE_RELEASE:\n        STZ G_BUSY\n        PLP',1)
    gate=gate.replace('\nGATE_END\n','\nHEADER_MAGIC DB "RC",3,7\nGATE_END\n',1)
    (gst/'rtc-gateway.asm').write_text(gate)
    (gst/'split-defs.inc').write_text('PROVIDER_SIZE EQU $1000\nPROVIDER_BASE EQU $8000\nPROVIDER_BITS EQU $EE\nPRIVATE_BASE EQU $6669\nPRIVATE_SIZE EQU 57\n')
    gbody,gs,gcells=assemble(gst,'rtc-gateway',0x6500,'GATE_END',0x6700)
    assert len(gbody)<=326,('gateway before fixed SPI table',len(gbody))
    image=bytearray((OUT/'split/gateway.bin').read_bytes());image[:len(gbody)]=gbody
    image[len(gbody):0x150]=bytes(0x150-len(gbody));image[0x146:0x14D]=b'SP\x01\x01\x4c\xb8\x66'
    image[0x1A2:0x1AE]=b'SM\x01\x01\x4c\xa9\x66\xa2\x06\x4c'+gs['ENTER'].to_bytes(2,'little')
    # 66AE denies public SRAM writes; 66AF is the workspace RESET/session latch.
    image[0x1AE:0x1B0]=b'\x01\0';image[0x1B8:0x1BD]=b'\xa2\x05\x4c'+gs['ENTER'].to_bytes(2,'little')
    assert image[0x1B0:0x1B8]==bytes.fromhex('AD0000608D000060')
    sector=bytearray([255])*4096;sector[:len(psealed)]=psealed;sector[0x900:0x900+len(bbody)]=bbody;sector[0xDF0:0xFF0]=image;sector[-2:]=crc(sector[:-2]).to_bytes(2,'big')
    assert crc(sector)==0 and crc(psealed)==0
    js_sector=jbody+bytes([255])*(3070-len(jbody));js_sector+=crc(js_sector).to_bytes(2,'big')+bytes([255])*1024
    assert crc(js_sector[:3072])==0
    (OUT/'str8n-rtc-component-8000-8fff.bin').write_bytes(sector);(OUT/'str8n-journal-9000-9fff.bin').write_bytes(js_sector)
    (OUT/'split/provider.bin').write_bytes(psealed);(OUT/'split/gateway.bin').write_bytes(image);(OUT/'split/gateway.s19').write_bytes(s19(dict(enumerate(image,0x6500)),0x6500))
    (OUT/'banner/build.json').write_text(json.dumps(dict(bytes=len(bbody),sha256=sha(bbody),symbols=bs,source=str(bst)),indent=2)+'\n')
    (OUT/'journal/build.json').write_text(json.dumps(dict(bytes=len(jbody),entry=0x9004,symbols=js,ee_entry=final_ps['EE_TRANSFER'],sha256=sha(js_sector),source=str(jst)),indent=2)+'\n')
    sm=read(OUT/'split/build.json');sm.update(provider_bytes=len(psealed),provider_sha256=sha(psealed),provider_symbols=final_ps,gateway_code_bytes=len(gbody),gateway_symbols=gs,gateway_sha256=sha(image),provider_crc_scope='whole sector 8',spi=True);(OUT/'split/build.json').write_text(json.dumps(sm,indent=2)+'\n')
    maintenance.OUT=OUT/'maint';maintenance.KERNEL_OUT=OUT;maintenance.VERSION='1.7';maintenance.JOURNAL=True;maintenance.main()
    meta=read(OUT/'build.json');meta.update(spi=True,provider_format=3,eui_binding=True,trim_control=True,clock_version='1.5',journal_code_seal_end=0x9C00,monitor_time=True,time_entry=0x890A,
        provider_bytes=len(psealed),service_component_bytes=len(psealed)+512,banner_bytes=len(bbody),journal_bytes=len(jbody),spi_entry=0x664A,sram_entry=0x66A6,capabilities=15,spi_request='6650-665F',spi_managed=0x66AE,
        spi_sizes=dict(provider=len(psealed),banner_and_helpers=len(bbody),journal_and_spi=len(jbody),gateway=len(gbody),allocation=512),spi_symbols=js,managed_default=1)
    meta['artifacts'].update({n:sha((OUT/n).read_bytes()) for n in ('str8n-rtc-component-8000-8fff.bin','str8n-journal-9000-9fff.bin')});(OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(ROOT/'BUILD/v2-rtc-trim/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    print('Resident SPI:',meta['spi_sizes'],'; public RG/I2 unchanged; no added sector or RAM; no board writes')

if __name__=='__main__':main()
