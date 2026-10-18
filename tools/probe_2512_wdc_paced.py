"""2512-only paced identity probe. Only SYNC and validated BOARD_INFO; no memory/EXEC commands."""
import argparse,json,time,hashlib,os
from pathlib import Path
from datetime import datetime,timezone
import serial
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();a.out.mkdir(parents=True)
    marker=json.loads((Q/'device-operations/2512.json').read_text());assert marker['block_snapshot']
    assert marker['state']=='inspection-required' or (marker['state']=='legacy-reset-required' and marker['phase']=='wdcmonv2-restore-historical-source')
    active=json.loads((Q/'active-rtc-campaign.json').read_text());assert '2512' not in active['powered_off_boards']
    ports=[p.device for p in comports() if p.serial_number==SERIALS['2512']];assert len(ports)==1
    report=dict(board='2512',pid=os.getpid(),passed=False,state='opening',started_utc=datetime.now(timezone.utc).isoformat(),persistent_writes=False,memory_writes=False,execution_requested=False,reset=False,port=ports[0],rts=True,rtscts=False,probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    def save():publish(a.out/'report.json',report)
    save()
    with (a.out/'serial.jsonl').open('x') as log:
      def event(direction,data):log.write(json.dumps(dict(time=time.time(),direction=direction,hex=data.hex()))+'\n');log.flush()
      link=serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=1);link.dtr=False;link.rts=True;link.rtscts=False;link.port=ports[0]
      try:
        link.open();link.reset_output_buffer();link.reset_input_buffer();report.update(state='armed',cts=link.cts);save();print('ARMED paced identity probe for 180 seconds; no memory or execution commands',flush=True);deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            packet=b'\x55\xaa';event('TX',packet);assert link.write(packet)==2;report['last_tx_unix']=time.time();save()
            end=time.monotonic()+2;received=bytearray()
            while time.monotonic()<end:
                data=link.read(max(1,link.in_waiting))
                if data:event('RX',data);received.extend(data)
                if b'\xcc' in received:break
            if b'\xcc' not in received:continue
            time.sleep(.1);link.reset_input_buffer();event('TX',b'\x0c');assert link.write(b'\x0c')==1;identity=bytearray();until=time.monotonic()+2
            while len(identity)<12 and time.monotonic()<until:
                data=link.read(12-len(identity))
                if data:event('RX',data);identity.extend(data)
            assert len(identity)==12 and identity[:4]==b'SXB2', 'Unexpected stock identity; inspect without memory commands'
            (a.out/'identity.bin').write_bytes(identity);report.update(passed=True,state='identity-verified',identity_hex=identity.hex(),finished_utc=datetime.now(timezone.utc).isoformat());save();print('PASS SXB2 identity',identity.hex(),flush=True);return
        report.update(state='no-response',finished_utc=datetime.now(timezone.utc).isoformat());save();raise TimeoutError('No stock identity; no memory, execution or persistent commands issued')
      except BaseException as e:report.update(error=repr(e),state='failed');save();raise
      finally:
        if link.is_open:link.cancel_write();link.reset_output_buffer();link.close()
if __name__=='__main__':main()
