"""Offline 65C02 proof of bf1 A/B prompt entry without configuration or persistent changes."""
import argparse,json
from pathlib import Path
import bf1_offline_recovery_model as h
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();a.out.mkdir(parents=True)
    h.setup()
    from test_v2_status import fresh,boot
    from test_v2_sram_store import console
    root=Path(__file__).resolve().parents[1];source=root/'output/qualification/bf1-2512-legacy-offline-2026-10-17-r6/wdcmonv2-convert';banks=[(source/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    cpu,m=fresh();m.fast=True
    for n,b in enumerate(banks):m.banks[n][:]=b
    before=([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.spi.devices[0].data),bytes(m.bus.rtc_regs))
    boot(cpu);checks=[]
    for page in (0xa0,0xb0):
        text=console(cpu,m,f'G {page:02X}87\r'.encode(),limit=35000000);text+=console(cpu,m,b'VERSION\r');assert m.ram[0x7d30]==page and (b'Running: MONITOR A' if page==0xa0 else b'Running: MONITOR B') in text,text[-600:]
        text+=console(cpu,m,b'BATCH MAINT;Q\r',limit=35000000);assert b'BATCH done' in text
        reply=console(cpu,m,b'BATCH R CLOCK;STATUS;Q\r',limit=35000000);assert b'CLOCK 1.11' in reply and b'BATCH done' in reply and reply.endswith(b'B3> ');text+=reply
        (a.out/f'{page:02x}.txt').write_bytes(text);checks.append(dict(page=page,prompt_entry=f'{page:02X}87',identity=True,native_CLOCK_BATCH=True,passed=True))
    assert before==([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.spi.devices[0].data),bytes(m.bus.rtc_regs))
    (a.out/'report.json').write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,bank_hashes=h.p.bank_hashes(banks),scope='65C02 software prompt-entry handoff after normal boot; no hardware RESET claim',persistent_devices_unchanged=True,board_access=False),indent=2)+'\n');print('PASS both A/B software prompt entries and BATCH; all persistent devices unchanged',flush=True)
if __name__=='__main__':main()
