"""Measure installed RTC against NTP; write time only with explicit --sync.

Save serial evidence, pre-SET outage data, requested UTC, operation brackets,
and initial offset intervals for later read-only drift comparisons. No flash,
alarm, trim, SRAM or EEPROM writes. Host system time is never changed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import socket
import struct
import time

from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load
from serial.tools.list_ports import comports

ROOT = Path(__file__).resolve().parents[1]
NTP_EPOCH = 2208988800


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def ntp_sample_once(server):
    address = socket.gethostbyname(server)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)
        sock.connect((address, 123))
        request = bytearray(48)
        request[0] = 0x23  # Version 4 client mode.
        mono1 = time.monotonic()
        t1 = time.time()
        full = t1 + NTP_EPOCH
        seconds = int(full)
        assert seconds < 2**32, 'NTP era rollover needs separate handling'
        struct.pack_into('!II', request, 40, seconds, int((full-seconds)*2**32))
        sock.send(request)
        packet = sock.recv(512)
        t4 = time.time()
        mono4 = time.monotonic()
    assert len(packet) >= 48 and packet[0] & 7 == 4
    assert packet[0] >> 6 != 3 and 1 <= packet[1] <= 15, 'NTP source is not synchronized'
    assert packet[24:32] == request[40:48], 'Unmatched NTP response'
    assert abs((t4-t1)-(mono4-mono1)) < .05, 'Host clock changed during NTP sample'
    def stamp(offset):
        whole, fraction = struct.unpack_from('!II', packet, offset)
        return whole-NTP_EPOCH + fraction/2**32
    t2, t3 = stamp(32), stamp(40)
    assert t2 and t3 and t3 >= t2
    offset = ((t2-t1)+(t3-t4))/2
    delay = (t4-t1)-(t3-t2)
    assert -.005 <= delay < 1, 'Unusable NTP network delay'
    dispersion = struct.unpack_from('!I', packet, 8)[0]/65536
    root_delay = struct.unpack_from('!i', packet, 4)[0]/65536
    uncertainty = max(0, delay)/2 + max(0, root_delay)/2 + dispersion + .005
    assert uncertainty < .25, 'NTP reference uncertainty too large'
    return dict(server=server, address=address, stratum=packet[1],
        host_send_unix=t1, server_receive_unix=t2, server_send_unix=t3,
        host_receive_unix=t4, receive_monotonic=mono4, server_minus_host_s=offset,
        round_trip_delay_s=delay, root_delay_s=root_delay, root_dispersion_s=dispersion,
        estimated_reference_uncertainty_s=uncertainty, packet_hex=packet.hex(),
        reference_utc_at_receive=iso(t4+offset))


def ntp_sample(server):
    # UDP replies can be lost or throttled; keep retries bounded and spaced.
    for attempt in range(3):
        try:
            sample=ntp_sample_once(server)
            sample['attempt_count']=attempt+1
            return sample
        except TimeoutError:
            if attempt==2:raise
            time.sleep(4)


class Reference:
    def __init__(self, samples):
        self.best = min(samples, key=lambda s:s['round_trip_delay_s'])
        offsets = [s['server_minus_host_s'] for s in samples]
        self.uncertainty = max(s['estimated_reference_uncertainty_s'] for s in samples) + max(offsets)-min(offsets)
        assert self.uncertainty < .5, 'Inconsistent NTP samples'

    def now(self):
        b = self.best
        return b['host_receive_unix'] + b['server_minus_host_s'] + time.monotonic()-b['receive_monotonic']


def decoded(data):
    c = data[2:10]
    return datetime(c[0]+256*c[1], c[2], c[3], c[5], c[6], c[7], tzinfo=timezone.utc).timestamp()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', required=True, choices=('2205','2609'))
    parser.add_argument('--port', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--server', default='time.nist.gov')
    parser.add_argument('--sync', action='store_true', help='Explicitly SET RTC to referenced UTC once')
    parser.add_argument('--set-adjust-seconds', type=int, choices=(-1,0,1), default=0,
        help='Explicit whole-second alignment correction, with --sync only')
    parser.add_argument('--baseline', type=Path, help='Compare read-only against an earlier report.json')
    args = parser.parse_args()
    assert not (args.sync and args.baseline)
    assert args.sync or args.set_adjust_seconds==0
    assert next(p for p in comports() if p.device.upper()==args.port.upper()).serial_number == SERIALS[args.board]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(board=args.board, port=args.port, mode='UTC sync' if args.sync else 'read-only drift measurement',
        flash_written=False, chip_memory_accessed=False, trim_changed=False, readings=[], reference_samples=[])
    report_path = args.out / 'report.json'
    def save():
        report_path.write_text(json.dumps(report, indent=2)+'\n')
    save()
    # Fresh external reference, anchored to monotonic time instead of stale PC synchronization.
    for index in range(3):
        if index:
            time.sleep(4)
        report['reference_samples'].append(ntp_sample(args.server))
        save()
    reference = Reference(report['reference_samples'])
    report['reference_uncertainty_s'] = reference.uncertainty
    with (args.out / 'serial.jsonl').open('x') as log:
        link = Link(args.port, log)
        try:
            end = time.monotonic()+.3
            while time.monotonic()<end:
                link.read(max(1,link.serial.in_waiting))
            link.command('',b'> ')
            link.command('B3')
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x03\x00\x65\xFF\x64'
            assert link.dump(0x7E60,0x7E63)==b'RA\x01\x0d'
            assert link.dump(0x6500,0x6503)==b'RG\x01\x04'
            client = ROOT / 'BUILD/v2-rtc-kernel/utc-client/rtc-sample-client.s19'
            report['client_sha256'] = load(link,client)
            expected = json.loads((client.parent/'sample-build.json').read_text())['sha256']
            assert report['client_sha256']==expected

            def capture(label,entry=0x2000):
                first = reference.now()
                host_first = time.time()
                link.send(f'G {entry:04X}\r'.encode())
                output = link.until(b'@')
                last = reference.now()
                output += link.until(b'\r\nB3> ')
                (args.out/f'{label}.txt').write_bytes(output)
                # The monitor's banner is another clock client after HOLD. Read
                # our saved result, whose acquisition is bounded by the marker.
                data = link.dump(0x2440,0x247F)
                (args.out/f'{label}.bin').write_bytes(data)
                item = dict(label=label, status=data[0], flags=data[1], calendar=list(data[2:10]),
                    raw=list(data[11:20]), outage=list(data[20:28]), evidence_valid=data[28],
                    captured_outage=list(data[48:56]), reference_start_utc=iso(first),
                    reference_end_utc=iso(last), reference_start_unix=first, reference_end_unix=last,
                    host_start_utc=iso(host_first), bracket_seconds=last-first)
                assert data[56]==data[58] and (data[57]^data[59]) & data[56]==0
                if data[1]&4:
                    rtc = decoded(data)
                    item.update(rtc_utc=iso(rtc), rtc_unix=rtc)
                    # The RTC read contains one-second quantization and happened inside this bracket.
                    item['rtc_minus_reference_interval_s'] = [rtc-last-reference.uncertainty,
                        rtc+1-first+reference.uncertainty]
                report['readings'].append(item)
                save()
                return item

            before = capture('before')
            assert before['status']==0, 'READ unusable; inspect raw evidence before any SET'
            if args.sync:
                # Staging is application RAM; SET copies it inside the protected allocation.
                target = math.ceil(reference.now()+1.5)
                utc = datetime.fromtimestamp(target+args.set_adjust_seconds,timezone.utc)
                fields = [utc.year&255,utc.year>>8,utc.month,utc.day,utc.isoweekday(),utc.hour,utc.minute,utc.second]
                report['requested_rtc_utc'] = iso(target+args.set_adjust_seconds)
                report['scheduled_set_reference_utc'] = iso(target)
                report['set_alignment_correction_seconds'] = args.set_adjust_seconds
                report['clock_set_attempted'] = False
                save()  # Preserve original outage/reference before SET can clear hardware evidence.
                link.command('M 2400 '+' '.join(f'{v:02X}' for v in fields))
                assert link.dump(0x2400,0x2407)==bytes(fields)
                assert target-reference.now()>.05, 'Missed sync target; no clock write issued'
                while reference.now()<target:
                    time.sleep(min(.02,max(.001,target-reference.now())))
                report['clock_set_attempted'] = True
                save()
                result = capture('set',0x2003)
                assert result['status']==0, 'SET failed; do not retry automatically'
                report['set_completed_reference_window_utc'] = [result['reference_start_utc'],result['reference_end_utc']]
                if before['evidence_valid']:
                    assert result['evidence_valid'] and result['captured_outage']==before['captured_outage']
                report['pre_set_outage_archived'] = True
                save()
            samples = []
            for attempt in range(8):
                # Vary sampling phase; fixed delay plus console turnaround can alias one-second ticks.
                time.sleep((.35,.75,.15,.55)[attempt%4])
                item = capture(f'read-{attempt+1}')
                if item['status']==0:
                    samples.append(item)
                    if len(samples)>=4 and samples[-1]['rtc_unix']>samples[0]['rtc_unix']:
                        break
                elif item['status']!=4:
                    raise IOError('READ transport failure after SET; inspect before retry')
            else:
                raise IOError('RTC did not become usable and advance')
            low = max(s['rtc_minus_reference_interval_s'][0] for s in samples)
            high = min(s['rtc_minus_reference_interval_s'][1] for s in samples)
            assert low<=high, 'Inconsistent RTC/reference samples'
            report.update(baseline_reference_utc=samples[-1]['reference_end_utc'],
                baseline_reference_unix=samples[-1]['reference_end_unix'],
                rtc_minus_reference_interval_s=[low,high], clock_advanced=True)
            # A fresh final NTP response checks the monotonic reference across the operation.
            verify = ntp_sample(args.server)
            projected = reference.now()
            measured = verify['host_receive_unix']+verify['server_minus_host_s'] + time.monotonic()-verify['receive_monotonic']
            report['final_reference_check'] = verify
            report['final_reference_difference_s'] = measured-projected
            assert abs(measured-projected)<=reference.uncertainty+verify['estimated_reference_uncertainty_s']
            if args.baseline:
                prior = json.loads(args.baseline.read_text())
                assert prior['board']==args.board and prior['passed']
                initial_low,initial_high = prior['rtc_minus_reference_interval_s']
                elapsed = report['baseline_reference_unix']-prior['baseline_reference_unix']
                assert elapsed>0
                change = [low-initial_high,high-initial_low]
                report.update(compared_baseline=str(args.baseline.resolve()),elapsed_seconds=elapsed,
                    drift_seconds_interval=change,
                    drift_ppm_interval=[x/elapsed*1e6 for x in change],
                    drift_seconds_per_day_interval=[x/elapsed*86400 for x in change])
            report['passed'] = True
            save()
            print('PASS',args.board,report.get('requested_rtc_utc','read-only'),
                  'RTC advancing; initial offset interval', [round(low,3),round(high,3)], flush=True)
        finally:
            link.serial.close()


if __name__=='__main__':
    main()
