"""Qualification gate for the owner-requested physical seconds display."""
from pathlib import Path
import rtc_drift_campaign as c
import rtc_led_collect as led
def enabled(state):
 if not led.CONFIG.exists():return False
 cfg=c.read(led.CONFIG)
 if not cfg.get('enabled'):return False
 assert cfg['profile']==led.PROFILE and cfg['driver_sha256']==c.sha(led.__file__)
 assert cfg['mode_sha256']==c.sha(__file__) and cfg['image_sha256']==led.IMAGE_SHA
 enabled=set(cfg['enabled_boards']);blocked=set(cfg['blocked_boards'])
 assert enabled and enabled|blocked==set(c.BOARDS) and not enabled&blocked
 p=Path(cfg['qualification_summary']);assert c.sha(p)==cfg['qualification_summary_sha256']
 proof=c.read(p);assert proof['passed'] and {x['board'] for x in proof['boards']}==enabled
 for item in proof['boards']:
  assert item['capture_profile']==led.PROFILE and item['RAM_restored']
  led.audit_board(item,state)
 led.load();return True
def campaign(state,admitted,skipped):
 assert enabled(state)
 cfg=c.read(led.CONFIG);selected=[b for b in admitted if b in cfg['enabled_boards']]
 skipped=list(skipped)+[dict(board=b,error='Owner holds board blocked; no port opened') for b in admitted if b in cfg['blocked_boards']]
 return led.campaign(state,selected,skipped)
