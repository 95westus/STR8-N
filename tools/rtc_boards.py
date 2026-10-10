"""USB identities for RTC analysis, separate from firmware qualification."""
from install_v2_rtc_upgrade import SERIALS as QUALIFIED_SERIALS

SERIALS = dict(QUALIFIED_SERIALS, **{'2604': 'A10MQGVHA'})
