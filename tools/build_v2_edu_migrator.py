"""Build beta15 RAM installer; commit WORK only after both B/C sectors verify."""
import build_v2_rtc_migrator as base
from build_v2_spi_resident import OUT
def main():
    base.OUT=OUT/'migrator';base.VERSION='2.0b15';base.MULTI_COMMIT=True;base.COMMIT_ADDRESS=0xB003;base.main()
if __name__=='__main__':main()
