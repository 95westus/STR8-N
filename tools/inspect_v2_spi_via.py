"""Read VIA state; optional qualification setup acknowledges disabled CB flags."""
import argparse,json,shutil,time
from pathlib import Path
import build_v2_config as compiler
from beta4_migration import Link,s19
from qualify_v2_rtc_board import load
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--out',required=True,type=Path);p.add_argument('--ack-disabled',action='store_true');a=p.parse_args()
    out=a.out;out.mkdir(parents=True,exist_ok=False);(out/'asm').mkdir()
    compiler.OUT=out;compiler.SOURCE=ROOT/'tools/v2-spi'
    source=compiler.SOURCE/'via-snapshot.asm'
    if a.ack_disabled:
        text=source.read_text().replace('        JMP $7E67','''        STZ $2405
        LDA $7FCE
        AND #$18
        BNE NO_ACK
        LDA $7FCC
        AND #$C0
        CMP #$80
        BEQ NO_ACK
        LDA $7FC2
        AND #$0F
        BNE NO_ACK
        LDA $7FC0
        INC $2405
NO_ACK: LDA $7FCD
        STA $2406
        JMP $7E67''')
        source=out/'snapshot-source.asm';source.write_text(text)
    cells,s=compiler.assemble('via-snapshot',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=compiler.SOURCE,source_file=source)
    (out/'snapshot.s19').write_bytes(s19(cells,0x2000))
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            link.command('');load(link,out/'snapshot.s19');link.command('G 2000');data=link.dump(0x2400,0x2406 if a.ack_disabled else 0x2404)
            names=('IFR','IER','PCR','ACR','DDRB');report=dict(zip(names,data[:5]));report['port_read_acknowledged']=bool(data[5]) if a.ack_disabled else False
            if a.ack_disabled:report['IFR_after']=data[6];assert report['port_read_acknowledged'] and data[1]&0x18==0 and data[6]&0x18==0
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
        finally:link.serial.close()

if __name__=='__main__':main()
