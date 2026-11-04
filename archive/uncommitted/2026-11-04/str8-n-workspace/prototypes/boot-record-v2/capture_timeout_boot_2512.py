"""Separate read-only full software-startup capture after completed b06 install.

The frozen deployment adapter/admission are reused unchanged. This helper sends
J3 with CRLF and safe CRLF during the input drain, then sends no selection key.
It never loads RAM, executes G, writes flash/settings, or requests physical RESET.
"""
import argparse
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / 'tools')]
import board_native_2512 as board


def completion(build, plan, run, marker):
    state = board.r.read(Path(run) / 'state.json')
    r = board.r
    r.require(state.get('passed') is True and state.get('phase') == 'completed'
              and state.get('transaction_device_verified') is True
              and state.get('all_four_banks_verified') is True
              and state.get('RAM_restored') is True and state.get('full_RAM_rereads') == 3
              and state.get('final_software_boot_RAM_reread') is True
              and state.get('final_console_mode') == 'BOTH'
              and not state.get('application_RAM_restore_pending') and not state.get('physical_reset_pending'),
              'The admitted b06 deployment must be completely closed first')
    info = r.read(Path(plan) / 'plan.json')
    r.require(state['plan_sha256'] == r.sha((Path(plan) / 'plan.json').read_bytes())
              and marker.get('installer_plan_sha256') == state['plan_sha256']
              and marker.get('installer_run') == str(Path(run).resolve())
              and marker.get('board') == board.BOARD and marker.get('firmware') == '2.0proto b06'
              and marker.get('monitor_generation') == 0x80000006
              and marker.get('current_firmware_profile') == 'experimental-bench-core'
              and marker.get('current_firmware_sha256') == r.sha((Path(build) / 'firmware.bin').read_bytes())
              and marker.get('current_physical_bank_sha256') == dict(zip(('B0', 'B1', 'B2', 'B3'), info['expected_sha256']))
              and marker.get('application_ram_restored') is True
              and not marker.get('block_snapshot') and not marker.get('installer_worker_active'),
              'Completed b06 marker/run/physical-bank binding differs')
    return state


class StartupReceiver:
    """Allow only the two already-qualified startup transmissions."""
    def __init__(self, link):
        self.link = link
        self.transmitted = []
        self.events = []
    def send(self, data):
        allowed = (b'J3\r\n', b'\r\n')
        index = len(self.transmitted)
        board.r.require(index < len(allowed) and data == allowed[index],
                        'Unexpected transmission during full startup capture')
        self.transmitted.append(data)
        self.events.append(dict(kind='TX', hex=data.hex(), utc=board.now(), monotonic=time.monotonic()))
        return self.link.send(data)
    def until(self, token, seconds=45):
        value = self.link.until(token, seconds)
        self.events.append(dict(kind='RX-boundary', token_hex=token.hex(), utc=board.now(),
                                monotonic=time.monotonic(), bytes=len(value)))
        return value


