"""Beta35: PF duration and CLOCK 1.10 recent on/off intervals; no board access."""
import json
from pathlib import Path
import shutil
from beta4_migration import crc,s19,journal,config_sum,metadata
from build_v2_spi_resident import assemble
import build_v2_config as c
import build_v2_recovery as fw
from build_bank_maint_v2 import long_branches

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'BUILD/v2-beta34-candidate';OUT=ROOT/'BUILD/v2-beta35-candidate'
read=lambda p:json.loads(p.read_text())
import hashlib
import binascii
sha=lambda b:hashlib.sha256(b).hexdigest()

BOOT_LOADER='''SHOW_TIME:
        LDA TIME_MODE
        BEQ SHOW_EVENT
        LDA #1
        BRA D_LOAD
D_LOAD_DURATION:
        JSR OF_FORMAT
        LDA #0
D_LOAD:
        PHA
        LDA $F3
        PHA
        LDA #2
        STA $F3
        STZ $E2
        STZ $E6
        LDA #$FB
        STA $E3
        LDA #$67
        STA $E7
        JSR KERNEL_CRC_INIT
D_READ_LOOP:
        LDA #16
        STA $EA
        JSR $7830
        LDY #0
D_COPY_LOOP:
        LDA $7C80,Y
        STA ($E6),Y
        JSR KERNEL_CRC_BYTE
        INY
        CPY #16
        BNE D_COPY_LOOP
        LDA $E2
        CLC
        ADC #16
        STA $E2
        STA $E6
        BCC D_READ_LOOP
        INC $E3
        INC $E7
        LDA $E7
        CMP #$6A
        BNE D_READ_LOOP
        LDA $7D38
        ORA $7D39
        BNE D_ASSET_BAD
        LDX #3
D_HEADER:
        LDA $6700,X
        CMP D_MAGIC,X
        BNE D_ASSET_BAD
        DEX
        BPL D_HEADER
        PLA
        STA $F3
        PLA
        JMP $6704
D_ASSET_BAD:
        PLA
        STA $F3
        PLA
        JMP UNAVAILABLE
D_MAGIC DB "PD",1,1
'''

BOOT_WRAP='''D_BOOT_UP:
        LDA #<RTC_OUTAGE+4
        STA OF_PTR
        LDA #>RTC_OUTAGE+4
        STA OF_PTR+1
        JSR OF_DECODE
        SEC
        LDA OF_PTR
        SBC #4
        STA OF_PTR
        BCS D_BOOT_PTR
        DEC OF_PTR+1
D_BOOT_PTR:
        LDA RTC_TIME
        STA D_YEAR
        LDA OF_MONTH
        CMP RTC_TIME+2
        BCC D_BOOT_YEAR
        BNE D_BOOT_PREV
        LDA OF_DAY
        CMP RTC_TIME+3
        BCC D_BOOT_YEAR
        BEQ D_BOOT_YEAR
D_BOOT_PREV:
        DEC D_YEAR
D_BOOT_YEAR:
        LDA RTC_FLAGS
        AND #7
        CMP #7
        LDA #0
        ROL A
        STA D_VALID
        STZ D_KIND
        JMP D_PRINT
'''

