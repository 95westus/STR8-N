"""Archive queued USB output and establish the B3 monitor before RTC reads."""
import time

def drain(link, quiet_seconds=1.0, timeout_seconds=10.0):
    deadline=time.monotonic()+timeout_seconds
    quiet_start=time.monotonic()
    archived=bytearray(link.pending)
    link.pending.clear()  # These bytes have already been recorded by Link.read.
    while time.monotonic()<deadline:
        data=link.read(max(1,link.serial.in_waiting))
        if data:
            archived.extend(data);quiet_start=time.monotonic()
        elif time.monotonic()-quiet_start>=quiet_seconds:
            return bytes(archived)
    raise TimeoutError('USB output did not settle; refuse RTC acquisition')

def establish_b3(link):
    drained=drain(link)
    initial=link.command('',b'> ')
    if any(p in initial for p in (b'CLOCK>',b'BM>',b'EDU>',b'SRAM>',b'WORK>')):
        link.command('Q',b'> ')
    drain(link)
    reply=link.command('B3',b'\r\nB3> ')
    assert reply.endswith(b'\r\nB3> '), 'B3 prompt required before RTC acquisition'
    drain(link)
    # Echoed command plus a new prompt prevents a queued old prompt satisfying sync.
    reply=link.command('',b'\r\nB3> ')
    assert reply.endswith(b'\r\nB3> '), 'Fresh B3 prompt required'
    return dict(passed=True,drained_bytes=len(drained),prompt='B3>',reset=False)
