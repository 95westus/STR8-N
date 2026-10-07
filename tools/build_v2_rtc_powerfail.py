"""Build beta7 outage-aware banner while preserving beta6 build evidence."""
import build_v2_rtc_banner as banner

OUT = banner.ROOT/'BUILD/v2-rtc-powerfail'
VERSION = '2.0b7'
GENERATION = 16


def main():
    banner.OUT,banner.VERSION,banner.GENERATION=OUT,VERSION,GENERATION
    banner.BANNER_SOURCE='rtc-powerfail-banner.asm'
    banner.main()


if __name__=='__main__':
    main()
