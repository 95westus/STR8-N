import build_v2_clock as base
OUT=base.ROOT/'BUILD/v2-clock-1.2'


def main():
    base.OUT=OUT;base.SOURCE_NAME='clock-journal.asm';base.VERSION='1.2';base.MAX_END=0x4000;base.main()


if __name__=='__main__':main()
