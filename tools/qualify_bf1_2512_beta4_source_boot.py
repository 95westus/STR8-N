"""Offline exact staged beta4 source boot and active-slot admission proof."""
import argparse,json
from pathlib import Path
import bf1_offline_recovery_model as h
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();a.out.mkdir(parents=True);h.setup()
    from test_v2_status import fresh
    root=Path(__file__).resolve().parents[1];folder=root/'output/qualification/bf1-2512-legacy-offline-2026-10-17-r6/v2-0b4-stage-source';banks=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)];cpu,m=fresh();m.fast=True
    for n,b in enumerate(banks):m.banks[n][:]=b
    before=([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.spi.devices[0].data),bytes(m.bus.rtc_regs));last=0
    for steps in range(30000000):
        cpu.step()
        if len(m.tx)!=last:
            last=len(m.tx)
            if bytes(m.tx).endswith(b'\r\nB3> '):break
    else:raise AssertionError(f'No beta4 prompt at {cpu.pc:04X}')
    assert m.ram[0x7d30]==0xa0 and b'2.0b4' in bytes(m.tx)
    assert before==([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.spi.devices[0].data),bytes(m.bus.rtc_regs))
    (a.out/'boot.txt').write_bytes(bytes(m.tx));(a.out/'report.json').write_text(json.dumps(dict(passed=True,source_bank_hashes=h.p.bank_hashes(banks),active_page=0xa0,steps=steps,version='2.0b4',persistent_devices_unchanged=True,board_access=False),indent=2)+'\n');print('PASS exact beta4 MON A source boots and preserves persistent devices',flush=True)
if __name__=='__main__':main()
