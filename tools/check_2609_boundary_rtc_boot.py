"""Supplement stable-boundary proof with the captured RTC date and PF flag."""
import argparse,json,hashlib,binascii
from pathlib import Path
import bf1_offline_recovery_model as harness
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--boundary',type=Path,required=True);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--measurement',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    proof=read(a.boundary/'report.json');assert proof['passed']
    measurement=read(a.measurement);assert measurement['passed']
    raw=measurement['readings'][-1]['raw'];assert len(raw)==9
    banks=[(a.boundary/f'expected-cut-b{i}.bin').read_bytes() for i in range(4)]
    assert [hashlib.sha256(b).hexdigest() for b in banks]==proof['expected_cut_hashes']
    assert not a.out.exists();a.out.mkdir();harness.setup()
    from test_v2_status import fresh,boot
    cases=[]
    for flag in (False,True):
        cpu,mem=fresh();mem.fast=True
        for i,bank in enumerate(banks):mem.banks[i][:]=bank
        ee=(a.backup/'eeprom.bin').read_bytes();mem.bus.ee[:128]=ee[:128];mem.bus.ee[0xff]=ee[128];mem.bus.ee[0xf0:0xf8]=ee[129:137]
        mem.spi.devices[0].data[:]=(a.backup/'sram.bin').read_bytes()
        seed=list(raw);seed[3]=(seed[3]|0x10) if flag else (seed[3]&~0x10);mem.bus.rtc_regs[:9]=bytes(seed)
        before=(bytes(mem.bus.ee),bytes(mem.spi.devices[0].data),bytes(mem.bus.rtc_regs))
        boot(cpu);assert mem.ram[0x7d30]==0xa0
        differences=[(b,i) for b in range(4) for i,(x,y) in enumerate(zip(banks[b],mem.banks[b])) if x!=y]
        result=dict(power_fail_seed=flag,selected_page=0xa0,flash_changed_bytes=len(differences),flash_changed_offsets=differences,
                    EEPROM_unchanged=before[0]==bytes(mem.bus.ee),SRAM_unchanged=before[1]==bytes(mem.spi.devices[0].data),
                    RTC_registers_unchanged=before[2]==bytes(mem.bus.rtc_regs),RTC_before=list(before[2]),RTC_after=list(mem.bus.rtc_regs))
        (a.out/f'PF-{int(flag)}-boot.txt').write_bytes(mem.tx)
        (a.out/f'PF-{int(flag)}-EEPROM-before.bin').write_bytes(before[0])
        (a.out/f'PF-{int(flag)}-EEPROM-after.bin').write_bytes(mem.bus.ee)
        (a.out/f'PF-{int(flag)}-I2C-writes.json').write_text(json.dumps(mem.bus.writes,indent=2)+'\n')
        assert not differences and result['SRAM_unchanged']
        if flag:
            changes=[i for i,(x,y) in enumerate(zip(before[0],mem.bus.ee)) if x!=y]
            slots={i//32 for i in changes};assert changes and max(changes)<128 and len(slots)==1
            slot=next(iter(slots));record=bytes(mem.bus.ee[slot*32:(slot+1)*32])
            assert record[:3]==b'PF\x01' and record[3]==slot+1 and record[4:8]==b'JR\x20\xa5'
            assert record[12:20]==before[2][0x18:0x20]
            assert int.from_bytes(record[28:30],'little')==binascii.crc_hqx(record[:28],0xffff)
            assert record[30:32]==b'\0\xa5'
            assert all(x==y for i,(x,y) in enumerate(zip(before[2],mem.bus.rtc_regs)) if i!=3 and not 0x18<=i<0x20)
            assert mem.bus.rtc_regs[3]==before[2][3]&~0x10
            commits=[n for n,(dev,addr,value) in enumerate(mem.bus.writes) if dev==0x57 and addr==slot*32+31 and value==0xa5]
            acknowledgments=[n for n,(dev,addr,value) in enumerate(mem.bus.writes) if dev==0x6f and addr==3 and not value&0x10]
            assert commits and acknowledgments and min(acknowledgments)>max(commits)
            result.update(expected_automatic_PF_journal=True,slot=slot,record_hex=record.hex(),record_crc_valid=True,
                          raw_outage_saved=True,ack_after_commit=True,calendar_control_trim_unchanged=True,
                          manual_ACK_CLEAR_commands_sent=False)
        else:
            assert result['EEPROM_unchanged'] and result['RTC_registers_unchanged']
        cases.append(result);(a.out/'progress.json').write_text(json.dumps(cases,indent=2)+'\n')
    result=dict(passed=True,model_processor='W65C02',cases=cases,boundary_report_sha256=sha(a.boundary/'report.json'),measurement_sha256=sha(a.measurement),physical_interruption_performed=False,board_access=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS PF-clear boot unchanged; PF-set boot preserves raw event in CRC-valid EEPROM record before automatic ACK; calendar/control/trim, flash and SRAM unchanged',flush=True)
if __name__=='__main__':main()
