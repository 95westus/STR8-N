"""Offline beta29 candidate for 2512's ABI; never opens a board port."""
import binascii,json,re,shutil
from pathlib import Path
import build_v2_config as c
import build_v2_recovery as fw
from build_v2_spi_resident import assemble,sha
from beta4_migration import crc,s19,metadata,journal,config_sum
from build_bank_maint_v2 import long_branches
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'BUILD/v2-beta28-b23';OUT=ROOT/'BUILD/v2-beta29-candidate'
RAM=0x7C90
read=lambda p:json.loads(p.read_text())

def insert_hook(text,label,call):
    pattern=r'^('+re.escape(label)+r':)'
    result,n=re.subn(pattern,r'\1 JSR '+call+'\n',text,count=1,flags=re.M)
    assert n,label
    return result

def link_monitor(meta,gate):
    c.OUT,c.SOURCE=OUT,OUT/'inputs';fw.OUT=OUT
    c.include_bytes(OUT/'asm/batch-gate.inc',gate)
    result={}
    for page in (0xA0,0xB0):
        cells,sy=c.assemble(f'monitor-{page:02x}',(page<<8)+128,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=OUT/'inputs'/f'monitor-{page:02x}.asm')
        body=c.dense_image(cells,(page<<8)+128,sy['V2_END']);assert len(body)<=3968,len(body)
        image=bytearray(fw.slot_image(body,sy,page,41,meta['boot_compatibility']));image[70:72]=sy['V2_M_EDIT'].to_bytes(2,'little');image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little')
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').write_bytes(image)
        (OUT/f'str8n-v2-recovery-slot-{page:02x}.s19').write_bytes(s19(dict(enumerate(image,page<<8)),0xF004));result[f'{page:02x}']=sy
    return result

