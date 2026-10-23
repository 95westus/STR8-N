"""Offline CPU differential qualification of the isolated fixed-F size candidate."""
import argparse,binascii,json,sys
from pathlib import Path
from collections import deque
from prepare_f_size import read,offline,protected
from str8build.formats import save,sha,read_s19
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'BUILD/v1.30/local/test-deps'),str(ROOT/'BUILD/test-deps-816')]
from py65.devices.mpu65c02 import MPU as CPU02
from py65816.devices.mpu65c816 import MPU as CPU816
from installer.flash_model import Memory as NOR
from installer.engine import runtime as rt,legacy_transport as wire
from test_monitor_size import fast_crc,crc_model_check

def banks_for(build):return [bytes([0xff])*32768]+[(build/'firmware.bin').read_bytes()[i:i+32768] for i in range(0,98304,32768)]
def config():return bytearray(rt.latest(banks_for(ARGS.control))[2][8:24])
def observable_ram(ram):
    # Calls finish with SP=FF. Dead stack return-address bytes relocate with
    # the code; live registers, ZP and every non-stack RAM byte must agree.
    return ram[:0x100]+ram[0x200:]
def journal(banks,rows,peer=None):
    b=list(map(bytearray,banks));b[3][0x4000:0x6000]=b'\xff'*8192
    for i,row in enumerate(rows):b[3][0x4000+i*128:0x4080+i*128]=row
    if peer is not None:b[3][0x5000:0x6000]=peer
    return list(map(bytes,b))

class Memory(NOR):
    def __init__(self,banks):
        super().__init__(banks);self.cuts=[]
    def mutated(self,kind,address,value):
        self.events.append((kind,self.bank,address,value))
        assert self.bank==3 and 0xa000<=address<0xf000,'Unexpected flash ownership'
        if kind=='erase':
            record=rt.latest(list(map(bytes,self.banks)))[2]
            index=3*8+(address>>12)-8
            assert int.from_bytes(record[24+3*index:27+3*index],'little')>0,'Unaccounted erase'
        if address&0xf000 in (0xc000,0xd000):
            self.cuts.append(bytes(self.banks[3][0x4000:0x6000]))

class Machine:
    def __init__(self,build,cpu,banks=None,accelerate=True):
        self.build=build;self.sy=read(build/'symbols.json')['core/str8n-v2-boot'];self.w=read(build/'symbols.json')['core/str8n-v2-worker']
        self.m=Memory(banks or banks_for(build));self.cpu=(CPU02 if cpu=='65c02' else CPU816)(memory=self.m,pc=0xf004)
        self.cpu.pc=0xf004;self.cpu.p=0x24;self.cpu.sp=255;self.m.cpu=self.cpu;self.name=cpu;self.steps=0;self.accelerate=accelerate
        if cpu!='65c02':self.cpu.b=0xa5
        self.run(lambda:self.cpu.pc==self.sy['BOOT_SELECT'])
        # Reset's CPU detector owns the temporary native/emulation exchange.
        # Set the caller's hidden B fixture after that initialization.
        if cpu!='65c02':self.cpu.b=0xa5
    def run(self,stop,limit=4000000):
        for _ in range(limit):
            if stop():return
            c,m=self.cpu,self.m;self.steps+=1
            if self.accelerate and c.pc==0xfabd and m.bank==3:fast_crc(c,m,0x7d38);continue
            if m.fault=='timeout' and c.pc==self.w['V2W_POLL']:
                c.stPop();c.pc=self.w['V2W_TIMEOUT'];continue
            if c.pc==self.w['V2W_BOOT_DELAY_OUTER']:c.pc=self.w['V2W_BOOT_DELAY_DONE'];continue
            op=m[c.pc]
            if self.name=='65c02' and op&15==15:
                pc=c.pc;bit=bool(m[m[(pc+1)&65535]]&(1<<((op>>4)&7)));take=bit if op&128 else not bit;d=m[(pc+2)&65535]
                c.pc=(pc+3+((d if d<128 else d-256) if take else 0))&65535
            else:c.step()
        raise AssertionError(('CPU timeout',self.name,hex(self.cpu.pc),bytes(self.m.tx[-200:])))
    def call(self,entry,mode=None,index=0,cfg=None):
        c,m=self.cpu,self.m;c.pc=self.sy[entry] if isinstance(entry,str) else entry;c.sp=255;c.a=0x31;c.x=0x42;c.y=0x53;c.p=0x24
        m.ram[0xf3]=3;m.ram[0x7d3c]=index
        if cfg is not None:m.ram[0x7d80:0x7d90]=cfg
        c.stPushWord(0x1ff);self.run(lambda:c.pc==0x200)
        assert m.bank==3 and (self.name=='65c02' or (c.mode==1 and c.b==0xa5))
        return (c.a,c.x,c.y,c.sp,c.p),bytes(m.ram),list(map(bytes,m.banks)),bytes(m.tx)

