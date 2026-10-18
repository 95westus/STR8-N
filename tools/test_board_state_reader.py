"""Execute every archive range and refusal with the bit-level I2C model."""
import hashlib,json
from build_board_state_reader import OUT
from test_v2_i2c import Devices
from test_v2_rtc import MPU

def main():
    meta=json.loads((OUT/'build.json').read_text());body=(OUT/'reader.bin').read_bytes();assert hashlib.sha256(body).hexdigest()==meta['sha256']
    checks=0
    for device,start,count in [(0xAE,0,128),(0xAE,0xF0,8),(0xAE,255,1),(0xDE,0,32),(0xDE,32,64),
                               (0xAE,0x78,9),(0xDE,0x5F,2),(0xAE,0xF0,9),(0xDE,0xFF,2),(0xC0,0,1),(0xDE,0,0),(0xDE,0,129)]:
        mem=Devices();rtc=bytearray((i*7+3)&255 for i in range(256));ee=bytearray((i*11+1)&255 for i in range(256))
        mem.devices[0x6F]=rtc;mem.devices[0x57]=ee
        mem.ram[0x2000:0x2000+len(body)]=body;mem.ram[0x2F00:0x2F03]=bytes([device,start,count])
        cpu=MPU(memory=mem,pc=0x2000)
        oldrtc=bytes(rtc);oldee=bytes(ee);ddr=mem.ram[0x7FC3]
        for _ in range(3000000):
            if cpu.pc==0x7E67:break
            cpu.step()
        else:raise AssertionError('Readout client timeout')
        allowed=(device,start,count) in [(0xAE,0,128),(0xAE,0xF0,8),(0xAE,255,1),(0xDE,0,32),(0xDE,32,64)]
        status=mem.ram[0x2F10]
        if allowed:
            assert status==0,(device,start,count,status)
            expected=(ee if device==0xAE else rtc)[start:start+count]
            assert mem.ram[0x3000:0x3000+count]==expected
            assert mem.ram[0x2F15]==count
        else:assert status==9 and not mem.accesses
        assert bytes(rtc)==oldrtc and bytes(ee)==oldee and not mem.writes
        assert mem.ram[0x7FC3]==ddr and mem.ram[0x2F11]==mem.ram[0x2F12]
        checks+=1
    (OUT/'test-results.json').write_text(json.dumps(dict(passed=True,tests=checks,sha256=meta['sha256'],device_data_writes=False),indent=2)+'\n')
    print('PASS',checks,'reader ranges/refusals; RTC/EEPROM unchanged and pin ownership restored')

if __name__=='__main__':main()
