"""2205 Foundation routing; preserve the other three qualified readers."""
import rtc_drift_campaign as c
import rtc_led_mode_g10_2604 as previous
import rtc_led_mode as original_mode
import rtc_led_collect as original
import rtc_led_collect_g10_2205 as board2205
import rtc_led_dispatch_g10_2205 as dispatch
CONFIG=c.Q/'rtc-led-g10-2205.json'

def enabled(state):return previous.enabled(state)

def ready(state):
    if not CONFIG.exists():return False
    cfg=c.read(CONFIG)
    if not cfg.get('qualified'):return False
    assert cfg['board']=='2205' and cfg['monitor_generation']=='00000010'
    assert cfg['driver_sha256']==c.sha(board2205.__file__)
    board2205.audit_board(cfg['qualification'],state)
    return True

def campaign(state,admitted,skipped):
    if state['board_admission']['2205'].get('monitor_generation')!='00000010':return previous.campaign(state,admitted,skipped)
    assert enabled(state)
    selected=list(admitted);skipped=list(skipped)
    for board,available in (('2205',ready(state)),('2604',previous.ready(state)),('2609',previous.previous.ready(state)),('2512',previous.previous.previous.ready(state))):
        if board in selected and not available:
            selected.remove(board);skipped.append(dict(board=board,error='MONg10 RTC readmission pending; no port opened'))
    saved_collect,saved_audit=original.collect,original.audit_board
    def collect(board,folder):
        if board=='2205':return board2205.collect(board,folder)
        if board=='2604':return previous.board2604.collect(board,folder)
        if board=='2609':return previous.board2609.collect(board,folder)
        if board=='2512' and state['board_admission']['2512'].get('monitor_generation')=='00000010':return previous.board2512.collect(board,folder)
        return saved_collect(board,folder)
    try:
        original.collect=collect;original.audit_board=dispatch.audit_board
        return original_mode.campaign(state,selected,skipped)
    finally:original.collect=saved_collect;original.audit_board=saved_audit
