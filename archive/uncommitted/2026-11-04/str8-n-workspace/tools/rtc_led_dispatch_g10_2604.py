"""Add2604 Foundation receipt audit; retain every earlier instrument audit."""
import rtc_drift_campaign as c
import rtc_led_dispatch_g10_2609 as previous
import rtc_led_collect_g10_2604_r2 as current


def audit_board(item,state):
    r=c.read(item['report'])
    if item['board']=='2604' and r['driver_sha256']==c.sha(current.__file__):
        return current.audit_board(item,state)
    return previous.audit_board(item,state)
