"""Backup-bound saved CLK upgrade; never writes flash or RTC settings."""
import argparse,json,re,os
from pathlib import Path
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta32-2609-candidate'
import upgrade_v2_fleet as f
from beta4_migration import Link
from build_v2_spi_resident import sha
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/qualification/clock19-2609-2026-10-16'
BUILD=ROOT/'BUILD/v2-beta32-2609-candidate'
PRIOR=ROOT/'output/qualification/beta32-2026-10-16/2609/upgrade'
read=lambda p:json.loads(p.read_text())

def devices(stage):
    campaign=read(ROOT/'output/qualification/active-rtc-campaign.json')
    f.call(f.devices,['--root',str(OUT),'--board','2609','--port',f.port('2609'),'--stage',stage,
        '--baseline-index',campaign['baseline_index'],'--clock-source','sram','--clock-name','CLK','--clock19-display-transition'])

def capture():
    OUT.mkdir(parents=True,exist_ok=False)
    with serial_lease('clk19-2609-backup',priority=True):
        f.call(f.array,['--root',str(OUT),'--board','2609','--port',f.port('2609'),'--stage','prior'])
        devices('before')

def model():
    from test_v2_status import fresh,boot
    from test_v2_sram_store import console
    cpu,m=fresh();m.fast=True
    m.banks=[bytearray((PRIOR/f'post-reset-b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
    array=(OUT/'sram-prior/array-0.bin').read_bytes();m.spi.devices[0].data[:]=array
    raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',(OUT/'devices-before/status.txt').read_bytes())[1].decode())
    m.bus.rtc_regs[:9]=raw
    ee=(OUT/'devices-before/eeprom-0.bin').read_bytes()
    m.bus.ee[:128]=ee[:128];m.bus.ee[255]=ee[128];m.bus.ee[240:248]=ee[129:137]
    boot(cpu);assert m.ram[0x7D30]==0xA0
    cm=read(BUILD/'clock/build.json');body=(BUILD/'clock/clock.bin').read_bytes()
    assert cm['version']=='1.9' and cm['batch_abi']==1 and sha(body)==cm['sha256']
    m.ram[0x2000:0x2000+len(body)]=body
    text=console(cpu,m,f'SRAM\rS CLK 2000 {0x2000+len(body)-1:04X} 2000\rQ\r'.encode(),limit=100000000)
    assert b'SRAM: 00' in text and text.endswith(b'B3> '),text[-1000:]
    expected=bytes(m.spi.devices[0].data);assert expected!=array and expected[65536:]==array[65536:]
    text+=console(cpu,m,b'BATCH SRAM;G CLK;Q\r',limit=100000000)
    assert b'CLOCK 1.9' in text and b'BATCH done' in text and text.endswith(b'B3> '),text[-1500:]
    assert bytes(m.spi.devices[0].data)==expected
    assert [bytes(x) for x in m.banks]==[(PRIOR/f'post-reset-b{i}.bin').read_bytes() for i in range(4)]
    assert bytes(m.bus.ee[:128])+bytes([m.bus.ee[255]])+bytes(m.bus.ee[240:248])==ee[:137]
    (OUT/'expected-sram.bin').write_bytes(expected);(OUT/'model-transcript.txt').write_bytes(text)
    report=dict(passed=True,clock_sha256=sha(body),prior_sram_sha256=sha(array),expected_sram_sha256=sha(expected),
        changed_sram_bytes=sum(a!=b for a,b in zip(array,expected)),workspace_unchanged=True,batch_verified=True)
    (OUT/'model.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)

def array_read(link,label):
    load_image(link,ROOT/'BUILD/v2-spi-resident/hardware-client/client.s19');blocks=[]
    for block in range(16):
        write(link,0x3E20,b'\x01\x03\0');write(link,0x3E00,memory_request(1,block*8192))
        link.command('G 2003');r=link.dump(0x3E10,0x3E38)
        assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24]
        blocks.append(link.dump(0x4000,0x5FFF));print(label,block+1,'/16',flush=True)
    return b''.join(blocks)

def install():
    proof=read(OUT/'model.json');assert proof['passed']
    body=(BUILD/'clock/clock.bin').read_bytes();assert sha(body)==proof['clock_sha256']
    with serial_lease('clk19-2609-install',priority=True),(OUT/'install-serial.jsonl').open('x') as log:
        link=Link(f.port('2609'),log)
        try:
            establish_b3(link);assert link.dump(0x7D30,0x7D30)==b'\xA0'
            assert b'2.0b32' in link.command('VERSION')
            assert sha(array_read(link,'Fresh SRAM guard'))==proof['prior_sram_sha256']
            assert load_image(link,BUILD/'clock/clock.s19')==proof['clock_sha256']
            link.command('SRAM',b'SRAM> ')
            text=link.command(f'S CLK 2000 {0x2000+len(body)-1:04X} 2000',b'SRAM> ')
            assert b'SRAM: 00' in text,text
            link.command('Q');(OUT/'save.txt').write_bytes(text)
            text=link.command('BATCH SRAM;G CLK;Q',b'BATCH done')+link.until(b'\r\nB3> ')
            assert b'CLOCK 1.9' in text and b'BATCH stopped' not in text,text
            (OUT/'batch.txt').write_bytes(text)
            text=link.command('BATCH SRAM;G CLK;STATUS;Q',b'BATCH done')+link.until(b'\r\nB3> ')
            assert b'Running: yes' in text and b'Backup enabled: yes' in text,text
            (OUT/'batch-status.txt').write_bytes(text)
            actual=array_read(link,'Final SRAM');assert sha(actual)==proof['expected_sram_sha256']
            (OUT/'actual-sram.bin').write_bytes(actual)
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert data==(PRIOR/f'post-reset-b{bank}.bin').read_bytes()
                (OUT/f'flash-b{bank}.bin').write_bytes(data);print('PASS unchanged flash B'+str(bank),flush=True)
            link.command('B3')
        finally:link.serial.close()
    with serial_lease('clk19-2609-rtc-final',priority=True):devices('after')
    assert read(OUT/'devices-after/report.json')['passed']
    (OUT/'qualification.json').write_text(json.dumps(dict(passed=True,board='2609',clock_version='1.9',
        batch_sram_g_clk_q_verified=True,full_sram_matches_model=True,all_flash_unchanged=True,
        rtc_settings_history_eeprom_identity_preserved=True,clock_sha256=proof['clock_sha256']),indent=2)+'\n')
    print('PASS CLOCK 1.9 installed; BATCH verified; flash/RTC/history preserved',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['capture','model','install']);a=p.parse_args();globals()[a.stage]()