CLOCK_WRAP='''D_CLOCK_UP:
        JSR OF_FORMAT
        SEC
        LDA OF_PTR
        SBC #4
        STA OF_PTR
        BCS D_CLOCK_PTR
        DEC OF_PTR+1
D_CLOCK_PTR:
        LDA D_HIST
        BEQ D_LIVE_YEAR
        STZ D_HIST
        LDY #20
        LDA (H_PTR),Y
        STA D_YEAR
        LDY #22
        LDA OF_MONTH
        CMP (H_PTR),Y
        BCC D_CAPTURE_YEAR
        BNE D_CAPTURE_PREV
        INY
        LDA OF_DAY
        CMP (H_PTR),Y
        BCC D_CAPTURE_YEAR
        BEQ D_CAPTURE_YEAR
D_CAPTURE_PREV:
        DEC D_YEAR
D_CAPTURE_YEAR:
        LDY #24
        LDA (H_PTR),Y
        AND #$80
        BRA D_YEAR_READY
D_LIVE_YEAR:
        LDA RTC_TIME
        STA D_YEAR
        LDA OF_MONTH
        CMP RTC_TIME+2
        BCC D_LIVE_READY
        BNE D_LIVE_PREV
        LDA OF_DAY
        CMP RTC_TIME+3
        BCC D_LIVE_READY
        BEQ D_LIVE_READY
D_LIVE_PREV:
        DEC D_YEAR
D_LIVE_READY:
        LDA RTC_FLAGS
        AND #7
        CMP #7
        LDA #0
        ROL A
D_YEAR_READY:
        STA D_VALID
        STZ D_KIND
        JMP D_PRINT
STATS:
        LDA #1
        STA S_STATS
        STZ S_SEEN
        LDX #<S_NOTE
        LDY #>S_NOTE
        JSR PRINT
        JMP HISTORY
S_GAP:
        LDA S_STATS
        BEQ S_GAP_DONE
        LDA S_SEEN
        BEQ S_REMEMBER
        STZ S_OK
        LDA S_VALID
        BEQ S_GAP_CHECKED
        LDY #24
        LDA (H_PTR),Y
        BPL S_GAP_CHECKED
        LDY #20
        LDA S_TIME
        SEC
        SBC (H_PTR),Y
        STA D_HUNDREDS
        INY
        LDA S_TIME+1
        SBC (H_PTR),Y
        BNE S_GAP_CHECKED
        LDA D_HUNDREDS
        CMP #2
        BCS S_GAP_CHECKED
        CMP #1
        BNE S_COMPARE
        LDY #22
        LDA S_TIME+2
        CMP (H_PTR),Y
        BCC S_COMPARE
        BNE S_GAP_CHECKED
        INY
        LDA S_TIME+3
        CMP (H_PTR),Y
        BEQ S_COMPARE
        BCS S_GAP_CHECKED
S_COMPARE:
        LDX #6
S_COMPARE_NEXT:
        LDY S_ORDER,X
        LDA (H_PTR),Y
        CMP S_TIME-20,Y
        BCC S_CHRONOLOGICAL
        BNE S_GAP_CHECKED
        DEX
        BPL S_COMPARE_NEXT
        BRA S_GAP_CHECKED
S_CHRONOLOGICAL:
        LDA #$80
        STA S_OK
S_GAP_CHECKED:
        LDY #3
S_COPY_PAIR:
        LDA S_DOWN,Y
        STA S_PACKET+4,Y
        TYA
        CLC
        ADC #16
        TAX
        PHY
        TXA
        TAY
        LDA (H_PTR),Y
        PLY
        STA S_PACKET,Y
        DEY
        BPL S_COPY_PAIR
        LDA #<S_PACKET
        STA OF_PTR
        LDA #>S_PACKET
        STA OF_PTR+1
        LDA S_YEAR
        STA D_YEAR
        LDA S_OK
        STA D_VALID
        LDA #1
        STA D_KIND
        JSR D_PRINT
        JSR NL
S_REMEMBER:
        LDY #27
S_TIME_COPY:
        LDA (H_PTR),Y
        STA S_TIME-20,Y
        DEY
        CPY #19
        BNE S_TIME_COPY
        LDY #0
S_COPY_DOWN:
        TYA
        CLC
        ADC #12
        TAX
        PHY
        TXA
        TAY
        LDA (H_PTR),Y
        PLY
        STA S_DOWN,Y
        INY
        CPY #4
        BNE S_COPY_DOWN
        LDY #20
        LDA (H_PTR),Y
        STA S_YEAR
        LDY #24
        LDA (H_PTR),Y
        AND #$80
        STA S_VALID
        LDY #19
        LDA (H_PTR),Y
        AND #$1F
        STA S_MONTH
        JSR OF_BCD
        LDY #22
        CMP (H_PTR),Y
        BCC S_UP_YEAR
        BNE S_UP_PREVIOUS
        LDY #18
        LDA (H_PTR),Y
        AND #$3F
        JSR OF_BCD
        LDY #23
        CMP (H_PTR),Y
        BCC S_UP_YEAR
        BEQ S_UP_YEAR
S_UP_PREVIOUS:
        DEC S_YEAR
S_UP_YEAR:
        LDA S_DOWN+3
        AND #$1F
        CMP S_MONTH
        BCC S_READY
        BNE S_PREV_YEAR
        LDY #18
        LDA (H_PTR),Y
        AND #$3F
        STA S_MONTH
        LDA S_DOWN+2
        AND #$3F
        CMP S_MONTH
        BCC S_READY
        BEQ S_READY
S_PREV_YEAR:
        DEC S_YEAR
S_READY:
        LDA #1
        STA S_SEEN
S_GAP_DONE:
        RTS
S_MENU_PROMPT:
        STZ S_STATS
        STZ D_HIST
        LDX #<PROMPT
        LDY #>PROMPT
        JMP PRINT
S_TRY:
        JSR OFFSET_TRY
        LDX #<S_COMMAND
        LDY #>S_COMMAND
        JSR MATCH
        BCC S_NOT_COMMAND
        JMP STATS
S_NOT_COMMAND:
        RTS
S_HISTORY_POINTER:
        JSR HISTORY_POINTER
        JMP S_GAP
S_HISTORY_OUTAGE:
        LDA #1
        STA D_HIST
        JMP OUTAGE_PRETTY
S_COMMAND DB "STATS",0
S_NOTE DB "Recent estimates: minutes; year inferred; <1yr assumed.",13,10,0
S_STATS DB 0
S_SEEN DB 0
S_YEAR DB 0
S_VALID DB 0
S_MONTH DB 0
S_OK DB 0
S_ORDER DB 27,26,25,23,22,20,21
S_TIME DS 8
S_DOWN DS 4
S_PACKET DS 8
D_HIST DB 0
'''


