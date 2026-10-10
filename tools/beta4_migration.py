#!/usr/bin/env python3
"""Portable beta4 migration planner and serial launcher; no vendor firmware."""
import argparse,binascii,hashlib,json,re,struct,sys,time
from datetime import datetime,timezone
from pathlib import Path

VERSION='2.0b4'
LEGACY_F={
    '43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a':('2.0a24',0x6ff0),
    '231fbec1b0e6a1e80f4a956009aa74f6259e4f0dfcf761f09f16755832aece36':('2.0a24c1 / beta1',0x7fd0),
    '6598e17948a964da78dfa25bf9fe7d1e920bb6d56ed024a3ecea2ecd92e0a6f4':('2.0b2',0x7fd0),
}
def sha(data):return hashlib.sha256(data).hexdigest()
def crc(data):return binascii.crc_hqx(data,0xffff)
def fnv(data):
    value=0x811c9dc5
    for byte in data:value=((value^byte)*0x1000193)&0xffffffff
    return value
def config_sum(config):
    a=b=0
    for v in config[:14]:a=(a+v)&255;b=(b+a)&255
    return bytes((a,b))
def default_config():
    data=bytearray([1,0,3,7,0xf0,10,0]+[0]*9);data[14:]=config_sum(data);return bytes(data)
def clean_config(data):
    if data in (bytes(16),b'\xff'*16):return default_config()
    if (len(data)!=16 or data[0]!=1 or data[1]>1 or data[2]>3 or data[5]<10
            or data[6]>1 or data[14:]!=config_sum(data)):
        raise ValueError('Invalid stored startup settings; resolve them before migration')
    address=int.from_bytes(data[3:5],'little')
    if data[6]==0 and not (address<0xe0 or 0x200<=address<=0x66ff or address>=0x8000):
        raise ValueError('Stored startup address conflicts with beta4 reserved RAM')
    # Retain startup fields and beta15's exact EDU-OFF tag. The obsolete slot
    # locator is rebuilt by the profile-specific planner, never copied blindly.
    new=bytearray(data[:7]+bytes(9));new[13]=0xA5 if data[13]==0xA5 else 0
    new[14:]=config_sum(new);return bytes(new)
def metadata(config,counts,sequence):
    if not 1<=sequence<=0xffffffff:raise ValueError('Journal sequence exhausted')
    r=bytearray(b'\xff'*128);r[:8]=b'WC\x01\0'+sequence.to_bytes(4,'little')
    r[8:24]=config;r[24:120]=b''.join(v.to_bytes(3,'little') for v in counts)
    r[120:122]=crc(r[:120]).to_bytes(2,'little');r[127]=0;return bytes(r)
def journal(source):
    records=[source[i:i+128] for i in range(0x4000,0x6000,128)]
    good=[r for r in records if r[:4]==b'WC\x01\0' and r[127]==0 and crc(r[:120])==int.from_bytes(r[120:122],'little')]
    return max(good,key=lambda r:int.from_bytes(r[4:8],'little')) if good else None
def slot_valid(data,page):
    return (len(data)==4096 and data[:4]==b'MI\x01'+bytes((page,)) and data[31]==0
        and crc(data[:18]+data[32:])==int.from_bytes(data[18:20],'little'))
