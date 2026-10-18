"""Model-check the temporary console-only observer and supported slot switch."""
import json,os,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';RUN=Q/'rc1-2604-2609-hardware-2026-10-18-r1'
def main():
    freeze=json.loads((Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json').read_text());ws=Path(freeze['frozen_source_directory']);os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*a,**k):raise RuntimeError('No board ports in observer model')
    serial.Serial=forbidden
    import beta4_migration;beta4_migration.Link=forbidden
    import test_asm as asm
    from test_v2_status import boot,layout
    image=(RUN/'extracted/str8n-2.0rc1/firmware/str8n-2.0rc1-apps-str8n-only.bin').read_bytes();cpu,m=asm.fixture(primary=layout());m.banks=[bytearray(b'\xff'*32768)]+[bytearray(image[n:n+32768]) for n in range(0,len(image),32768)];m.spi.banks=m.banks;m.fast=True;m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 00 0C');boot(cpu)
    cells,entry=beta4_migration.read_s19(ROOT/'tmp/rc1mode1/mode.s19')
    for addr,value in cells.items():m.ram[addr]=value
    text=asm.command(cpu,b'G 2000\r');rows=re.findall(rb'(?:[0-9A-F]{2} ){13}[0-9A-F]{2}',text);assert len(rows)==1,text
    raw=bytes.fromhex(rows[0].decode());assert raw[:6]==bytes.fromhex('02ff00000000') and raw[6]&12==4 and raw[7:12]==bytes.fromhex('0117040102') and raw[12]&1 and raw[13]==0xa5
    text=asm.command(cpu,b'P B\r');assert b'Preferred B 00000031' in text,text
    text=asm.command(cpu,b'J3\r');assert b'2.0rc1' in text and m.ram[0x7d30]==0xb0
    (RUN/'observer-and-slot-switch-model.json').write_text(json.dumps(dict(passed=True,console_observer_result=raw.hex(),P_B_J3_selects_MON_B_generation49=True,board_access=False,enters_native_mode=False),indent=2)+'\n')
    print('PASS console-only observer and P B/J3 rc1 slot switch model',flush=True)
if __name__=='__main__':main()