def main():
    parent=read(BASE/'build.json');q=read(BASE/'beta34-qualification.json')
    assert q['passed'] and q['build_sha256']==sha((BASE/'build.json').read_bytes())
    assert not OUT.exists();shutil.copytree(BASE,OUT)
    for p in OUT.glob('beta34-*.json'):p.unlink()
    banks=[bytearray((BASE/f'candidate/b{i}.bin').read_bytes()) for i in range(4)]
    include=long_branches((ROOT/'tools/v2-rtc/outage-duration.inc').read_text()).replace('BM_LONG_','D35_LONG_')
    names=('D_MIN','D_HOUR','D_DAY','D_MONTH','D_YEAR','D_VALID','D_DAYS','D_DAYS_HI','D_HUNDREDS','D_KIND')
    eq=''.join(f'{n} EQU ${0x6A00+i:04X}\n' for i,n in enumerate(names))
    stage=OUT/'resident-banner/source';text=(stage/'rtc-banner.asm').read_text()
    first=text.index('SHOW_TIME:\n');last=text.index('SHOW_EVENT:\n',first)
    original_time=text[first:last];raw_time=original_time[original_time.index('        JSR NL\n'):]
    text=text[:first]+BOOT_LOADER+text[last:]
    assert text.count('        JSR OF_FORMAT\nEVENT_DONE:')==1
    text=text.replace('        JSR OF_FORMAT\nEVENT_DONE:','        JSR D_LOAD_DURATION\nEVENT_DONE:')
    text=text.replace('RTCC: Time stopped - use R CLOCK','RTCC: stopped').replace('RTCC: Time invalid - use R CLOCK','RTCC: invalid')
    text=text.replace('SP_READ_MODE:', '        DS $3F5-(*-START)\nSP_READ_MODE:',1)
    (stage/'rtc-banner.asm').write_text(text)
    body,sy,_=assemble(stage,'rtc-banner',0x8900,'BANNER_END',0x890D)
    old=read(BASE/'banner/build.json')
    assert len(body)==old['bytes'],(len(body),old['bytes'])
    for n,a in old['symbols'].items():
        if n.startswith(('SP_','SPI_')):assert sy[n]==a,(n,a,sy[n])
    sector=bytearray((BASE/'str8n-rtc-component-8000-8fff.bin').read_bytes())
    sector[0x900:0x900+len(body)]=body
    assert sector[0xDF0:0xFFE]==(BASE/'str8n-rtc-component-8000-8fff.bin').read_bytes()[0xDF0:0xFFE]
    sector[-2:]=crc(sector[:-2]).to_bytes(2,'big');assert crc(sector)==0
    (OUT/'str8n-rtc-component-8000-8fff.bin').write_bytes(sector)
    (OUT/'str8n-rtc-component-8000-8fff.s19').write_bytes(s19(dict(enumerate(sector,0x8000)),0x8000))
    (OUT/'banner/build.json').write_text(json.dumps(dict(bytes=len(body),sha256=sha(body),symbols=sy),indent=2)+'\n')
    banks[3][:4096]=sector
    worker=OUT/'pf-worker/source';worker.mkdir(parents=True)
    links=('PRINT','PUTC','DECIMAL_2','NL','OF_PTR','OF_MINUTE','OF_HOUR','OF_DAY','OF_MONTH','OF_TEMP','OF_UNITS','OF_RAW_HOUR','OF_MAX_DAY','OF_DECODE','OF_FORMAT','OF_MONTH_DAYS','SHOW_EVENT','UTC_TEXT')
    defs=''.join(f'{n} EQU ${sy[n]:04X}\n' for n in links)
    wtext='''        MODULE PF_WORKER
        XDEF START
        XDEF APP_END
        INCLUDE "kernel-rtc-api.inc"
'''+defs+eq+'''        CODE
START:  DB "PD",1,1
        CMP #1
        BNE D_BOOT_UP
'''+raw_time+'        JMP SHOW_EVENT\n'+BOOT_WRAP+'        INCLUDE "outage-duration.inc"\nAPP_END:\n        ENDMOD\n        END\n'
    (worker/'pf.asm').write_text(wtext);(worker/'outage-duration.inc').write_text(include)
    shutil.copyfile(stage/'kernel-rtc-api.inc',worker/'kernel-rtc-api.inc')
    wb,ws,_=assemble(worker,'pf',0x6700,'APP_END',0x6704);assert len(wb)<=766,len(wb)
    wa=wb+b'\xff'*(766-len(wb));wa+=crc(wa).to_bytes(2,'big')
    assert crc(wa)==0
    (OUT/'pf-worker/asset.bin').write_bytes(wa)
    (OUT/'pf-worker/build.json').write_text(json.dumps(dict(bytes=len(wb),symbols=ws),indent=2)+'\n')
    version=bytearray((BASE/'version/asset.bin').read_bytes());assert version[0x300:0x600]==b'\xff'*768
    version[0x300:0x600]=wa;seed=crc(version[:-10])
    for word in range(65536):
        patch=word.to_bytes(2,'big')
        if binascii.crc_hqx(patch+version[-8:],seed)==0:version[-10:-8]=patch;break
    else:raise AssertionError('VERSION CRC patch unavailable')
    assert crc(version)==0
    (OUT/'version/asset.bin').write_bytes(version);banks[2][0x7800:]=version
    # A RAM CLOCK image can grow within its existing three-sector record.
    stage=OUT/'clock/source';text=(stage/'clock.asm').read_text().replace('CLOCK 1.9','CLOCK 1.10')
    # Preserve the three private CLOCK input addresses used by the BATCH gate.
    text=text.replace('        LDX #<PROMPT\n        LDY #>PROMPT\n        JSR PRINT\n','        JSR S_MENU_PROMPT\n        NOP\n        NOP\n        NOP\n        NOP\n',1)
    text=text.replace('        JSR OFFSET_TRY\n','        JSR S_TRY\n',1)
    text=text.replace('HISTORY_ROW:\n        JSR HISTORY_POINTER\n','HISTORY_ROW:\n        JSR S_HISTORY_POINTER\n',1)
    text=text.replace('        JMP OUTAGE_PRETTY\nHISTORY_CALL:', '        JMP S_HISTORY_OUTAGE\nHISTORY_CALL:',1)
    text=text.replace('        JSR OF_FORMAT\n        JMP NL\nHEX_SPACE:', '        JSR D_CLOCK_UP\n        JMP NL\nHEX_SPACE:',1)
    text=text.replace('No saved event in requested history.','No saved event in requested history',1)
    oldhelp='HISTORY        Saved outages (UTC; slots 1-4)'
    newhelp='HISTORY/STATS  Recent PF intervals (UTC)'
    text=text.replace(oldhelp,newhelp.ljust(len(oldhelp)),1)
    # CLOCK owns ordinary application RAM for its scratch variables.
    variables=''.join(n+' DB 0\n' for n in names)
    text=text.replace('APP_END:',variables+long_branches(CLOCK_WRAP).replace('BM_LONG_','C35_LONG_')+'        INCLUDE "outage-duration.inc"\nAPP_END:')
    (stage/'clock.asm').write_text(text);(stage/'outage-duration.inc').write_text(include)
    clock,cs,_=assemble(stage,'clock',0x2000,'APP_END',0x2000)
    assert len(clock)<=12264,len(clock)
    oldclock=read(BASE/'clock/build.json')['symbols']
    for n in ('READLINE','LINE','LINE_LENGTH','OVERFLOW'):
        assert cs[n]==oldclock[n],(n,cs[n],oldclock[n])
    (OUT/'clock/clock.bin').write_bytes(clock)
    (OUT/'clock/clock.s19').write_bytes(s19(dict(enumerate(clock,0x2000)),0x2000))
    record=b'SR\x01\x3f\x00\x20'+len(clock).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+clock
    record+=b'\xff'*(12288-len(record));(OUT/'clock/storage.bin').write_bytes(record)
    meta_clock=read(BASE/'clock/build.json');meta_clock.update(version='1.10',bytes=len(clock),end=0x2000+len(clock),sha256=sha(clock),symbols=cs,storage_sha256=sha(record),s19_sha256=sha((OUT/'clock/clock.s19').read_bytes()))
    (OUT/'clock/build.json').write_text(json.dumps(meta_clock,indent=2)+'\n')
    # Retain beta28 A; install the new beta35 monitor into B.
    textmeta=read(OUT/'source/str8n-v2-text.json')
    for row in textmeta:row['text']=row['text'].replace('2.0b34','2.0b35')
    (OUT/'source/str8n-v2-text.json').write_text(json.dumps(textmeta,indent=2)+'\n')
    first=next(i for i,row in enumerate(textmeta) if row['name']=='V2_BAD_PREFIX');pool=bytearray()
    for i,row in enumerate(textmeta):
        raw=bytearray(row['text'].replace('{version}','2.0b35').encode())
        if i<first:raw=raw[4:]
        raw[-1]|=128;pool.extend(raw)
    c.OUT,c.SOURCE,fw.OUT=OUT,OUT/'inputs',OUT;c.include_bytes(OUT/'asm/text-image.inc',pool)
    p=OUT/'asm/text-image.inc';p.write_text('V2_TEXT:\n'+p.read_text())
    cells,ms=c.assemble('monitor-b0',0xB080,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=OUT/'inputs/monitor-b0.asm')
    code=c.dense_image(cells,0xB080,ms['V2_END']);image=bytearray(fw.slot_image(code,ms,0xB0,47,parent['boot_compatibility']))
    image[70:72]=ms['V2_M_EDIT'].to_bytes(2,'little');image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little')
    (OUT/'str8n-v2-recovery-slot-b0.bin').write_bytes(image)
    (OUT/'str8n-v2-recovery-slot-b0.s19').write_bytes(s19(dict(enumerate(image,0xB000)),0xF004))
    banks[3][0x3000:0x4000]=image
    j=journal(banks[3]);cfg=bytearray(j[8:24]);cfg[7:13]=b'P\xB0'+(47).to_bytes(4,'little');cfg[14:]=config_sum(cfg)
    counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
    banks[3][0x4000:0x5000]=metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    for i,b in enumerate(banks):(OUT/f'candidate/b{i}.bin').write_bytes(b)
    for n,off,size in [('str8n-v2-recovery-a000-dfff',0x2000,16384),('str8n-v2-recovery-c000-dfff',0x4000,8192)]:
        b=banks[3][off:off+size];(OUT/(n+'.bin')).write_bytes(b);(OUT/(n+'.s19')).write_bytes(s19(dict(enumerate(b,0x8000+off)),0xF004))
    meta=dict(parent);meta.update(version='2.0b35',generation=47,clock_bytes=len(clock),banner_bytes=len(body),
        version_asset_sha256=sha(version),pf_worker_bytes=len(wb),pf_worker_flash=0xFB00,pf_worker_ram=0x6700,
        clock_version='1.10',clock_sha256=sha(clock),clock_storage_sha256=sha(record),clock_symbols=cs,
        parent_build_sha256=sha((BASE/'build.json').read_bytes()),outage_duration=True,recent_interval_stats=True,
        persistent_history_format_unchanged=True,hardware_tested=False,boards_flashed=False)
    meta['monitors']['b0']=ms
    meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in parent['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    (OUT/'candidate/manifest.json').write_text(json.dumps(dict(version='2.0b35',candidate_only=True,
        installation_permitted=False,board_access=False,boards_flashed=False,
        banks=[sha(b) for b in banks],build_sha256=sha((OUT/'build.json').read_bytes())),indent=2)+'\n')
    print('BUILT beta35; banner',len(body),'/1263; CLOCK',len(clock),'/12264; ASM unchanged',flush=True)


if __name__=='__main__':main()
