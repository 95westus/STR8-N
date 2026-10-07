import build_v2_clock as base

OUT=base.ROOT/'BUILD/v2-clock-1.1'


def main():
    base.OUT=OUT
    base.SOURCE_NAME='clock-powerfail.asm'
    base.VERSION='1.1'
    base.main()


if __name__=='__main__':
    main()
