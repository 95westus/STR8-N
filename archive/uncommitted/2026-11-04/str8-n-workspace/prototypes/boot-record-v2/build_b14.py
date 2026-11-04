"""Offline b14: unframed $0200 BIN load, three-second idle autorun, no R."""
import argparse,json,re,sys
from pathlib import Path
import build_b13 as previous
HERE=previous.HERE;ROOT=previous.ROOT
BASE=ROOT/'BUILD/pr04-b13-packed-r1'
HELP=b'L=BIN 0200 idle3s/run\r\nA/B 0-3 C1=USB/2=ACIA/3=both\r\n'
SPARES={}
# Empty poll budgets are qualified against actual linked instructions.
FT_POLLS=214256
AC_POLLS=203363

def pad(label,count,byte='$FF'):
    assert count>=0,(label,count);SPARES[label]=count
    return label+':\n'+('        DB '+','.join([byte]*count)+'\n' if count else '')

def b14_source(source):
    source=previous.b13_source(source)
    sy=json.loads((BASE/'symbols.json').read_bytes())['core/str8n-v2-boot']
    eq='B14_TICKS EQU $7C68\nB14_PENDING EQU $7C69\nB14_PENDING_BYTE EQU $7C6A\n'
    for key,n in [('FT',FT_POLLS),('AC',AC_POLLS)]:
        # Cascaded DEX/DEY/DEC count: X/Y zero encode 256, not zero.
        lo=(n-1)%256+1;mid=((n-1)//256)%256+1;hi=(n-1)//65536+1
        eq+=f'B14_{key}_LO EQU {lo%256}\nB14_{key}_MID EQU {mid%256}\nB14_{key}_HI EQU {hi}\n'
    source,n=re.subn(r'^ +CODE\n',lambda _:eq+'        CODE\n',source,count=1,flags=re.M);assert n==1
    for label in ['RL_HEADER','RL_VALID','RL_START','RL_LENGTH','RL_END','RL_LEFT']:
        source=re.sub(r'^'+label+r' EQU [^\n]+\n','',source,flags=re.M)
    source=source.replace('        STZ RL_VALID','        DB $EA,$EA,$EA')
    begin,end=source.index("        CMP #'L'",source.index('BOOT_MENU:')),source.index("        CMP #'A'",source.index('BOOT_MENU:'))
    source=source[:begin]+"        CMP #'L'\n        BNE B14_NOT_LOAD\n        JMP RL_LOAD\nB14_NOT_LOAD:\n"+pad('B14_FREE_DISPATCH',15,'$EA')+source[end:]
    begin,end=source.index('RL_RUN:'),source.index('BOOT_USB_WAIT_DONE:')
    # The raw body and vector image are measured separately; no shared entry
    # is allowed to drift when their explicit original allocations are filled.
    main=(HERE/'raw-loader-b14.inc').read_text()
    source=source[:begin]+'BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"\n'+main+'B14_MAIN_END:\n        DS B14_MAIN_BASE+106-B14_MAIN_END,$FF\n'+source[end:]
    source=source.replace('BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"\n'+main,
                          'BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"\nB14_MAIN_BASE:\n'+main,1)
    begin,end=source.index('B12_NO_IMAGE:'),source.index('BOOT_CONSUMING:')
    init=(HERE/'raw-start-b14.inc').read_text()
    source=source[:begin]+'B14_INIT_BASE:\n'+init+'B14_INIT_END:\n        DS B14_INIT_BASE+99-B14_INIT_END,$FF\n'+source[end:]
    begin,end=source.index('; RAW_POLL preserves X/Y.'),source.index('BOOT_READ_RECORD:')
    source=source[:begin]+'BOOT_STARTUP:\n        JMP B13_USB_START\n'+pad('B14_FREE_FIRST',17)+source[end:]
    # Remove the old ROM vector copy and startup trampoline at F's tail.
    begin=source.index('BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"',source.index('BOOT_WORKER_IMAGE:'))
    source=source[:begin]
    for label,body,capacity in [('B12_HELP_TEXT',HELP[:30],31),('B12_HELP_TAIL',HELP[30:],24)]:
        source,n=re.subn(label+r': DB [0-9,]+\n',lambda _:label+': DB '+','.join(str(x) for x in body+b'\0')+'\n'+pad('B14_FREE_'+label,capacity-len(body)-1),source)
        assert n==1,label
    old='Recovery L/R A/B 0-3 C1/2/3 ?';new='Recovery L A/B 0-3 C1/2/3 ?'
    source=source.replace('BR_RECOVERY: DB "'+old+'",13,10,0','BR_RECOVERY: DB "'+new+'",13,10,0\n'+pad('B14_FREE_BANNER',len(old)-len(new)))
    begin,end=source.index('BR_REFUSED:'),source.index('BOOT_DRAIN_DONE:')
    texts='BR_REFUSED: DB "REFUSED: RAM range",13,10,0\nB14_RX_TEXT: DB "REFUSED: receive error",13,10,0\nRL_SEND: DB "SEND BIN",13,10,0\n'
    # This allocation is 65 bytes in b13; preserve the cleanup entry after it.
    capacity=sy['BOOT_DRAIN_DONE']-sy['BR_REFUSED']
    used=sum(len(t)+3 for t in ['REFUSED: RAM range','REFUSED: receive error','SEND BIN'])
    source=source[:begin]+texts+pad('B14_FREE_MESSAGES',capacity-used)+source[end:]
    source=source.replace('RL_SIGNATURE: DB "RLP1",1,1',pad('B14_FREE_SIGNATURE',6).rstrip())
    assert all(label+':' not in source for label in ['RL_RUN','RL_HEADER_BYTE','RL_HCRC','RL_MAGIC','RL_BODY','RL_GET','RL_ADVANCE','B10_WAIT_FIRST'])
    return source

def main():
    code=Path(previous.previous.previous.__file__).read_text()
    code=code[code.index('def main():'):code.index("if __name__=='__main__':")]
    code=code.replace('0x8000000B','0x8000000E').replace('2.0proto b11','2.0proto b14').replace('b11_source','b14_source')
    code=code.replace('source=original.read_text()', '''source=original.read_text()
    source=source.replace("a.link('core','ram-config',0x2000", "a.link('core','ram-config',0x0200")
    source=source.replace("config=dict(start=0x2000", "config=dict(start=0x0200")
    source=source.replace('from installer_build import build_installer','from installer_build_b14 import build_installer')''')
    ns=dict(__file__=__file__,HERE=HERE,ROOT=ROOT,Path=Path,argparse=argparse,json=json,sys=sys,HELP=HELP,b14_source=b14_source)
    exec(compile(code,__file__,'exec'),ns);ns['main']()
    out=Path(sys.argv[sys.argv.index('--out')+1]);path=out/'prototype-report.json';report=json.loads(path.read_bytes())
    report.pop('b11_recovery_patch');s=json.loads((out/'symbols.json').read_bytes())['core/str8n-v2-boot']
    a=json.loads((BASE/'symbols.json').read_bytes())['core/str8n-v2-boot']
    for k,v in a.items():
        if k.startswith('BOOT_API_') or k in ['BOOT_RESET','BOOT_SLOT_CHECK','BOOT_CHECK_FIELDS','BOOT_READ_RECORD','BOOT_PRINT','J_CRC_INIT','J_CRC_BYTE','BOOT_READ_LINE','BOOT_CON_SELECT']:
            assert s[k]==v,(k,hex(v),hex(s[k]))
    for name in ['RL_RUN','RL_GET','RL_ADVANCE','RL_SIGNATURE','RL_HEADER','RL_LENGTH','RL_VALID']:assert name not in s,name
    main_used=s['B14_MAIN_END']-s['B14_MAIN_BASE'];init_used=s['B14_INIT_END']-s['B14_INIT_BASE']
    SPARES['B14_FREE_MAIN']=106-main_used;SPARES['B14_FREE_INIT']=99-init_used
    inherited={k:v for k,v in previous.previous.SPARES.items() if k in s and k.startswith(('B12_FREE_','B12_EXISTING_','B13_FREE_'))}
    holes={k:dict(address=s[k],bytes=n) for k,n in {**inherited,**SPARES}.items() if n and k in s}
    for name in ['MAIN','INIT']:
        n=SPARES['B14_FREE_'+name]
        if n:holes['B14_FREE_'+name]=dict(address=s['B14_'+name+'_END'],bytes=n)
    report['raw_loader']=dict(load_start=0x200,entry=0x200,end_exclusive=0x6500,max_bytes=0x6300,
        protocol='raw BIN',header_bytes=0,length_field=False,CRC=False,run_command=False,
        first_byte_wait='indefinite; every byte value including 03 is data',idle_seconds=3,nominal_CPU_Hz=8_000_000,
        idle_rule='Reset after every byte; then execute $0200 after three seconds without input',
        port='First data source among enabled consoles owns the transfer; other port untouched',
        errors='Overflow or detected serial receive error refuses without execution',
        ready='SEND BIN; optional command CRLF LF is consumed before this message',
        empty_polls=dict(FT245=FT_POLLS,ACIA=AC_POLLS),main_bytes=main_used,init_bytes=init_used,
        internal_spare_regions=holes,internal_spare_bytes=sum(x['bytes'] for x in holes.values()),
        contiguous_free_bytes=report['f']['free'],total_spare_bytes=report['f']['free']+sum(x['bytes'] for x in holes.values()),
        shared_entry_addresses_unchanged=True,vector_ROM_copy_relocated=True,hardware_flashed=False)
    report['new_f_features']=[x for x in report['new_f_features'] if x not in ['framed CRC16 RAM load','RAM readback and escrow','explicit RAM run']]+['raw $0200 load and three-second idle autorun']
    report['console']['binary']='Raw load: first data port owns transfer, no echo or control decoding; text console restored before execution'
    report['new_ram_tools']=['Raw $0200 CONFIG and OIP1 opaque installer; OIP1 retains its own flash safety protocol']
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS b14 offline',report['f'],report['raw_loader'],flush=True)

if __name__=='__main__':main()
