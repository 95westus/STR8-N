"""Offline differential CPU qualification of the F control-flow candidate."""
import argparse,sys
from pathlib import Path
import test_f_size as common
import test_f_recovery as recovery
from prepare_f_flow import BASE,protected,offline,read
from str8build.formats import save,sha
ROOT=Path(__file__).resolve().parents[1]

def compare(a,b,label,registers=True):
    assert common.observable_ram(a.m.ram)==common.observable_ram(b.m.ram),(label,'RAM')
    assert bytes(a.m.tx)==bytes(b.m.tx) and a.m.events==b.m.events,(label,'output/mutations')
    if registers:assert tuple(getattr(a.cpu,k) for k in ('a','x','y','p','sp'))==tuple(getattr(b.cpu,k) for k in ('a','x','y','p','sp')),(label,'registers')
    if a.name=='65c816-e':assert a.cpu.mode==b.cpu.mode==1 and a.cpu.b==b.cpu.b==0xa5,label
    for n in range(4):
        end=0x7000 if n==3 else 32768
        assert bytes(a.m.banks[n][:end])==bytes(b.m.banks[n][:end]),(label,'flash',n)

def branches(a):
    changes=read(a.candidate/'f-flow-build.json')['changes'];os=read(a.control/'symbols.json')['core/str8n-v2-boot'];ns=read(a.candidate/'symbols.json')['core/str8n-v2-boot'];count=0
    for CPU in (common.CPU02,common.CPU816):
        old=[0]*65536;new=old.copy();old[0x8000:]=common.banks_for(a.control)[3];new[0x8000:]=common.banks_for(a.candidate)[3]
        before,after=CPU(memory=old,pc=0x200),CPU(memory=new,pc=0x200)
        for change in changes:
            for flags in range(256):
                for c,pc in ((before,change['before_pc']),(after,change['after_pc'])):
                    c.pc=pc;c.p=flags|0x30 if CPU is common.CPU816 else flags;c.a=0x42;c.x=0x37;c.y=0x19;c.sp=0xe5;c.stPushWord(0x1ff)
                    if CPU is common.CPU816:c.b=0xa5
                before.step();after.step()
                if change['kind']=='conditional':
                    if before.pc==change['before_pc']+2:before.step()
                    if before.pc==os[change['skip']]:assert after.pc==ns[change['skip']]
                    elif change['semantic_dest']=='BOOT_SLOT_BAD':
                        assert before.pc==os['BOOT_SLOT_BAD'] and after.pc==ns['FBC_SLOT_BAD']
                        for c in (before,after):c.step();c.step()
                        assert before.pc==after.pc==0x200
                    else:
                        if change['dest']=='FBC_UPDATE_REFUSE':after.step()
                        assert before.pc==os[change['semantic_dest']] and after.pc==ns[change['semantic_dest']]
                else:assert before.pc==os[change['dest']] and after.pc==ns[change['dest']]
                assert tuple(getattr(before,k) for k in ('a','x','y','p','sp'))==tuple(getattr(after,k) for k in ('a','x','y','p','sp')),(change,flags)
                if CPU is common.CPU816:assert before.mode==after.mode==1 and before.b==after.b==0xa5
                assert old[:0x8000]==new[:0x8000]
                count+=1
    assert count==18432
    return count