def source_settings(source,kind):
    if len(source)!=32768:raise ValueError('Source must be one complete 32768-byte B3 readback')
    f=source[0x7000:]
    if kind=='wdc':
        if f[:4]==b'SN\x02\0':raise ValueError('STR8-N is installed; use the STR8-N upgrade launcher')
        return 'stock board monitor',default_config(),[0]*32,0
    if f[:4]!=b'SN\x02\0':raise ValueError('No supported STR8-N F signature')
    identity=sha(f)
    normalized=sha(f[:0xfd0]+b'\xff'*16+f[0xfe0:])
    profile=LEGACY_F.get(identity) or LEGACY_F.get(normalized)
    if profile:
        name,offset=profile;return name,clean_config(source[offset:offset+16]),[0]*32,0
    # Recovery format 1 carries a self-CRC32 compatibility ID in F and each slot.
    if b'WR\x01\x01' not in f[:256]:raise ValueError('Unrecognized STR8-N source firmware')
    slots=[source[i:i+4096] for i in (0x2000,0x3000)]
    slots=[s for s,p in zip(slots,(0xa0,0xb0)) if slot_valid(s,p)]
    if not slots:raise ValueError('No complete source monitor slot; use recovery before upgrading')
    compatible=False
    for slot in slots:
        token=slot[20:24];start=0
        while True:
            offset=f.find(token,start)
            if offset<0:break
            if binascii.crc32(f[:offset]+bytes(4)+f[offset+4:])&0xffffffff==int.from_bytes(token,'little'):
                compatible=True;break
            start=offset+1
    if not compatible:raise ValueError('Source recovery core integrity check failed')
    record=journal(source)
    if record is None:
        if source[0x4000:0x6000]!=b'\xff'*8192:raise ValueError('Source configuration journal has no valid snapshot')
        return 'recovery format 1',default_config(),[0]*32,0
    counts=[int.from_bytes(record[24+i*3:27+i*3],'little') for i in range(32)]
    return 'recovery format 1',clean_config(record[8:24]),counts,int.from_bytes(record[4:8],'little')
def read_s19(path,max_end=0x4000):
    cells={};entry=None
    for line in Path(path).read_text(encoding='ascii').splitlines():
        if not re.fullmatch(r'S[019][0-9A-Fa-f]+',line):raise ValueError('Unsupported S-record')
        raw=bytes.fromhex(line[2:]);address=int.from_bytes(raw[1:3],'big')
        if len(raw)!=raw[0]+1 or sum(raw)&255!=255:raise ValueError('S-record checksum/count mismatch')
        if line[1]=='1':
            for offset,value in enumerate(raw[3:-1],address):
                if offset in cells:raise ValueError('S-record overlap')
                cells[offset]=value
        elif line[1]=='9':
            if entry is not None or len(raw)!=4:raise ValueError('Invalid S9 entry')
            entry=address
    if not cells or entry is None or set(cells)!=set(range(min(cells),max(cells)+1)):raise ValueError('Incomplete/sparse RAM image')
    if not 0x2000<=min(cells)<=entry<=max(cells)<max_end:raise ValueError('RAM image outside approved range')
    return cells,entry
def s_record(kind,address,data=b''):
    raw=bytes((len(data)+3,))+address.to_bytes(2,'big')+data
    return 'S'+kind+(raw+bytes((255-(sum(raw)&255),))).hex().upper()
def s19(cells,entry):
    first,last=min(cells),max(cells)
    lines=[s_record('0',0,b'STR8-N 2.0b4 exact source migration')]
    lines += [s_record('1',a,bytes(cells[i] for i in range(a,min(a+32,last+1)))) for a in range(first,last+1,32)]
    return ('\n'.join(lines+[s_record('9',entry)])+'\n').encode('ascii')
def validate_kit(kit):
    manifest=json.loads((kit/'manifest.json').read_text())
    if manifest['version']!=VERSION:raise ValueError('Wrong release version')
    for name,digest in manifest['artifacts'].items():
        if Path(name).name!=name:raise ValueError('Unsafe package name')
        if sha((kit/name).read_bytes())!=digest:raise ValueError('Kit hash mismatch: '+name)
    template=json.loads((kit/'migrator.json').read_text())
    image=kit/'str8n-v2-b4-migrator-2000.s19'
    if sha(image.read_bytes())!=template['sha256']:raise ValueError('Migration template hash mismatch')
    cells,entry=read_s19(image)
    if entry!=0x2000 or min(cells)!=0x2000 or template['count'] not in cells:
        raise ValueError('Invalid migration template entry/count')
    if cells[template['count']]!=0 or any(a not in cells for a in range(template['table'],template['table']+template['table_bytes'])):
        raise ValueError('Invalid migration plan table')
    return manifest
