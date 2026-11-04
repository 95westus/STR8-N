"""Run combined OIP1 suite with differentially verified app/F CRC loop summaries.

The new app checks about 16 KiB before EVERY request. Bulk CRC summaries keep
the exhaustive 17,256-prefix suite practical. All comparisons/refusal branches
still execute linked code. UART cycle timing is not covered by this summary.
"""
import argparse
import json
from pathlib import Path
import test_recovery_kit as ck

t=ck.t


def summary(h, start, end, successor, loop):
    m,c=h.m,h.c
    assert m.bank==3 and t.word(m,0xe0)==start
    data=bytes(m.ram[start:end]) if end else bytes(m.banks[3][0x7000:])
    assert data
    # Leave exactly the last CRC call's stack cells, registers and flags.
    # Pointer increment and loop exit flags are also reproduced. Clock cycles
    # are intentionally omitted, as in the existing bulk OIP1 loop summaries.
    seed=t.word(m,0x7d38)
    m.ram[0x7d38:0x7d3a]=t.base.binascii.crc_hqx(data[:-1],seed).to_bytes(2,'little')
    c.a=data[-1]
    c.stPushWord(loop+4)
    t.base.fast_crc(c,m,0x7d38)
    t.store_word(m,0xe0,end)
    inc=(end&255) or (end>>8)
    c.p=(c.p&~0x82)|(2 if not inc else inc&128)
    c.pc=successor


def crc_hooks(h):
    sy=h.i
    f_loop=sy['MA_F_CRC']
    # Bind this summary to the exact linked 19-byte F traversal shape.
    code=bytes(h.m.ram[f_loop:f_loop+22])
    assert code[:2]==bytes((0xb2,0xe0)) and code[19:22]==bytes((0xad,0x38,0x7d)),code
    return {
        sy['MA_SELF']:lambda z:summary(z,sy['MA_START'],sy['MA_SUM'],sy['MA_SELF_CHECK'],sy['MA_SELF']),
        f_loop:lambda z:summary(z,0xf000,0,f_loop+19,f_loop),
    }


def registers(h):
    return {name:getattr(h.c,name) for name in ('pc','a','x','y','p','sp','b','mode','dbr','pbr','dpr') if hasattr(h.c,name)}


def validate(build,cpu):
    rows=[]
    t.base.GENERATION=json.loads((build/'prototype-report.json').read_text())['experimental_generation']
    for fault in ('none','app','F'):
        h=t.patterned_machine(build,cpu)
        if fault=='app': h.m.ram[h.i['MA_IMAGE_B']+21]^=1
        if fault=='F': h.m.banks[3][0x7fdf]^=1
        h.m.tx.clear();h.m.acia_tx.clear()
        h.c.pc=h.i['CK_VERIFY'];h.c.sp=255;h.c.stPushWord(0x1ff)
        h.run(lambda:h.c.pc==h.i['MA_SELF'])
        fast=t.clone_prepared(h,h.m.banks)
        # Validate the app loop at exactly the same linked successor.
        h.run(lambda:h.c.pc==h.i['MA_SELF_CHECK'] and t.word(h.m,0xe0)==h.i['MA_SUM'])
        crc_hooks(fast)[fast.i['MA_SELF']](fast)
        assert registers(h)==registers(fast),(registers(h),registers(fast))
        assert h.m.ram==fast.m.ram and h.m.banks==fast.m.banks
        rows.append(dict(cpu=cpu,case='app-CRC-summary-'+fault,passed=True,bytes=h.i['MA_SUM']-0x200))
        # Faulty apps refuse before reaching the F loop, as linked checks do.
        if fault=='app':
            for z in (h,fast): z.run(lambda:bytes(z.m.tx).endswith(ck.F_REC))
        else:
            for z in (h,fast): z.run(lambda:z.c.pc==z.i['MA_F_CRC'])
            h.run(lambda:h.c.pc==h.i['MA_F_CRC']+19)
            crc_hooks(fast)[fast.i['MA_F_CRC']](fast)
            assert registers(h)==registers(fast),(registers(h),registers(fast))
            assert h.m.ram==fast.m.ram and h.m.banks==fast.m.banks
            rows.append(dict(cpu=cpu,case='F-CRC-summary-'+fault,passed=True,bytes=4096))
            for z in (h,fast): z.run(lambda:z.c.pc==0x200 or bytes(z.m.tx).endswith(ck.F_REC))
        assert registers(h)==registers(fast)
        assert h.m.ram==fast.m.ram and h.m.banks==fast.m.banks
        assert h.m.tx==fast.m.tx and h.m.acia_tx==fast.m.acia_tx
        assert not h.m.events and not fast.m.events
        print('PASS',cpu,'linked-app/F-CRC-summary-differential',fault,flush=True)
    proof=build/f'recovery-kit-crc-summary-{cpu}.json'
    t.base.save(proof,dict(passed=True,hardware=False,serial_access=False,checks=len(rows),failures=0,cases=rows,
        app_sha256=t.sha((build/'payload/recovery-kit.bin').read_bytes()),checker_sha256=t.sha(Path(__file__).read_bytes()),
        limitations=['Bulk CRC cycles omitted; same successor registers/flags/stack/full RAM/flash and final linked acceptance/refusal checked']))
    return proof


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
    p.add_argument('--cpu',choices=('65c02','65c816-e'),required=True);p.add_argument('--mode',choices=('opaque',),default='opaque')
    x=p.parse_args();build=x.build.resolve();proof=validate(build,x.cpu)
    original=t.accelerated_hooks
    def accelerated(h,*args,**kw):
        hooks=original(h,*args,**kw);hooks.update(crc_hooks(h));return hooks
    t.accelerated_hooks=accelerated
    ck.main()
    result=build/f'recovery-kit-opaque-{x.cpu}.json'
    data=json.loads(result.read_text());data['CRC_loop_summary_proof']=dict(path=str(proof),sha256=t.sha(proof.read_bytes()))
    data['accelerated_driver_sha256']=t.sha(Path(__file__).read_bytes());t.base.save(result,data)
