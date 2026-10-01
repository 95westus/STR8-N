"""Execute alpha36 startup extension with RTC, EEPROM and crypto boundary models."""
import json,sys
from pathlib import Path
for directory in sorted(Path('BUILD').glob('v*/local/test-deps'),reverse=True):
    if (directory/'py65').is_dir(): sys.path.insert(0,str(directory))
from py65.devices.mpu65c02 import MPU
from build_v2_crypto_info import crc
import build_v2_a36 as build
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
def run(crypto='valid',rtc=True,pins=0x81,serial=bytes.fromhex('01231454D6545F9FEE'),
        counters=(0,0), locks=(0x55,0x55), hour=0x17):
    m=Memory(pins); cpu=MPU(memory=m,pc=S['RTC_ENTRY']);cpu.stPushWord(0x3fff)
    out=bytearray();tx=[];reads=0;bytebuf=[];rtreads=0
    sample=[0x89,0x54,hour,0x34,0x30,0x09,0x26]
    response_data=[bytes.fromhex('00006003'),bytes([0,0,*locks]),
                   counters[0].to_bytes(4,'little'),counters[1].to_bytes(4,'little'),
                   serial[:4],serial[4:8],serial[8:]+bytes.fromhex('AABBCC')]
    packets=[bytes.fromhex('04113343')]+[bytes([7])+v+crc(bytes([7])+v) for v in response_data]
    if crypto in ('badcrc','badserial'):
        i=2 if crypto=='badcrc' else 7
        packets[i]=packets[i][:-1]+bytes([packets[i][-1]^1])
    if crypto=='badcount': packets[5]=bytes([255])
    if crypto=='statuserror': packets[6]=bytes.fromhex('040F2342')
    m[0xEC:0xEE]=bytes.fromhex('AABB')
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
    assert m[0xEC:0xEE]==[0xAA,0xBB]
    assert m[S['EE_CFG']+2]==3 and m[S['EE_CFG']+5]==64
    return out.decode(),tx,reads
valid,tx,reads=run()
(build.OUT/'startup-preview.txt').write_bytes(valid.encode('ascii'))
assert all('['+h+']' in valid for h in ('SYSTEM CONFIGURATION','CRYPTO STATUS','BOOT SETTINGS'))
assert '  VIA1 $7FC0  A:I2C  B:SPI\r\n\r\nDEVICE' in valid
assert reads==8 and 'ATECC608        I2C   $60  RESPONDING' in valid
assert 'REVISION       00006003' in valid and 'CONFIG LOCK    UNLOCKED' in valid
assert 'DATA/OTP LOCK  UNLOCKED' in valid and 'COUNTERS       00000000 / 00000000' in valid
assert 'RTC' in valid and '26-09-30 17:54:10' in valid and 'AUTOSTART' in valid
expected=[0xc1]
for packet in ('0730000000035d', '0702001500175d', '07240000000cfd', '0724000100057d', '07020000001e2d', '070200020018ad', '0702000300112d'):
    expected += [0xc0,3,*bytes.fromhex(packet),0xc1]
expected += [0xc0,1]
assert tx==expected, (tx,expected)
serial_line='  SERIAL                  01231454D6545F9FEE'
assert 'RESPONDING\r\n'+serial_line+'\r\n23LCV1024' in valid
for mode in ('badcrc','badserial','badcount','statuserror','absent'):
    bad,_,_=run(mode)
    assert 'ATECC608        I2C   $60  UNAVAILABLE' in bad
    assert '[CRYPTO STATUS]\r\nUNAVAILABLE' in bad and 'BOOT SETTINGS' in bad
    assert 'SERIAL' not in bad
for serial in (bytes(9),bytes.fromhex('123456789ABCDEF012'),bytes([255])*9):
    output,_,_=run(serial=serial,counters=(0x123456,0x1FFFFF),locks=(0,0))
    assert '  SERIAL                  '+serial.hex().upper() in output
    assert 'COUNTERS       00123456 / 001FFFFF' in output
    assert 'CONFIG LOCK    LOCKED' in output and 'DATA/OTP LOCK  LOCKED' in output
for hour,expected_hour in ((0x41,'01'),(0x52,'00'),(0x61,'13'),(0x72,'12')):
    output,_,_=run(hour=hour)
    assert f'26-09-30 {expected_hour}:54:10' in output
no_rtc,_,_=run(rtc=False);assert 'EDU KIT' in no_rtc and 'UNKNOWN' in no_rtc
for pins in (0,1,0x80):
    output,_,_=run(pins=pins)
    assert 'SERIAL' not in output and 'BOOT SETTINGS' in output
(build.OUT/'a36-display-results.json').write_text(json.dumps({'image_sha256':__import__('hashlib').sha256(IMAGE).hexdigest(),'positive_crypto':True,'crc_rejection':True,'absent_crypto':True,'absent_rtc':True,'serial_order_and_live_values':True,'bad_serial_crc':True,'malformed_count':True,'status_error':True,'locked_and_nonzero_counters':True,'12_hour_rtc':True},indent=2)+'\n')
print('PASS: serial order/live values, bad CRC/count/status, absent/stuck bus, locks/counters, RTC 12-hour conversion, return and VIA restore')
