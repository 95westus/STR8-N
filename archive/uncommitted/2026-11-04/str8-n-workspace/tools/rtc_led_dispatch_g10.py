"""Retain old receipt audits; add only2512 g10."""
import rtc_drift_campaign as c
import rtc_led_dispatch_gf as previous
import rtc_led_collect_g10 as current
def audit_board(item,state):
    r=c.read(item['report'])
    if item['board']=='2512' and r['driver_sha256']==c.sha(current.__file__):return current.audit_board(item,state)
    return previous.audit_board(item,state)