def branches():
    oldsy=read(ARGS.control/'symbols.json')['core/str8n-v2-boot'];newsy=read(ARGS.candidate/'symbols.json')['core/str8n-v2-boot'];pairs=read(ARGS.candidate/'f-size-build.json')['pairs'];count=0
    for CPU in (CPU02,CPU816):
        old=[0]*65536;new=old.copy();old[0x8000:]=banks_for(ARGS.control)[3];new[0x8000:]=banks_for(ARGS.candidate)[3]
        a,b=CPU(memory=old,pc=0x200),CPU(memory=new,pc=0x200)
        for p in pairs:
            before=oldsy[p['skip']]-5;after=newsy[p['skip']]-2
            for flags in range(256):
                for c,pc in ((a,before),(b,after)):
                    c.pc=pc;c.p=flags|0x30 if CPU is CPU816 else flags;c.a=0x42;c.x=0x37;c.y=0x19;c.sp=0xe5
                    if CPU is CPU816:c.b=0xa5
                a.step()
                if a.pc==before+2:a.step()
                b.step();expected=newsy[p['skip']] if a.pc==oldsy[p['skip']] else newsy[p['dest']]
                assert b.pc==expected and (a.a,a.x,a.y,a.sp,a.p)==(b.a,b.x,b.y,b.sp,b.p)
                if CPU is CPU816:assert a.mode==b.mode==1 and a.b==b.b==0xa5
                count+=1
    return count

def functional():
    rows=[];cuts=0;cfg=config();base=banks_for(ARGS.control)
    def record(seq=1,counts=None,cfg=cfg):return rt.record(cfg,counts or [1]*32,seq)
    scenarios=[('read-valid',[record()],None,'BOOT_API_READ',None,0,None),('read-blank',[],None,'BOOT_API_READ',None,0,None),
        ('unchanged-config',[record()],None,'BOOT_API_CFG',cfg,0,None)]
    changed=bytearray(cfg);changed[1]=1;changed[14:]=wire.config_sum(changed)
    promoted=rt.preference(cfg,0xb0,50)
    scenarios += [('save-config',[record()],None,'BOOT_API_CFG',changed,0,None),('promote',[record()],None,'BOOT_API_PROMOTE',promoted,0,None)]
    for idx in range(32):scenarios.append(('wear-'+str(idx),[record()],None,'BOOT_ERASE_ENTRY',None,idx,None))
    for value in (0xfe,0xff,0xffff,0xfffffe,0xffffff):
        counts=[1]*32;counts[5]=value;scenarios.append(('counter-'+hex(value),[record(counts=counts)],None,'BOOT_ERASE_ENTRY',None,5,None))
    scenarios += [('sequence-full',[record(0xffffffff)],None,'BOOT_API_CFG',changed,0,None),
        ('rollover',[record(i+1) for i in range(31)],bytes(4096),'BOOT_API_CFG',changed,0,None),
        ('rollover-peer-blank',[record(i+1) for i in range(31)],None,'BOOT_API_CFG',changed,0,None),
        ('rollover-no-reservation',[record(i+1) for i in range(32)],bytes(4096),'BOOT_API_CFG',changed,0,None),
        ('write-timeout',[record()],None,'BOOT_API_CFG',changed,0,'timeout'),
        ('erase-verify',[record(i+1) for i in range(31)],bytes(4096),'BOOT_API_CFG',changed,0,'erase_verify')]
    badcrc=bytearray(record(2));badcrc[24]^=1
    torn=bytearray(record(3));torn[127]=255
    scenarios += [('bad-CRC-and-torn',[record(),badcrc,torn],None,'BOOT_API_READ',None,0,None)]
    for cpu in ('65c02','65c816-e'):
        for label,recs,peer,entry,newcfg,idx,fault in scenarios:
            hs=[]
            for build in (ARGS.control,ARGS.candidate):
                b=journal(banks_for(build),recs,peer);h=Machine(build,cpu,b);h.m.fault=fault;hs.append(h)
            results=[h.call(entry,index=idx,cfg=newcfg) for h in hs]
            assert results[0][0]==results[1][0] and observable_ram(results[0][1])==observable_ram(results[1][1]) and results[0][3]==results[1][3],(cpu,label,'registers/RAM/output')
            for n in range(4):assert results[0][2][n][:(0x7000 if n==3 else 32768)]==results[1][2][n][:(0x7000 if n==3 else 32768)],(cpu,label,'flash')
            assert hs[0].m.events==hs[1].m.events and hs[0].m.cuts==hs[1].m.cuts,(cpu,label,'mutation order/cuts')
            # Every modeled mutation boundary is a possible power-loss snapshot.
            # Re-enter the actual read API from each complete NOR snapshot.
            if label in ('save-config','rollover'):
                for i,cut in enumerate(hs[0].m.cuts):
                    outcomes=[]
                    for build in (ARGS.control,ARGS.candidate):
                        b=list(map(bytearray,banks_for(build)));b[3][0x4000:0x6000]=cut
                        h=Machine(build,cpu,list(map(bytes,b)));outcome=h.call('BOOT_API_READ');outcomes.append((outcome[0],observable_ram(outcome[1])));assert not h.m.events
                    assert outcomes[0]==outcomes[1],(cpu,label,i,'cut read')
                    # The last committed record must always remain readable.
                    rt.latest([base[0],base[1],base[2],base[3][:0x4000]+cut+base[3][0x6000:]])
                    cuts+=1
            rows.append(dict(cpu=cpu,case=label,passed=True,mutations=len(hs[0].m.events)))
            print('PASS journal',cpu,label,flush=True)
            save(ARGS.out/'journal-progress.json',dict(cases=rows,power_cut_read_states=cuts))
    return rows,cuts

