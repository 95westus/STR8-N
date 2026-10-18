"""Test actual legacy installer RAM transports with simulated endpoints only."""
import argparse,json
from pathlib import Path
import beta4_migration as m
from plan_bf1_2512_legacy import sha

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plans',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();checks=[];inputs={}
    for kind in ('wdcmonv2','v2-0b4'):
        folder=a.plans/(kind+'-convert');path=folder/'installer-model-only.s19';plan=json.loads((folder/'plan.json').read_text());assert sha(path.read_bytes())==plan['installer_sha256']
        cells,entry=m.read_s19(path);assert min(cells)==entry==0x2000 and max(cells)==0x36ff
        inputs[kind]=dict(plan_sha256=sha((folder/'plan.json').read_bytes()),installer_sha256=sha(path.read_bytes()))
        expected=bytes(cells[i] for i in range(0x2000,0x3700))
        class Stock:
            stock_load=m.Link.stock_load
            stock_read=m.Link.stock_read
            def __init__(self,bad=None):self.ram=bytearray(32768);self.commands=[];self.command=None;self.readback=None;self.bad=bad;self.executed=None
            def protocol(self,command):self.commands.append(command);self.command=command
            def send(self,data):
                if self.command in (2,3):
                    address=int.from_bytes(data[:3],'little');n=int.from_bytes(data[3:6],'little');assert 0x2000<=address<0x3700 and 1<=n<=256
                    if self.command==2:assert len(data)==6+n;self.ram[address:address+n]=data[6:]
                    else:
                        assert len(data)==6;self.readback=bytearray(self.ram[address:address+n])
                        if self.bad is not None and address<=self.bad<address+n:self.readback[self.bad-address]^=1
                elif self.command==6:self.executed=int.from_bytes(data,'little')
                else:raise AssertionError('Unexpected stock protocol command')
            def exact(self,count):
                if self.command==2:assert count==1;return b'\0'
                assert self.command==3 and len(self.readback)==count;return bytes(self.readback)
        for bad in (None,0x2000,0x2c80,0x36ff):
            endpoint=Stock(bad)
            if bad is None:
                endpoint.stock_load(cells,entry);assert endpoint.executed==entry and endpoint.ram[0x2000:0x3700]==expected
                checks.append(dict(name=kind+' actual stock_load, full RAM readback before execution',passed=True,bytes=len(expected),protocol_commands=endpoint.commands))
            else:
                try:endpoint.stock_load(cells,entry)
                except IOError:assert endpoint.executed is None and 6 not in endpoint.commands
                else:raise AssertionError('Corrupt stock RAM readback executed')
                checks.append(dict(name=kind+' stock readback refusal '+hex(bad),passed=True,execution_refused=True))
        class Monitor:
            monitor_load=m.Link.monitor_load
            def __init__(self,bad=False):self.sent=[];self.bad=bad
            def command(self,command,prompt):assert command=='L' and prompt==b'S19'
            def send(self,data):self.sent.append(data)
            def until(self,prompt):assert prompt==b'\r\nB3> ';return prompt
            def dump(self,first,last):
                assert (first,last)==(0x2000,0x36ff);data=bytearray(expected)
                if self.bad:data[len(data)//2]^=1
                return bytes(data)
        # Eliminate transport pacing only; execute the unchanged loader method.
        from unittest.mock import patch
        for bad in (False,True):
            endpoint=Monitor(bad)
            with patch.object(m.time,'sleep',return_value=None):
                if bad:
                    try:endpoint.monitor_load(path)
                    except IOError:assert not any(row.startswith(b'G ') for row in endpoint.sent)
                    else:raise AssertionError('Corrupt monitor RAM readback executed')
                else:
                    endpoint.monitor_load(path);assert endpoint.sent[-1]==b'G 2000\r'
                    assert endpoint.sent[:-1]==[row+b'\r\n' for row in path.read_bytes().splitlines()]
            checks.append(dict(name=kind+' monitor S19 '+('readback refusal' if bad else 'readback-before-G'),passed=True))
    report=dict(passed=True,cases=len(checks),checks=checks,inputs=inputs,scope='Host transfer/readback logic against simulated endpoints; no claim of physical WDC handshake acceptance',transport_source_sha256=sha(Path(m.__file__).read_bytes()),test_source_sha256=sha(Path(__file__).read_bytes()),board_access=False,hardware_qualified=False,publication_permitted=False)
    a.out.write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),'actual-installer transport checks')
if __name__=='__main__':main()
