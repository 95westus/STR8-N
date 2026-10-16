"""Generation 35: one bounded FTDI FIFO drain before startup input opens."""
import json
import build_v2_startup_keys as build

def patch(text):
    marker='                        LDY #$A0\nBOOT_STARTUP_DOTS:'
    assert text.count(marker)==1
    text=text.replace(marker,'                        JSR BOOT_FIFO_DRAIN\n'+marker,1)
    # Reclaim alignment padding, keeping the shared F router at its old address.
    marker='                        DB $FF,$FF,$FF\n'
    assert text.count(marker)==1;text=text.replace(marker,'',1)
    # Keep journal/CRC/core identity addresses stable by exchanging 18 bytes of
    # recovery status text for the bounded helper. Menu and update syntax stay.
    for old,new in (('SEND 4096 SLOT BIN','SEND 4096 BIN'),('IMAGE COMMITTED','COMMITTED'),('REFUSED/FAILED','REFUSED')):
        assert text.count(old)==1;text=text.replace(old,new,1)
    helper='''; Read at most 4*256 pending FTDI bytes, stopping at the first empty poll.
; No wait for more input; reset software buffering once, before input opens.
BOOT_FIFO_DRAIN:        LDY #$04
                        LDX #$00
BOOT_FIFO_DRAIN_NEXT:   JSR V2W_RAW_POLL
                        BCC BOOT_FIFO_DRAIN_DONE
                        DEX
                        BNE BOOT_FIFO_DRAIN_NEXT
                        DEY
                        BNE BOOT_FIFO_DRAIN_NEXT
BOOT_FIFO_DRAIN_DONE:   JMP V2W_RX_RESET
'''
    text=text.replace('BOOT_COMPAT_DATA:',helper+'BOOT_COMPAT_DATA:',1)
    return text

def main():
    build.OLD=build.ROOT/'BUILD/v2-startup-keys'
    build.OUT=build.ROOT/'BUILD/v2-startup-fifo'
    build.GENERATION=35;build.patch=patch;build.main()
    path=build.OUT/'build.json';meta=json.loads(path.read_text())
    meta.update(startup_fifo_drain=True,startup_fifo_drain_limit=1024)
    path.write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':main()
