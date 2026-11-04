"""Preserve historical gD audits; dispatch only qualified gE2512 receipts."""
import rtc_drift_campaign as c
import rtc_led_collect as old
import rtc_led_collect_ge as ge
OLD_AUDIT=old.audit_board
def audit_board(item,state):
    report=c.read(item['report'])
    if item['board']=='2512' and report['driver_sha256']==c.sha(ge.__file__):return ge.audit_board(item,state)
    return OLD_AUDIT(item,state)
