"""Offline actual-package RAM transport, guarded source capture and failure checks."""
import argparse,hashlib,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'

def main():
    p=argparse.ArgumentParser();p.add_argument('--kit',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists()
    sys.path.insert(0,str(a.kit.resolve()));import workflow as w;import install_transport as engine;import runtime as r;import migrate as m;import factory_wdc as f;import recover
    checks=[]
    def passed(name):checks.append(dict(name=name,passed=True))
    def refused(name,call):
        try:call()
        except (ValueError,OSError,TimeoutError,KeyError):passed(name)
        else:raise AssertionError('Accepted failure '+name)
    plans=Q/'bf1-empty-bank-tests-2026-10-18-r1'
    class ReadEndpoint:
        def __init__(self,b3,bad=False):self.b3=b3;self.calls=[];self.bad=bad;self.ram=bytes((n%251 for n in range(0x6300)))
        def stock_read(self,address,count):
            self.calls.append((address,count))
            if address==0x8000:
                return (bytes([self.b3[0]^1])+self.b3[1:]) if self.bad and len(self.calls)>1 else self.b3
            assert (address,count)==(0x200,0x6300);return self.ram
        def dump(self,first,last,*args):
            if first==0x8000:return self.stock_read(first,last-first+1)
            return self.ram[first-0x200:last-0x200+1]
    with tempfile.TemporaryDirectory(prefix='bf1-live-wire-',dir=ROOT/'tmp') as tmp:
        tmp=Path(tmp);prepared=[]
        for label,source_name,stock in [('WDC','2609-WDC-to-full-bf1',True),('beta4','2604-beta4-to-full-bf1',False)]:
            source=(plans/source_name/'source-b3.bin').read_bytes();cap=tmp/(label+'-capture');ep=ReadEndpoint(source)
            identity=w.capture_empty(ep,'fixture',cap,stock,'EXPLICIT-USB')
            assert identity['schema']==2 and identity['repeat_verified'] is False and identity['assumed_erased_banks']==[0,1,2]
            assert len([x for x in ep.calls if x[0]==0x8000])==2
            m.capture(cap);passed(label+' source capture labels assumed erased banks honestly and repeats only B3')
            output=tmp/(label+'-plan')
            if stock:plan=f.prepare(cap,a.kit,output,accept_unknown_history=True);f.validate_plan(output,a.kit)
            else:plan=m.prepare_beta4(cap,a.kit,output);m.validate_beta4_plan(output,a.kit)
            assert (output/'expected-b0.bin').read_bytes()==b'\xff'*32768 and b'UCHESS\0' in (output/'expected-b1.bin').read_bytes()
            prepared.append((label,output,stock,plan,cap));passed(label+' guarded complete plan installs all providers and UCHESS')
            refused(label+' inconsistent source capture refuses before RAM archive',lambda:w.capture_empty(ReadEndpoint(source,True),'fixture',tmp/(label+'-bad'),stock))
        for label,folder,stock,plan,cap in prepared:
            ops=plan['transaction']['operations'] if stock else plan['transaction']['operations'][1:]
            class Endpoint:
                def __init__(self,fault=None):
                    self.fault=fault;self.sent=[];self.ram=bytearray(32768);self.entry=None;self.executed=False;self.method=None;self.row=0;self.stream=None;self.loader_calls=[]
                def command(self,command,prompt):assert command=='L';return prompt
                def protocol(self,method):self.method=method
                def exact(self,count):return b'\1' if self.fault=='bad-ack' else b'\0'
                def stock_load(self,cells,entry):self.loader_calls.append('stock-readback');self.executed=True
                def monitor_load(self,path):self.loader_calls.append('monitor-readback');self.executed=True
                def send(self,data):
                    self.sent.append(data)
                    if self.stream is not None:
                        if self.fault=='short-transfer':raise IOError('Simulated short serial write')
                        self.stream.extend(data)
                        if len(self.stream)==4096:
                            assert bytes(self.stream)==(folder/f'transfer-{self.row:02d}.bin').read_bytes();self.row+=1;self.stream=None
                        return
                    if data==b'Y\r':return
                    if self.method==2:
                        address=int.from_bytes(data[:3],'little');count=int.from_bytes(data[3:6],'little');assert len(data)==6+count
                        self.ram[address:address+count]=data[6:];return
                    if self.method==6:self.entry=int.from_bytes(data,'little');self.executed=True;return
                    if data.startswith(b'S1'):
                        raw=bytes.fromhex(data[2:].strip().decode());address=int.from_bytes(raw[1:3],'big');self.ram[address:address+len(raw[3:-1])]=raw[3:-1]
                    elif data.startswith(b'S9'):self.entry=int.from_bytes(bytes.fromhex(data[2:].strip().decode())[1:3],'big')
                    elif data.startswith(b'G '):self.executed=True
                def until(self,token,seconds=45):
                    if token==b'\r\nB3> ':return b'Bad load\r\nB3> ' if self.fault=='bad-loader' else f'Entry {self.entry:04X}\r\nB3> '.encode()
                    if token==b'Y then Enter> ':assert self.executed;return token
                    if token.startswith(b'SEND '):
                        if self.fault=='timeout':raise TimeoutError('Simulated transfer timeout')
                        op=ops[self.row];assert token==f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode();self.stream=bytearray();return token
                    assert token==b'MIGRATION VERIFIED; PRESS PHYSICAL RESET' and self.row==len(ops)
                    if self.fault=='device-refused':raise IOError('Simulated device verification failure')
                    return token
            with patch.object(engine.time,'sleep',return_value=None):
                for readback in (True,False):
                    endpoint=Endpoint();result=engine.execute(endpoint,folder,stock=stock,host_readback=readback)
                    assert result['transaction_device_verified'] and endpoint.row==len(ops) and result['physical_reset_pending']
                    assert bool(endpoint.loader_calls)==readback
                    passed(label+(' default RAM-readback loader' if readback else ' owner-selected no-extra-host-readback loader')+' sends exact complete transfer sequence')
                for fault in ('timeout','short-transfer','device-refused','bad-ack' if stock else 'bad-loader'):
                    endpoint=Endpoint(fault)
                    refused(label+' '+fault+' aborts without retry or false completion',lambda:engine.execute(endpoint,folder,stock=stock,host_readback=False))
                    if fault in ('bad-ack','bad-loader'):assert not endpoint.executed
                transfer=folder/'transfer-00.bin';saved=transfer.read_bytes();transfer.write_bytes(saved[:-1])
                endpoint=Endpoint();refused(label+' truncated local payload refuses before serial writes',lambda:engine.execute(endpoint,folder,stock=stock,host_readback=False));assert not endpoint.sent;transfer.write_bytes(saved)
            endpoint=Endpoint();(cap/'application-ram.bin').write_bytes(b'X'*0x6300)
            refused(label+' changed RAM restoration archive refuses before serial load',lambda:w.restore_ram(endpoint,cap,False));assert not endpoint.sent
        # Direct-WDC completed recovery is write-free; unsupported earlier cuts must refuse.
        label,folder,stock,plan,cap=prepared[0]
        def captured(path,banks):
            path.mkdir();files={}
            for n,body in enumerate(banks):
                for suffix in ('','-repeat'):
                    name=f'b{n}{suffix}.bin';(path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
            (path/'capture.json').write_text(json.dumps(dict(schema=1,board='fixture',repeat_verified=True,files=files)))
        target=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)];current=tmp/'complete';captured(current,target)
        result=recover.prepare_recovery('prepare-forward',a.kit,folder,current,tmp/'factory-no-write');assert result['write_required'] is False
        passed('Direct-WDC exact completed target produces a no-write recovery receipt')
        unknown=list(target);unknown[2]=bytes([target[2][0]^1])+target[2][1:];other=tmp/'unknown';captured(other,unknown)
        refused('Direct-WDC unknown partial state refuses guessed recovery',lambda:recover.prepare_recovery('prepare-forward',a.kit,folder,other,tmp/'unknown-recovery'))
        refused('Vendor restoration cannot be disguised as beta4 restoration',lambda:recover.prepare_recovery('prepare-restore-beta4',a.kit,folder,current,tmp/'vendor-restore'))
        import shutil
        disabled=tmp/'disabled-kit';shutil.copytree(a.kit,disabled,ignore=shutil.ignore_patterns('__pycache__'))
        manifest=r.read(disabled/'kit-manifest.json');manifest['live_installation_enabled']=False
        (disabled/'kit-manifest.json').write_text(json.dumps(manifest))
        refused('Explicitly disabled workflow gate refuses before serial selection/import',lambda:w.gate(disabled))
    a.out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,board_access=False,hardware_qualified=False,
        kit_manifest_sha256=r.sha((a.kit/'kit-manifest.json').read_bytes()),install_transport_sha256=r.sha(Path(engine.__file__).read_bytes()),
        test_sha256=r.sha(Path(__file__).read_bytes()),scope='Actual packaged transport and capture/admission failure paths with simulated endpoints; physical CPU proofs separate'),indent=2)+'\n')
    print('PASS',len(checks),'actual portable transport/capture/recovery refusal checks; no board ports')

if __name__=='__main__':main()
