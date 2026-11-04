"""2512 b11 update/boot verification, with live idle-cancel and delayed RX probes."""
from pathlib import Path
import board_b07_2512 as frozen


def b11_idle(link,seconds):
    start=time.monotonic();raw=bytearray(link.pending);link.pending.clear()
    while time.monotonic()-start<seconds:raw.extend(link.read(4096))
    r.require(not raw,'Unexpected output while awaiting first byte; raw serial evidence retained')
    return time.monotonic()-start


def b11_help_probe(link,run,label='fresh'):
    from build_b11 import HELP
    raw=link.command('?',REC_PROMPT)
    r.require(HELP in raw and b'REFUSED' not in raw,'Recovery ? help differs')
    for key in ('R','V'):
        reply=link.command(key,REC_PROMPT)
        r.require(b'REFUSED: no valid RAM image\r\n' in reply and b'timeout' not in reply,
                  key+' absent-image diagnostic differs')
        raw+=reply
    (Path(run)/('b11-help-'+label+'.txt')).write_bytes(raw)
    save(Path(run)/('b11-help-'+label+'.json'),dict(passed=True,hardware=True,
        commands=['?','R','V'],help_verified=True,R_V_no_valid_RAM_image=True,timeout_message_absent=True,
        RAM_or_flash_load_sent=False))


def b11_wait_probe(link,run):
    b11_help_probe(link,run)
    prompt=link.command('L',b'SEND HEADER+BIN\r\n')
    elapsed=b11_idle(link,12)
    link.send(b'\x03');reply=link.until(REC_PROMPT)
    r.require(reply.endswith(REC_PROMPT) and b'REFUSED' not in reply,'Initial Ctrl-C did not return cleanly to REC')
    b11_help_probe(link,run,'after-cancel')
    (Path(run)/'b11-idle-cancel.txt').write_bytes(prompt+reply)
    save(Path(run)/'b11-idle-cancel.json',dict(passed=True,hardware=True,
        initial_idle_seconds=elapsed,unexpected_RX_bytes=0,Ctrl_C_hex='03',
        returned_to_REC_without_REFUSED=True,flash_command_sent=False))


source=Path(frozen.__file__).read_text()
for before,after in (
    ('b06 -> b07','b10 -> b11'),
    ('import deployment_b07 as deployment_plan','import deployment_b11 as deployment_plan'),
    ('from b07_admission import bindings','from b11_admission import bindings'),
    ('deploy-native-b07-bench-core','deploy-native-b11-bench-core'),
    ('Boot : 3 2 1 0','Boot : 6 5 4 3 2 1 0'),
    ('RAM recovery L/R/D/V A/B','Recovery L/R/D/V A/B 0-3'),
    ("source='2.0proto b06'","source='2.0proto b10'"),
    ("'source-b06'","'source-b10'"),
    ('native b06 repeated capture','native b10 repeated capture'),
    ('pr04-b07-bench-core','pr04-b11-bench-core'),
    ('b07 startup','b11 startup'),('ordered b07 physical','ordered b11 physical'),
    ("        link.command('C1', REC_PROMPT)","        link.command('C1', REC_PROMPT)\n        b11_wait_probe(link,run)"),
    ('    packet = rlp_header(body) + body','    link.b11_binary_wait_seconds = b11_idle(link,3)\n    packet = rlp_header(body) + body'),
    ('        rlp_load_readback(link, body)', '''        rlp_load_readback(link, body)
        save(Path(run)/'b11-delayed-binary.json',dict(passed=True,hardware=True,
             initial_idle_seconds=link.b11_binary_wait_seconds,verified_payload_bytes=len(body),
             payload_contains_03=3 in body,RLP1_header_payload_and_V_readback_CRC_verified=True))
        state.update(initial_L_wait_Ctrl_C_verified=True,delayed_binary_load_verified=True)'''),
):
    assert before in source,before
    source=source.replace(before,after)
before='        state.update(application_RAM_restore_pending=False, RAM_restored=True,'
after='''        owner_zp=(Path(plan)/'capture/owner-zp.bin').read_bytes()
        r.require(len(owner_zp)==0xe0,'Fresh owner ZP escrow missing')
        for _ in range(2):r.require(link.dump(0,0xdf)==owner_zp,'Original owner ZP00-DF differs')
        state.update(owner_ZP_preserved=True,final_owner_ZP_rereads=2)
'''+before
assert source.count(before)==1
source=source.replace(before,after)
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
