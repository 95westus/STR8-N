"""Build unflashed beta9 RTCC messages; retain qualified beta8 artifacts."""
import build_v2_rtc_journal as journal
import build_bank_maint_rtc as maintenance

OUT=journal.ROOT/'BUILD/v2-rtc-messages'

def main():
    journal.OUT=OUT;journal.VERSION='2.0b9';journal.GENERATION=18
    journal.main()
    maintenance.OUT=OUT/'maint';maintenance.KERNEL_OUT=OUT
    maintenance.VERSION='1.7';maintenance.JOURNAL=True;maintenance.main()

if __name__=='__main__':main()