def updates(a):
    cases=[]
    for cpu in ('65c02','65c816-e'):
        for target in ('A','B'):
            for status in (0,1,2,0x5a,0xff):
                hs=[]
                for build in (a.control,a.candidate):
                    h,u,_,off=recovery.initialized(build,cpu,target,status)
                    assert recovery.attempt(h,u,target)=='committed' and bytes(h.m.banks[3][off:off+4096])==u and b'COMMITTED' in h.m.tx
                    hs.append(h)
                compare(*hs,(cpu,target,status));cases.append(dict(cpu=cpu,target=target,case='status-'+hex(status),passed=True))
            for name in ('blank-journal','bad-CRC','partial','stale','preferred','active','cancel','invalid-journal','wear-full'):
                hs=[];results=[]
                for build in (a.control,a.candidate):
                    h,u,_,off=recovery.initialized(build,cpu,target,0x5a,name);before=list(map(bytes,h.m.banks))
                    results.append(recovery.attempt(h,u,target,name));hs.append(h)
                    if name!='blank-journal':assert list(map(bytes,h.m.banks))==before and not h.m.events
                assert results[0]==results[1];compare(*hs,(cpu,target,name))
                assert results[1]==('committed' if name=='blank-journal' else 'partial' if name=='partial' else 'refused')
                cases.append(dict(cpu=cpu,target=target,case=name,passed=True))
            for fault in ('timeout','erase_verify','program_verify','commit_timeout'):
                hs=[]
                for build in (a.control,a.candidate):
                    h,u,_,off=recovery.initialized(build,cpu,target,0x5a)
                    assert recovery.attempt(h,u,target,fault=fault)=='refused' and h.m.ram[0xf6] and b'COMMITTED' not in h.m.tx
                    if fault!='commit_timeout':assert h.m.banks[3][off+31]==255
                    hs.append(h)
                compare(*hs,(cpu,target,fault))
                for h in hs:
                    h.m.fault=None
                    if fault=='commit_timeout':h.m.mutated=common.Memory.mutated.__get__(h.m,common.Memory)
                    assert recovery.attempt(h,u,target)=='committed' and bytes(h.m.banks[3][off:off+4096])==u
                compare(*hs,(cpu,target,fault,'retry'))
                cases.append(dict(cpu=cpu,target=target,case=fault,passed=True,new_fault_refused=True,same_session_retry_committed=True))
            print('PASS recovery/refusal/fault/retry',cpu,target,flush=True);save(a.out/'recovery-progress.json',dict(cases=cases))
    return cases

def slots(a):
    cases=[];parser=[]
    for cpu in ('65c02','65c816-e'):
        for target in ('A','B'):
            page=0xa0 if target=='A' else 0xb0;off=(page-0x80)*256;original=common.banks_for(a.control)[3][off:off+4096]
            variants=[('valid',original)]
            for index in list(range(32))+[0x80,0x81,0x100,0xfff]:
                for value in sorted({0,1,0x7f,0x80,0xfe,0xff,original[index]^1}):
                    if value==original[index]:continue
                    b=bytearray(original);b[index]=value
                    # Traverse structural validation with correctly sealed data;
                    # preserve deliberately corrupted checksum/commit fields.
                    if index not in (18,19,31):b[18:20]=common.wire.crc(b[:18]+b[32:]).to_bytes(2,'little')
                    variants.append((f'byte-{index:x}-{value:x}',bytes(b)))
            for length in (0,1,0xf7f,0xf80,0xf81,0xfff,0x1000,0xffff):
                b=bytearray(original);b[12:14]=length.to_bytes(2,'little');b[18:20]=common.wire.crc(b[:18]+b[32:]).to_bytes(2,'little');variants.append(('length-'+hex(length),bytes(b)))
            for location in ('flash','RAM-upload'):
                hs=[common.Machine(build,cpu) for build in (a.control,a.candidate)]
                for name,data in variants:
                    answers=[]
                    for h in hs:
                        pointer=page if location=='flash' else 0x68
                        if location=='flash':h.m.banks[3][off:off+4096]=data
                        else:h.m.ram[0x6800:0x7800]=data
                        h.m.ram[0xe0:0xe2]=bytes([0,pointer]);h.m.ram[0x7d31]=page
                        answers.append(h.call('BOOT_SLOT_CHECK')[0])
                        assert not h.m.events
                    assert answers[0]==answers[1],(cpu,target,location,name)
                    compare(*hs,(cpu,target,location,name));cases.append(dict(cpu=cpu,target=target,location=location,case=name,passed=True,valid=bool(answers[0][-1]&1)))
                print('PASS slot header/CRC/length boundaries',cpu,target,location,len(variants),flush=True)
            for command in ('U','UA','U  A','U C','U A!','U B!','U\tA','U 0'):
                hs=[]
                for build in (a.control,a.candidate):
                    h,_,_,_=recovery.initialized(build,cpu,target,0x5a)
                    h.m.ram[0x7c00:0x7c20]=bytes(32);h.m.ram[0x7c00:0x7c00+len(command)]=command.encode()
                    h.cpu.pc=h.sy['BOOT_UPDATE'];h.cpu.sp=255
                    h.run(lambda:h.cpu.pc==h.sy['BOOT_MENU'])
                    assert b'REFUSED' in h.m.tx and not h.m.events;hs.append(h)
                compare(*hs,(cpu,target,command));parser.append(dict(cpu=cpu,target=target,command=command,passed=True))
    return dict(slot_validation_cases=cases,invalid_update_command_cases=parser)

