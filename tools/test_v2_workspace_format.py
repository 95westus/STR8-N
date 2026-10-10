"""Qualify explicit FORMAT recovery, administrative cuts and counter refusal."""
import binascii
import json

from test_v2_workspace import fresh, install, call, req, OUT, META, k
from test_v2_sram_store import (
    formatted, install as install_store, run_api as store_api,
    request as store_request,
)


def seal(array, address, size=64):
    end = address + size - 4
    array[end:end + 2] = binascii.crc_hqx(
        array[address:end], 0xFFFF).to_bytes(2, 'big')


def selected_session(array):
    packets = [p for p in (0x280, 0x2C0) if array[p + 63] == 0xA5]
    return max(packets, key=lambda p: int.from_bytes(array[p + 4:p + 8], 'little'))


class Cut(Exception):
    pass


def trace(cpu, memory, request):
    addresses = []
    memory.cut = addresses.append
    try:
        assert call(cpu, memory, request)[0] == 0
    finally:
        memory.cut = None
    return addresses


def interrupt(cpu, memory, baseline, request, cut):
    memory.spi.devices[0].data[:] = baseline
    install(cpu, memory)
    cpu.sp = 0xFF
    memory.ram[0x66AF] = 1
    memory.ram[0x66AE] = 1
    writes = [0]

    def stop(address):
        writes[0] += 1
        if writes[0] == cut:
            raise Cut()

    memory.cut = stop
    try:
        call(cpu, memory, request)
    except Cut:
        pass
    else:
        raise AssertionError(('unreached administrative cut', cut))
    finally:
        memory.cut = None
    # Re-enter after the interrupted foreground call, with normal public policy.
    install(cpu, memory)
    cpu.sp = 0xFF
    memory.ram[0x66AF] = 0
    memory.ram[0x66AE] = 1