def reseal(slot,generation):
    b=bytearray(slot);b[8:12]=generation.to_bytes(4,'little');b[18:20]=wire.crc(b[:18]+b[32:]).to_bytes(2,'little');return bytes(b)

def recovery():
    cases=[]
    for cpu in ('65c02','65c816-e'):
        for target in ('A','B'):
            for label in ('valid-journal','blank-journal','nonzero-status','bad-upload','partial-upload','reject-stale','reject-preferred'):
                hs=[];oldslots=[]
                for build in (ARGS.control,ARGS.candidate):
                    b=list(map(bytearray,banks_for(build)));page=0xa0 if target=='A' else 0xb0;off=(page-0x80)*256
                    upload=reseal(b[3][off:off+4096],51)
                    b[3][0x2000:0x4000]=b'\xff'*8192
                    if label=='blank-journal':b[3][0x4000:0x6000]=b'\xff'*8192
                    h=Machine(build,cpu,list(map(bytes,b)));m,c=h.m,h.cpu
                    # Existing recovery inherits FLASH_ERROR on the accounted
                    # journal path. Test both an initialized status and the
                    # pre-existing refusal for a nonzero inherited status.
                    if label=='valid-journal':m.ram[0xf6]=0
                    if label in ('reject-stale','reject-preferred'):
                        m.ram[0x7d30]=0xb0 if target=='A' else 0xa0
                        other=0xb0 if target=='A' else 0xa0;oo=(other-0x80)*256
                        src=banks_for(build)[3][oo:oo+4096];m.banks[3][oo:oo+4096]=src
                        pref=rt.preference(config(),page if label=='reject-preferred' else other,50)
                        m.banks[3][0x4000:0x6000]=b'\xff'*8192;m.banks[3][0x4000:0x4080]=rt.record(pref,[1]*32,1)
                        if label=='reject-stale':upload=reseal(upload,49)
                    if label=='bad-upload':upload=bytearray(upload);upload[200]^=1;upload=bytes(upload)
                    m.ram[0x7c00:0x7c04]=('U '+target+'\0').encode();c.pc=h.sy['BOOT_UPDATE'];c.sp=255
                    h.run(lambda:bytes(m.tx).endswith(b'Y then Enter> ') or c.pc==h.sy['BOOT_MENU'])
                    refused=c.pc==h.sy['BOOT_MENU']
                    if label=='reject-preferred':assert refused and not m.events
                    else:
                        assert not refused;m.rx.extend(b'Y\r');h.run(lambda:bytes(m.tx).endswith(b'SEND 4096 BIN\r\n'))
                        m.rx.extend(upload[:1024] if label=='partial-upload' else upload)
                        if label=='partial-upload':
                            h.run(lambda:not m.rx and c.pc==h.sy['BOOT_RECEIVE']);assert not m.events
                        else:
                            h.run(lambda:c.pc in (h.sy['BOOT_RESET'],h.sy['BOOT_MENU']),limit=6000000)
                            if label in ('bad-upload','reject-stale'):assert c.pc==h.sy['BOOT_MENU'] and not m.events
                            elif label=='nonzero-status':assert c.pc==h.sy['BOOT_MENU'] and m.events and m.banks[3][off+31]==255
                            else:assert c.pc==h.sy['BOOT_RESET'] and b'COMMITTED' in m.tx and bytes(m.banks[3][off:off+4096])==upload
                    hs.append(h)
                assert bytes(hs[0].m.tx)==bytes(hs[1].m.tx) and observable_ram(hs[0].m.ram)==observable_ram(hs[1].m.ram) and hs[0].m.events==hs[1].m.events,(cpu,target,label)
                for n in range(4):assert bytes(hs[0].m.banks[n][:(0x7000 if n==3 else 32768)])==bytes(hs[1].m.banks[n][:(0x7000 if n==3 else 32768)])
                cases.append(dict(cpu=cpu,target=target,case=label,passed=True,mutations=len(hs[0].m.events)))
                print('PASS recovery',cpu,target,label,flush=True)
    return cases

