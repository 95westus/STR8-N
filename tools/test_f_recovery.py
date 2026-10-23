"""Offline qualification for status-corrected F-size candidate; no devices."""
import argparse,sys,json
from pathlib import Path
from types import SimpleNamespace
import test_f_size as shared
from prepare_f_size import offline,protected,read
from str8build.formats import save,sha

def initialized(build,cpu,target,status=0x5a,case='valid'):
    b=list(map(bytearray,shared.banks_for(build)));page=0xa0 if target=='A' else 0xb0;off=(page-0x80)*256
    upload=shared.reseal(b[3][off:off+4096],51);b[3][0x2000:0x4000]=b'\xff'*8192
    if case=='blank-journal':b[3][0x4000:0x6000]=b'\xff'*8192
    if case=='invalid-journal':b[3][0x4000:0x6000]=bytes(8192)
    h=shared.Machine(build,cpu,list(map(bytes,b)));m,c=h.m,h.cpu;m.ram[0xf6]=status
    if case in ('stale','preferred','active'):
        other=0xb0 if target=='A' else 0xa0
        if case=='active':other=page
        oo=(other-0x80)*256;m.banks[3][oo:oo+4096]=shared.banks_for(build)[3][oo:oo+4096];m.ram[0x7d30]=other
        pref=shared.rt.preference(shared.config(),page if case=='preferred' else other,50)
        m.banks[3][0x4000:0x6000]=b'\xff'*8192;m.banks[3][0x4000:0x4080]=shared.rt.record(pref,[1]*32,1)
        if case=='stale':upload=shared.reseal(upload,49)
    if case=='bad-CRC':u=bytearray(upload);u[200]^=1;upload=bytes(u)
    if case=='wear-full':
        counts=[1]*32;counts[3*8+(page>>4)-8]=0xffffff
        m.banks[3][0x4000:0x4080]=shared.rt.record(shared.config(),counts,1)
    return h,upload,page,off

def attempt(h,upload,target,case='valid',fault=None):
    m,c=h.m,h.cpu;start=len(m.tx)
    m.ram[0x7c00:0x7c04]=('U '+target+'\0').encode();c.pc=h.sy['BOOT_UPDATE'];c.sp=255
    h.run(lambda:bytes(m.tx[start:]).endswith(b'Y then Enter> ') or c.pc==h.sy['BOOT_MENU'])
    if c.pc==h.sy['BOOT_MENU']:return 'refused'
    m.rx.extend(b'N\r' if case=='cancel' else b'Y\r')
    h.run(lambda:bytes(m.tx[start:]).endswith(b'SEND 4096 BIN\r\n') or c.pc==h.sy['BOOT_MENU'])
    if c.pc==h.sy['BOOT_MENU']:return 'refused'
    m.fault=fault if fault in ('timeout','erase_verify') else None
    injected=[];realstep=c.step
    if fault=='program_verify':
        def step():
            if not injected and c.pc==h.w['V2W_VERIFY'] and m.bank==3:
                off=0x2000 if target=='A' else 0x3000;m.banks[3][off+0x20]^=1;injected.append(True)
            return realstep()
        c.step=step
    if fault=='commit_timeout':
        realmutated=m.mutated
        def mutated(kind,address,value):
            realmutated(kind,address,value)
            if kind=='program' and address==(0xa01f if target=='A' else 0xb01f):m.fault='timeout';injected.append(True)
        m.mutated=mutated
    m.rx.extend(upload[:1024] if case=='partial' else upload)
    if case=='partial':
        h.run(lambda:not m.rx and c.pc==h.sy['BOOT_RECEIVE']);return 'partial'
    h.run(lambda:c.pc in (h.sy['BOOT_RESET'],h.sy['BOOT_MENU']),limit=6000000)
    if fault in ('program_verify','commit_timeout'):assert injected
    c.step=realstep
    return 'committed' if c.pc==h.sy['BOOT_RESET'] else 'refused'

def status_entry(candidate):
    rows=[]
    for cpu in ('65c02','65c816-e'):
        for target in ('A','B'):
            h,_,page,_=initialized(candidate,cpu,target)
            for status in range(256):
                c,m=h.cpu,h.m;c.pc=0xf57d;c.sp=255;c.a=page;c.x=0x42;c.y=0x53;c.p=0x24;m.ram[0xf6]=status
                h.run(lambda:c.pc==h.sy['BOOT_UPDATE_WRITE'])
                assert m.ram[0xf6]==0 and (c.a,c.x,c.y,c.sp,c.p)==(page,0x42,0x53,253,0x24) and not m.events
                if cpu=='65c816-e':assert c.mode==1 and c.b==0xa5
            rows.append(dict(cpu=cpu,target=target,statuses=256,passed=True))
    return rows

