"""Owner-authorized 2512 memory backup/change/restore/independent verification.

One reversible changed sector at B0:E; F and every original byte retained.
Native flash journals are restored exactly. Two raw flash erase attempts are
recorded separately on the host, not claimed as native journal increments.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import memory_tool as m
from serial_test_coordination import serial_lease, drift_pending


def run(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    m.durable(out/'.gitignore', b'*\n')
    profile = json.loads((m.ROOT/'firmware/memory-agent/profile.example.json').read_text())
    profile.update(board='2512', cpu='65c02', port='COM4', usb_serial='A10MQFLCA')
    m.save(out/'profile.json', profile)
    for name in ('memory_tool.py', 'trial_memory_2512.py'):
        m.durable(out/name, (m.ROOT/'tools'/name).read_bytes())
    agent = m.ROOT/'BUILD/memory-agent-v1'
    m.durable(out/'agent-manifest.json', (agent/'manifest.json').read_bytes())
    report = {'board': '2512', 'passed': False, 'phase': 'prepared',
              'started_utc': datetime.now(timezone.utc).isoformat(),
              'authorization': 'test it on 2512 with a full backup and restore, then verify all the memory matches the original',
              'F_writes': 0, 'raw_flash_erase_attempts': [], 'changes': [],
              'native_erase_history_policy': 'Exact original journals; additional raw attempts retained in this host receipt',
              'cpu_ram_scope': ['0000-00DF', '0200-66FF'],
              'excluded': ['active CPU stack/registers', 'system zero page E0-FF',
                           'monitor/agent workspace 6700-7EFF', 'I/O', 'EEPROM factory/protected 80-FF'],
              'RTC_calendar_writes': 0, 'resets': 0, 'power_cuts': 0}
    def save():
        m.save(out/'report.json', report)
    save()
    initial_marker = m.ROOT/'output/qualification/device-operations/2512.json'
    m.durable(out/'marker-before.json', initial_marker.read_bytes())
    initial_state = json.loads(initial_marker.read_text())
    d = None
    originals = None
    mutation_started = False
    with serial_lease('2512-memory-full-backup-restore', timeout=30):
        m.require(not drift_pending(), 'RTC collection pending; no port opened')
        session = out/'session'
        session.mkdir()
        try:
            report['phase'] = 'fresh-backup'
            save()
            d = m.SerialDevice(profile, agent, session)
            m.backup(d, out/'original', list(m.ORDER))
            _, originals = m.archive(out/'original')
            report['original_sha256'] = {n: m.sha(data) for n, data in originals.items()}
            report['original_bytes'] = {n: len(data) for n, data in originals.items()}
            report['phase'] = 'backup-complete-before-mutation'
            save()
            # Refuse an occupied flash target. Do not infer that WORK/EEPROM
            # bytes are disposable: every test change has a verified preimage.
            flash_offset = 0x6000
            m.require(originals['flash'][flash_offset:flash_offset+4096] == b'\xff'*4096,
                      'B0:E is occupied; no test mutation admitted')
            m.require(originals['spi-mode'] in (b'\0', b'\x40', b'\x80'), 'Unknown SRAM mode')
            tests = []
            flash = bytearray(originals['flash'][flash_offset:flash_offset+4096])
            flash[:64] = bytes((i*37+0x51)&255 for i in range(64))
            tests.append(('flash', flash_offset, bytes(flash)))
            spi_offset = 0x1ff00
            tests.append(('spi-sram', spi_offset,
                          bytes(x^0xa5 for x in originals['spi-sram'][spi_offset:spi_offset+256])))
            mode = b'\x40' if originals['spi-mode'] == b'\x80' else b'\x80'
            tests.append(('spi-mode', 0, mode))
            tests.append(('eeprom', 120, bytes(x^0x5a for x in originals['eeprom'][120:128])))
            zp = bytearray(originals['zero-page'])
            zp[0x40:0x50] = bytes(x^0x3c for x in zp[0x40:0x50])
            tests.append(('zero-page', 0, bytes(zp)))
            tests.append(('cpu-ram', 0xe00,
                          bytes(x^0xc3 for x in originals['cpu-ram'][0xe00:0xf00])))
            report['phase'] = 'reversible-test-changes'
            save()
            mutation_started = True
            for name, offset, data in tests:
                pending = {'region': name, 'offset': offset, 'bytes': len(data), 'sha256': m.sha(data)}
                report['pending_change'] = pending
                if name == 'flash':
                    report['raw_flash_erase_attempts'].append({'phase': 'test-pattern', 'bank': 0, 'sector': 'E'})
                save()
                d.write(name, offset, data)
                m.require(d.read(name, offset, len(data)) == data, 'Test change readback failed: '+name)
                report['changes'].append(pending)
                report['pending_change'] = None
                save()
                print('TEST CHANGE VERIFIED: '+name, flush=True)
            report['phase'] = 'full-restore'
            save()
            changes = m.plan(d, originals)
            m.save(out/'restore-plan.json', {'changes': changes})
            report['raw_flash_erase_attempts'].append({'phase': 'restore-original', 'bank': 0, 'sector': 'E'})
            save()
            m.apply(d, originals, changes, out/'restore-receipt.json')
            # apply verifies storage before final RAM restoration; avoid using
            # the staging buffer again until close has restored owner RAM.
            report['phase'] = 'restore-verified-cleanup'
            save()
        except BaseException as error:
            report['error'] = repr(error)
            save()
            # A known frame boundary admits restoration from the fresh backup.
            # Never send recovery bytes into an ambiguous incomplete request.
            if mutation_started and originals and d and d.wire.synchronized:
                try:
                    changes = m.plan(d, originals)
                    m.apply(d, originals, changes, out/'error-restoration-receipt.json')
                    report['error_cleanup_restored'] = True
                    save()
                except BaseException as cleanup_error:
                    report['error_cleanup_error'] = repr(cleanup_error)
                    save()
            raise
        finally:
            if d:
                d.close()
                report['owner_RAM_cleanup'] = json.loads((session/'ram-state.json').read_text())
                save()
        # New monitor entry, fresh owner capture and newly uploaded service;
        # no reuse of previous receive buffers or saved postimages.
        report['phase'] = 'independent-new-session-verification'
        save()
        verify = out/'independent-verification'
        verify.mkdir()
        v = None
        try:
            v = m.SerialDevice(profile, agent, verify)
            comparisons = {}
            for name in m.ORDER:
                first = m.read_region(v, name, initial=True)
                second = m.read_region(v, name, initial=True)
                m.require(first == second == originals[name], 'Independent original comparison failed: '+name)
                m.durable(verify/(name+'.bin'), first)
                comparisons[name] = {'bytes': len(first), 'sha256': m.sha(first),
                                     'matches_original': True, 'matching_captures': 2}
                print('FINAL ORIGINAL MATCH: '+name+' '+str(len(first))+' bytes', flush=True)
            report['comparisons'] = comparisons
            report['all_requested_memory_matches_original'] = True
            report['verified_bytes'] = sum(i['bytes'] for i in comparisons.values())
            save()
        finally:
            if v:
                v.close()
                report['independent_owner_RAM_cleanup'] = json.loads((verify/'ram-state.json').read_text())
                save()
        state = json.loads(initial_marker.read_text())
        m.require(not state['application_RAM_restore_pending'] and not state['block_snapshot'], 'RAM cleanup pending')
        state['firmware_verification_pending'] = initial_state.get('firmware_verification_pending', False)
        state['current_physical_bank_sha256'] = {f'B{i}': m.sha(originals['flash'][i*32768:(i+1)*32768]) for i in range(4)}
        state['last_memory_full_restore_trial'] = str(out/'report.json')
        state['memory_full_restore_qualified'] = True
        state['memory_tool_raw_erase_evidence'] = str(out/'report.json')
        state['memory_tool_additional_raw_erase_attempts'] = {'B0:E': len(report['raw_flash_erase_attempts'])}
        m.save(initial_marker, state)
        report.update(passed=True, phase='complete', port_released=True,
                      finished_utc=datetime.now(timezone.utc).isoformat())
        save()
    print(json.dumps({'passed': report['passed'], 'verified_bytes': report['verified_bytes'],
                      'report': str(out/'report.json')}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
