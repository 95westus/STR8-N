"""Execute exact board B/C/E/F updater success, refusal and rollback opcodes."""
import argparse
import json
from pathlib import Path
import test_v2_b2 as host
import test_v2_b2_board_update as harness
import build_v2_b2_board_update as update


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--phases',nargs='+',choices=('b','c','e','f'),default=['b','c','e','f'])
    args=parser.parse_args()
    folder=args.evidence
    before=[(folder/f'before-b{i}.bin').read_bytes() for i in range(4)]
    phase_bank=bytearray(before[3])
    worker=(folder/'before-worker.bin').read_bytes()[:741]
    passed=[]
    artifacts={}
    image=host.boot.IMAGE
    try:
        for phase in args.phases:
            directory=folder/(phase+'-updater')
            meta=json.loads((directory/'manifest.json').read_text())
            path=directory/f'str8n-v2-b2-{phase}-update-2000.s19'
            code,entry=host.firmware.read_s19(path)
            assert update.sha(path.read_bytes())==meta['s19_sha256']
            assert update.sha(phase_bank)==meta['source_full_b3_sha256']
            new=(directory/'staged-sector.bin').read_bytes()
            base=int(phase,16)*4096-0x8000
            for case in ('success','cancel','old-target','guard-after-confirm',
                         'unrelated-after-confirm','rollback'):
                host.boot.IMAGE=bytes(phase_bank[-8192:])
                mem=host.flash.FlashMemory(3)
                for bank in range(4):mem.banks[bank][:]=before[bank]
                mem.banks[3][:]=phase_bank
                cpu=harness.B2CPU(memory=mem,pc=0xF004)
                mem.cpu=cpu
                host.boot.run(cpu,lambda:host.boot.waiting(cpu),limit=2_000_000)
                assert mem.ram[0x7900:0x7900+741]==worker
                for address,value in code.items():mem.ram[address]=value
                cpu.pc=entry
                if case=='old-target':mem.banks[3][base]^=1
                expected=bytearray(mem.banks[3])
                if case!='old-target':
                    harness.prompt(cpu,meta['symbols'])
                    if case=='guard-after-confirm':
                        offset=meta['guard_sector']*256-0x8000
                        mem.banks[3][offset]^=1
                        expected[offset]^=1
                    elif case=='unrelated-after-confirm':
                        offset=0x5FFF
                        mem.banks[3][offset]^=1
                        expected[offset]^=1
                    elif case=='rollback':mem.fault='timeout'
                    mem.rx.append(ord('N' if case=='cancel' else 'Y'))
                    if case=='rollback':
                        host.boot.run(cpu,lambda:cpu.pc==meta['symbols']['E_ROLLBACK'],limit=15_000_000)
                        mem.fault=None
                harness.finish(cpu)
                if case=='success':
                    expected[base:base+4096]=new
                    assert b'b2 VERIFIED' in mem.tx
                elif case=='cancel':assert b'ABORTED' in mem.tx
                elif case=='rollback':assert b'OLD RESTORED' in mem.tx
                else:assert b'IMAGE MISMATCH' in mem.tx
                assert bytes(mem.banks[3])==expected
                assert [bytes(b) for b in mem.banks[:3]]==before[:3]
                if case not in ('success','rollback'):assert not mem.events
                passed.append(phase+':'+case)
                print('PASS:',phase,case,flush=True)
            phase_bank[base:base+4096]=new
            artifacts[phase]=meta['s19_sha256']
        assert bytes(phase_bank)==(folder/'expected-installed-b3.bin').read_bytes()
        assert phase_bank[0x7FD0:0x7FE0]==before[3][0x7FD0:0x7FE0]
    finally:host.boot.IMAGE=image
    (folder/'autoload-updater-host-tests.json').write_text(json.dumps(dict(
        passed=passed,artifacts=artifacts,source_full_b3_sha256=update.sha(before[3]),
        expected_full_b3_sha256=update.sha(phase_bank),identical_ram_worker=True,
        staging=0x6100,application_end=0x527D,physical_hardware_tested=False),indent=2)+'\n')


if __name__=='__main__':main()
