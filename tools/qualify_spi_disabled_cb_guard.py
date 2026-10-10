"""RAM-only cold-start comparison; SRAM READ only, no firmware writes."""
import argparse, json, shutil, time
from pathlib import Path
import build_v2_config as compiler
from beta4_migration import Link, s19
from qualify_v2_rtc_board import load
from install_v2_rtc_upgrade import SERIALS
from serial.tools.list_ports import comports

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert any(x.device.upper() == a.port.upper() and x.serial_number == SERIALS['2609'] for x in comports()), '2609 port identity mismatch'
    out = a.out
    out.mkdir(parents=True, exist_ok=False)
    (out/'asm').mkdir()
    compiler.OUT = out
    source = ROOT/'tools/v2-spi'
    cells, symbols = compiler.assemble('spi-disabled-cb-guard', 0x2000, shutil.which('wdc02as'), shutil.which('wdcln'), source=source)
    (out/'guard.s19').write_bytes(s19(cells, 0x2000))
    wrapper = ROOT/'tools/v2-spi/spi-guard-hardware.asm'
    shutil.copyfile(wrapper, out/'guard-client.asm')
    cells, symbols = compiler.assemble('guard-client', 0x2300, shutil.which('wdc02as'), shutil.which('wdcln'), source=out)
    (out/'client.s19').write_bytes(s19(cells, 0x2300))
    request = bytes([1,0,0,0,0,0,0x25,64]+[0]*8)
    with (out/'serial.jsonl').open('x') as log:
        link = Link(a.port, log)
        try:
            end = time.monotonic()+.3
            while time.monotonic()<end:
                link.read(max(1,link.serial.in_waiting))
            link.command('')
            load(link,out/'guard.s19')
            load(link,out/'client.s19')
            link.write_ram(0x2400,request)
            (out/'run.txt').write_bytes(link.command('G 2300'))
            data = link.dump(0x2450,0x245A)
            (out/'result.bin').write_bytes(data)
            (out/'read64.bin').write_bytes(link.dump(0x2500,0x253F))
            names = ('IFR_before','IER','PCR','ACR','DDRB_before','read_before','guard','read_after','IFR_after','DDRB_after','read_count')
            report = dict(zip(names,data))
            report['passed'] = data == bytes([0x1A,0x80,0,0,0,1,0,0,2,0,64])
            report['firmware_written'] = False
            report['sram_data_written'] = False
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
            assert report['passed'], 'Cold-start comparison did not match; evidence retained'
        finally:
            link.serial.close()

if __name__ == '__main__':
    main()
