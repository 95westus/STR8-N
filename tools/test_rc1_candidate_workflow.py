"""Run the real packaged install workflow with deterministic serial endpoints only."""
import argparse,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
def main():
    p=argparse.ArgumentParser();p.add_argument('--kit',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,str(a.kit.resolve()));import workflow as w;import runtime as r
    checks=[];assert not a.out.exists();w.gate(a.kit)
    with tempfile.TemporaryDirectory(prefix='rc1-workflow-',dir=a.out.resolve().parent) as tmp:
        temp=Path(tmp)
        for route,name in [('wdcmonv2','2609-WDC-to-full-bf1'),('beta4','2604-beta4-to-full-bf1')]:
            root=temp/route;active_plan=root/'plan';source=(a.fixtures/name/'source-b3.bin').read_bytes();ram=bytes(n%251 for n in range(0x6300));opened=[]
            class Endpoint:
                def __init__(self,port,log,stock=False):
                    assert port=='SIMULATED';opened.append(stock);self.stock=stock;self.serial=self;self.pending=bytearray();self.row=0;self.method=None;self.stream=None;self.entry=None;self.ramloads=0
                def reset_input_buffer(self):pass
                def close(self):pass
                def stock_info_after_reset(self,seconds):return b'SXB6'+b'\0'*12
                def stock_read(self,address,count):return source if address==0x8000 else ram
                def dump(self,first,last,*args):return source if first==0x8000 else ram[first-0x200:last-0x200+1]
                def command(self,text,prompt=b'\r\nB3> '):
                    if text=='T 1':return b'UCHESS\r\nB3> '
                    return prompt
                def protocol(self,method):self.method=method
                def exact(self,count):return b'\0'
                def send(self,data):
                    if self.stream is not None:
                        self.stream.extend(data)
                        if len(self.stream)==4096:
                            assert bytes(self.stream)==(active_plan/f'transfer-{self.row:02d}.bin').read_bytes();self.row+=1;self.stream=None
                        return
                    if data in (b'Y\r',b'VERSION\r'):return
                    if self.method==2:return
                    if self.method==6:self.entry=int.from_bytes(data,'little');return
                    if data.startswith(b'S9'):self.entry=int.from_bytes(bytes.fromhex(data[2:].strip().decode())[1:3],'big')
                def until(self,token,seconds=45):
                    if token==b'\r\nB3> ':return f'Entry {self.entry or 0x200:04X}\r\nB3> '.encode()
                    if token.startswith(b'SEND '):
                        plan=r.read(active_plan/'plan.json');ops=plan['transaction']['operations'] if self.stock else plan['transaction']['operations'][1:]
                        op=ops[self.row];assert token==f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode();self.stream=bytearray()
                    if token==b'MIGRATION VERIFIED; PRESS PHYSICAL RESET':
                        plan=r.read(active_plan/'plan.json');assert self.row==len(plan['transaction']['operations'])-(0 if self.stock else 1)
                    return token
            def selection(port,usb):assert (port,usb)==('SIMULATED','USB-ONLY')
            with patch.object(w.wire,'Link',Endpoint),patch.object(w,'selected_port',selection),patch.object(w.time,'sleep',return_value=None):
                result=w.install(route,a.kit,'SIMULATED','USB-ONLY','local-fixture',root,empty_banks=True,unknown_wear=True,host_readback=False,ask=lambda text:'INSTALL RC1')
            assert result['passed'] and result['transfers_completed']==22 and result['RAM_restoration']['loader_acknowledged'] and not result['RAM_restoration']['host_verified']
            assert not result['application_RAM_restore_pending'] and not result['clock_set'] and not result['trim_changed'] and opened==[route=='wdcmonv2',False]
            checks.append(dict(name=route+' full capture/plan/exact 22 transfers/reset/rc1/U CHESS/RAM workflow'.replace('U CHESS','UCHESS'),passed=True))
            if route=='beta4':
                current=temp/'current';current.mkdir();files={}
                for n in range(4):
                    body=(root/'plan'/f'expected-b{n}.bin').read_bytes()
                    for suffix in ('','-repeat'):
                        filename=f'b{n}{suffix}.bin';(current/filename).write_bytes(body);files[filename]=dict(bytes=len(body),sha256=r.sha(body))
                (current/'capture.json').write_text(json.dumps(dict(schema=1,board='local-fixture',usb_serial='USB-ONLY',repeat_verified=True,files=files)))
                active_plan=temp/'restore-beta4';opened.clear()
                with patch.object(w.wire,'Link',Endpoint),patch.object(w,'selected_port',selection),patch.object(w.time,'sleep',return_value=None):
                    result=w.recovery_live('restore-beta4',a.kit,root/'plan',current,active_plan,'SIMULATED','USB-ONLY','local-fixture',host_readback=False,ask=lambda text:'RECOVER RC1')
                assert result['transaction_device_verified'] and opened==[False,False]
                assert r.read(active_plan/'RAM-restoration.json')['sha256']==r.sha(ram)
                checks.append(dict(name='live bounded beta4 restoration uses original pre-migration RAM archive, not interrupted RAM',passed=True))
        # Preconditions must refuse even an enabled kit without importing/enumerating serial.
        with patch.object(w.wire,'Link',side_effect=AssertionError('Forbidden real port')):
            try:w.install('beta4',a.kit,'NO-PORT',None,'fixture',temp/'refuse',empty_banks=True)
            except ValueError as error:assert 'USB serial' in str(error)
            else:raise AssertionError('Missing USB identity accepted')
        checks.append(dict(name='enabled workflow refuses missing explicit USB identity before serial import',passed=True))
    a.out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,kit_manifest_sha256=r.sha((a.kit/'kit-manifest.json').read_bytes()),board_access=False,simulated_endpoints=True),indent=2)+'\n')
    print('PASS real packaged full workflow with simulated serial endpoints:',len(checks))
if __name__=='__main__':main()
