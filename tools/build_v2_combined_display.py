"""Build beta20: quiet returns, UTC weekday and boot/TIME trim correction."""
import build_v2_status as status
from build_v2_trim_display import main

if __name__=='__main__':
    status.WEEKDAY_DISPLAY=True
    main(out='BUILD/v2-combined-display',version='2.0b20',generation=29)
