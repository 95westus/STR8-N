"""Preserve gD/gE receipt audits; add only2512 gF."""
import rtc_drift_campaign as c
import rtc_led_dispatch as previous
import rtc_led_collect_gf as gf
def audit_board(item,state):
    r=c.read(item['report'])
    if item['board']=='2512' and r['driver_sha256']==c.sha(gf.__file__):return gf.audit_board(item,state)
    return previous.audit_board(item,state)
