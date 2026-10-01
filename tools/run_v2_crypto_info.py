"""Load verified RAM-only informational probe on board 2205 and record replies."""
import hashlib,json,re,time
from pathlib import Path
import serial
from serial.tools import list_ports
from build_v2_crypto_info import OUT,NAME,crc

def main():
    r=json.loads((OUT/'build.json').read_text()); tests=json.loads((OUT/'test-results.json').read_text())
    image=(OUT/(NAME+'.bin')).read_bytes()
    assert hashlib.sha256(image).hexdigest()==r['sha256']==tests['sha256'] and tests['passed']
    from build_v2_a24 import read_s19
    memory,entry=read_s19(OUT/(NAME+'.s19'))
    assert entry==0x2000 and sorted(memory)==list(range(0x2000,0x2000+len(image)))
    assert bytes(memory[a] for a in sorted(memory))==image
    assert any(p.device=='COM3' and p.serial_number=='A10MPUPNA' for p in list_ports.comports())
    folder=OUT/time.strftime('board-2205-%Y%m%d-%H%M%S'); folder.mkdir()
    with (folder/'serial.jsonl').open('w') as log, serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=5) as link:
        link.dtr=False; link.rts=False; link.port='COM3'; link.open()
        pending=bytearray()
        def record(direction,data):
            log.write(json.dumps({'time':time.time(),'direction':direction,'hex':data.hex(),'text':data.decode('latin1')})+'\n'); log.flush()
        def send(data): link.write(data); link.flush(); record('TX',data)
        def until(token,seconds=10):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                found=pending.find(token)
                if found>=0:
                    end=found+len(token); data=bytes(pending[:end]); del pending[:end]; return data
                data=link.read(256)
                if data: pending.extend(data); record('RX',data)
            raise RuntimeError(f'Timeout: {bytes(pending)[-300:]!r}')
        send(b'\r'); until(b'B3> ')
        send(b'G F007\r'); baseline=until(b'B3> ')
        assert b'STR8-N 2.0a31 B3 65C02' in baseline and b'EDU KIT       DETECTED' in baseline
        send(b'L\r'); until(b'S19')
        for line in (OUT/(NAME+'.s19')).read_bytes().splitlines(keepends=True):
            send(line); time.sleep(.055)
        loaded=until(b'B3> ')
        assert b'entry 2000' in loaded.lower()
        send(f'D 2000 {0x2000+len(image)-1:04X}\r'.encode()); dumped=until(b'B3> ',20)
        actual={}
        for match in re.finditer(rb'(?m)^([0-9A-Fa-f]{4}):((?: [0-9A-Fa-f]{2}){1,16})',dumped):
            addr=int(match[1],16)
            for n,v in enumerate(bytes.fromhex(match[2].decode())): actual[addr+n]=v
        assert all(actual.get(0x2000+i)==b for i,b in enumerate(image)), 'RAM readback mismatch; not executing'
        send(b'G 2000\r'); result=until(b'B3> ',30)
        (folder/'output.txt').write_bytes(result)
        print(result.decode('ascii',errors='replace'))
        decoded=[]
        for match in re.finditer(rb'(?m)^([0-9A-F]{2}):((?: [0-9A-F]{2})+)',result):
            i=int(match[1],16); packet=bytes.fromhex(match[2].decode())
            valid=len(packet)==packet[0] and crc(packet[:-2])==packet[-2:]
            decoded.append({'index':i,'name':r['commands'][i]['name'],'response':packet.hex(),'crc_valid':valid,'data':packet[1:-2].hex()})
        (folder/'responses.json').write_text(json.dumps(decoded,indent=2)+'\n')
        print('Evidence:',folder)
        assert b'CRYPTO INFO DONE' in result, 'Probe could not complete; see transport evidence'
        assert len(decoded)==69 and all(d['crc_valid'] for d in decoded), 'Incomplete or invalid CRC response'
        cfg=b''.join(bytes.fromhex(d['data']) for d in decoded if d['name'].startswith('config_'))
        if len(cfg)==128: (folder/'config.bin').write_bytes(cfg)
        from decode_v2_crypto_info import summarize
        summary=summarize(decoded)
        (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
