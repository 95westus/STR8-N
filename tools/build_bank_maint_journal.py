import build_bank_maint_rtc as base
from build_v2_rtc_journal import OUT

def main():
    base.OUT=OUT/'maint';base.KERNEL_OUT=OUT;base.VERSION='1.7';base.JOURNAL=True;base.main()

if __name__=='__main__':main()