def cold(a):
    sys.path.insert(0,str(ROOT/'tmp'));import phase21_boot_features as boot;import monitor_install_features as feature
    recorded=ROOT/'output/qualification/f-size-install-2604-20261022-r1/install-plan'
    original=[(recorded/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert original[3][-4096:]==common.banks_for(a.control)[3][-4096:]
    result=[]
    for cpu in ('65c02','65c816-e'):
        for slot in ('A','B'):
            outcomes=[]
            for label,build in (('baseline',a.control),('candidate',a.candidate)):
                boot.BUILD=build;b=list(original);b[3]=b[3][:-4096]+common.banks_for(build)[3][-4096:]
                h=boot.ColdHarness(b,cpu,slot,boot=False);h.run(lambda:h.waiting('monitor'));h.booting=False;h.boot_output=bytes(h.m.tx).decode()
                sy=h.symbols['core/str8n-v2-boot'];assert all(h.visits[sy[key]] for key in ('BOOT_RESET','BOOT_SLOT_CHECK','J_VALID'))
                assert h.m.ram[0x7d30]==(0xa0 if slot=='A' else 0xb0) and bytes(h.m.ram[0x7d80:0x7d90])==h.expected_config
                # Actual CRC opcodes during reset; only the unchanged helper is
                # accelerated for foreground commands after 3072 CPU oracles.
                realstep=h.cpu.step
                def step():
                    if h.cpu.pc==0xfabd and h.m.bank==3:common.fast_crc(h.cpu,h.m,0x7d38);return h.cpu
                    return realstep()
                h.cpu.step=step;feature.PAYLOAD=boot.PAYLOAD[:-1]+bytes([0xa1 if slot=='A' else 0xb1])
                checks=feature.run(h);h.check_persistent()
                outcomes.append((h.boot_output,checks,common.observable_ram(bytes(h.m.ram)),boot.registers(h)))
                save(a.out/f'cold-{cpu}-{slot}-{label}.json',dict(passed=True,steps=h.steps,boot=h.boot_output,features=checks,reset_CRC_accelerated=False,foreground_unchanged_CRC_accelerated=True))
                print('PASS actual cold boot/features',cpu,slot,label,flush=True)
            assert outcomes[0]==outcomes[1],(cpu,slot,'full state/output')
            result.append(dict(cpu=cpu,slot=slot,passed=True))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=('core','slots','cold'),default='core');a=p.parse_args()
    for name in ('control','candidate','out'):setattr(a,name,getattr(a,name).resolve())
    offline();snapshot=protected();assert not a.out.exists();a.out.mkdir(parents=True);common.ARGS=a
    assert sha((a.control/'firmware.bin').read_bytes())==BASE and read(a.candidate/'f-flow-build.json')['passed']
    crc=common.crc_model_check(a.control)
    if a.mode=='cold':result=dict(cold_boot=cold(a),reset_CRC_accelerated=False)
    elif a.mode=='slots':result=slots(a)
    else:
        b=branches(a);entries=recovery.status_entry(a.candidate);print('PASS all 18432 branch/jump states and 1024 status-entry cases',flush=True)
        rows,cuts=common.functional();result=dict(branch_states=b,status_entry_cases=entries,journal_cases=rows,power_cut_read_states=cuts)
        save(a.out/'pre-recovery-qualification.json',dict(passed=True,**result));result['recovery_cases']=updates(a)
    assert protected()==snapshot and sha((ROOT/'BUILD/current/firmware.bin').read_bytes())==BASE
    save(a.out/'report.json',dict(passed=True,board_access=False,serial_network_used=False,mode=a.mode,firmware_sha256=sha((a.candidate/'firmware.bin').read_bytes()),test_sha256=sha(Path(__file__).read_bytes()),shared_test_sha256=sha(Path(common.__file__).read_bytes()),recovery_helper_sha256=sha(Path(recovery.__file__).read_bytes()),unchanged_CRC_oracle_cases=crc,physical_electrical_timing_tested=False,**result))
    print('PASS F flow qualification:',a.out/'report.json',flush=True)
if __name__=='__main__':main()
