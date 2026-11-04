"""Complete only the approved SRAM/owner restoration after the ACK parser fix."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mon_program_2609_trial as trial
import mon_program_2609_preflight as base
import mon_features_2609_ram as t

CASE = ROOT / 'output/qualification/2609-PROGRAM-positive-trial-20261030-r2'
SCOPE = ROOT / 'output/qualification/2609-PROGRAM-positive-scope-20261030-r2'
OUT = CASE / 'restoration-closeout'


def run():
    p = json.loads((SCOPE / 'plan.json').read_text())
    auth = json.loads((SCOPE / 'approval.json').read_text())
    previous = json.loads((CASE / 'report.json').read_text())
    assert previous['SRAM_restore_pending'] and previous['final_context'] == 'PB> '
    assert len(previous['stores']) == 4
    assert 'CRC-repaired-restore' in previous['checks']
    assert t.sha((SCOPE / 'plan.json').read_bytes()) == auth['plan_sha256']
    assert auth['approved'] and auth['scope_unchanged']
    cap = Path(p['capture'])
    ram, zp = (cap / 'owner-ram.bin').read_bytes(), (cap / 'owner-zp.bin').read_bytes()
    snapshot = (cap / 'SRAM-pass1-131072.bin').read_bytes()
    assert t.sha(snapshot) == p['SRAM_sha256']
    reader = (base.KIT / 'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert t.sha(reader) == t.live.READBACK_SHA256
    OUT.mkdir(exist_ok=False)
    result = dict(board='2609', passed=False, started_utc=base.utc(),
                  SRAM_restore_pending=True, owner_RAM_restored=False,
                  flash_writes=0, journal_writes=0, RTC_SET=0, trim_writes=0,
                  PF_ACK=0, power_cuts=0, source_trial=str(CASE / 'report.json'),
                  host_correction='Accept exact O+CRC reply; do not parse Ehh inside CRC')
    def save():
        t.save(OUT / 'report.json', result)
    def mark(**fields):
        marker = json.loads(t.MARK.read_text())
        marker.update(fields)
        t.save(t.MARK, marker)
    save()
    with t.serial_lease('2609-PROGRAM-approved-restoration', timeout=30):
        with (OUT / 'serial.jsonl').open('x') as log:
            session = trial.Session(OUT, log, reader, p, SCOPE)
            mark(program_restore_worker_active=True, block_snapshot=True,
                 application_RAM_restore_pending=True, PROGRAM_SRAM_restore_pending=True)
            try:
                session.link.send(b'R000000\r')
                session.until((trial.BENCH,))
                session.bench()
                for text in p['allowed_64_byte_writes']:
                    address = int(text, 16)
                    body = (SCOPE / f'original-{address:04X}.bin').read_bytes()
                    assert body == snapshot[address:address + 64]
                    session.block(address, body)
                result['allowed_blocks_restored_verified'] = 20
                save()
                print('PASS all 20 original PROGRAM blocks restored and device-verified', flush=True)
                session.workbench()
                assert session.full_sram('SRAM-restored') == snapshot
                result.update(SRAM_restore_pending=False, all_131072_SRAM_bytes_restored=True,
                              SRAM_sha256=t.sha(snapshot))
                mark(PROGRAM_SRAM_restore_pending=False)
                save()
                session.recovery()
                session.service()
                for bank in range(4):
                    body = session.client.flash(bank)
                    assert t.sha(body) == p['source_bank_sha256'][bank]
                    (OUT / f'final-B{bank}.bin').write_bytes(body)
                result['all_flash_banks_unchanged'] = True
                result.update(session.client.restore_owner(ram, zp))
                session.context = t.REC
                result.update(owner_RAM_restored=True, owner_RAM_ZP_verified=True,
                              passed=True, final_context='REC>', COM8_released=True,
                              finished_utc=base.utc())
                save()
                final = dict(previous)
                final.update(result)
                final.update(passed=True, phase='PROGRAM_816E_PASSED', source_trial=str(CASE / 'report.json'),
                             restoration_report=str(OUT / 'report.json'),
                             source_trial_sha256=t.sha((CASE / 'report.json').read_bytes()),
                             restoration_report_sha256=t.sha((OUT / 'report.json').read_bytes()),
                             host_only_failures=['bench Q terminator before any SRAM write',
                                                 'ACK parser during restoration after functional checks passed'],
                             additional_firmware_builds=0, SRAM_scope_unchanged=True,
                             source_bank_sha256=p['source_bank_sha256'])
                final['checks'] = previous['checks'] + ['full-SRAM-restore-compare', 'all-banks-unchanged', 'owner-RAM-ZP-restored']
                t.save(CASE / 'final-receipt.json', final)
                mark(program_trial_worker_active=False, program_restore_worker_active=False,
                     application_RAM_restore_pending=False, application_ram_restored=True,
                     PROGRAM_SRAM_restore_pending=False, block_snapshot=False, final_prompt='REC>',
                     last_PROGRAM_positive_acceptance=str(CASE / 'final-receipt.json'))
                print(json.dumps(final, indent=2), flush=True)
            except BaseException as error:
                result.update(error=repr(error), finished_utc=base.utc())
                save()
                raise
            finally:
                session.link.close()
                mark(program_restore_worker_active=False,
                     application_RAM_restore_pending=not result['owner_RAM_restored'],
                     application_ram_restored=result['owner_RAM_restored'],
                     PROGRAM_SRAM_restore_pending=result['SRAM_restore_pending'],
                     block_snapshot=not (result['owner_RAM_restored'] and not result['SRAM_restore_pending']))


if __name__ == '__main__':
    run()