def maintenance_storage(kit):
    storage=(kit/'str8n-v2-b4-maint-8000-9fff.bin').read_bytes()
    cells,entry=read_s19(kit/'str8n-bank-maint-1.5-2000.s19')
    code=bytes(cells[a] for a in range(min(cells),max(cells)+1))
    wanted=b'SR\x01\x3f'+entry.to_bytes(2,'little')+len(code).to_bytes(2,'little')+b'MAINT'.ljust(16,b'\0')+code
    if storage!=wanted+b'\xff'*(8192-len(wanted)):raise ValueError('Invalid release MAINT storage image')
    return storage
def plan(source,kit,kind):
    manifest=validate_kit(kit)
    name,config,counts,sequence=source_settings(source,kind)
    candidate={p:(kit/n).read_bytes() for p,n in (
        (0xa0,'str8n-v2-b4-slot-a.bin'),(0xb0,'str8n-v2-b4-slot-b.bin'),
        (0xe0,'str8n-v2-b4-e000-efff.bin'),(0xf0,'str8n-v2-b4-f000-ffff.bin'))}
    if any(len(data)!=4096 for data in candidate.values()):raise ValueError('Firmware sectors must be 4096 bytes')
    for page in (0xa0,0xb0):
        if not slot_valid(candidate[page],page):raise ValueError('Release slot integrity check failed')
    storage=maintenance_storage(kit)
    candidate[0x80]=storage[:4096];candidate[0x90]=storage[4096:]
    changed=[p for p,data in candidate.items() if source[(p<<8)-0x8000:(p<<8)-0x7000]!=data]
    if 0x90 in changed and 0x80 not in changed:changed.append(0x80)
    if not changed:return dict(no_change=True,source_firmware=name),{},source
    # Keep an accepted preference when the existing monitor slots need no change.
    if not any(p in changed for p in (0xa0,0xb0)) and (record:=journal(source)):
        config=record[8:24]
    # Migration provisions a fresh journal containing retained counters/settings.
    # Its recorded attempts cover each sector in the bounded migration plan.
    candidate[0xd0]=b'\xff'*4096
    changed += [0xc0]
    if source[0x5000:0x6000]!=candidate[0xd0]:changed += [0xd0]
    after=list(counts)
    for p in changed:
        index=24+(p>>4)-8
        if after[index]==0xffffff:raise ValueError('Erase-attempt counter exhausted')
        after[index]+=1
    candidate[0xc0]=metadata(config,after,sequence+1)+b'\xff'*(4096-128)
    order=[p for p in (0xd0,0xc0,0xa0,0xb0,0xe0,0x80,0x90,0xf0) if p in changed]
    commit_after=0
    if 0x80 in changed:
        pending=bytearray(candidate[0x80]);pending[3]=0xff;candidate[0x80]=bytes(pending)
        commit_after=order.index(0x90 if 0x90 in changed else 0x80)+1
    expected=bytearray(source);rows=[]
    for page in order:
        data=candidate[page];rows.append(bytes((page,))+fnv(expected).to_bytes(4,'little')+fnv(data).to_bytes(4,'little'))
        expected[(page<<8)-0x8000:(page<<8)-0x7000]=data
        if len(rows)==commit_after:expected[3]=0x3f
    cells,entry=read_s19(kit/'str8n-v2-b4-migrator-2000.s19')
    template=json.loads((kit/'migrator.json').read_text())
    if sha((kit/'str8n-v2-b4-migrator-2000.s19').read_bytes())!=template['sha256']:raise ValueError('Template hash mismatch')
    table=b''.join(rows)
    cells[template['count']]=len(order)
    cells[template['commit_after']]=commit_after
    for a,value in enumerate(table,template['table']):
        if a not in cells:raise ValueError('Plan table outside installer')
        cells[a]=value
    info=dict(no_change=False,version=VERSION,source_firmware=name,kind=kind,source_sha256=sha(source),
        expected_sha256=sha(expected),config=config.hex(),erase_counts_before=counts,erase_counts_after=after,
        sectors=[p>>4 for p in order],generation=manifest['generation'],entry=entry,
        preserved='B0-B2; B3:8/9 now contains the saved MAINT record',maintenance_installed=True,
        storage_commit_after=commit_after,initial_f_install_power_loss_safe=False)
    return info,dict(installer=s19(cells,entry),transfers=[candidate[p] for p in order]),bytes(expected)
