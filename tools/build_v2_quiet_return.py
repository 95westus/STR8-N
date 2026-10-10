"""Build beta19 quiet monitor returns separately from the pinned beta18 flash."""
from build_v2_trim_display import main

if __name__=='__main__':
    main(out='BUILD/v2-quiet-return',version='2.0b19',generation=28)