def cold():
    # Run actual reset, relocated vector copying and foreground features with
    # actual CRC instructions. No CRC acceleration is used in this proof.
    sys.path.insert(0,str(ROOT/'tmp'))
    import phase21_boot_features as boot
    import monitor_install_features as feat
    recorded=ROOT/'output/qualification/monitor-size-install-2604-20261022-r1/install-plan'
    original=[(recorded/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert original[3][-4096:]==banks_for(ARGS.control)[3][-4096:]
    cases=[]
    for cpu in ('65c02','65c816-e'):
        for slot in ('A','B'):
            results=[]
            for label,build in (('baseline',ARGS.control),('candidate',ARGS.candidate)):
                boot.BUILD=build;b=list(original);b[3]=b[3][:-4096]+banks_for(build)[3][-4096:]
                h=boot.ColdHarness(b,cpu,slot,boot=False)
                h.run(lambda:h.waiting('monitor'));h.booting=False;h.boot_output=bytes(h.m.tx).decode()
                bs=h.symbols['core/str8n-v2-boot']
                assert h.visits[0xf004] and h.visits[bs['BOOT_SLOT_CHECK']] and h.visits[bs['J_VALID']]
                assert h.m.ram[0x7d30]==(0xa0 if slot=='A' else 0xb0) and bytes(h.m.ram[0x7d80:0x7d90])==h.expected_config
                feat.PAYLOAD=boot.PAYLOAD[:-1]+bytes([0xa1 if slot=='A' else 0xb1])
                # After real reset/CRC/vector initialization, accelerate only
                # the byte-identical common CRC helper for foreground tests.
                realstep=h.cpu.step
                def step():
                    if h.cpu.pc==0xfabd and h.m.bank==3:fast_crc(h.cpu,h.m,0x7d38);return h.cpu
                    return realstep()
                h.cpu.step=step
                result=feat.run(h);h.check_persistent()
                results.append((h.boot_output,result,observable_ram(bytes(h.m.ram)),boot.registers(h)))
                save(ARGS.out/f'cold-{cpu}-{slot}-{label}.json',dict(passed=True,steps=h.steps,boot=h.boot_output,features=result,reset_CRC_accelerated=False,foreground_unchanged_CRC_accelerated=True))
                print('PASS actual cold boot/features',cpu,slot,label,flush=True)
            assert results[0]==results[1],(cpu,slot,'full cold state/output')
            cases.append(dict(cpu=cpu,slot=slot,passed=True))
    return cases

def main():
    global ARGS
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cold-only',action='store_true');ARGS=p.parse_args()
    for k in ('control','candidate','out'):setattr(ARGS,k,getattr(ARGS,k).resolve())
    offline();snapshot=protected();assert not ARGS.out.exists();ARGS.out.mkdir(parents=True)
    if ARGS.cold_only:
        crc=crc_model_check(ARGS.control)
        result=dict(cold_boot=cold(),reset_CRC_accelerated=False,foreground_unchanged_CRC_accelerated=True,unchanged_CRC_acceleration_oracle_cases=crc)
    else:
        count=branches();print('PASS exhaustive branch states',count,flush=True)
        crc=crc_model_check(ARGS.control);print('PASS unchanged-CRC test acceleration oracle',crc,flush=True)
        rows,cuts=functional();result=dict(branch_states=count,journal_cases=rows,power_cut_read_states=cuts,recovery_cases=recovery(),unchanged_CRC_acceleration_oracle_cases=crc)
    assert protected()==snapshot
    save(ARGS.out/'report.json',dict(passed=True,board_access=False,serial_network_used=False,firmware_sha256=sha((ARGS.candidate/'firmware.bin').read_bytes()),test_sha256=sha(Path(__file__).read_bytes()),physical_electrical_timing_tested=False,**result))
    print('PASS fixed-F CPU qualification:',ARGS.out/'report.json',flush=True)
if __name__=='__main__':main()
