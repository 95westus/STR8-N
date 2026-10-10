"""Execute WORK's KiB console, confirmations and resize refusals; no ports."""
import json
from test_v2_workspace import fresh,install,call,req,OUT,META,k
from test_v2_sram_store import boot,console,formatted

HELP=b'? capacity; P 16/32/48/64 (KiB); U upgrade; V repair; F format; HELP; Q\r\n'
def run(cpu,m,keys):
    install(cpu,m)
    return console(cpu,m,keys,entry=META['entry'],limit=30000000)

def main():
    checks=[]
    def passed(label):checks.append(label);print('PASS',label,flush=True)
    cpu,m=fresh();before=bytes(m.spi.devices[0].data)
    output=run(cpu,m,b'?\rP 64\rHELP\rQ\r')
    assert ('WORK '+META['version']).encode()+b'\r\n'+HELP+b'WORK> ' in output
    assert b'Programs: 64 KiB; workspace: 65504 bytes\r\n' in output
    assert b'No change.\r\nWORK> ' in output and b'Apply?' not in output
    assert output.count(HELP)==2 and bytes(m.spi.devices[0].data)==before
    assert b'B3> ' in output
    passed('plain prompt, help once/on HELP, decimal capacities and same-size no-write result')

    cpu,m=fresh();baseline=bytes(m.spi.devices[0].data)
    invalid=b'P 2\rP 17\rP 65\rP 032\rP 32X\rP 32 \rHELP X\r?X\rF X\rU X\rV X\rQ X\r'
    output=run(cpu,m,invalid+b'P 32\r\rP 32\rn\rP 32\rYES\rP 32\r\x1bP 32\r\x03F\rYES\rU\rNO\rV\r\rQ\r')
    assert output.count(b'Invalid command. Use HELP.')==12
    assert output.count(b'Canceled.')==8
    assert bytes(m.spi.devices[0].data)==baseline
    assert b'Resized.' not in output and b'Formatted.' not in output
    passed('old unit syntax/trailing input refuse; blank, N, wrong confirmation, ESC and Ctrl-C cancel without writes')

    cpu,m=fresh();baseline=bytes(m.spi.devices[0].data);flash=[bytes(b) for b in m.banks]
    rtc=bytes(m.bus.rtc_regs);ee=bytes(m.bus.ee)
    output=run(cpu,m,b'P 16\ry\r?\rP 32\rY\r?\rP 48\rY\r?\rP 64\rY\r?\rQ\r')
    for size,capacity in ((16,114656),(32,98272),(48,81888),(64,65504)):
        text=f'Programs: {size} KiB; workspace: {capacity} bytes\r\n'.encode()
        assert output.count(text)==2
    assert output.count(b'Resized.')==4 and output.count(HELP)==1
    assert m.spi.devices[0].data[0x800:]==baseline[0x800:]
    assert [bytes(b) for b in m.banks]==flash and bytes(m.bus.rtc_regs)==rtc and bytes(m.bus.ee)==ee
    (OUT/'console-example.txt').write_bytes(output)
    passed('all four direct KiB selections preview/confirm/report correctly, preserving payload, flash, RTC and EEPROM')

    cpu,m=fresh()
    assert call(cpu,m,req(5,units=2,key=b'RESIZE!!'))[0]==0
    assert call(cpu,m,req(1,size=256))[0]==0
    baseline=bytes(m.spi.devices[0].data)
    output=run(cpu,m,b'P 64\rY\rQ\r')
    assert b'Resize refused: workspace overlaps.' in output and b'Resized.' not in output
    assert bytes(m.spi.devices[0].data)==baseline
    passed('growing into a live workspace claim refuses with readable reason and no storage change')

    cpu,m=fresh();baseline=bytes(m.spi.devices[0].data)
    output=run(cpu,m,b'F\rFORMAT SRAM\rV\rYES\rQ\r')
    assert b'Formatted.' in output and b'Repaired.' in output
    assert m.spi.devices[0].data[0x800:]==baseline[0x800:]
    cpu,m=formatted(fast=True);install(cpu,m)
    baseline=bytes(m.spi.devices[0].data)
    output=run(cpu,m,b'P 32\rY\rU\rYES\rQ\r')
    assert b'Upgrade required. Use U.' in output and b'Upgraded.' in output
    assert m.spi.devices[0].data[0x800:]==baseline[0x800:]
    passed('format retains exact FORMAT SRAM; upgrade/repair retain exact YES and readable results')

    cpu,m=boot();m.fast=True;before=bytes(m.spi.devices[0].data)
    output=run(cpu,m,b'?\rP 32\rQ\r')
    assert output.count(b'Storage not initialized.')==2 and b'Apply?' not in output
    assert bytes(m.spi.devices[0].data)==before
    cpu,m=boot();m.fast=True;m.ram[0x7D04]=0
    output=run(cpu,m,b'?\rQ\r')
    assert b'SPI SRAM unavailable.' in output
    passed('uninitialized and missing optional service report plainly without formatting')
    report=dict(passed=True,checks=checks,workspace_sha256=META['sha256'],resident_artifacts=k.REPORT['artifacts'],board_access=False,boards_flashed=False)
    (OUT/'console-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
