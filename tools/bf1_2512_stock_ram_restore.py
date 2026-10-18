"""Bounded stock-debugger application RAM restoration; never executes RAM."""
import hashlib

def restore(link,original):
    original=bytes(original)
    if len(original)!=0x6300:raise ValueError('Exact $0200-$64FF application RAM archive required')
    for offset in range(0,len(original),256):
        address=0x200+offset;data=original[offset:offset+256]
        link.protocol(2);link.send(address.to_bytes(3,'little')+len(data).to_bytes(3,'little')+data)
        if link.exact(1)!=b'\0' or link.stock_read(address,len(data))!=data:raise IOError('Stock application RAM restore readback mismatch')
    actual=link.stock_read(0x200,len(original))
    if actual!=original:raise IOError('Full application RAM restoration verification failed')
    return dict(passed=True,first=0x200,last=0x64ff,bytes=len(actual),sha256=hashlib.sha256(actual).hexdigest(),execution_requested=False)
