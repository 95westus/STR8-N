"""Restore RAM around the original 816 debugger's live $0700 stack.

The omitted page is restored only after bf1 takes over; never claim a full
application restoration while this stock debugger is running.
"""
import hashlib

FIRST=0x200
LAST=0x6500
PROTECTED_FIRST=0x700
PROTECTED_LAST=0x800

def restore_safe(link,original):
    original=bytes(original)
    if len(original)!=LAST-FIRST:
        raise ValueError('Exact application RAM archive required')
    for address in range(FIRST,LAST,256):
        if PROTECTED_FIRST<=address<PROTECTED_LAST:
            continue
        data=original[address-FIRST:address-FIRST+256]
        link.protocol(2)
        link.send(address.to_bytes(3,'little')+len(data).to_bytes(3,'little')+data)
        if link.exact(1)!=b'\0' or link.stock_read(address,len(data))!=data:
            raise IOError('Safe stock RAM restore readback differs')
    for first,last in ((FIRST,PROTECTED_FIRST),(PROTECTED_LAST,LAST)):
        if link.stock_read(first,last-first)!=original[first-FIRST:last-FIRST]:
            raise IOError('Final safe RAM range differs')
    return dict(passed=True,application_ram_restored=False,
        protected_first=PROTECTED_FIRST,protected_last=PROTECTED_LAST-1,
        deferred_bytes=256,verified_bytes=len(original)-256,
        original_sha256=hashlib.sha256(original).hexdigest(),execution_requested=False)

def safe_ranges_equal(actual,original):
    return len(actual)==len(original)==LAST-FIRST and all(
        actual[a-FIRST:b-FIRST]==original[a-FIRST:b-FIRST]
        for a,b in ((FIRST,PROTECTED_FIRST),(PROTECTED_LAST,LAST)))
