"""2512 b12 update/boot verification, with live idle-cancel and delayed RX probes."""
from pathlib import Path
import board_b07_2512 as frozen


def b12_idle(link,seconds):
    start=time.monotonic();raw=bytearray(link.pending);link.pending.clear()
    while time.monotonic()-start<seconds:raw.extend(link.read(4096))
    r.require(not raw,'Unexpected output while awaiting first byte; raw serial evidence retained')
    return time.monotonic()-start


def b12_help_probe(link,run,label='fresh'):
    from build_b12 import HELP
    raw=link.command('?',REC_PROMPT)
    r.require(HELP in raw and b'REFUSED' not in raw,'Recovery ? help differs')
    reply=link.command('R',REC_PROMPT)
    r.require(b'REFUSED: no valid RAM image\r\n' in reply and b'timeout' not in reply, 'R absent-image diagnostic differs')
    raw+=reply
    for key in ('D','V','d','v'):
        reply=link.command(key,REC_PROMPT)
        r.require(reply==key.encode()+b'\r\nREFUSED: command\r\nREC> ',key+' must refuse as removed command')
        raw+=reply
    (Path(run)/('b12-help-'+label+'.txt')).write_bytes(raw)
    save(Path(run)/('b12-help-'+label+'.json'),dict(passed=True,hardware=True,
        commands=['?','R','D','V','d','v'],help_verified=True,R_no_valid_RAM_image=True,removed_D_V_refused=True,timeout_message_absent=True,
        RAM_or_flash_load_sent=False))


def b12_wait_probe(link,run):
    b12_help_probe(link,run)
    prompt=link.command('L',b'SEND HEADER+BIN\r\n')
    elapsed=b12_idle(link,12)
    link.send(b'\x03');reply=link.until(REC_PROMPT)
    r.require(reply.endswith(REC_PROMPT) and b'REFUSED' not in reply,'Initial Ctrl-C did not return cleanly to REC')
    b12_help_probe(link,run,'after-cancel')
    (Path(run)/'b12-idle-cancel.txt').write_bytes(prompt+reply)
    save(Path(run)/'b12-idle-cancel.json',dict(passed=True,hardware=True,
        initial_idle_seconds=elapsed,unexpected_RX_bytes=0,Ctrl_C_hex='03',
        returned_to_REC_without_REFUSED=True,flash_command_sent=False))


def b12_runtime_image(body,sector,symbols):
    r.require(len(sector)==4096,'Exact read-only source sector required')
    header=b'OIP1\x01\x00\x00\x80\x00\x10'+bytes(8)
    header+=wire.crc(header).to_bytes(2,'little')
    first=symbols['OI_HEADER']-0x2000
    r.require(symbols['OI_CRC']==symbols['OI_HEADER']+20 and symbols['OI_PAGES']==symbols['OI_CRC']+2
              and body[first:first+23]==bytes(23),'Qualified tool scratch layout differs')
    expected=bytearray(body)
    expected[first:first+23]=header+wire.crc(sector).to_bytes(2,'little')+b'\0'
    return bytes(expected)


def b12_mon_readback(link,run,body,sector,symbols):
    expected=b12_runtime_image(body,sector,symbols)
    raw=link.dump(0x2000,0x1fff+len(body))
    r.require(raw==expected,'Independent MON readback of executed tool differs')
    (Path(run)/'b12-tool-RAM-readback.bin').write_bytes(raw)
    save(Path(run)/'b12-tool-RAM-readback.json',dict(passed=True,hardware=True,bytes=len(raw),
        sha256=r.sha(raw),expected_sha256=r.sha(expected),payload_sha256=r.sha(body),
        runtime_scratch_bytes=23,runtime_scratch_expected_from_exact_OIP_request_and_sector_CRC=True,
        method='MON D hex transport, host decoded bytes; all code/data checked including predicted mutable workspace',
        recovery_D_V_sent_as_transfer=False))


source=Path(frozen.__file__).read_text()
for before,after in (
    ('b06 -> b07','b11 -> b12'),
    ('import deployment_b07 as deployment_plan','import deployment_b12 as deployment_plan'),
    ('from b07_admission import bindings','from b12_admission import bindings'),
    ('deploy-native-b07-bench-core','deploy-native-b12-bench-core'),
    ('Boot : 3 2 1 0','Boot : 6 5 4 3 2 1 0'),
    ('RAM recovery L/R/D/V A/B','Recovery L/R A/B 0-3 C1/2/3 ?'),
    ("source='2.0proto b06'","source='2.0proto b11'"),
    ("'source-b06'","'source-b11'"),
    ('native b06 repeated capture','native b11 repeated capture'),
    ('pr04-b07-bench-core','pr04-b12-bench-core'),
    ('b07 startup','b12 startup'),('ordered b07 physical','ordered b12 physical'),
    ("        link.command('C1', REC_PROMPT)","        link.command('C1', REC_PROMPT)\n        b12_wait_probe(link,run)"),
    ('    packet = rlp_header(body) + body','    link.b12_binary_wait_seconds = b12_idle(link,3)\n    packet = rlp_header(body) + body'),
    ('        rlp_load_readback(link, body)', '''        rlp_load_readback(link, body)
        save(Path(run)/'b12-delayed-binary.json',dict(passed=True,hardware=True,
             initial_idle_seconds=link.b12_binary_wait_seconds,verified_payload_bytes=len(body),
             payload_contains_03=3 in body,RLP1_header_payload_CRC_accepted=True,verification_method='MON RAM readback after safe OIP execution'))
        state.update(initial_L_wait_Ctrl_C_verified=True,delayed_binary_load_verified=True)'''),
):
    assert before in source,before
    source=source.replace(before,after)
start=source.index('def rlp_load_readback(')
stop=source.index('\ndef oip_read_only(',start)
load=source[start:stop]
cut=load.index("    link.send(b'V")
source=source[:start]+load[:cut]+source[stop:]
source=source.replace('LOADED; R runs, V reads back','LOADED; R runs')
source=source.replace('rlp_load_readback','rlp_load')
needle="        select_ftdi(link, build, expected, run, 'target-after-probe')"
assert source.count(needle)==1
source=source.replace(needle,"        b12_mon_readback(link,run,body,expected[0][:4096],symbols['core/ram-installer'])\n        state.update(MON_tool_RAM_readback_verified=True)\n"+needle)

before='        state.update(application_RAM_restore_pending=False, RAM_restored=True,'
after='''        owner_zp=(Path(plan)/'capture/owner-zp.bin').read_bytes()
        r.require(len(owner_zp)==0xe0,'Fresh owner ZP escrow missing')
        for _ in range(2):r.require(link.dump(0,0xdf)==owner_zp,'Original owner ZP00-DF differs')
        state.update(owner_ZP_preserved=True,final_owner_ZP_rereads=2)
'''+before
assert source.count(before)==1
source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
