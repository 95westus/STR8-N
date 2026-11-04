"""Package both offline RAM BINs, reproduce them, and verify wear limits."""
import argparse,json,shutil,copy
from pathlib import Path
from datetime import datetime,timezone
import prepare_mon_install_2609 as p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plans','proof','rebuild','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();plans=args.plans.resolve();out=args.out.resolve();rebuild=args.rebuild.resolve()
    assert not out.exists() and not rebuild.exists()
    proof=p.base.r.read(args.proof)
    assert proof['passed'] and not proof['hardware'] and not proof['flashed']
    assert proof['test_source_sha256']==p.base.digest(p.HERE/'test_mon_install_2609.py')
    current,bare,hist,oldhist,existing,mon,inputs=p.provenance(p.SESSION)
    additional=[];infos={}
    from test_mon_install_2609 import Model,REC
    for mode in ('mon-only','cd-mon'):
        partial=Model(plans/mode,fault='erase-B');row=partial.install()
        assert p.base.wire.slot_valid(bytes(partial.h.m.banks[3][0x2000:0x3000]),0xa0),'A lost after B failure'
        partial.h.c.pc=0xf004;partial.h.m.rx.clear();n=len(partial.h.m.tx)
        partial.h.run(lambda:len(partial.h.m.tx)>n and bytes(partial.h.m.tx).endswith(REC))
        additional.append(dict(row,case='B-erase-failure-keeps-committed-A-and-restarts-to-REC',A_valid=True))
        print('PASS',mode,'B failure preserves committed A; F resets to REC',flush=True)
    timeout=Model(plans/'mon-only',fault='timeout');row=timeout.install()
    assert not timeout.erases and max(p.base.snbt_records(timeout.h.m.banks))[0]==1015
    additional.append(dict(row,case='reservation-program-timeout-stops-before-MON-erase',old_journal_retained=True))
    print('PASS reservation timeout stops before any MON erase',flush=True)
    for mode,source,history in (('mon-only',current,hist),('cd-mon',bare,oldhist)):
        info=p.verify(plans/mode);infos[mode]=info
        assert proof['plans'][mode]==p.base.digest(plans/mode/'plan.json') and proof['BIN_sha256'][mode]==info['BIN_sha256']
        rebuilt=p.build(rebuild/mode,mode,source,history,existing,mon,inputs)
        assert rebuilt['BIN_sha256']==info['BIN_sha256'] and rebuilt['expected_sha256']==info['expected_sha256']
        assert (plans/mode/'payload'/info['BIN']).read_bytes()==(rebuild/mode/'payload'/info['BIN']).read_bytes()
        additional.append(dict(passed=True,case='independent-byte-identical-rebuild',mode=mode))
        for index in ([26,27] if mode=='mon-only' else [26,27,28,29]):
            bad=copy.deepcopy(history);bad['counts'][index]=0xffffff
            try:p.derive(source,bad,mode,existing,mon)
            except ValueError:pass
            else:raise AssertionError('Exhausted count accepted')
        bad=copy.deepcopy(history);bad['sequence']=0xffffffff
        try:p.derive(source,bad,mode,existing,mon)
        except ValueError:pass
        else:raise AssertionError('Exhausted sequence accepted')
        additional.append(dict(passed=True,case='host-refuses-exhausted-counts-and-sequence',mode=mode))
        print('PASS',mode,'independent identical rebuild + count/sequence exhaustion refusal',flush=True)
    assert infos['mon-only']['counts_after']==infos['cd-mon']['counts_after']
    assert infos['mon-only']['expected_sha256']==infos['cd-mon']['expected_sha256']
    out.mkdir(parents=True)
    shutil.copy2(args.proof,out/'model-proof.json')
    for mode,info in infos.items():shutil.copy2(plans/mode/'payload'/info['BIN'],out/info['BIN'])
    report=dict(passed=True,hardware=False,board_access=False,serial_access=False,flashed=False,
        checks=proof['checks']+len(additional),model_checks=proof['checks'],additional_checks=additional,
        prepared_utc=datetime.now(timezone.utc).isoformat(),board='2609',
        profiles={mode:{k:info[k] for k in ('starting_state','BIN','bytes','BIN_sha256','load_address','end_exclusive',
                    'erase_order','counts_before','counts_after','sequence_before','sequence_after','confirmation','expected_sha256')} for mode,info in infos.items()},
        input_plans={mode:dict(path=str(plans/mode/'plan.json'),sha256=p.base.digest(plans/mode/'plan.json')) for mode in infos},
        proof_sha256=p.base.digest(args.proof),B0_backup_sha256=p.base.WDC_SHA,F_sha256=p.base.F_SHA,
        owner_wear_history_unchanged=True,board_state_unchanged=True,ACIA_board_tested=False,
        source_sha256={path.name:p.base.digest(path) for path in (Path(__file__),p.HERE/'prepare_mon_install_2609.py',p.HERE/'ram-mon-install-2609.asm',p.HERE/'test_mon_install_2609.py')},
        limits=['CPU/NOR and F USB-loader simulation only; no board loaded/flashed in this step',
                'Combined BIN is bound to archived 2609 F-only preimages and will refuse current F+C/D',
                'Interrupted states refuse blind replay; no automatic hardware power-loss recovery claim',
                'Durable host reservation/attempt log required for any future execution; first combined D erase has no earlier onboard journal'])
    p.save(out/'qualification.json',report)
    receipt=f'''# 2609 RAM MON installers — prepared and tested; no flashing

**PASS: {report['checks']} offline groups/checks. No board port opened, RAM
program uploaded, flash written, or authoritative wear history changed.**

| BIN | Required starting state | Planned erases | Bytes |
|---|---|---|---:|
| [2609-MON-AB-RAM.bin](2609-MON-AB-RAM.bin) | Current, hardware-verified F+C/D | A then B; no C/D erase | {infos['mon-only']['bytes']} |
| [2609-CD-MON-AB-RAM.bin](2609-CD-MON-AB-RAM.bin) | Archived 2609 F-only checkpoint; C/D still vendor bytes | D, C, A, B | {infos['cd-mon']['bytes']} |

Both are RAM applications loaded/executed at `$0200` through F raw `L`, not
flash-sector images. They embed only the required journal records and exact
qualified b15 MON A/B components. F and the opaque-image sectors are unchanged.
Both produce identical final flash banks, configuration and counts. B0 backup
SHA-256 remains `{p.base.WDC_SHA}`.

The MON-only route preserves current C=78, D=47 and F=30. Before A erase it
appends a committed full-CRC reservation at C100: sequence 1016, A 49→50. Before
B erase it appends C200: sequence 1017, B 52→53. Existing C000/D000 snapshots
remain byte-identical. Other 30 counts remain unchanged. Both new MON slots
are verified fully before and after their commit byte at offset 31 is written.

The combined route starts from F-only counts C=77/D=46/F=30. It initializes D
and C with the preserved history plus the two reserved journal erases, then
performs the same A/B reservations and installs. It is **not for running on
2609's current F+C/D state**; its exact preimage guard refuses that state. These
are 2609-bound payloads, not generic factory-board images with copied counts.

After either route the latest journal is sequence 1017, recovery default S,
no enabled opaque banks, generation 8000000F, original legacy configuration
body and unknown-lifetime mask FFFFFFFF retained. Settings and image selection
remain separate later operations. No automatic MON launch is configured.

## Operator procedure for a future authorized run

1. Check the selected BIN hash and matching source plan; archive fresh source
   reads and a durable wear reservation/attempt log. Use USB; ACIA remains
   unqualified. The first combined D erase has no prior onboard SNBT journal.
2. At `REC>` type `C1` Enter, then `L` Enter. At `SEND BIN`, transmit the exact
   BIN as binary without text conversion or extra bytes. About three seconds
   of idle after the last byte runs `$0200`; loading does not erase flash.
3. Wait for the RAM/ABI/four-bank checks and `B0 OK` through `B3 OK`.
   The prompt is `RAM MINSTALL ? V W I Q> `. `W` shows imported/planned counts;
   `V` verifies the complete source state without changing flash.
4. `I` Enter requests confirmation. MON-only requires **`INSTALL MON`** Enter;
   combined requires **`INSTALL CD MON`** Enter. Wrong input or Ctrl-C refuses.
   The tool rechecks its entire RAM image, b15 RAM ABI and all four banks before
   the first action. Progress names each address, erase, body check and commit.
5. After `ALL COMPONENTS VERIFIED`, `V` Enter verifies all four complete final
   banks; `Q` Enter restarts F to `REC>`. Stop before changing configuration or
   launching applications unless separately directed. A/B launch/return was
   checked in both CPU models, not performed on the board by this preparation.

Preflight/programming failure halts in RAM. Retain the host log and inspect
the changed preimages before constructing recovery; never replay the old plan
or reset the owner counts. No install command is sent by this preparation.

| Payload | SHA-256 |
|---|---|
| MON-only | `{infos['mon-only']['BIN_sha256']}` |
| C/D+MON | `{infos['cd-mon']['BIN_sha256']}` |

[Qualification](qualification.json) · [CPU/NOR proof](model-proof.json).
The main operator guide is [STR8N_B15_FROM_F_GUIDE.md](../../../../docs/STR8N_B15_FROM_F_GUIDE.md).
'''
    (out/'receipt.md').write_text(receipt,encoding='utf-8')
    print('PASS',report['checks'],'offline groups/checks; both RAM BINs ready; STOP before hardware',flush=True)


if __name__=='__main__':main()
