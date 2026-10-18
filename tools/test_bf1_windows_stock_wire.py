"""Exercise actual packaged RAM loaders with simulated 2609 endpoints only."""
import argparse
import hashlib
import importlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kit',type=Path,required=True);p.add_argument('--plans',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists()
    sys.path.insert(0,str(a.kit.resolve()));m=importlib.import_module('legacy_transport');checks=[]
    class Serial:
        def __init__(self,**kw):self.settings=kw;self.opened=False
        def open(self):self.opened=True
    for stock in (False,True):
        with patch.dict(sys.modules,serial=SimpleNamespace(Serial=Serial)):
            link=m.Link('selected-port',io.StringIO(),stock=stock)
            assert link.serial.opened and link.serial.dtr is False and link.serial.rtscts is False and link.serial.rts is stock
        checks.append(dict(name='explicit port, DTR off, CTS gating off, RTS contract '+str(stock),passed=True))
    for phase in ('stage-original-816','original-816-to-bf1'):
        folder=a.plans/phase;plan=json.loads((folder/'plan.json').read_text());path=folder/'installer-model-only.s19';assert hashlib.sha256(path.read_bytes()).hexdigest()==plan['installer_sha256']
        cells,entry=m.read_s19(path);first,last=min(cells),max(cells);expected=bytes(cells[x] for x in range(first,last+1))
        class Stock:
            stock_load=m.Link.stock_load;stock_read=m.Link.stock_read
            def __init__(self,bad=False):self.ram=bytearray(32768);self.bad=bad;self.command=None;self.go=None;self.commands=[]
            def protocol(self,c):self.command=c;self.commands.append(c)
            def send(self,data):
                if self.command==6:self.go=int.from_bytes(data,'little');return
                address=int.from_bytes(data[:3],'little');count=int.from_bytes(data[3:6],'little');assert first<=address and address+count<=last+1
                if self.command==2:self.ram[address:address+count]=data[6:]
                else:
                    assert self.command==3;self.reply=bytearray(self.ram[address:address+count])
                    if self.bad:self.reply[0]^=1
            def exact(self,n):return b'\0' if self.command==2 else bytes(self.reply)
        for bad in (False,True):
            endpoint=Stock(bad)
            if bad:
                try:endpoint.stock_load(cells,entry)
                except IOError:assert endpoint.go is None and 6 not in endpoint.commands
                else:raise AssertionError('Bad stock readback executed')
            else:endpoint.stock_load(cells,entry);assert endpoint.go==entry and bytes(endpoint.ram[first:last+1])==expected
            checks.append(dict(name=phase+' stock load '+('bad readback refuses EXEC' if bad else 'exact RAM readback before EXEC'),passed=True,entry=entry))
        class Monitor:
            monitor_load=m.Link.monitor_load
            def __init__(self,bad=False):self.bad=bad;self.sent=[]
            def command(self,command,prompt):assert command=='L' and prompt==b'S19'
            def send(self,data):self.sent.append(data)
            def until(self,prompt):return prompt
            def dump(self,begin,end):
                assert (begin,end)==(first,last);return bytes([expected[0]^1])+expected[1:] if self.bad else expected
        for bad in (False,True):
            endpoint=Monitor(bad)
            with patch.object(m.time,'sleep',return_value=None):
                if bad:
                    try:endpoint.monitor_load(path)
                    except IOError:assert not any(line.startswith(b'G ') for line in endpoint.sent)
                    else:raise AssertionError('Bad monitor readback executed')
                else:endpoint.monitor_load(path);assert endpoint.sent[-1]==f'G {entry:04X}\r'.encode()
            checks.append(dict(name=phase+' monitor load '+('bad readback refuses G' if bad else 'exact RAM readback before G'),passed=True))
    report=dict(passed=True,cases=len(checks),checks=checks,transport_source_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),
                test_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),board_access=False,hardware_qualified=False,
                scope='Actual packaged constructor and stock/monitor RAM loaders for exact staging/bootstrap images; no physical stock handshake or native execution claim')
    a.out.write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),'packaged Windows transport checks; no ports opened')


if __name__=='__main__':main()
