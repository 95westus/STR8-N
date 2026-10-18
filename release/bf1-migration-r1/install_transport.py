"""Shared bounded RAM installer transport. No port enumeration, reset or setters."""
import hashlib,json,time
from pathlib import Path
import legacy_transport as wire

def require(value,message):
    if not value:raise ValueError(message)

def execute(link,plan_root,*,stock=False,host_readback=True,progress=None):
    root=Path(plan_root);plan=json.loads((root/'plan.json').read_text())
    installer=root/'installer-model-only.s19'
    require(hashlib.sha256(installer.read_bytes()).hexdigest()==plan['installer_sha256'],'Changed RAM installer')
    cells,entry=wire.read_s19(installer)
    operations=plan['transaction']['operations'] if stock else plan['transaction']['operations'][1:]
    transfers=[]
    for n,op in enumerate(operations):
        raw=(root/f'transfer-{n:02d}.bin').read_bytes();require(len(raw)==4096,'Short transfer')
        body=bytearray(raw)
        if op['commit_address'] is not None:
            body[op['commit_address']-op['address']]=(root/f"expected-b{op['bank']}.bin").read_bytes()[op['commit_address']-0x8000]
        require(hashlib.sha256(body).hexdigest()==op['data_sha256'],'Changed transfer payload')
        transfers.append(raw)
    if host_readback:
        if stock:link.stock_load(cells,entry)
        else:link.monitor_load(installer)
    elif stock:
        for start in range(min(cells),max(cells)+1,256):
            body=bytes(cells[x] for x in range(start,min(start+256,max(cells)+1)))
            link.protocol(2);link.send(start.to_bytes(3,'little')+len(body).to_bytes(3,'little')+body)
            require(link.exact(1)==b'\0','Stock RAM load rejected; execution forbidden')
        link.protocol(6);link.send(entry.to_bytes(3,'little'))
    else:
        link.command('L',b'S19')
        for row in installer.read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
        loaded=link.until(b'\r\nB3> ')
        require(f'Entry {entry:04X}'.encode() in loaded and not any(v in loaded for v in (b'Bad',b'Protected',b'Wrap',b'Error')),'RAM loader refused image')
        link.send(f'G {entry:04X}\r'.encode())
    link.until(b'Y then Enter> ');link.send(b'Y\r')
    for n,(op,body) in enumerate(zip(operations,transfers)):
        link.until(f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode(),90)
        for offset in range(0,4096,64):link.send(body[offset:offset+64]);time.sleep(.01)
        if progress:progress(n+1,op)
    result=link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90)
    return dict(transaction_device_verified=True,physical_reset_pending=True,transfers_completed=len(transfers),
        host_memory_readbacks=host_readback,result=result.decode('ascii','replace'))