def capture(link, plan, out):
    """No serial access except through the already opened admitted link."""
    out, plan = Path(out), Path(plan)
    original = (plan / 'capture/application-ram.bin').read_bytes()
    board.r.require(len(original) == 0x6300, 'Exact 25344-byte original RAM escrow required')
    before = link.dump(0x7d01, 0x7d02)
    board.r.require(before == b'\x02\x03' and link.dump(0x7d30, 0x7d30) == b'\xb0',
                    'Expected 65C02 MON B with ordinary BOTH console')
    receiver = StartupReceiver(link)
    prefix = board.software_startup(receiver, out, 'timeout-default')
    # Deliberately no send/command between CHOICES and the default MON prompt.
    tail = receiver.until(board.MON_PROMPT, 60)
    raw = prefix + tail
    (out / 'software-timeout-boot.txt').write_bytes(raw)
    board.r.require(receiver.transmitted == [b'J3\r\n', b'\r\n'], 'Startup TX sequence differs')
    banner = b'STR8-N 2.0proto b06 B3 65C02'
    tokens = (b'Consuming input\r\n', board.CHOICES, b'3 2 1 0\r\n', banner)
    positions = [raw.find(token) for token in tokens]
    board.r.require(all(pos >= 0 for pos in positions) and positions == sorted(positions)
                    and len(set(positions)) == len(positions) and raw.endswith(board.MON_PROMPT),
                    'Complete ordered software startup/countdown/default boot missing')
    board.r.require(tail.count(b'3 2 1 0\r\n') == 1 and tail.count(banner) == 1,
                    'Expected one complete countdown and one default boot banner')
    after = link.dump(0x7d01, 0x7d02)
    board.r.require(after == b'\x02\x03' and link.dump(0x7d30, 0x7d30) == b'\xb0',
                    'Software default boot changed CPU, BOTH mode or saved MON B')
    board.r.require(board.workflow.read_range(link, 0x200, 0x64ff) == original,
                    'Full original application RAM differs after software default boot')
    events = receiver.events
    return dict(passed=True, board=board.BOARD, usb_serial=board.USB,
                software_J3_CRLF_timeout_default_B_verified=True,
                Consuming_input_and_complete_3_2_1_0_observed=True,
                no_selection_transmitted=True, allowed_startup_TX_hex=[b.hex() for b in receiver.transmitted],
                CPU='65C02', final_console_mode='BOTH', active_monitor='B',
                original_application_RAM_bytes=len(original), original_application_RAM_sha256=board.r.sha(original),
                full_RAM_readbacks_after_this_boot=1, flash_written=False, RAM_loaded=False,
                application_RAM_borrowed=False, physical_RESET_requested=False,
                software_boot_stream_sha256=board.r.sha(raw), startup_events=events,
                host_observed_seconds=dict(J3_to_Consuming_input=events[1]['monotonic']-events[0]['monotonic'],
                    Consuming_input_to_choices=events[3]['monotonic']-events[1]['monotonic'],
                    choices_to_default_prompt=events[4]['monotonic']-events[3]['monotonic']),
                timing_scope='Host RX boundaries include CPU/transport/scheduling overhead; no oscillator or ACIA electrical qualification',
                physical_boot_capture=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'plan', 'run', 'authorization', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--coordination', type=Path, default=board.DEFAULT_COORDINATION)
    p.add_argument('--marker', type=Path, default=ROOT / 'output/qualification/device-operations/2512.json')
    args = p.parse_args()
    for name in ('build', 'plan', 'run', 'authorization', 'out', 'coordination', 'marker'):
        setattr(args, name, getattr(args, name).resolve())
    board.admission(args.build, args.plan, args.run, board.r.read(args.authorization))
    marker = board.r.read(args.marker)
    completion(args.build, args.plan, args.run, marker)
    board.r.require(not args.out.exists(), 'Use a fresh standalone evidence directory')
    args.out.mkdir(parents=True)
    (args.out / '.gitignore').write_text('*\n')
    state_sha = board.r.sha((args.run / 'state.json').read_bytes())
    marker_sha = board.r.sha(args.marker.read_bytes())
    # Redirect only new serial/synchronization evidence; admission still binds
    # the completed install run above. pending=False never mutates its marker.
    live_args = Namespace(**vars(args))
    live_args.run = args.out
    live_args.stage = 'software-timeout-boot'
    live_args.campaign_receipt = None
    with board.live_link(live_args, pending=False) as (link, locked_marker):
        completion(args.build, args.plan, args.run, locked_marker)
        report = capture(link, args.plan, args.out)
    board.r.require(board.r.sha((args.run / 'state.json').read_bytes()) == state_sha
                    and board.r.sha(args.marker.read_bytes()) == marker_sha, 'Completion state/marker changed during read-only capture')
    evidence = [p for p in sorted(args.out.iterdir()) if p.is_file() and p.name != '.gitignore']
    report.update(completed_utc=board.now(), serial_released=True, completed_state_unchanged=True,
                  completed_state_sha256=state_sha, marker_unchanged=True, marker_sha256=marker_sha,
                  plan_sha256=board.r.sha((args.plan / 'plan.json').read_bytes()),
                  helper_sha256=board.r.sha(Path(__file__).read_bytes()),
                  admitted_adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),
                  files={p.name: dict(bytes=p.stat().st_size, sha256=board.r.sha(p.read_bytes())) for p in evidence})
    board.save(args.out / 'software-timeout-boot.json', report)
    print('PASS full software timeout startup and original RAM; serial released', args.out, flush=True)


if __name__ == '__main__':
    main()