def main():
    checks = []

    def passed(text):
        checks.append(text)
        print('PASS', text, flush=True)

    cpu, memory = fresh()
    array = memory.spi.devices[0].data
    status, result = call(cpu, memory, req(1, owner=0xBEEF, size=512))
    assert status == 0
    old_handle = result[4:12]
    claim = 0x300 + old_handle[0] * 32
    array[claim + 4] ^= 1
    assert call(cpu, memory, req(3, owner=0xBEEF, handle=old_handle, count=1))[0] == 0x41
    payload = bytes(array[0x800:])
    epoch = int.from_bytes(array[selected_session(array) + 8:selected_session(array) + 12], 'little')
    assert call(cpu, memory, req(6, key=b'FORMAT!!'))[0] == 0
    assert all(array[0x31F + i * 32] == 0 for i in range(4))
    assert bytes(array[0x800:]) == payload
    packet = selected_session(array)
    assert int.from_bytes(array[packet + 8:packet + 12], 'little') == epoch + 1
    assert call(cpu, memory, req(3, owner=0xBEEF, handle=old_handle, count=1))[0] == 0x4B
    assert call(cpu, memory, req(1, owner=0xBEEF, size=512))[0] == 0
    passed('explicit FORMAT clears corrupt committed claims, preserves payload and valid epoch counters, and permits fresh allocation')

    # Exercise FORMAT against existing ownership, saved records and a corrupt
    # claim. Every byte interruption must permit an explicit successful retry.
    cpu, memory = fresh()
    array = memory.spi.devices[0].data
    for owner in range(1, 5):
        assert call(cpu, memory, req(1, owner=owner, size=64))[0] == 0
    install_store(cpu, memory)
    memory.ram[0x2000:0x2020] = bytes(range(32))
    assert store_api(cpu, memory, store_request(1)) == 0
    install(cpu, memory)
    array[0x304] ^= 1
    baseline = bytes(array)
    format_request = req(6, key=b'FORMAT!!')
    format_addresses = trace(cpu, memory, format_request)
    format_cuts = []
    for cut in range(1, len(format_addresses) + 1):
        interrupt(cpu, memory, baseline, format_request, cut)
        assert bytes(array[0x800:]) == baseline[0x800:]
        status, _ = call(cpu, memory, req(0))
        assert status in (0, 0x40), (cut, status)
        assert call(cpu, memory, format_request)[0] == 0, cut
        assert all(array[0x31F + i * 32] == 0 for i in range(4))
        assert all(array[0x7F + i * 64] == 0 for i in range(8))
        assert bytes(array[0x800:]) == baseline[0x800:]
        assert call(cpu, memory, req(1, size=64))[0] == 0, cut
        assert memory.ram[0x66AE] == 1
        format_cuts.append(cut)
    passed(f'all {len(format_cuts)} existing-session FORMAT write cuts preserve data and recover through explicit retry')

    # Upgrade must leave all v1 program records/payload intact at every cut.
    # Once the v2 secondary is published, V repairs its missing primary.
    cpu, memory = formatted(fast=True)
    array = memory.spi.devices[0].data
    program = bytes(range(32))
    memory.ram[0x2000:0x2020] = program
    assert store_api(cpu, memory, store_request(1)) == 0
    install(cpu, memory)
    baseline = bytes(array)
    upgrade_request = req(7, key=b'UPGRADE!')
    upgrade_addresses = trace(cpu, memory, upgrade_request)
    upgrade_cuts = []
    for cut in range(1, len(upgrade_addresses) + 1):
        interrupt(cpu, memory, baseline, upgrade_request, cut)
        assert bytes(array[64:576]) == baseline[64:576]
        assert bytes(array[0x800:]) == baseline[0x800:]
        status, result = call(cpu, memory, req(0))
        assert status == 0 and result[21] == 4, (cut, status)
        assert call(cpu, memory, upgrade_request)[0] == 0, cut
        status, result = call(cpu, memory, req(0))
        assert status == 0 and not result[22]
        if result[23]:
            assert call(cpu, memory, req(8, key=b'REPAIR!!'))[0] == 0
        install_store(cpu, memory)
        memory.ram[0x2000:0x2020] = bytes(32)
        assert store_api(cpu, memory, store_request(2)) == 0
        assert memory.ram[0x2000:0x2020] == program
        install(cpu, memory)
        assert call(cpu, memory, req(1, size=64))[0] == 0
        assert bytes(array[64:576]) == baseline[64:576]
        assert bytes(array[0x800:]) == baseline[0x800:]
        assert memory.ram[0x66AE] == 1
        upgrade_cuts.append(cut)
    passed(f'all {len(upgrade_cuts)} UPGRADE write cuts preserve named images; explicit retry/repair restores both utilities')

    exhaustion = []
    for field, offset, size, operation in (
        ('ticket', 12, 2, req(1, size=64)),
        ('session revision', 4, 4, req(1, size=64)),
        ('epoch', 8, 4, req(1, size=64)),
    ):
        cpu, memory = fresh()
        array = memory.spi.devices[0].data
        packet = selected_session(array)
        array[packet + offset:packet + offset + size] = bytes([0xFF]) * size
        seal(array, packet)
        if field == 'epoch':
            memory.ram[0x66AF] = 0
        before = bytes(array)
        assert call(cpu, memory, operation)[0] == 0x48, field
        assert bytes(array) == before and memory.ram[0x66AE] == 1
        exhaustion.append(field)
    cpu, memory = fresh()
    array = memory.spi.devices[0].data
    for address in (0, 0x240):
        array[address + 8:address + 12] = bytes([0xFF]) * 4
        seal(array, address)
    before = bytes(array)
    assert call(cpu, memory, req(5, units=3, key=b'RESIZE!!'))[0] == 0x48
    assert bytes(array) == before
    exhaustion.append('layout revision')
    passed('epoch, session revision, ticket and layout revision exhaustion refuse wrap without changing retained bytes')

    report = dict(
        passed=True, workspace_sha256=META['sha256'],
        resident_artifacts=k.REPORT['artifacts'], checks=checks,
        format_write_cuts=format_cuts, upgrade_write_cuts=upgrade_cuts,
        exhaustion_fields=exhaustion, hardware_tested=False, board_access=False,
    )
    (OUT / 'format-test-results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
