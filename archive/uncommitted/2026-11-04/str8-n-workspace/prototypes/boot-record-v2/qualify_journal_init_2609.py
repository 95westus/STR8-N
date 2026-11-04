"""Package tested RAM initializer, independently reproduce it, check readers.

Offline preparation only. Deliberately has no hardware/serial execution path.
"""
import argparse
import json
import shutil
from pathlib import Path

import prepare_journal_init_2609 as planner
from installer.common import save
from test_journal_init_2609 import Model, PROMPT, REC
from test_b14_raw import start, feed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--proof',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--rebuild',type=Path,required=True)
    args=p.parse_args();plan=args.plan.resolve();out=args.out.resolve()
    assert not out.exists()
    info=planner.verify(plan);proof=json.loads(args.proof.read_text())
    assert proof['passed'] and proof['checks']==28 and proof['plan_sha256']==planner.digest(plan/'plan.json')
    assert proof['image_sha256']==info['image_sha256']
    assert proof['test_source_sha256']==planner.digest(Path(__file__).with_name('test_journal_init_2609.py'))
    extra=[]
    for cpu in ('65c816-e','65c02'):
        model=Model(plan,cpu=cpu);model.execute();model.command(b'Q\r',REC)
        h=model.h
        # Stop the initializer-specific hash shortcut before loading a different
        # RAM program whose unrelated instructions may share those addresses.
        h.c.step=type(h.c).step.__get__(h.c)
        before=list(map(bytes,h.m.banks));events=len(h.m.events)
        start(h,1);app=(planner.TARGET/'payload/ram-config-offline.bin').read_bytes()
        feed(h,1,app);prompt=b'CONFIG prototype I(blank only) W C target Q> '
        h.run(lambda:bytes(h.m.tx).endswith(prompt))
        result=h.port_command(1,b'W\r',prompt)
        for bank in range(4):
            for n,value in enumerate(info['counts_reserved'][8*bank:8*bank+8]):
                assert f'B{bank}:{8+n:X} {value:06X}\r\n'.encode() in result
        assert b'UNKNOWN HISTORY' in result and b'OK\r\n' in result and b'REFUSED' not in result
        assert h.m.ram[0x6720:0x6730].hex()==info['config_before']
        assert len(h.m.events)==events and list(map(bytes,h.m.banks))==before
        h.port_command(1,b'Q\r',REC)
        extra.append(dict(passed=True,case='existing-b15-RAM-CONFIG-W-reads-exact-imported-counts-'+cpu,
                          record_body_CRC_and_duplicate_guard_admitted=True,unknown_history_retained=True,
                          config_body_preserved=True,no_flash_mutation=True))
        print('PASS',extra[-1]['case'],flush=True)
    real=Model(plan,accelerate=False)
    print('RUN complete four-bank/RAM guard with actual 65C816 instructions (no FNV shortcut)',flush=True)
    steps_before=real.h.steps;cycles_before=real.h.c.processorCycles
    real.h.run(lambda:bytes(real.h.m.tx).endswith(PROMPT) or real.h.c.pc==real.sy['JI_HALT'],limit=100_000_000)
    assert bytes(real.h.m.tx).endswith(PROMPT) and not real.h.m.events
    extra.append(dict(passed=True,case='complete-preflight-actual-65C816-instructions',
                      CPU_steps=real.h.steps-steps_before,cycles=real.h.c.processorCycles-cycles_before,
                      FNV_acceleration=False,all_four_banks_checked=True,no_flash_mutation=True))
    print('PASS',extra[-1]['case'],extra[-1]['CPU_steps'],'steps',flush=True)
    rebuilt=planner.prepare(args.rebuild)
    assert rebuilt['image_sha256']==info['image_sha256']
    same=['payload/2609-journal-init-RAM.bin','snapshot-C.bin','snapshot-D.bin',*[f'expected-b{n}.bin' for n in range(4)]]
    assert all((plan/name).read_bytes()==(args.rebuild/name).read_bytes() for name in same)
    extra.append(dict(passed=True,case='independent-build-and-journal-postimages-reproduce-byte-for-byte',files=same))
    print('PASS',extra[-1]['case'],flush=True)
    out.mkdir(parents=True)
    # Bank escrow stays in the plan directory, never in a transfer payload.
    shutil.copy2(plan/'payload/2609-journal-init-RAM.bin',out/'2609-journal-init-RAM.bin')
    shutil.copy2(plan/'plan.json',out/'plan.json')
    shutil.copy2(args.proof,out/'model-proof.json')
    (out/'reader-transcript.txt').write_bytes(result)
    report=dict(passed=True,hardware=False,serial_access=False,board_access=False,flashed=False,
                checks=proof['checks']+len(extra),base_model_groups=proof['checks'],additional_checks=extra,
                board='2609',image_bytes=info['bytes'],image_sha256=info['image_sha256'],
                load_address=info['load_address'],end_exclusive=info['end_exclusive'],
                source_plan=str(plan/'plan.json'),source_plan_sha256=planner.digest(plan/'plan.json'),
                base_model_proof=str(args.proof.resolve()),base_model_proof_sha256=planner.digest(args.proof),
                counts_before=info['counts_before'],counts_reserved=info['counts_reserved'],
                owner_wear_file_unchanged=True,B0_backup_sha256=info['B0_backup_sha256'],
                planned_erase_order=info['planned_erase_order'],MON_installed=False,
                ACIA_board_tested=False,
                limitations=['CPU/NOR models only; board has not loaded/run this initializer',
                             'First D erase has host reservation only; valid onboard accounting starts at D commit',
                             'Interrupted states require a newly assessed host recovery plan',
                             'F keeps its current reset console behavior; legacy config body is preserved'],
                source_sha256={p.name:planner.digest(p) for p in (Path(__file__),Path(__file__).with_name('test_journal_init_2609.py'),Path(__file__).with_name('prepare_journal_init_2609.py'),Path(__file__).with_name('ram-journal-init-2609.asm'))})
    save(out/'qualification.json',report)
    receipt=f'''# 2609 RAM journal initializer — prepared, not executed

Passed {report['checks']} offline groups/checks. No port opened, board program
loaded, flash sector written, MON installed, or owner wear history changed.

- RAM BIN: `2609-journal-init-RAM.bin`, {info['bytes']} bytes, load/entry `$0200`,
  end exclusive `${info['end_exclusive']}`. This is not a flash sector image.
- SHA-256: `{info['image_sha256']}`.
- Plan: [{plan.name}/plan.json](../{plan.name}/plan.json).
- [CPU/NOR proof](model-proof.json), [qualification](qualification.json),
  [existing wear-reader transcript](reader-transcript.txt).
- Allowed future erases: B3:D then B3:C only. Full 4096-byte verification after
  each commit; no repeated initialization or blind partial-state retry.
- Planned counts: C 77→78, D 46→47, F remains 30. Other 30 counters unchanged;
  prior lifetime remains unknown (`FFFFFFFF`). Nothing has incremented on board.
- B0 backup retained: `{info['B0_backup_sha256']}`.
- D snapshot sequence 1014; C sequence 1015. Both carry the full reservation,
  original legacy configuration body, recovery default S, no enabled banks,
  and b15 generation `8000000F`. F does not apply the legacy console byte.

The first D erase cannot have a prior onboard SNBT reservation: C/D still hold
vendor bytes. Retain a durable host reservation and event log for execution.
D's verified committed snapshot reserves the C erase before it starts. If the
process stops early, reserved counts can exceed completed erases; reconcile
from the log before recovery, without resetting the imported history.

Future operator sequence (not performed): at USB `REC>` use `C1` Enter, then
`L` Enter; send this exact BIN in binary mode; wait for autorun and four `Bn OK`
lines. At `RAM JINIT ? V W I Q>` use `W` or `V` for read-only review. A separately
authorized initialization would use `I` Enter, then `INIT C/D` Enter. After both
verified commits, `V`, `W`, then `Q` return to F `REC>`. Do not use ordinary
CONFIG `I` for these nonblank vendor sectors. Do not load an S19 as raw BIN.

Current F fixes journals at C/D (`C000–DFFF`). D/E would require a coordinated
new F image, readers/writers, protections and sector map; this prepared tool
does not relocate the journal. MON A/B and every other sector stay outside it.

Qualification includes the actual raw F loader on 65C816 emulation and 65C02,
all non-C/D preservation checks at each observed NOR mutation, tested partial
states refusing replay, failure injection, existing CONFIG W full-CRC admission,
an unaccelerated complete 65C816 preflight, and an independent identical build.
It is not board, electrical power-cut, or ACIA hardware qualification.
'''
    (out/'receipt.md').write_text(receipt,encoding='utf-8')
    print('PASS prepared package',out,report['checks'],'groups/checks; STOP before hardware',flush=True)


if __name__=='__main__':main()
