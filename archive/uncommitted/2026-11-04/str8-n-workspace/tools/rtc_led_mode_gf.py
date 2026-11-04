"""2512 gF qualification gate; prior modes/instruments remain intact."""
import rtc_drift_campaign as c
import rtc_led_mode_ge as previous
import rtc_led_mode as original_mode
import rtc_led_collect as original
import rtc_led_collect_gf as gf
import rtc_led_dispatch_gf as dispatch
CONFIG=c.Q/'rtc-led-gf-2512.json'
def enabled(state):return previous.enabled(state)
def ready(state):
    if not CONFIG.exists():return False
    cfg=c.read(CONFIG)
    if not cfg.get('qualified'):return False
    assert cfg['board']=='2512' and cfg['monitor_generation']=='0000000F'
    assert cfg['driver_sha256']==c.sha(gf.__file__)
    assert cfg['qualification']['board']=='2512'
    gf.audit_board(cfg['qualification'],state)
    return True
def campaign(state,admitted,skipped):
    if state['board_admission']['2512'].get('monitor_generation')!='0000000F':return previous.campaign(state,admitted,skipped)
    assert enabled(state)
    selected=list(admitted);skipped=list(skipped)
    if '2512' in selected and not ready(state):
        selected.remove('2512');skipped.append(dict(board='2512',error='MON gF RTC readmission pending; no port opened'))
    saved_collect,saved_audit=original.collect,original.audit_board
    def collect(board,folder):return gf.collect(board,folder) if board=='2512' else saved_collect(board,folder)
    try:
        original.collect=collect;original.audit_board=dispatch.audit_board
        return original_mode.campaign(state,selected,skipped)
    finally:original.collect=saved_collect;original.audit_board=saved_audit
