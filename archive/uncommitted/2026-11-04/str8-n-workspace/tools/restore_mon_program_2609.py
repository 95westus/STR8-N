"""Preserving recovery from the host-only PROGRAM bench prompt error."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mon_features_2609_ram as t
import mon_program_2609_preflight as base

FAILED = ROOT / 'output/qualification/2609-PROGRAM-positive-trial-20261030-r1'
SCOPE = ROOT / 'output/qualification/2609-PROGRAM-positive-scope-20261030-r1'
OUT = FAILED / 'preserving-recovery'


def run():
    p = json.loads((SCOPE / 'plan.json').read_text())
    failed = json.loads((FAILED / 'report.json').read_text())
    assert not failed['SRAM_restore_pending'] and not failed['checks']
    assert t.sha((FAILED / 'SRAM-fresh-before-131072.bin').read_bytes()) == p['SRAM_sha256']
    cap = Path(p['capture'])
    ram, zp = (cap / 'owner-ram.bin').read_bytes(), (cap / 'owner-zp.bin').read_bytes()
    reader = (base.KIT / 'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert t.sha(reader) == t.live.READBACK_SHA256
    OUT.mkdir(exist_ok=False)
    result = dict(passed=False, flash_writes=0, SRAM_data_writes=0, reset=False)
    with t.serial_lease('2609-PROGRAM-preserving-recovery', timeout=30):
        with (OUT / 'serial.jsonl').open('x') as log:
            link = t.transport.RecoveryLink('COM8', log, usb_serial='A10MPQXCA')
            try:
                def prompt():
                    body = bytearray()
                    deadline = time.monotonic() + 15
                    last_rx = time.monotonic()
                    while time.monotonic() < deadline:
                        chunk = link.read(max(1, link.serial.in_waiting))
                        if chunk:
                            body.extend(chunk)
                            last_rx = time.monotonic()
                        if time.monotonic() - last_rx >= .2:
                            for candidate in (t.REC, t.MON, t.WB):
                                if body.endswith(candidate):
                                    return candidate, bytes(body)
                    raise TimeoutError(repr(body[-200:]))
                link.send(b'\r')
                context, raw = prompt()
                (OUT / 'initial-prompt.txt').write_bytes(raw)
                if context == t.WB:
                    link.send(b'Q\r')
                    context, raw = prompt()
                if context == t.MON:
                    link.send(b'Q\r')
                    context, raw = prompt()
                assert context == t.REC
                t.recovery.PROMPT = b'RAM SERVICE BASE1> '
                client = t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(link), timeout=60)
                client.load(reader, t.live.READBACK_SHA256, REC_observed=True)
                for bank in range(4):
                    body = client.flash(bank)
                    assert t.sha(body) == p['source_bank_sha256'][bank]
                    (OUT / f'unchanged-B{bank}.bin').write_bytes(body)
                result.update(client.restore_owner(ram, zp))
                result.update(passed=True, all_flash_banks_unchanged=True,
                              full_SRAM_read_matches_approved=True, COM8_released=True,
                              owner_RAM_ZP_restored_verified=True, final_context='REC>')
                marker = json.loads(t.MARK.read_text())
                marker.update(program_trial_worker_active=False, application_RAM_restore_pending=False,
                              application_ram_restored=True, PROGRAM_SRAM_restore_pending=False,
                              block_snapshot=False, final_prompt='REC>',
                              last_PROGRAM_preserving_recovery=str(OUT / 'report.json'))
                t.save(t.MARK, marker)
                t.save(OUT / 'report.json', result)
                print(json.dumps(result, indent=2), flush=True)
            finally:
                link.close()


if __name__ == '__main__':
    run()
