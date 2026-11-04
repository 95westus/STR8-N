"""Build only CLOCK's private CPU-RAM device boundary, never production F."""
import json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_native_apps import normalized,conservative_branches,cells,sha
from time_prep_ram_packets import Code,symbols
OUT=ROOT/'BUILD/clock-fault-RAM-r3'
REUSE=ROOT/'BUILD/clock-fault-RAM-r2'

def build():
    assert not OUT.exists(),'Fresh build folder required'
    frozen=json.loads((REPO/'F_FREEZE.json').read_text())
    assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==frozen['sha256']
    assert all(sha((REPO/n).read_bytes())==h for n,h in frozen['sources'].items())
    OUT.mkdir();sources={}
    for folder in ('monitors/native','monitors/qualification'):
      for p in (REPO/folder).iterdir():
        if p.suffix in ('.asm','.inc'):
          (OUT/p.name).write_text(p.read_text(encoding='utf-8-sig'));sources[str(p.relative_to(REPO))]=sha(p.read_bytes())
    provider=(OUT/'rtc-provider.asm').read_text()
    prefix=provider[:provider.index('; VIA no-handshake')]
    equ=provider[provider.index('BUSY EQU'):provider.rindex('SERVICE_END\n')]
    body=prefix+equ+'\n        INCLUDE "clock-fault-constants.inc"\n        INCLUDE "clock-fault-transport.inc"\nSERVICE_END\n        ENDMOD\n        END\n'
    (OUT/'rtc-provider.asm').write_text(body)
    def link(name,origin,end,limit):
      for p in OUT.glob('*.inc'):
        text,_=conservative_branches(normalized(p.read_text()),'Q_'+re.sub(r'\W','_',p.name)+'_')
        p.write_text(text)
      p=OUT/(name+'.asm');text=re.sub(r'^\s*XDEF.*$','',p.read_text(),flags=re.M)
      text,_=conservative_branches(normalized(text),name.replace('-','_')+'_Q_');p.write_text(text)
      if REUSE.exists():
        def same_tree(filename,seen=None):
          seen=set() if seen is None else seen
          if filename in seen:return True
          seen.add(filename);new=(OUT/filename).read_text();old=(REUSE/filename).read_text()
          assert new==old,filename
          for inc in re.findall(r'INCLUDE\s+"([^"]+)"',new,re.I):same_tree(inc,seen)
          return True
        assert same_tree(name+'.asm')
        for suffix in ('.map','.s19','.bin'):shutil.copyfile(REUSE/(name+suffix),OUT/(name+suffix))
        sy=symbols(OUT/(name+'.map'));b=(OUT/(name+'.bin')).read_bytes()
        data=cells(OUT/(name+'.s19'));assert b==bytes(data.get(a,255) for a in range(origin,sy[end]))
        return b,sy
      log=[]
      for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W',name+'.asm'],
                  [shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',name+'.s19',name+'.obj']):
        result=subprocess.run(cmd,cwd=OUT,capture_output=True,text=True);log.append(result.stdout+result.stderr)
        (OUT/(name+'-build.txt')).write_text('\n'.join(log));assert result.returncode==0,log[-1]
      sy=symbols(OUT/(name+'.map'));data=cells(OUT/(name+'.s19'))
      assert sy['START']==origin and sy[end]<=limit,(name,sy[end],limit)
      result=bytes(data.get(a,255) for a in range(origin,sy[end]));(OUT/(name+'.bin')).write_bytes(result)
      return result,sy
    provider,ps=link('rtc-provider',0x400,'SERVICE_END',0x1000)
    assert not any(bytes((op,a&255,a>>8)) in provider for a in (0x7FC3,0x7FCF) for op in (0x8D,0xAD))
    (OUT/'journal-transport.inc').write_text(f'EE_TRANSFER EQU ${ps["EE_TRANSFER"]:04X}\nTRIM_CONTROL EQU ${ps["TRIM_CONTROL"]:04X}\nBIND_FLASH_BYTE EQU $5DF0\n')
    journal,js=link('journal',0x1000,'JOURNAL_END',0x1A00)
    cs=symbols(ROOT/'BUILD/native-apps-g1-r15/clock.map')
    raw=(REPO/'monitors/candidates/native-g00000001-r16/CLOCK-g00000001-RAM.bin').read_bytes()
    assert raw==(ROOT/'BUILD/native-apps-g1-r15/CLOCK-g00000001-RAM.bin').read_bytes()
    install=(ROOT/'output/qualification/2512-startup-traditional-scope-20261101-r1/B2-target.bin').read_bytes()
    flash=(REPO/'monitors/candidates/native-g00000001-r16/CLOCK-g00000001-flash.bin').read_bytes()
    assert install[0x3000:0x6000]==flash
    clock=bytearray(raw);i=cs['H_SIGNATURE']-0x2000
    assert clock[i:i+8]==bytes.fromhex('50 4A 01 01 04 90 00 6B');clock[i+5]=0x10
    assert clock.count(bytes.fromhex('20 64 7B'))==4
    clock=clock.replace(bytes.fromhex('20 64 7B'),bytes.fromhex('20 F0 5D'))
    assert bytes.fromhex('20 64 7B') not in clock
    (OUT/'clock-private.bin').write_bytes(clock)
    # Bootstrap/exit preserve every discovery byte used by the temporary API.
    c=Code(0x200);c.emit(0x78,0xD8,0xA2,0xFF,0x9A)
    c.imm(0xA2,34);c.label('save');c.absolute(0xBD,0x7D04);c.absolute(0x9D,0x1C80);c.emit(0xCA);c.branch(0x10,'save')
    c.absolute(0xAD,0x7DF9);c.absolute(0x8D,0x1CA3);c.absolute(0x9C,0x7DF9);c.absolute(0x9C,0x6AF5)
    c.imm(0xA2,0x60);c.imm(0xA9,0);c.label('private');c.absolute(0x9D,0x6600);c.emit(0xE8);c.branch(0xD0,'private')
    c.imm(0xA2,0);c.label('scratch');c.absolute(0x9D,0x6B00);c.emit(0xE8);c.branch(0xD0,'scratch')
    c.imm(0xA2,22);c.label('gateway');c.absolute(0xBD,0x1CC0);c.absolute(0x9D,0x6500);c.emit(0xCA);c.branch(0x10,'gateway')
    for address,data in ((0x7D04,bytes.fromhex('53 56 01 01 00 65 FF 64')),(0x7D19,clock[i:i+8]),(0x7D22,b'\0')):
      for n,v in enumerate(data):c.imm(0xA9,v);c.absolute(0x8D,address+n)
    c.absolute(0x4C,cs['MENU']);start=c.done();assert len(start)<256
    c=Code(0x300);c.emit(0x78,0xD8,0xA2,0xFF,0x9A);c.absolute(0xAD,0x6AF5);c.absolute(0x8D,0x1ACA)
    c.imm(0xA2,34);c.label('restore');c.absolute(0xBD,0x1C80);c.absolute(0x9D,0x7D04);c.emit(0xCA);c.branch(0x10,'restore')
    c.absolute(0xAD,0x1CA3);c.absolute(0x8D,0x7DF9);c.imm(0xA9,3);c.absolute(0x8D,0x7D00);c.absolute(0x20,0x7848);c.absolute(0x4C,0xF2AF)
    exit=c.done();assert len(exit)<256
    image=bytearray(b'\xff'*0x6300)
    def put(a,b):image[a-0x200:a-0x200+len(b)]=b
    put(0x200,start);put(0x300,exit);put(0x400,provider);put(0x1000,journal);put(0x2000,clock)
    put(0x5DF0,bytes.fromhex('EE C9 1A A9 06 18 60'));put(0x5E00,bytes.fromhex('4C 00 03'));put(0x5E4E,b'\x60')
    facade=bytearray(b'RG\x01\x04')
    for addr in (0x404,0x407,0x40A,0x40D):facade+=bytes((0x4C,addr&255,addr>>8))
    facade+=b'I2\x01\x01'+bytes((0x4C,ps['PUBLIC_I2C']&255,ps['PUBLIC_I2C']>>8))
    assert len(facade)==23;put(0x1CC0,facade)
    (OUT/'CLOCK-FAULT-RAM.bin').write_bytes(image)
    (OUT/'manifest.json').write_text(json.dumps(dict(packet_sha256=sha(image),bytes=len(image),F_sha256=frozen['sha256'],
      builds=[],reused_logic_from=str(REUSE),CLOCK_reused_sha256=sha(raw),CLOCK_private_sha256=sha(clock),
      provider_end=f'{ps["SERVICE_END"]:04X}',journal_end=f'{js["JOURNAL_END"]:04X}',sources=sources,
      boundary='No physical GPIO/I2C transport linked; all RTC/EEPROM data is CPU RAM; all flash writers denied',
      patches=['H_SIGNATURE journal pointer 9004->1004','four CLOCK flash-call sites ->5DF0 denied'],
      limitations=['Physical RTC bus/write behaviour is not qualified by injected responses']),indent=2)+'\n')
    print((OUT/'manifest.json').read_text())

if __name__=='__main__':build()
