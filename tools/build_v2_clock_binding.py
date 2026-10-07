import build_v2_clock as base
OUT=base.ROOT/'BUILD/v2-clock-1.4'

def main():
    base.OUT=OUT;base.SOURCE_NAME='clock-binding.asm';base.VERSION='1.4';base.MAX_END=0x4000;base.main()

if __name__=='__main__':main()