def main():
    assert not list(OUT.glob('hardware-qualification-*.json'))
    parent=read(BASE/'build.json');assert read(BASE/'hardware-qualification-2512.json')['passed']
    for n,h in parent['artifacts'].items():assert sha((BASE/n).read_bytes())==h,n
    shutil.copytree(BASE,OUT,dirs_exist_ok=True)
    for p in list(OUT.glob('*test-results.json'))+list(OUT.glob('*qualification*.json')):p.unlink()
    (OUT/'profile-proof.json').unlink(missing_ok=True)
    inputs=OUT/'inputs';inputs.mkdir(exist_ok=True)
    messages=read(OUT/'source/str8n-v2-text.json')
    for msg in messages:
        if msg['name']=='V2_HELP':msg['text']='D G L J C W S R T'
        if msg['name']=='V2_PROMPT_TEXT':msg['text']='\r\n'
        if msg['name']=='V2_RISK_TEXT':msg['text']=msg['text'].removesuffix('B')
        if msg['name']=='V2_UPDATE_USAGE':msg['text']='U A|B'
        if msg['name']=='V2_INSTALL_TEXT':msg['text']=' replace/erase'
        if msg['name']=='V2_SELF_TEXT':msg['text']='Self\r\n'
    (OUT/'source/str8n-v2-text.json').write_text(json.dumps(messages,indent=2)+'\n')
    pool=bytearray();first=next(i for i,m in enumerate(messages) if m['name']=='V2_BAD_PREFIX')
    for i,msg in enumerate(messages):
        raw=bytearray(msg['text'].replace('{version}','2.0b29').encode())
        if i<first:raw=raw[4:]
        raw[-1]|=128;pool.extend(raw)
    c.include_bytes(OUT/'asm/text-image.inc',pool);p=OUT/'asm/text-image.inc';p.write_text('V2_TEXT:\n'+p.read_text())
    for page in (0xA0,0xB0):
        text=(BASE/'asm'/f'monitor-{page:02x}.asm').read_text()
        text=text.replace('V2_RESET:\n','V2_RESET:\n                        STZ $7EE4\n                        STZ $7EE7\n')
        text=text.replace('V2_ENTER:\n','V2_ENTER:\n                        LDX #B29_GATE_END-B29_GATE_IMAGE-1\nB29_INSTALL:\n                        LDA B29_GATE_IMAGE,X\n                        STA $7C90,X\n                        DEX\n                        BPL B29_INSTALL\n                        LDA #<V2_BANK_READ_LINE\n                        STA $7EEA\n                        LDA #>V2_BANK_READ_LINE\n                        STA $7EEB\n                        JSR B29_CHECK_PROVIDER\n')
        text=text.replace('JSR     V2_BANK_READ_LINE','JSR     $7C90',1)
        text=text.replace("CMP     #$03\n                        BEQ V2_CANCEL", "CMP     #$1B\n                        BEQ V2_CANCEL\n                        CMP     #$03\n                        BEQ V2_CANCEL",1)
        text=text.replace('V2_BANK_READ_LINE:     LDA     V2_SELECTED',"V2_BANK_READ_LINE:     LDA #'B'\n                        JSR V2_PUTC\n                        LDA V2_SELECTED")
        text=text.replace('                        PHX\n                        LDX     #V2_BAD_PREFIX','                        JSR $7C98\n                        PHX\n                        LDX     #V2_BAD_PREFIX',1)
        check='''B29_CHECK_PROVIDER:
        STZ $7EF4
        LDA V2_SELECTED
        PHA
        LDA #2
        STA V2_SELECTED
        STZ V2_ADDR
        LDA #$80
        STA V2_ADDR+1
        LDA #16
        STA V2_COUNT
        JSR V2W_READ
        LDX #3
B29_PROVIDER_HEADER:
        LDA V2_BYTES,X
        CMP B29_PROVIDER_MAGIC,X
        BNE B29_PROVIDER_BAD
        DEX
        BPL B29_PROVIDER_HEADER
        JSR $FAB4
B29_PROVIDER_BLOCK:
        LDY #0
B29_PROVIDER_CRC:
        LDA V2_BYTES,Y
        JSR $FABD
        INY
        CPY #16
        BNE B29_PROVIDER_CRC
        CLC
        LDA V2_ADDR
        ADC #16
        STA V2_ADDR
        BCC B29_PROVIDER_READ
        INC V2_ADDR+1
        LDA V2_ADDR+1
        CMP #$D8
        BEQ B29_PROVIDER_SEAL
B29_PROVIDER_READ:
        JSR V2W_READ
        BRA B29_PROVIDER_BLOCK
B29_PROVIDER_SEAL:
        LDA J_CRC
        ORA J_CRC+1
        BNE B29_PROVIDER_BAD
        LDA #$B9
        STA $7EF4
        BRA B29_PROVIDER_RESTORE
B29_PROVIDER_BAD:
        STZ $7EE4
B29_PROVIDER_RESTORE:
        PLA
        STA V2_SELECTED
        RTS
B29_PROVIDER_MAGIC DB "UX",2,41
'''
        text=text.replace('V2_END:',check+'B29_GATE_IMAGE:\n                        INCLUDE "batch-gate.inc"\nB29_GATE_END:\nV2_END:')
        (inputs/f'monitor-{page:02x}.asm').write_text(text)
    monitors=link_monitor(parent,bytes(96))
    stage=OUT/'xip/source';p=stage/'utilities.asm';text=(BASE/'xip/source/utilities.asm').read_text()
    for a,b in [('BANK MAINT 2.3','BANK MAINT 2.4'),('SRAM 1.3','SRAM 1.4'),('WORK 1.3','WORK 1.4'),('EDU 1.3','EDU 1.4')]:text=text.replace(a,b)
    text=text.replace('DB "UX",1,0','DB "UX",2,41',1)
    text=text.replace('CMP #$03\n                        BEQ MM_LINE_CANCEL','CMP #$1B\n                        BEQ MM_LINE_CANCEL\n                        CMP #$03\n                        BEQ MM_LINE_CANCEL',1)
    # BN reads must use the logical bank reader. Never remap a ROM fetch.
    start=text.index('MM_BN_READ:');end=text.index('MM_BN_JOURNAL_MAGIC',text.index('MM_BN_READBACK:'))
    part=text[start:end]
    seq='LDA $7FEC\n        PHA\n        AND #$11\n        ORA #$EE\n        STA $7FEC'
    assert part.count(seq)==2
    part=part.replace(seq,'LDA X28_BANK\n        PHA\n        LDA #3\n        STA X28_BANK')
    part=part.replace('PLA\n        STA $7FEC','PLA\n        STA X28_BANK')
    part=part.replace('LDA $7FEC\n        STA MM_BN_BANK\n        AND #$11\n        ORA #$EE\n        STA $7FEC','LDA X28_BANK\n        STA MM_BN_BANK\n        LDA #3\n        STA X28_BANK')
    part=part.replace('LDA MM_BN_BANK\n        STA $7FEC','LDA MM_BN_BANK\n        STA X28_BANK')
    part=part.replace('JSR MM_BN_FLASH_BYTE','JSR X28_C9')
    assert '$7FEC' not in part
    text=text[:start]+part+text[end:]
    wrappers=[]
    readers=['V2_BANK_READ_LINE','MM_READLINE','SM_C_READLINE','WK_LINE_READ','ED_READ_LINE','READLINE']
    for provider,(label,oldcall) in enumerate([('MM_BM_MENU','MM_READLINE'),('SM_C_PROMPT','SM_C_READLINE'),('WK_PROMPT','WK_LINE_READ'),('ED_PROMPT','ED_READ_LINE')],1):
        begin=text.index(label+':');i=text.index('JSR '+oldcall,begin);text=text[:i]+text[i:].replace('JSR '+oldcall,f'JSR B29_LINE_{provider}',1)
        wrappers.append(f'''B29_LINE_{provider}:
        LDA $7D30
        CMP #$B0
        BNE B29_OLD_{provider}
        LDA $7EF4
        CMP #$B9
        BNE B29_OLD_{provider}
        LDA #{provider}
        JMP $7C9F
B29_OLD_{provider}: JMP {oldcall}
''')
    for label in ['MM_BM_BAD','MM_BM_CANCEL','MM_BM_FAIL','MM_COMPARE_DIFFERENT','MM_X_BAD','MM_X_FAIL','MM_X_FAIL_TEXT','MM_BN_BAD','MM_BN_FAILED','WK_CON_ERROR','WK_CON_CANCEL','ED_BAD','ED_CONFIG_BAD','ED_SAVE_BAD','ED_CANCEL','ED_ABSENT']:
        text=insert_hook(text,label,'B29_ERROR_HOOK')
    for label in ['MM_LINE_CANCEL','SM_C_LINE_CANCEL','WK_LINE_CANCEL','ED_READ_CANCEL']:
        text=insert_hook(text,label,'B29_CANCEL_HOOK')
    text=text.replace('SM_C_CON_RESULT:\n','SM_C_CON_RESULT:\n        CMP #0\n        BEQ B29_SRAM_OK\n        JSR B29_ERROR_HOOK\nB29_SRAM_OK:\n')
    # G is permitted only for programs explicitly carrying the batch ABI.
    text=text.replace('        JMP X28_EXEC\n','        JSR B29_APP_CHECK\n        BCS B29_APP_OK\n        LDA #$4A\n        JMP SM_C_FINISH\nB29_APP_OK:\n        JMP X28_EXEC\n',1)
    helpers='''B29_ERROR_HOOK:
        PHP
        PHA
        LDA $7D30
        CMP #$B0
        BNE B29_ERROR_DONE
        LDA $7EE4
        BEQ B29_ERROR_DONE
        LDA $7EE7
        CMP #2
        BEQ B29_ERROR_DONE
        LDA #1
        STA $7EE7
B29_ERROR_DONE:
        PLA
        PLP
        RTS
B29_CANCEL_HOOK:
        PHP
        PHA
        LDA $7D30
        CMP #$B0
        BNE B29_CANCEL_DONE
        LDA $7EE4
        BEQ B29_CANCEL_DONE
        LDA #2
        STA $7EE7
B29_CANCEL_DONE:
        PLA
        PLP
        RTS
B29_APP_CHECK:
        LDA $7EE4
        BEQ B29_APP_ACCEPT
        LDA $7D30
        CMP #$B0
        BNE B29_APP_ACCEPT
        LDY #0
        LDA ($FE),Y
        CMP #$80
        BNE B29_APP_REFUSE
        INY
        LDA ($FE),Y
        CMP #4
        BNE B29_APP_REFUSE
        LDY #5
B29_APP_MAGIC:
        LDA ($FE),Y
        CMP B29_APP_ID-2,Y
        BNE B29_APP_REFUSE
        DEY
        CPY #1
        BNE B29_APP_MAGIC
B29_APP_ACCEPT:
        SEC
        RTS
B29_APP_REFUSE:
        JSR B29_ERROR_HOOK
        CLC
        RTS
B29_APP_ID DB "BT",1,1
'''
    clock=build_clock(parent)
    batch=long_branches((ROOT/'tools/v2-spi/batch29.asm').read_text()).replace('BM_LONG_','B29_LONG_')
    full=next(msg['text'] for msg in read(BASE/'source/str8n-v2-text.json') if msg['name']=='V2_HELP')+'\r\nBATCH cmd;cmd (34 text bytes); ESC cancels\r\n'
    raw=full.encode()+b'\0';batch+='\nB29_FULL_HELP_TEXT:\n'+''.join('        DB '+','.join(f'${v:02X}' for v in raw[i:i+16])+'\n' for i in range(0,len(raw),16))
    sy=monitors['a0'];cs=clock['symbols']
    tables=f"B29_MON_DELTA EQU ${((sy['V2_BANK_READ_LINE']>>8)-0xA0):02X}\n"
    tables+='B29_READERS DW '+','.join(f'${a:04X}' for a in [sy['V2_BANK_READ_LINE'],0,0,0,0,cs['READLINE']])+'\n'
    # Native reader addresses are symbolic, keeping tables correct after link.
    tables=tables.replace('$0000,$0000,$0000,$0000','MM_READLINE,SM_C_READLINE,WK_LINE_READ,ED_READ_LINE')
    tables+='B29_LINES DW $7C00,MM_BM_LINE,SM_C_LINE,WK_LINE,ED_LINE,'+f"${cs['LINE']:04X}\n"
    tables+='B29_LENGTHS DW $7EEF,MM_LINELEN,SM_D_LINE_LENGTH,WK_LINE_N,ED_COUNT,'+f"${cs['LINE_LENGTH']:04X}\n"
    tables+='B29_LIMITS DB 41,64,64,56,8,40\n'
    text=text.replace('X28_END:', '\n'.join(wrappers)+helpers+batch+'\n'+tables+'X28_END:')
    p.write_text(text)
    body,sy,_=assemble(stage,'utilities',0x8000,'X28_END',0x8000)
    # Relink the WORK compatibility image and re-embed it without changing size.
    p=stage/'work-stub.asm';stub=p.read_text();old=read(BASE/'xip/build.json')['symbols']
    for label in ['WK_API','WK_ENTRY']:stub=stub.replace(f"${old[label]:04X}",f"${sy[label]:04X}")
    p.write_text(stub);wb,_,_=assemble(stage,'work-stub',0x5000,'STUB_END',0x5100);assert len(wb)<=64
    c.include_bytes(stage/'work-stub.inc',wb+b'\xff'*(64-len(wb)))
    body,sy,_=assemble(stage,'utilities',0x8000,'X28_END',0x8000)
    assert len(body)<=0x57FE,('utility overflow',len(body))
    asset=body+b'\xff'*(0x57FE-len(body));asset+=crc(asset).to_bytes(2,'big');(OUT/'xip/utilities.bin').write_bytes(asset)
    gate,gs=build_gate(sy['B29_ENGINE'],parent['worker']['V2W_SELECT'])
    assert len(gate)<=96,len(gate)
    assert gs['B29_CLOCK']==0x7C94 and gs['B29_ERROR']==0x7C98 and gs['B29_APP']==0x7C9E and gs['B29_COMMON']==0x7C9F
    monitors2=link_monitor(parent,gate+b'\xea'*(96-len(gate)))
    assert monitors2==monitors,'Monitor layout moved between passes'
    # Mark failed native launches for stop-on-error, using remaining status room.
    stage=OUT/'storage-status/source';p=stage/'storage-services.inc';t=p.read_text();t=t.replace('XIP_FAIL:\n','XIP_FAIL:\n        INC $7EE7\n',1)
    t=t.replace('DB "UX",1,0','DB "UX",2,41')
    start=t.index('XIP_ENTRIES:');end=t.index('XIP_NAME_0',start)
    t=t[:start]+'XIP_ENTRIES:\n'+''.join('        DW '+f"${sy[n]:04X}\n" for n in ['MM_START','SM_ENTRY','WK_ENTRY','ED_START','X28_APPS'])+t[end:];p.write_text(t)
    p=stage/'storage-status.asm';t=p.read_text().replace('TIME_UNAVAILABLE:\n','TIME_UNAVAILABLE:\n        LDA KIND\n        LSR A\n        BEQ B29_NOT_TIME_ERROR\n        INC $7EE7\nB29_NOT_TIME_ERROR:\n',1);p.write_text(t)
    p=stage/'local-loader.inc';t=p.read_text().replace('LOCAL_BAD:\n','LOCAL_BAD:\n        INC $7EE7\n',1);p.write_text(t)
    status,ss,_=assemble(stage,'storage-status',0x6E00,'APP_END',0x6E07);assert len(status)<=2558
    sa=status+b'\xff'*(2558-len(status));sa+=crc(sa).to_bytes(2,'big');(OUT/'boot-status/asset.bin').write_bytes(sa)
    regions=[dict(start=0x7BD4,end_exclusive=0x7BF8,bytes=36,purpose='34-byte batch text; padding'),dict(start=0x7C90,end_exclusive=0x7CF0,bytes=96,purpose='bank-safe gateway; byte reads remain 16 bytes at 7C80'),dict(start=0x7EE4,end_exclusive=0x7EFC,bytes=24,purpose='batch state; private vector tail')]
    meta=dict(parent);meta.update(version='2.0b29',generation=41,monitors=monitors2,monitor_bytes={n:s['V2_END']-((int(n,16)<<8)+128) for n,s in monitors2.items()},candidate_only=True,boards_flashed=False,hardware_tested=False,board_access=False,parent_build_sha256=sha((BASE/'build.json').read_bytes()),batch=True,batch_target_active_page=0xB0,batch_ram_regions=regions,batch_ram_bytes=156,batch_queue_bytes=34,batch_max_payload_bytes=34,status_symbols=ss,status_code_bytes=len(status),status_asset_sha256=sha(sa),clock_version='1.9',clock_sha256=clock['sha256'],clock_bytes=clock['bytes'],clock_symbols=clock['symbols'],maintenance_version='2.4',fallback_version='2.0b28',fallback_generation=40)
    for n in ['clock/clock.bin','clock/clock.s19','clock/storage.bin','clock/clock-1.9-2000.s19','boot-status/asset.bin','version/asset.bin']:meta['artifacts'][n]=''
    meta.update(clock_storage_sha256=sha((OUT/'clock/storage.bin').read_bytes()),clock_details_unchanged=False,fallback_build_sha256=sha((BASE/'build.json').read_bytes()))
    meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in meta['artifacts']};(OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    x=read(BASE/'xip/build.json');x.update(version='2.0b29',generation=41,symbols=sy,flash_linked_bytes=len(body),flash_spare_bytes=0x57FE-len(body),sha256=sha(asset),batch_ram_bytes=156)
    (OUT/'xip/build.json').write_text(json.dumps(x,indent=2)+'\n');reference(meta)
    print('BUILT beta29 candidate:',len(body)+2,'utility bytes,',0x57FE-len(body),'spare; batch RAM 156 bytes; CLOCK',clock['bytes'],'bytes. NO FLASH.')

def build_gate(engine,select):
    stage=OUT/'batch/source';stage.mkdir(parents=True,exist_ok=True)
    text=f'''        MODULE BATCH_GATE
        XDEF B29_GATE_END
        CODE
B29_MON: JMP B29_MON_VERIFY
        NOP
B29_CLOCK: LDA #5
        BRA B29_COMMON
B29_ERROR: LDA #1
        STA $7EE7
        RTS
B29_APP: RTS
B29_COMMON:
        STA $7EE8
        LDA $7FEC
        STA $7EE9
        LDA #2
        JSR ${select:04X}
        LDA $7EE8
        JSR ${engine:04X}
        BCS B29_RETURN
        LDA $7EE9
        STA $7FEC
        JSR B29_ORIGINAL
        BCC B29_RAW_RETURN
        PHX
        PHY
        LDA #2
        JSR ${select:04X}
        LDA $7EE8
        ORA #$80
        JSR ${engine:04X}
        PLY
        PLX
B29_RETURN:
        PHP
        LDA $7EE9
        STA $7FEC
        PLP
B29_RAW_RETURN:
        RTS
B29_ORIGINAL: JMP ($7EEA)
B29_MON_VERIFY:
        LDA $7EF4
        CMP #$B9
        BEQ B29_MON_ENABLED
        JMP ($7EEA)
B29_MON_ENABLED:
        LDA #0
        JMP B29_COMMON
B29_GATE_END:
        ENDMOD
'''
    (stage/'batch-gate.asm').write_text(text);body,sy,_=assemble(stage,'batch-gate',RAM,'B29_GATE_END',0x8000);return body,sy

def build_clock(parent):
    stage=OUT/'clock/source';p=stage/'clock.asm';text=p.read_text()
    text=text.replace('START:\n','START: DB $80,4,"BT",1,1\nB29_CLOCK_START:\n',1)
    text=text.replace('JSR READLINE','JSR B29_CLOCK_LINE',1)
    for label in ['BAD_COMMAND','NO_SERVICE','CANCELED','UI_READ_ERROR','UI_STATUS_ERROR','ACK_FAILED','ACK_VERIFY_FAILED','SET_FAILED','CHECK_FAILED','EUI_ACCEPT_FAILED','OFFSET_BAD','OFFSET_FAILED','OFFSET_WRITE_FAILED','BT_FAILED','BT_BAD']:
        text=insert_hook(text,label,'B29_CLOCK_ERROR')
    text=insert_hook(text,'LINE_CANCEL','B29_CLOCK_CANCEL')
    text=text.replace('CLOCK 1.8','CLOCK 1.9')
    helpers='''B29_CLOCK_VALID:
        LDA $7D30
        CMP #$B0
        BNE B29_CLOCK_NO
        LDA $7EF4
        CMP #$B9
        BNE B29_CLOCK_NO
        SEC
        RTS
B29_CLOCK_NO: CLC
        RTS
B29_CLOCK_LINE:
        JSR B29_CLOCK_VALID
        BCC B29_CLOCK_OLD
        JMP $7C94
B29_CLOCK_OLD: JMP READLINE
B29_CLOCK_ERROR:
        PHP
        PHA
        JSR B29_CLOCK_VALID
        BCC B29_CLOCK_ERROR_DONE
        LDA $7EE7
        CMP #2
        BEQ B29_CLOCK_ERROR_DONE
        JSR $7C98
B29_CLOCK_ERROR_DONE:
        PLA
        PLP
        RTS
B29_CLOCK_CANCEL:
        PHP
        PHA
        JSR B29_CLOCK_VALID
        BCC B29_CLOCK_CANCEL_DONE
        LDA #2
        STA $7EE7
B29_CLOCK_CANCEL_DONE:
        PLA
        PLP
        RTS
'''
    text=text.replace('APP_END:',helpers+'APP_END:');p.write_text(text)
    body,sy,_=assemble(stage,'clock',0x2000,'APP_END',0x2000)
    assert sy['APP_END']<0x6400
    image=s19(dict(enumerate(body,0x2000)),0x2000)
    (OUT/'clock/clock.bin').write_bytes(body);(OUT/'clock/clock-1.9-2000.s19').write_bytes(image);(OUT/'clock/clock.s19').write_bytes(image)
    record=b'SR\x01?\x00\x20'+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body;assert len(record)<=12288
    (OUT/'clock/storage.bin').write_bytes(record+b'\xff'*(12288-len(record)))
    info=read(BASE/'clock/build.json');info.update(version='1.9',symbols=sy,bytes=len(body),end=sy['APP_END'],sha256=sha(body),s19_sha256=sha(image),source_sha256=sha(p.read_bytes()),input_source_sha256=sha(text.encode()),storage_sha256=sha((OUT/'clock/storage.bin').read_bytes()),batch_abi=1,hardware_tested=False)
    (OUT/'clock/build.json').write_text(json.dumps(info,indent=2,sort_keys=True)+'\n');(OUT/'clock/core-test-results.json').unlink(missing_ok=True)
    return dict(symbols=sy,bytes=len(body),sha256=sha(body))

def reference(meta):
    source=ROOT/'output/qualification/beta28-2026-10-15/2512/upgrade'
    banks=[bytearray((source/f'post-reset-b{i}.bin').read_bytes()) for i in range(4)]
    banks[2][:0x5800]=(OUT/'xip/utilities.bin').read_bytes();banks[2][0x5800:0x6200]=(OUT/'boot-status/asset.bin').read_bytes()
    banks[3][0x3000:0x4000]=(OUT/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    program=(OUT/'clock/clock.bin').read_bytes();record=b'SR\x01?\x00\x20'+len(program).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+program
    assert len(record)<=12288
    banks[1][0x3000:0x6000]=record+b'\xff'*(12288-len(record))
    j=journal(banks[3]);cfg=bytearray(j[8:24]);cfg[7:13]=b'P\xB0'+(41).to_bytes(4,'little');cfg[14:]=config_sum(cfg)
    counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
    banks[3][0x4000:0x5000]=metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    folder=OUT/'candidate';folder.mkdir(exist_ok=True)
    for i,b in enumerate(banks):(folder/f'b{i}.bin').write_bytes(b)
    for name,off,size in [('str8n-v2-recovery-a000-dfff',0x2000,16384),('str8n-v2-recovery-c000-dfff',0x4000,8192)]:
        data=banks[3][off:off+size];(OUT/(name+'.bin')).write_bytes(data);(OUT/(name+'.s19')).write_bytes(s19(dict(enumerate(data,0x8000+off)),0xF004))
    meta['artifacts']={n:sha((OUT/n).read_bytes()) for n in meta['artifacts']};(OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    (folder/'manifest.json').write_text(json.dumps(dict(candidate_only=True,installation_permitted=False,board_access=False,boards_flashed=False,banks=[sha(b) for b in banks],build_sha256=sha((OUT/'build.json').read_bytes()),note='Offline reference images only; wear counts unchanged; no installer generated.'),indent=2)+'\n')

if __name__=='__main__':main()
