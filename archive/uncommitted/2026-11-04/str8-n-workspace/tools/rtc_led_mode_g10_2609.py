"""2609 g10 admission; keep2512 g10 and all legacy routing unchanged."""
import rtc_drift_campaign as c
import rtc_led_mode_g10 as previous
import rtc_led_mode as original_mode
import rtc_led_collect as original
import rtc_led_collect_g10 as board2512
import rtc_led_collect_g10_2609_r2 as board2609
import rtc_led_dispatch_g10_2609 as dispatch
CONFIG=c.Q/'rtc-led-g10-2609.json'

def enabled(state):return previous.enabled(state)

def ready(state):
    if not CONFIG.exists():return False
    cfg=c.read(CONFIG)
    if not cfg.get('qualified'):return False
    assert cfg['board']=='2609' and cfg['monitor_generation']=='00000010'
    assert cfg['driver_sha256']==c.sha(board2609.__file__) and cfg['qualification']['board']=='2609'
    board2609.audit_board(cfg['qualification'],state)
    return True

def campaign(state,admitted,skipped):
    if state['board_admission']['2609'].get('monitor_generation')!='00000010':return previous.campaign(state,admitted,skipped)
    assert enabled(state)
    selected=list(admitted);skipped=list(skipped)
    for board,isready in (('2609',ready(state)),('2512',previous.ready(state))):
      if board in selected and not isready:
        selected.remove(board);skipped.append(dict(board=board,error='MON g10 RTC readmission pending; no port opened'))
    saved_collect,saved_audit=original.collect,original.audit_board
    def collect(board,folder):
      if board=='2609':return board2609.collect(board,folder)
      if board=='2512' and state['board_admission']['2512'].get('monitor_generation')=='00000010':return board2512.collect(board,folder)
      return saved_collect(board,folder)
    try:
      original.collect=collect;original.audit_board=dispatch.audit_board
      return original_mode.campaign(state,selected,skipped)
    finally:original.collect=saved_collect;original.audit_board=saved_audit
