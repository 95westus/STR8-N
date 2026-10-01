"""Execute alpha32 startup extension with RTC, EEPROM and crypto boundary models."""
import json,sys
from pathlib import Path
for directory in sorted(Path('BUILD').glob('v*/local/test-deps'),reverse=True):
    if (directory/'py65').is_dir(): sys.path.insert(0,str(directory))
from py65.devices.mpu65c02 import MPU
from build_v2_crypto_info import crc
import build_v2_a32 as build
R=json.loads((build.OUT/'build.json').read_text())
S={**R['rtc_symbols'],**R['display_symbols']}
IMAGE=(build.OUT/f'{build.STEM}-e000-ffff.bin').read_bytes()
class Memory(list):
    def __init__(self,pins=0x81):
        super().__init__([0]*65536)
        super().__setitem__(slice(0xe000,0x10000),IMAGE)
        super().__setitem__(slice(0x7e60,0x7e64),b'RA\x01\x0d')
        super().__setitem__(0x7fc3,0x36);super().__setitem__(0x7fcf,0x24)
        self.pins=pins;self.writes=[]
    def __getitem__(self,key):
        if key==0x7fcf:
            ddr=super().__getitem__(0x7fc3)
            return (super().__getitem__(key)&ddr)|(self.pins&~ddr)
        return super().__getitem__(key)
    def __setitem__(self,key,value):
        if isinstance(key,int):
            self.writes.append((key,value))
            assert key<0xe000,hex(key)
        super().__setitem__(key,value)
def ret(cpu): cpu.pc=(cpu.stPopWord()+1)&65535
def run(crypto='valid',rtc=True,pins=0x81):
    m=Memory(pins); cpu=MPU(memory=m,pc=S['RTC_ENTRY']);cpu.stPushWord(0x3fff)
    out=bytearray();tx=[];reads=0;bytebuf=[];rtreads=0
    sample=[0x89,0x54,0x17,0x34,0x30,0x09,0x26]
    response_data=[bytes.fromhex('00006003'),bytes.fromhex('00005555'),bytes(4),bytes(4)]
    packets=[bytes.fromhex('04113343')]+[bytes([7])+v+crc(bytes([7])+v) for v in response_data]
    if crypto=='badcrc': packets[2]=packets[2][:-1]+bytes([packets[2][-1]^1])
    for step in range(300000):
        pc=cpu.pc
        if pc==0x4000:break
        if pc==0x7e6d: out.append(cpu.a);ret(cpu)
        elif pc==0x7e7c:out.extend(f'{cpu.a:02X}'.encode());ret(cpu)
        elif pc==0x7e7f:out.extend(b'\r\n');ret(cpu)
        elif pc==S['RTREAD']:
            if rtc:
                values=sample.copy();values[0]=0x90 if rtreads else 0x89
                m[S['RTCBUF']:S['RTCBUF']+7]=values
                cpu.p|=1
            else:cpu.p&=~1
            rtreads+=1;ret(cpu)
        elif pc==S['RTC_WAIT1']:cpu.pc=S['RTC_WAIT2']+6
        elif pc==S['EE_READ']:
            m[S['EE_STATE']]=3
            m[S['EE_CFG']+1]=0;m[S['EE_CFG']+2]=3;m[S['EE_CFG']+5]=64;m[S['EE_CFG']+6]=1
            cpu.p|=1;ret(cpu)
        elif pc==S['CR_DELAY']:ret(cpu)
        elif pc==S['I2WRITE'] and crypto!='absent':tx.append(cpu.a);cpu.p|=1;ret(cpu)
        elif pc==S['I2READ'] and crypto!='absent':
            if not bytebuf:
                bytebuf=list(packets[min(reads,len(packets)-1)]);reads+=1
            cpu.a=bytebuf.pop(0);ret(cpu)
        else:cpu.step()
    else:raise AssertionError('startup extension did not return')
    assert m[0x7fc3]==0x36 and m[0x7fcf]&0x36==0x24
    return out.decode(),tx,reads
valid,tx,reads=run()
assert reads==5 and 'ATECC608        I2C   $60  RESPONDING' in valid
assert 'REVISION       00006003' in valid and 'CONFIG LOCK    UNLOCKED' in valid
assert 'DATA/OTP LOCK  UNLOCKED' in valid and 'COUNTERS       00000000 / 00000000' in valid
assert 'RTC' in valid and '26-09-30 17:54:10' in valid and 'AUTOSTART' in valid
expected=[0xc1]
for packet in ('0730000000035d','0702001500175d','07240000000cfd','0724000100057d'):
    expected += [0xc0,3,*bytes.fromhex(packet),0xc1]
expected += [0xc0,1]
assert tx==expected, (tx,expected)
bad,_,_=run('badcrc');assert 'ATECC608        I2C   $60  UNAVAILABLE' in bad and 'CRYPTO STATUS\r\nUNAVAILABLE' in bad
absent,_,_=run('absent');assert 'ATECC608        I2C   $60  UNAVAILABLE' in absent and 'BOOT SETTINGS' in absent
no_rtc,_,_=run(rtc=False);assert 'EDU KIT' in no_rtc and 'UNKNOWN' in no_rtc
(build.OUT/'a32-display-results.json').write_text(json.dumps({'image_sha256':__import__('hashlib').sha256(IMAGE).hexdigest(),'positive_crypto':True,'crc_rejection':True,'absent_crypto':True,'absent_rtc':True},indent=2)+'\n')
print('PASS: live values, CRC rejection, absent crypto, absent RTC, bounded return and VIA restoration')
