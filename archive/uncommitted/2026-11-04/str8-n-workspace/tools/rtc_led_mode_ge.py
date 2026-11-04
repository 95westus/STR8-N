"""Versioned2512 MON gE admission; original instruments/config stay intact."""
import rtc_drift_campaign as c
import rtc_led_mode as oldmode
import rtc_led_collect as old
import rtc_led_collect_ge as ge
import rtc_led_dispatch as dispatch
OLD_COLLECT=old.collect
CONFIG=c.Q/'rtc-led-ge-2512.json'
def enabled(state):return oldmode.enabled(state)
def ready(state):
    if not CONFIG.exists():return False
    cfg=c.read(CONFIG)
    if not cfg.get('qualified'):return False
    assert cfg['board']=='2512' and cfg['monitor_generation']=='0000000E'
    assert cfg['driver_sha256']==c.sha(ge.__file__)
    item=cfg['qualification'];assert item['board']=='2512'
    ge.audit_board(item,state)
    return True
def campaign(state,admitted,skipped):
    assert enabled(state)
    selected=list(admitted);skipped=list(skipped)
    is_ge=state['board_admission']['2512'].get('monitor_generation')=='0000000E'
    if is_ge and '2512' in selected and not ready(state):
        selected.remove('2512');skipped.append(dict(board='2512',error='MON gE RTC readmission pending; no port opened'))
    def collect(board,folder):
        return ge.collect(board,folder) if board=='2512' and is_ge else OLD_COLLECT(board,folder)
    before_collect,before_audit=old.collect,old.audit_board
    try:
        old.collect=collect;old.audit_board=dispatch.audit_board
        return oldmode.campaign(state,selected,skipped)
    finally:old.collect=before_collect;old.audit_board=before_audit
