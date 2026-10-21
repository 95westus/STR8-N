"""Run the actual one-command workflow against deterministic endpoints, no ports."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();pkg=a.package.resolve();sys.path[:0]=[str(pkg),str(pkg/'engine')]
    import upgrade as u
    import serial.tools.list_ports
    checks=[]
    class Endpoint:
        fail_restore=False
        def __init__(self,banks,kind):
            self.banks=list(map(bytes,banks));self.kind=kind;self.ram=bytearray(n%251 for n in range(32768));self.original=bytes(self.ram[0x200:0x6500])
            self.pending=bytearray();self.serial=self;self.in_waiting=0;self.bank=3;self.closed=False;self.loading=False;self.entry=0x200
            self.flash_calls=0;self.RAM_loads=0;self.stock_RAM_reads=0;self.first_stock_RAM=None;self.unstable_RAM=False
        def read(self,n):return b''
        def close(self):self.closed=True
        def command(self,text,prompt=b'\r\nB3> '):
            if text.startswith('B') and len(text)==2 and text[1] in '0123':self.bank=int(text[1])
            if text=='VERSION' and self.kind=='beta4':return b'VERSION\r\nBad cmd\r\nB3> '
            if text=='VERSION':
                version='2.0b4' if self.kind=='beta4' else '2.0rc1'
                gen=13 if self.kind=='beta4' else 50
                return f'STR8-N {version} 65C02 Board: MODEL\r\nMONITOR A gen {gen:08X} VALID\r\nMONITOR B gen {gen:08X} VALID\r\nB3> '.encode()
            if text=='L':self.loading=True;self.RAM_loads+=1
            return prompt
        def dump(self,first,last,prompt=None):
            if self.kind=='beta4' and first in (0x7d01,0x7d30):raise AssertionError('New service descriptor queried on beta4')
            if first>=0x8000:return self.banks[self.bank][first-0x8000:last-0x7fff]
            if (first,last)==(0x7d0a,0x7d0b):return b'\xff\x64'
            if first==last==0x7d01:return b'\x02'
            if first==last==0x7d30:return b'\xa0'
            if (first,last)==(0x7bfc,0x7bff):return bytes(4)
            body=bytes(self.ram[first:last+1])
            if self.fail_restore and self.RAM_loads and first<0x6500:body=bytes([body[0]^1])+body[1:]
            return body
        def send(self,body):
            if body.startswith(b'S1'):
                row=bytes.fromhex(body.strip()[2:].decode());address=int.from_bytes(row[1:3],'big');self.ram[address:address+len(row[3:-1])]=row[3:-1]
            elif body.startswith(b'S9'):
                self.entry=int.from_bytes(bytes.fromhex(body.strip()[2:].decode())[1:3],'big')
        def until(self,token,seconds=45):
            if token==b'> ':
                if self.kind in ('wdc','wdc816'):raise TimeoutError('No ASCII monitor')
                return b'\r\nB3> '
            if self.loading:
                self.loading=False;return f'Entry {self.entry:04X}\r\nB3> '.encode()
            return b'STR8-N 2.0rc1\r\nB3> '
        def stock_info_after_reset(self,seconds):return (b'SXB6' if self.kind=='wdc816' else b'SXB2')+bytes(8)
        def stock_read(self,address,count):
            if address==0x8000:return self.banks[3]
            self.stock_RAM_reads+=1
            if self.kind=='wdc816':self.ram[0x700]=(self.ram[0x700]+1)&255
            if self.unstable_RAM and self.stock_RAM_reads>=3:self.ram[0x900]^=1
            result=bytes(self.ram[address:address+count])
            if self.first_stock_RAM is None:self.first_stock_RAM=result
            return result
    inputs=[('current',Q/'rc1-uniform-model-development-r4/v1g-a0-capture'),
            ('rc1',Q/'rc1-uniform-model-development-r4/v1f-a0-capture'),
            ('beta4',Q/'rc1-uniform-bootstrap-development-r3/beta4-a0-capture'),
            ('wdc',Q/'rc1-uniform-bootstrap-development-r3/wdcmonv2-65C02-capture'),
            ('wdc816',Q/'rc1-uniform-bootstrap-development-r3/wdcmonv2-65C816-capture')]
    with tempfile.TemporaryDirectory(prefix='uniform-host-',dir=ROOT/'tmp') as temporary:
        temp=Path(temporary)
        def invoke(name,capture,*,fail_restore=False,allow_flash=True,qualification=True,unknown=False,unstable_RAM=False):
            banks=[(capture/f'b{n}.bin').read_bytes() for n in range(4)]
            if unknown:
                row=bytearray(banks[1]);row[0x2000]^=1;banks[1]=bytes(row)
            endpoint=Endpoint(banks,name);endpoint.fail_restore=fail_restore;endpoint.unstable_RAM=unstable_RAM
            args=SimpleNamespace(board='MODEL',usb_serial='MODEL-USB',port='SIMULATED',out=temp/(name+str(len(checks))),
                coordination_root=temp/'lease',reset_timeout=10,accept_unknown_wear_history=True,history=None,metadata_escrow=None)
            def engine(link,plan,**kw):
                u.plans.verify(pkg,plan);endpoint.flash_calls+=1
                endpoint.banks=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)];endpoint.kind='rc1'
                endpoint.ram[0x2000]^=1
                assert kw['host_readback'] is True and kw['stock']==(name in ('wdc','wdc816'))
                tx=u.r.read(plan/'plan.json')['transaction'];ops=tx['operations'] if name in ('wdc','wdc816') else tx['operations'][1:]
                return dict(transaction_device_verified=True,physical_reset_pending=True,transfers_completed=len(ops))
            with patch.object(serial.tools.list_ports,'comports',return_value=[SimpleNamespace(device='SIMULATED',serial_number='MODEL-USB')]),\
                 patch.object(u.wire,'Link',return_value=endpoint),patch.object(u.coordination,'serial_lease',return_value=contextlib.nullcontext()),\
                 patch.object(u,'settle',return_value=b''),patch.object(u.engine,'execute',side_effect=engine),\
                 patch.object(u.board.time,'sleep',return_value=None),contextlib.redirect_stdout(io.StringIO()):
                try:result=u.run(args,allow_flash=allow_flash,qualification=qualification)
                except (ValueError,IOError):result=u.r.read(args.out/'report.json') if args.out.exists() else None
            return endpoint,result,args.out
        ep,result,_=invoke(*inputs[0],allow_flash=False)
        assert result['passed'] and result['already_current'] and not result['flash_written'] and ep.flash_calls==ep.RAM_loads==0 and ep.closed
        checks.append(dict(name='actual-current-workflow-no-flash-no-RAM-load-no-reset',passed=True))
        for name,capture in inputs[1:]:
            ep,result,_=invoke(name,capture)
            assert result['passed'] and result['RAM_restored'] and result['full_RAM_rereads']==2 and ep.flash_calls==1 and ep.closed
            assert bytes(ep.ram[0x200:0x6500])==(ep.first_stock_RAM if name in ('wdc','wdc816') else ep.original)
            checks.append(dict(name=name+' actual single-command capture/plan/transport/reset/target/readback/full-RAM restoration',passed=True,transfers=result['transfers']))
        ep,result,_=invoke(*inputs[2],unknown=True)
        assert not result['passed'] and ep.flash_calls==ep.RAM_loads==0
        checks.append(dict(name='beta4 Bad cmd hint cannot admit occupied or unknown source bytes',passed=True))
        ep,result,_=invoke(*inputs[4],unstable_RAM=True)
        assert not result['passed'] and ep.flash_calls==ep.RAM_loads==0 and not result['application_RAM_restore_pending']
        checks.append(dict(name='SXB6 fresh RAM change outside live debugger page refuses before mutation',passed=True))
        source=bytes(0x6300)
        for offset,accepted in ((0x4ff,False),(0x500,True),(0x5ff,True),(0x600,False)):
            changed=bytearray(source);changed[offset]=1
            assert u.stable_stock_RAM_equal(b'SXB6',source,changed)==accepted
            assert not u.stable_stock_RAM_equal(b'SXB2',source,changed)
        checks.append(dict(name='SXB6 live stack exemption has exact 0700-07FF boundaries; SXB2 has none',passed=True))
        ep,result,_=invoke(*inputs[1],allow_flash=False)
        assert not result['passed'] and ep.flash_calls==ep.RAM_loads==0 and not result['application_RAM_restore_pending']
        checks.append(dict(name='read-only admission cannot silently flash an older source',passed=True))
        ep,result,_=invoke(*inputs[1],unknown=True)
        assert not result['passed'] and ep.flash_calls==ep.RAM_loads==0 and not result['application_RAM_restore_pending']
        checks.append(dict(name='unrecognized profile refuses before RAM/flash write',passed=True))
        ep,result,_=invoke(*inputs[1],fail_restore=True)
        assert not result['passed'] and result['application_RAM_restore_pending'] and 'restoration_failure' in result and ep.closed
        checks.append(dict(name='failed full-RAM restoration retains pending flag and refuses success',passed=True))
        ep,result,_=invoke(*inputs[0],qualification=False)
        assert result is None and ep.flash_calls==ep.RAM_loads==0
        checks.append(dict(name='unqualified kit refuses public live execution before port enumeration',passed=True))
    assert not a.out.exists();u.save(a.out,dict(passed=True,board_access=False,checks=checks,cases=len(checks),
        uniform_manifest_sha256=u.r.sha((pkg/'uniform-manifest.json').read_bytes()),test_source_sha256=u.r.sha(Path(__file__).read_bytes()),
        hardware_evidence=False,native_debugging=False,RTC_drift_in_release_qualification=False))
    print('PASS',len(checks),'actual uniform-workflow host checks; no ports opened')


if __name__=='__main__':main()
