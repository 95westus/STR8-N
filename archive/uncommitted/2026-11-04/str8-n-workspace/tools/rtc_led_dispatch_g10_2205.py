"""2205 Foundation receipt audit; retain all previous instrument audits."""
import rtc_drift_campaign as c
import rtc_led_dispatch_g10_2604 as previous
import rtc_led_collect_g10_2205 as current

def audit_board(item,state):
    r=c.read(item['report'])
    if item['board']=='2205' and r['driver_sha256']==c.sha(current.__file__):return current.audit_board(item,state)
    return previous.audit_board(item,state)
