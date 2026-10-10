"""Build the beta13 guarded RAM installer; no board access."""
import build_v2_rtc_migrator as base
from build_v2_rtc_trim import OUT

def main():
    base.OUT=OUT/'migrator';base.VERSION='2.0b13';base.MULTI_COMMIT=True;base.main()

if __name__=='__main__':main()
