"""2512-only b12->b14 installer with raw 0200/idle auto-run verification."""
from pathlib import Path
import board_b07_2512 as frozen

def b14_idle(link,seconds):
    start=time.monotonic();raw=bytearray(link.pending);link.pending.clear()
    while time.monotonic()-start<seconds:raw.extend(link.read(4096))
    r.require(not raw,'Unexpected output while raw loader should wait; preserve serial evidence')
    return time.monotonic()-start

def b14_help_probe(link,run):
    from build_b14 import HELP
    raw=link.command('?',REC_PROMPT)
    r.require(HELP in raw and b'RLP1' not in raw,'Wrong b14 recovery help')
    for key in ['R','r','D','d','V','v']:
        reply=link.command(key,REC_PROMPT)
        r.require(reply==key.encode()+b'\r\nREFUSED: command\r\nREC> ','Removed '+key+' accepted')
        raw+=reply
    (Path(run)/'b14-help.txt').write_bytes(raw)
    save(Path(run)/'b14-help.json',dict(passed=True,hardware=True,help_verified=True,removed_R_D_V_refused=True))

def raw_load_auto_run(link,body):
    r.require(0<len(body)<=0x6300,'Raw BIN exceeds b14 load range')
    link.command('L',b'SEND BIN\r\n')
    initial=b14_idle(link,5)
    first=now();mid=len(body)//2
    for start,stop in [(0,mid),(mid,len(body))]:
        if start:intermediate=b14_idle(link,2)
        for off in range(start,stop,64):
            packet=body[off:min(off+64,stop)]
            link.send(packet);last=time.monotonic();last_utc=now()
            time.sleep(.01)
    reply=link.until(OI_PROMPT,15);elapsed=time.monotonic()-last
    r.require(reply==OI_PROMPT,'Raw BIN did not auto-run to exact installer prompt; no R sent')
    r.require(2.75<=elapsed<=4.5,'Raw idle-to-program prompt outside host-observed three-second window')
    link.b14_raw_receipt=dict(passed=True,hardware=True,start=0x200,entry=0x200,bytes=len(body),
        initial_no_data_wait_seconds=initial,inter_chunk_idle_seconds=intermediate,
        first_data_sent_utc=first,last_data_sent_utc=last_utc,program_prompt_received_utc=now(),
        host_observed_last_TX_to_program_prompt_seconds=elapsed,header_bytes=0,length_field=False,CRC=False,R_command_sent=False,
        bytes_sent_sha256=r.sha(body),payload_contains_03=3 in body,
        timing_limit='Host serial timestamps at FT245; physical last-byte arrival is not directly measured')

def b14_runtime_image(body,sector,symbols):
    r.require(len(sector)==4096,'Exact read-only sector required')
    header=b'OIP1\x01\x00\x00\x80\x00\x10'+bytes(8);header+=wire.crc(header).to_bytes(2,'little')
    first=symbols['OI_HEADER']-0x200
    r.require(symbols['OI_CRC']==symbols['OI_HEADER']+20 and symbols['OI_PAGES']==symbols['OI_CRC']+2
              and body[first:first+23]==bytes(23),'Tool scratch layout differs')
    result=bytearray(body);result[first:first+23]=header+wire.crc(sector).to_bytes(2,'little')+b'\0'
    return bytes(result)

def b14_mon_readback(link,run,body,sector,symbols):
    expected=b14_runtime_image(body,sector,symbols);raw=link.dump(0x200,0x1ff+len(body))
    r.require(raw==expected,'Independent MON readback of raw-loaded tool differs')
    (Path(run)/'b14-tool-RAM-readback.bin').write_bytes(raw)
    save(Path(run)/'b14-tool-RAM-readback.json',dict(passed=True,hardware=True,start=0x200,bytes=len(raw),
        sha256=r.sha(raw),expected_sha256=r.sha(expected),payload_sha256=r.sha(body),runtime_scratch_bytes=23,
        method='MON D; exact whole executed image including predicted mutable request/CRC/page workspace'))

source=Path(frozen.__file__).read_text()
for before,after in [('b06 -> b07','b12 -> b14'),
    ('import deployment_b07 as deployment_plan','import deployment_b14 as deployment_plan'),
    ('from b07_admission import bindings','from b14_admission import bindings'),
    ('deploy-native-b07-bench-core','deploy-native-b14-bench-core'),
    ('Boot : 3 2 1 0','Boot : 6 5 4 3 2 1 0'),
    ('RAM recovery L/R/D/V A/B','Recovery L A/B 0-3 C1/2/3 ?'),
    ("source='2.0proto b06'","source='2.0proto b12'"),
    ("'source-b06'","'source-b12'"),('native b06 repeated capture','native b12 repeated capture'),
    ('pr04-b07-bench-core','pr04-b14-bench-core'),('b07 startup','b14 startup'),
    ('ordered b07 physical','ordered b14 physical'),
    ("        link.command('C1', REC_PROMPT)","        link.command('C1', REC_PROMPT)\n        b14_help_probe(link,run)"),
    ('        rlp_load_readback(link, body)', '''        raw_load_auto_run(link, body)
        save(Path(run)/'b14-raw-autorrun.json',link.b14_raw_receipt)'''),
    ('    link.command(\'R\', OI_PROMPT)\n',''),
    ('RLP1_load_readback_verified=True','raw_BIN_autorun_verified=True')]:
    assert before in source,before;source=source.replace(before,after)
# Remove obsolete private RLP1 functions; target recovery never sees R/V.
a,b=source.index('def rlp_header('),source.index('def oip_read_only(');source=source[:a]+source[b:]
needle="        select_ftdi(link, build, expected, run, 'target-after-probe')"
source=source.replace(needle,"        b14_mon_readback(link,run,body,expected[0][:4096],symbols['core/ram-installer'])\n        state.update(MON_tool_RAM_readback_verified=True)\n"+needle)
before='        state.update(application_RAM_restore_pending=False, RAM_restored=True,'
source=source.replace(before,"        owner_zp=(Path(plan)/'capture/owner-zp.bin').read_bytes()\n        r.require(len(owner_zp)==0xe0,'Owner ZP escrow missing')\n        for _ in range(2):r.require(link.dump(0,0xdf)==owner_zp,'Owner ZP00-DF differs')\n        state.update(owner_ZP_preserved=True,final_owner_ZP_rereads=2)\n"+before)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
