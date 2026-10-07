"""Build a guarded RAM installer for beta12; never opens serial ports."""
import build_v2_rtc_migrator as base
from build_v2_rtc_binding import OUT
def main():
    base.OUT=OUT/'migrator';base.VERSION='2.0b12';base.MULTI_COMMIT=True;base.main()
if __name__=='__main__':main()
