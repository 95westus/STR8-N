"""Build read-only STATUS extents once; frozen F and native app bodies are reused."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,equs,sha
from mona_branches import conservative_branches

TEXT={
 'ST_CPU02':'CPU: 65C02\r\n','ST_CPU816':'CPU: 65C816 emulation\r\n',
 'ST_BOARD':'Board: ','ST_UNKNOWN':'--*','ST_RAM':'RAM $0200-$66FF\r\n',
 'ST_EDU_ON':'EDU ON\r\n','ST_EDU_OFF_TEXT':'EDU OFF\r\n',
 'ST_PROGRAM':'SSRAM: PROGRAM payload ','ST_WORKSPACE':'SSRAM: WORKSPACE ',
 'ST_BYTES_TEXT':' bytes\r\n','ST_SRAM_NONE':'SSRAM: --*\r\n',
 'ST_RTCC':'RTCC: ','ST_NONE':'--*\r\n','ST_BATTERY':'Battery: ',
 'ST_WITHIN':'within age policy*','ST_WARN_TEXT':'warning due*',
 'ST_REPLACE_TEXT':'replacement due*','ST_UNCERTAIN':'date uncertain*',
 'ST_CAVEAT':'* Health/prior wear unmeasured; attempts.\r\n',
 'ST_MONITOR':'MONITOR ','ST_GENERATION':' gen ','ST_VALID':' VALID',
 'ST_INVALID':' INVALID','ST_DEFAULT':' default',
 'ST_WEEKDAYS':'Mon Tue Wed Thu Fri Sat Sun ',
 'ST_FLASH':'FLASH: ','ST_MAXIMUM':' tracked max ','ST_UTC':' UTC',
}

def seal(body,size):
    if len(body)>size-2:raise ValueError(f'Linked {len(body)} bytes exceed {size-2} code/data bytes')
    body=body.ljust(size-2,b'\xff');return body+binascii.crc_hqx(body,65535).to_bytes(2,'big')

def build(out,ram_trial=False):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    f=(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert len(f)==4096 and sha(f)==freeze['sha256']
    ws=equs(ROOT/'src/core/worker-public-symbols.inc');bs=equs(ROOT/'src/core/boot-symbols.inc')
    assert ws['V2W_END']==0x7BE8
    text_bases=(0x2000,0x20C0) if ram_trial else (0x8040,0x8240)
    code_bases=(0x3000,0x3400) if ram_trial else (0xAC00,0xFA50)
    interface=(ROOT/'monitors/status/status-interface.inc').read_text(encoding='utf-8')
    if ram_trial:
        def relocate(m):
            value=int(m[2],16)
            if 0xAC00<=value<0xB000:value+=0x3000-0xAC00
            elif 0xFA50<=value<0xFFFA:value+=0x3400-0xFA50
            return m[1]+f'{value:04X}'
        interface=re.sub(r'^(\w+ EQU \$)([0-9A-Fa-f]+)',relocate,interface,flags=re.M)
    # Partition complete strings into two existing unused192-byte intervals.
    items=[(k,v.encode('ascii')+b'\0') for k,v in TEXT.items()]
    reachable={0:[]}
    for i,(_,body) in enumerate(items):
        for n,chosen in list(reachable.items()):
            if n+len(body)<=190:reachable.setdefault(n+len(body),chosen+[i])
    total=sum(len(v) for _,v in items)
    fits=[n for n in reachable if total-n<=190]
    if not fits:raise ValueError(f'{total} string bytes do not fit two190-byte intervals')
    first=set(reachable[max(fits)]);symbols={};artifacts={}
    for j,base in enumerate(text_bases):
        raw=bytearray()
        for i,(name,body) in enumerate(items):
            if (i in first)==(j==0):symbols[name]=base+len(raw);raw.extend(body)
        image=seal(bytes(raw),192);name=f'STATUS-text-{base:04X}.bin';(out/name).write_bytes(image)
        artifacts[name]=dict(address=f'{base:04X}',bytes=len(image),data_bytes=len(raw),sha256=sha(image))
    text_symbols=''.join(f'{k} EQU ${v:04X}\n' for k,v in symbols.items())
    bindings=f'ST_F_READ EQU ${ws["V2W_READ"]:04X}\nST_F_SLOT_CHECK EQU ${bs["BOOT_SLOT_CHECK"]:04X}\n'
    files=['status-core.asm','status-details.asm','status-sram.inc','status-mon-sram.inc','status-interface.inc']
    sources={('monitors/status/'+n):sha((ROOT/'monitors/status'/n).read_bytes()) for n in files}
    logs=[];linked={}
    for stem,base,end,size in [('status-core',code_bases[0],'SC_END',1024),('status-details',code_bases[1],'SD_END',1450)]:
        stage=out/stem;stage.mkdir()
        for n in files:
            body=interface if n=='status-interface.inc' else (ROOT/'monitors/status'/n).read_text(encoding='utf-8')
            body=re.sub(r'^\s*SAY (\w+)\s*$',lambda m:f'        LDX #<{m[1]}\n        LDY #>{m[1]}\n        JSR ST_PRINT',body,flags=re.M)
            if n.endswith(('.asm','-sram.inc')):body,_=conservative_branches(body,stem.replace('-','_')+'_'+n.replace('.','_').replace('-','_')+'_')
            (stage/n).write_text(body,encoding='utf-8',newline='\n')
        (stage/'status-bindings.inc').write_text(bindings,encoding='ascii')
        (stage/'status-text.inc').write_text(text_symbols,encoding='ascii')
        shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
        for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W',stem+'.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c'+f'{base:04X}','-hm19','-j','-o',stem+'.s19',stem+'.obj']):
            r=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));(out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
            if r.returncode:raise RuntimeError('WDC failed; inspect build-log.json')
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(stem+'.map')).read_text(),re.M)}
        memory=cells(stage/(stem+'.s19'));assert set(memory)==set(range(base,sy[end]))
        body=bytes(memory[a] for a in range(base,sy[end]));linked[stem]=dict(linked_bytes=len(body),capacity=size-2,free_bytes=size-2-len(body))
        # Retain the size result even when a real repair is necessary.
        (out/'linked-sizes.json').write_text(json.dumps(linked,indent=2)+'\n')
        image=seal(body,size);name=f'STATUS-{base:04X}.bin';(out/name).write_bytes(image)
        artifacts[name]=dict(address=f'{base:04X}',bytes=len(image),linked_bytes=len(body),free_bytes=size-2-len(body),sha256=sha(image))
    report=dict(component='Read-only shared startup STATUS',generation='00000001',status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',RAM_trial=ram_trial,source_sha256=sources,artifacts=artifacts,linked=linked,F_sha256=sha(f),F_rebuilt=False,CPU_simulations=0,hardware_access=False,build_passes=1,gate='7BE8-7BFB after frozen V2W_END',scratch='MON6A; fixed gate; boot frame6700; system ZP E0-FF',owner_RAM_writes=ram_trial,RTC_writes=False,flash_writes=False,SRAM_writes=False)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(linked,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--ram-trial',action='store_true');a=p.parse_args();build(a.out,a.ram_trial)
