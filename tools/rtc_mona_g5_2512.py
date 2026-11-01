"""2512 Mona g5 entry/return adapter for the frozen qualified RAM RTC sampler."""
import sys,json,types
from pathlib import Path
ROOT=Path('C:/SRC/STR8-N');sys.path.insert(0,str(ROOT/'tools'))
import rtc_drift_campaign as c
Q=ROOT/'output/qualification'
PROFILE='BASE1-RTC-RAM1-MONA-G5'
RPATH=Q/'2512-mona-g5-wb1-20261029-r1/final-receipt.json'
RSHA='b464ad4c32d4cad85f270b778363712adb49cb8fd2150eed2d2e68dc8e60822e'
assert c.sha(RPATH)==RSHA
G5=c.read(RPATH)
path=ROOT/'tools/rtc_base1_collect.py'
assert c.sha(path)=='fea08bf9f2d8cd98b76fb31e2ebf56271a329601c3af1532c69b3d9834eab92e'
source=path.read_text()
source=source.replace("marker['final_prompt']=='REC>'","marker['final_prompt']=='MonaB>'")
old="banks=[marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]\n    assert banks==r['after_bank_sha256']\n    return marker,receipt,meta,bodies,proof,image,reader,banks"
new="""assert r['RAM_sha256']==G5['owner_restore']['RAM_sha256'] and r['ZP_sha256']==G5['owner_restore']['ZP_sha256']
    banks=G5['after_bank_sha256']
    marker=dict(marker,current_physical_bank_sha256={f'B{n}':v for n,v in enumerate(banks)})
    return marker,RPATH,meta,bodies,proof,image,reader,banks"""
assert old in source
source=source.replace(old,new).replace("'BASE1-RTC-RAM1'",repr(PROFILE))
d=types.ModuleType('g5_rtc_driver');d.__file__=str(path);d.G5=G5;d.RPATH=RPATH
exec(compile(source,str(path),'exec'),d.__dict__)
original_inputs=d.inputs
def inputs():
    m=c.read(d.MARK)
    assert c.sha(RPATH)==RSHA and G5['passed'] and G5['COM4_released'] and G5['owner_RAM_ZP_restored_after_physical_boot']
    assert m['state']=='Mona-g5-installed-default-B-ready' and m['final_prompt']=='MonaB>'
    assert Path(m['last_preservation_report']).resolve()==RPATH.resolve()
    assert G5['foundation']['F_sha256']==d.F_SHA and G5['generation']=='00000005'
    for name,expected in G5['evidence_sha256'].items():
        assert c.sha(RPATH.parent/name)==expected,name
    return original_inputs()
d.inputs=inputs
OriginalLink=d.transport.RecoveryLink
class MonaLink(OriginalLink):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.first=True;self.returned=False
    def until(self,token,seconds=60):
        if self.first:
            self.first=False
            assert token==d.live.REC
            OriginalLink.until(self,b'MonaB> ',seconds=15)
            self.send(b'Q\r')
        return OriginalLink.until(self,token,seconds=seconds)
    def close(self):
        records=[json.loads(x) for x in folder.joinpath('serial.jsonl').read_text().splitlines()]
        rx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='RX')
        try:
            if rx.endswith(d.live.REC):
                self.send(b'B\r')
                body=OriginalLink.until(self,b'MonaB> ',seconds=20)
                assert b'g00000005 / MON B' in body
                folder.joinpath('final-MonaB.txt').write_bytes(body)
                self.returned=True
        finally:super().close()
apath=ROOT/'tools/rtc_base1_audit.py'
assert c.sha(apath)=='45dc570f0672231fde7548fbb30c3cc70026e969bfba52cac7f0a7e992be2b9b'
audit_source=apath.read_text().replace("'BASE1-RTC-RAM1'",repr(PROFILE))
audit_source=audit_source.replace("assert rx.endswith(b'REC> ')","assert rx.endswith(b'MonaB> ')")
audit_source=audit_source.replace("expected=b'\\rC1\\rL\\r'","expected=b'\\rQ\\rC1\\rL\\r'")
audit_source=audit_source.replace("assert tx==expected,","assert tx==expected+b'B\\r',")
a=types.ModuleType('g5_rtc_audit');a.__file__=str(apath)
exec(compile(audit_source,str(apath),'exec'),a.__dict__)

def collect(out):
    global folder
    folder=Path(out)
    inputs()
    previous=d.transport.RecoveryLink
    d.transport.RecoveryLink=MonaLink
    try:
        r=d.collect(folder)
    finally:
        d.transport.RecoveryLink=previous
    assert (folder/'final-MonaB.txt').read_bytes().endswith(b'MonaB> ')
    r.update(original_prompt='MonaB>',returned_to_original_Mona=True,REC_was_intermediate_only=True)
    c.save(folder/'report.json',r)
    c.save(folder/'Mona-adapter.json',dict(receipt=str(RPATH),receipt_sha256=RSHA,script_sha256=c.sha(__file__),initial_and_final_prompt='MonaB>',no_sampler_binary_changes=True))
    (folder/'adapted-driver.py').write_text(source)
    (folder/'adapted-audit.py').write_text(audit_source)
    return r

def audit_board(item,state):
    point=a.audit_board(item,state)
    r=c.read(item['report']);folder=Path(item['report']).parent
    assert r['initial_qualified_receipt_sha256']==RSHA and r['returned_to_original_Mona']
    assert (folder/'final-MonaB.txt').read_bytes().endswith(b'MonaB> ')
    assert c.read(folder/'Mona-adapter.json')['script_sha256']==c.sha(__file__)
    return point

if __name__=='__main__':
    inputs()
    print('PASS Mona g5 admission and frozen sampler inputs; no ports opened')
