"""Build the standalone boot/opaque tree with WDC tools; no parent-tree inputs."""
import argparse,binascii,hashlib,json,re,shutil,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()


def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')


def cells(path):
    result={}
    for line in path.read_text().splitlines():
        if not line:continue
        if not re.fullmatch(r'S[019][0-9a-fA-F]+',line):raise ValueError('Unsupported S-record')
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
        if line[1]=='1':
            for address,value in enumerate(raw[3:-1],int.from_bytes(raw[1:3],'big')):
                assert address not in result;result[address]=value
    return result


def db(path,data):path.write_text(''.join(' DB '+','.join(f'${b:02X}' for b in data[n:n+16])+'\n' for n in range(0,len(data),16)),encoding='ascii')


def s19(data,address,entry):
    def row(kind,where,body):
        raw=bytes([len(body)+3])+where.to_bytes(2,'big')+body
        return 'S'+kind+(raw+bytes([255-(sum(raw)&255)])).hex().upper()
    return ('\n'.join([row('0',0,b'STR8N-F component')]+[row('1',address+n,data[n:n+32]) for n in range(0,len(data),32)]+[row('9',entry,b'')])+'\n').encode()


def build(out,assembler=None,linker=None,candidate=False):
    if 'candidate' in json.loads((ROOT/'release.json').read_text()).get('status','') and not candidate:
        raise ValueError('This is the PR05 development tree; build with --candidate')
    out=Path(out).resolve();assert not out.exists(),'Use a fresh output directory'
    assembler=assembler or shutil.which('wdc02as');linker=linker or shutil.which('wdcln')
    if not assembler or not linker:raise RuntimeError('WDC wdc02as and wdcln must be installed/on PATH; see docs/BUILD.md')
    out.mkdir(parents=True);shutil.copytree(ROOT/'src',out/'s');(out/'payload').mkdir();core=out/'s/core';symbols={};compiled=[]
    def link(name,start,end,key):
        logs=[]
        for cmd in ([assembler,'-G','-L','-S','-W','-I',str(core),name+'.asm'],
                    [linker,'-g','-s','-t',f'-c{start:04X}','-hm19','-j','-o',name+'.s19',name+'.obj']):
            result=subprocess.run(cmd,cwd=core,capture_output=True,text=True)
            logs.append(dict(command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr));save(core/(name+'.log.json'),logs)
            if result.returncode:raise RuntimeError('WDC failed: '+name+'; inspect '+str(core/(name+'.log.json')))
        sy={name:int(value,16) for value,name in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',(core/(name+'.map')).read_text(),re.M)}
        memory=cells(core/(name+'.s19'));stop=sy[end];assert set(memory)==set(range(start,stop))
        body=bytes(memory[a] for a in range(start,stop));symbols[key]=sy;compiled.append(dict(module=key,start=start,end=stop,bytes=len(body),sha256=sha(body)))
        print(key,len(body),'bytes',flush=True);return body,sy
    worker,ws=link('str8n-v2-worker',0x7800,'V2W_END','worker');db(core/'worker-image.inc',worker)
    (core/'worker-public-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in ws.items() if n.startswith('V2W_')))
    vectors,vs=link('str8n-v2-vectors',0x7e20,'V2V_END','vectors');db(core/'vectors-image.inc',vectors)
    (core/'vectors-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in dict(ws,**vs).items() if n.startswith(('V2V_','V2W_')))+f'V2_VECTOR_SIZE EQU ${len(vectors):X}\n')
    body,bs=link('str8n-v2-boot',0xf000,'BOOT_END','boot');assert len(body)<=0xfe0
    (core/'boot-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in bs.items() if ((n.startswith('BOOT_') and v>=0xf000) or n in ('J_CRC_INIT','J_CRC_BYTE')) and n!='BOOT_API_ERASE'))
    image=bytearray(b'\xff'*4096);image[:len(body)]=body
    names={0xffe4:'V2V_NATIVE_COP',0xffe6:'V2V_NATIVE_BRK',0xffe8:'V2V_NATIVE_ABORT',0xffea:'V2V_NATIVE_NMI',0xffee:'V2V_NATIVE_IRQ',
           0xfff4:'V2V_COP',0xfff8:'V2V_ABORT',0xfffa:'V2V_NMI',0xfffe:'V2V_IRQ_BRK'}
    for address,label in names.items():image[address-0xf000:address-0xf000+2]=vs[label].to_bytes(2,'little')
    image[0xffc:0xffe]=(0xf004).to_bytes(2,'little')
    artifacts={'STR8N-F-BOOT-4096.bin':(bytes(image),0xf000,0xf004)}
    for name,start,end,key,filename in (('ram-config',0x200,'CONFIG_END','config','STR8N-F-CONFIG-RAM.bin'),
        ('ram-installer',0x200,'INSTALLER_END','opaque','STR8N-F-OPAQUE-RAM.bin'),('ram-demo',0x200,'DEMO_END','demo','STR8N-F-DEMO-RAM.bin')):
        data,sy=link(name,start,end,key);assert start+len(data)<=0x6500;artifacts[filename]=(data,start,start)
    baseline=json.loads((ROOT/'baseline.json').read_text());manifest={};changes=[]
    for name,(data,address,entry) in artifacts.items():
        expected=baseline['artifacts'][name]
        if len(data)!=expected['bytes'] or sha(data)!=expected['sha256']:
            assert candidate,'Baseline mismatch: '+name
            changes.append(name)
        (out/'payload'/name).write_bytes(data);(out/'payload'/name.replace('.bin','.s19')).write_bytes(s19(data,address,entry))
        manifest[name]=dict(bytes=len(data),sha256=sha(data),address=f'{address:04X}',entry=f'{entry:04X}')
    save(out/'symbols.json',symbols);save(out/'manifest.json',dict(passed=True,offline=True,hardware_access=False,identity='b15c1 / PR05 layout candidate' if candidate else baseline['identity'],candidate=candidate,baseline_changes=changes,execution_qualified=False if candidate else None,artifacts=manifest,compiled=compiled,
        source={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted((ROOT/'src').rglob('*')) if p.is_file()}))
    print('PASS core candidate build; no execution qualification' if candidate else 'PASS standalone direct-source build; all four BINs match qualified baselines',flush=True)
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=ROOT/'build/local')
    parser.add_argument('--assembler');parser.add_argument('--linker');parser.add_argument('--candidate',action='store_true');args=parser.parse_args();build(args.out,args.assembler,args.linker,args.candidate)
