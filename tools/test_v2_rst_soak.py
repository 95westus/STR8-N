"""Execute the actual RST soak transaction against a guarded linked model."""
import argparse,json,os,shutil,types
from pathlib import Path

def main(root,board,names,attempt):
    from run_v2_rst_soak import unit,clock
    source=root/board;plan=json.loads((source/'soak-plan.json').read_text());os.environ['STR8_RTC_BUILD']=plan['source']['source_build']
    from test_v2_status import fresh,boot,layout,snapshot
    from test_v2_storage import cmd
    modelroot=root/('model-'+board+'-'+attempt);folder=modelroot/board;folder.mkdir(parents=True,exist_ok=False)
    for name in ('soak-plan.json','initial-state.json','clock-original.json','wear-state.json'):
        shutil.copyfile(source/name,folder/name)
    for p in source.glob('*-original.bin'):shutil.copyfile(p,folder/p.name)
    shutil.copytree(source/'prior-verified',folder/'prior-verified')
    c,m=fresh(primary=layout());m.banks=[bytearray((source/f'prior-verified/b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
    ee=(root/(board+'-eeprom-original.bin')).read_bytes();m.bus.ee[:128]=ee[:128];m.bus.ee[0xFF]=ee[128];m.bus.ee[0xF0:0xF8]=ee[129:137]
    registers=bytes.fromhex(json.loads((source/'clock-original.json').read_text())['control_trim']);m.bus.rtc_regs[7:9]=registers
    original_mutated=m.mutated
    def guard(self,kind,address,value):
        assert (self.bank==2 and 0x8000<=address<0xA000) or (self.bank==3 and 0xC000<=address<0xE000),'Mutation outside scratch and existing wear journal'
        original_mutated(kind,address,value)
    m.mutated=types.MethodType(guard,m);boot(c)
    class Link:
        def command(self,text,prompt=None):return cmd(c,m,(text+'\r').encode())
        def dump(self,first,last,prompt=None):
            # The monitor stays resident in B3; D reads the selected bank via its
            # RAM worker rather than directly dereferencing the current ROM bank.
            return bytes(m.banks[m.ram[0xF3]][a-0x8000] if a>=0x8000 else m[a] for a in range(first,last+1))
        def write_ram(self,address,data,prompt=None):m.ram[address:address+len(data)]=data
    l=Link();before=snapshot(m)
    # Same calendar-independent raw history/trim/identity contract as hardware.
    assert clock(l)==json.loads((source/'clock-original.json').read_text())
    results=[]
    for i,name in enumerate(names):
        out=folder/f'{i:05d}-{name}';out.mkdir();results.append(unit(l,modelroot,plan,name,i,out,model=True))
        assert snapshot(m)[1:]==before[1:],'RTC/EEPROM/SRAM changed'
    report=dict(passed=True,board=board,programs=names,all_transactions_executed=True,
        scratch_whitelist_guard=True,original_firmware_programs_and_devices_preserved=True,results=results)
    (modelroot/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',board,'exact guarded parallel-soak transaction qualification',names,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);p.add_argument('--attempt',default='r2');p.add_argument('--programs',nargs='+',default=['MAINT','CLOCK','SRAM','WORK','EDU']);a=p.parse_args();main(a.root.resolve(),a.board,a.programs,a.attempt)