def recovery(control,candidate,out):
    cases=[]
    def compare(before,after,label):
        assert shared.observable_ram(before.m.ram)==shared.observable_ram(after.m.ram),label
        assert bytes(before.m.tx)==bytes(after.m.tx) and before.m.events==after.m.events,label
        assert tuple(getattr(before.cpu,k) for k in ('a','x','y','p','sp'))==tuple(getattr(after.cpu,k) for k in ('a','x','y','p','sp')),label
        if before.name=='65c816-e':assert before.cpu.mode==after.cpu.mode==1 and before.cpu.b==after.cpu.b==0xa5,label
        for n in range(4):
            end=0x7000 if n==3 else 32768
            assert bytes(before.m.banks[n][:end])==bytes(after.m.banks[n][:end]),label
    for cpu in ('65c02','65c816-e'):
        for target in ('A','B'):
            # The differential oracle is the original firmware with initialized
            # status. Every status in the candidate must produce that result.
            baseline,upload,_,off=initialized(control,cpu,target,0)
            assert attempt(baseline,upload,target)=='committed'
            for status in (0,1,2,0x5a,0xff):
                h,u,_,off=initialized(candidate,cpu,target,status)
                assert attempt(h,u,target)=='committed' and bytes(h.m.banks[3][off:off+4096])==u and b'COMMITTED' in h.m.tx
                compare(baseline,h,(cpu,target,status))
                cases.append(dict(cpu=cpu,target=target,case='status-'+hex(status),passed=True,committed=True))
            # Reproduce the old bug separately so the regression has a known
            # failing control and a fixed result, rather than only a new oracle.
            buggy,u,_,off=initialized(control,cpu,target,0x5a)
            assert attempt(buggy,u,target)=='refused' and buggy.m.banks[3][off+31]==255
            for label in ('blank-journal','bad-CRC','partial','stale','preferred','active','cancel','invalid-journal','wear-full'):
                hs=[];results=[]
                for build in (control,candidate):
                    # Requests reaching the write attempt compare against an
                    # initialized baseline; pre-write refusals retain status.
                    status=0 if build==control and label in ('blank-journal','invalid-journal','wear-full') else 0x5a
                    h,u,_,off=initialized(build,cpu,target,status,label)
                    flash_before=list(map(bytes,h.m.banks));results.append(attempt(h,u,target,label));hs.append(h)
                    if label!='blank-journal':
                        assert list(map(bytes,h.m.banks))==flash_before and not h.m.events,(cpu,target,label,'refusal/partial must preserve existing flash')
                assert results[0]==results[1];compare(*hs,(cpu,target,label))
                if label=='blank-journal':assert results[1]=='committed'
                elif label=='partial':assert results[1]=='partial' and not hs[1].m.events
                else:assert results[1]=='refused' and b'REFUSED' in hs[1].m.tx and b'COMMITTED' not in hs[1].m.tx,(cpu,target,label)
                cases.append(dict(cpu=cpu,target=target,case=label,passed=True,result=results[1]))
            for fault in ('timeout','erase_verify','program_verify','commit_timeout'):
                hs=[]
                for build in (control,candidate):
                    h,u,_,off=initialized(build,cpu,target,0 if build==control else 0x5a)
                    assert attempt(h,u,target,fault=fault)=='refused' and b'COMMITTED' not in h.m.tx and h.m.ram[0xf6]!=0
                    if fault!='commit_timeout':assert h.m.banks[3][off+31]==255
                    hs.append(h)
                compare(*hs,(cpu,target,fault))
                # Clear only the simulated hardware fault. Keep the inherited
                # status and retry the complete command in the same session.
                h=hs[1];h.m.fault=None
                if fault=='commit_timeout':
                    # Remove the fault hook for the second commit attempt.
                    h.m.mutated=shared.Memory.mutated.__get__(h.m,shared.Memory)
                assert attempt(h,u,target)=='committed' and bytes(h.m.banks[3][off:off+4096])==u
                cases.append(dict(cpu=cpu,target=target,case=fault,passed=True,genuine_failure_refused=True,same_session_retry_committed=True))
            print('PASS recovery status, refusal, real-fault and same-session retry',cpu,target,flush=True)
            save(out/'recovery-progress.json',dict(cases=cases))
    return cases

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cold-only',action='store_true');a=p.parse_args()
    for k in ('control','candidate','out'):setattr(a,k,getattr(a,k).resolve())
    offline();snapshot=protected();assert not a.out.exists();a.out.mkdir(parents=True);shared.ARGS=a
    assert read(a.candidate/'f-size-build.json')['recovery_status_fixed']
    crc=shared.crc_model_check(a.control)
    if a.cold_only:result=dict(cold_boot=shared.cold(),reset_CRC_accelerated=False,foreground_unchanged_CRC_accelerated=True)
    else:
        b=shared.branches();entries=status_entry(a.candidate);print('PASS branch states and all 1024 CPU/slot/status entry cases',flush=True)
        rows,cuts=shared.functional()
        result=dict(branch_states=b,status_entry_cases=entries,journal_cases=rows,power_cut_read_states=cuts)
        save(a.out/'pre-recovery-qualification.json',dict(passed=True,**result))
        result['recovery_cases']=recovery(a.control,a.candidate,a.out)
    assert protected()==snapshot
    save(a.out/'report.json',dict(passed=True,board_access=False,serial_network_used=False,firmware_sha256=sha((a.candidate/'firmware.bin').read_bytes()),test_sha256=sha(Path(__file__).read_bytes()),shared_test_sha256=sha(Path(shared.__file__).read_bytes()),unchanged_CRC_oracle_cases=crc,physical_electrical_timing_tested=False,**result))
    print('PASS corrected F recovery qualification:',a.out/'report.json',flush=True)
if __name__=='__main__':main()
