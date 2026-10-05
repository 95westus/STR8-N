"""Qualify the existing SERVICE.REGISTER board probe against the autoload image."""
import argparse
import json
from pathlib import Path
import test_v2_b2 as host
import test_v2_b2_board_update as harness
from v2_b2_config import checksum
import build_v2_b2_board_update as update


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    folder=args.evidence
    prior=folder.parent/'service-install-1791125311788929100'
    probe=prior/'probe/service-probe-2000.s19'
    meta=json.loads((prior/'probe/manifest.json').read_text())
    private=(folder/'before-module-ram.bin').read_bytes()[0x600:0x709]
    assert private==(prior/'before-module-ram.bin').read_bytes()[0x600:0x709]
    code,entry=host.firmware.read_s19(probe)
    bank=bytearray((folder/'expected-installed-b3.bin').read_bytes())
    header=bytearray(bank[0x5000:0x5010]);header[10]=0xA1;header[14:]=checksum(header[:14])
    block=bytearray(64);block[:4]=b'AL\x01\x3F'
    for i,(key,address) in enumerate([('R',0),('S',0),('T',0),('X',0xC70A),('H',0xC00A)]):
        block[8+i*4:12+i*4]=bytes((ord(key),1,address&255,address>>8))
    block[62:]=checksum(block[:62])
    bank[0x5000:0x5010]=header;bank[0x5010:0x5050]=block
    mem=host.flash.FlashMemory(3);mem.banks[3][:]=bank
    mem.ram[0x7700:0x7809]=private
    cpu=harness.B2CPU(memory=mem,pc=0xF004);mem.cpu=cpu
    host.boot.hold(cpu)
    assert mem.ram[host.MGR['MG_COUNT']]==18
    for address,value in code.items():mem.ram[address]=value
    cpu.pc=entry
    host.boot.hold(cpu)
    assert b'SERVICE REGISTER / CALLABLE / DATA / VERSION / DUPLICATE PASS' in mem.tx
    assert mem.ram[0x7DEB]==12
    cpu.pc=0xF004;host.boot.hold(cpu)
    assert mem.ram[0x7DEB]==0 and mem.ram[host.MGR['MG_COUNT']]==18
    cpu.pc=meta['RESTORE'];host.boot.hold(cpu)
    assert bytes(mem.ram[0x7700:0x7809])==private
    assert not mem.events
    (folder/'autoload-service-probe-tests.json').write_text(json.dumps(dict(
        passed=True,probe=str(probe.resolve()),probe_sha256=update.sha(probe.read_bytes()),
        initializer=entry,restore=meta['RESTORE'],before_private_sha256=update.sha(private),
        candidate_sha256=update.sha((folder/'expected-installed-b3.bin').read_bytes()),
        callable_data_versions_duplicates_passed=True,reset_and_restore_passed=True),indent=2)+'\n')
    print('PASS: existing board service probe, new autoload image, reset and scratch restoration')


if __name__=='__main__':main()