def save_plan(source,kit,kind,out):
    out.mkdir(parents=True,exist_ok=False)
    (out/'.gitignore').write_text('*\n')
    (out/'prior-b3.bin').write_bytes(source)
    info,payload,expected=plan(source,kit,kind)
    (out/'expected-b3.bin').write_bytes(expected)
    (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n')
    if payload:
        (out/'installer.s19').write_bytes(payload['installer'])
        for page,data in zip(info['sectors'],payload['transfers']):(out/f'b3-{page:X}.bin').write_bytes(data)
    return info,payload,expected

class Link:
    def __init__(self,port,log,*,stock=False):
        import serial
        self.serial=serial.Serial(port=None,baudrate=115200,timeout=.05,write_timeout=5)
        self.serial.dtr=False;self.serial.rtscts=stock;self.serial.rts=stock
        self.serial.port=port;self.serial.open()
        self.log=log;self.pending=bytearray()
    def record(self,direction,data):
        self.log.write(json.dumps(dict(time=time.time(),direction=direction,hex=data.hex()))+'\n');self.log.flush()
    def send(self,data):
        self.record('TX',data)
        if self.serial.write(data)!=len(data):raise IOError('Short serial write')
        self.serial.flush()
    def read(self,count):
        data=self.serial.read(count)
        if data:self.record('RX',data)
        return data
    def exact(self,count):
        out=bytearray();deadline=time.monotonic()+20
        while len(out)<count:
            data=self.read(count-len(out));out.extend(data)
            if time.monotonic()>deadline:raise TimeoutError('Serial reply incomplete')
        return bytes(out)
    def until(self,token,seconds=45):
        deadline=time.monotonic()+seconds
        while True:
            end=self.pending.find(token)
            if end>=0:
                end+=len(token);result=bytes(self.pending[:end]);del self.pending[:end];return result
            if time.monotonic()>deadline:raise TimeoutError('Waiting for '+repr(token)+': '+repr(bytes(self.pending[-160:])))
            data=self.read(max(1,self.serial.in_waiting));self.pending.extend(data)
            if b'MIGRATION REFUSED/FAILED' in self.pending:raise IOError('RAM migrator refused/failed; keep power on and inspect the log')
    def command(self,text,prompt=b'\r\nB3> '):
        self.send(text.encode('ascii')+b'\r');return self.until(prompt)
    def write_ram(self,address,data,prompt=b'\r\nB3> '):
        """Stage RAM in short monitor commands; refuse errors and verify bytes."""
        data=bytes(data)
        if not 0<=address<0x8000 or address+len(data)>0x8000:
            raise ValueError('RAM staging must stay below 8000')
        for offset in range(0,len(data),8):
            line=f'M {address+offset:04X} '+' '.join(f'{v:02X}' for v in data[offset:offset+8])
            reply=self.command(line,prompt)
            if any(error in reply for error in (b'Long line',b'Bad',b'Protected',b'Wrap')):
                raise IOError('Monitor rejected RAM staging at '+f'{address+offset:04X}'+': '+repr(reply))
        if data and self.dump(address,address+len(data)-1,prompt)!=data:
            raise IOError('RAM staging readback mismatch at '+f'{address:04X}')
    def dump(self,first,last,prompt=b'\r\nB3> '):
        result=self.command(f'D {first:04X} {last:04X}',prompt);cells={}
        for line in result.decode('ascii').splitlines():
            m=re.fullmatch(r'([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
            if m:cells.update((int(m[1],16)+i,v) for i,v in enumerate(bytes.fromhex(m[2])))
        if set(cells)!=set(range(first,last+1)):raise IOError('Incomplete memory readback')
        return bytes(cells[a] for a in range(first,last+1))
    def protocol(self,command):
        self.send(b'\x55\xaa')
        if self.exact(1)!=b'\xcc':raise IOError('Stock monitor sync failed; press RESET and restart')
        self.send(bytes((command,)))
    def stock_info_after_reset(self,seconds=60):
        """Read-only startup probe while the operator presses RESET.

        Some retained board images start a program unless the debugger
        connects during startup. Repeated sync/identity probes issue no
        memory writes or execution commands.
        """
        deadline=time.monotonic()+seconds
        self.serial.reset_input_buffer();self.pending.clear()
        while time.monotonic()<deadline:
            self.send(b'\x55\xaa')
            received=self.read(max(1,self.serial.in_waiting))
            if b'\xcc' not in received:continue
            # Allow pending sync pairs/acknowledgements to drain before INFO.
            time.sleep(.1);self.serial.reset_input_buffer()
            self.send(b'\x0c');reply=bytearray();end=min(deadline,time.monotonic()+1)
            while len(reply)<12 and time.monotonic()<end:reply.extend(self.read(12-len(reply)))
            if len(reply)!=12:continue
            if reply[:3]!=b'SXB' or not 0x21<=reply[3]<=0x7e:
                raise ValueError('Unsupported stock board identity: '+bytes(reply).hex())
            return bytes(reply)
        raise TimeoutError('No stock debugger identity during RESET window; no RAM or flash writes were issued')
    def stock_read(self,address,count):
        self.protocol(3);self.send(address.to_bytes(3,'little')+count.to_bytes(3,'little'));return self.exact(count)
    def stock_load(self,cells,entry):
        first,last=min(cells),max(cells)
        for a in range(first,last+1,256):
            data=bytes(cells[i] for i in range(a,min(a+256,last+1)))
            self.protocol(2);self.send(a.to_bytes(3,'little')+len(data).to_bytes(3,'little')+data)
            if self.exact(1)!=b'\0' or self.stock_read(a,len(data))!=data:raise IOError('Installer RAM readback mismatch; execution refused')
        self.protocol(6);self.send(entry.to_bytes(3,'little'))
    def monitor_load(self,path):
        cells,entry=read_s19(path);self.command('L',b'S19')
        for line in Path(path).read_bytes().splitlines():self.send(line+b'\r\n');time.sleep(.04)
        self.until(b'\r\nB3> ')
        if self.dump(min(cells),max(cells))!=bytes(cells[a] for a in range(min(cells),max(cells)+1)):
            raise IOError('Installer RAM readback mismatch; execution refused')
        self.send(f'G {entry:04X}\r'.encode())

def kit_path():
    here=Path(__file__).resolve().parent
    for p in (here,here.parent/'BUILD/v2-beta4/kit'):
        if (p/'manifest.json').is_file():return p
    raise ValueError('Extract the full release ZIP, or build beta4 first')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=('wdc','str8n'),required=True)
    p.add_argument('--port');p.add_argument('--kit',type=Path);p.add_argument('--out',type=Path)
    p.add_argument('--source',type=Path,help='Prepare from an existing B3 backup; no serial access')
    p.add_argument('--validate-only',action='store_true');p.add_argument('--backup-only',action='store_true')
    args=p.parse_args();kit=(args.kit or kit_path()).resolve();validate_kit(kit)
    if args.validate_only:
        print('PASS beta4 kit hashes and migration template; no serial port opened');return
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out=(args.out or kit/'backups'/stamp).resolve()
    if args.source:
        info,_,_=save_plan(args.source.read_bytes(),kit,args.kind,out);print(json.dumps(info,indent=2));return
    import serial.tools.list_ports
    ports=[x.device for x in serial.tools.list_ports.comports()]
    print('Detected ports: '+', '.join(ports))
    port=args.port or input('Serial port: ').strip()
    if not port:raise ValueError('A serial port is required')
    if args.kind=='wdc':
        board=input('Physical board type (W65C02SXB or W65C816SXB): ').strip()
        if board not in ('W65C02SXB','W65C816SXB'):raise ValueError('Board type not confirmed')
    out.mkdir(parents=True,exist_ok=False);(out/'.gitignore').write_text('*\n')
    with (out/'serial.jsonl').open('x') as log:
        link=Link(port,log,stock=args.kind=='wdc')
        try:
            if args.kind=='wdc':
                print('Port is open; debugger probe armed for 60 seconds. Press and release physical RESET now.',flush=True)
                identity=link.stock_info_after_reset()
                print('Stock monitor connected; RESET window is closed. Follow the installation prompts; reset again only when asked.',flush=True)
                if identity[:3]!=b'SXB':raise ValueError('Unsupported stock board identity')
                source=link.stock_read(0x8000,32768)
                repeat=link.stock_read(0x8000,32768)
            else:
                # Require an idle STR8-N monitor, rather than dispatching arbitrary RAM input.
                link.command('',b'> ');link.command('B3')
                source=link.dump(0x8000,0xffff);repeat=link.dump(0x8000,0xffff)
            if source!=repeat:raise IOError('Independent backup reads differ; installation refused')
            (out/'prior-b3.bin').write_bytes(source)
            (out/'backup.json').write_text(json.dumps(dict(sha256=sha(source),bytes=32768,repeat_verified=True),indent=2)+'\n')
            print('B3 host backup independently verified: '+str(out/'prior-b3.bin'))
            if args.backup_only:return
            info,payload,expected=plan(source,kit,args.kind)
            (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n')
            if info['no_change']:print('Board already matches this beta4 firmware; no writes');return
            (out/'expected-b3.bin').write_bytes(expected)
            (out/'installer.s19').write_bytes(payload['installer'])
            print('Source: '+info['source_firmware']+'; target: STR8-N '+VERSION)
            print('Replace B3 sectors: '+', '.join(f'{s:X}' for s in info['sectors']))
            print('B0-B2 are preserved. B3:8/9 installs MAINT. Keep power stable until verified.')
            if input('Type INSTALL STR8-N 2.0b4 to proceed: ').strip()!='INSTALL STR8-N 2.0b4':
                print('Canceled; backup retained; no flash writes');return
            if args.kind=='wdc':
                cells,entry=read_s19(out/'installer.s19');link.stock_load(cells,entry)
            else:link.monitor_load(out/'installer.s19')
            link.until(b'Y then Enter> ');link.send(b'Y\r')
            for sector,data in zip(info['sectors'],payload['transfers']):
                link.until(f'SEND 4096 BYTES FOR B3:{sector:X}\r\n'.encode(),90)
                for offset in range(0,4096,64):link.send(data[offset:offset+64]);time.sleep(.01)
                print(f'Sent B3:{sector:X}',flush=True)
            result=link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90)
            print(result.decode('ascii','replace'))
            input('Press physical RESET, wait for the monitor selection, then press Enter: ')
            # Drain completed startup output, including its bounded selection window.
            time.sleep(4);link.pending.clear();link.serial.reset_input_buffer()
            link.command('');link.command('B3')
            actual=link.dump(0x8000,0xffff)
            (out/'final-b3.bin').write_bytes(actual)
            if actual!=expected:raise IOError('Post-reset B3 differs from the expected image')
            (out/'verification.json').write_text(json.dumps(dict(version=VERSION,
                expected_sha256=sha(expected),actual_sha256=sha(actual),exact_readback=True),indent=2)+'\n')
            print('PASS STR8-N 2.0b4 complete post-reset B3 readback; backup retained')
        finally:link.serial.close()

if __name__=='__main__':
    try:main()
    except (ValueError,IOError,TimeoutError) as error:print('ERROR: '+str(error),file=sys.stderr);sys.exit(1)
