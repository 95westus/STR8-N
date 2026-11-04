"""Single-owner serial console and paced BASE1 RAM loading. No GUI/port on import."""
import hashlib
import json
import re
from pathlib import Path
import time

REC=b'REC> '
SEND_BIN=b'SEND BIN\r\n'
SEND_S19=b'SEND S19 (S0/S1/S9); Ctrl-C cancels\r\n'
RAM_LIMIT=0x6300


class ConsoleError(ValueError):
    pass


def checked_s19(body):
    """Validate a complete RAM S0/S1/S9 file before transmitting any byte."""
    if not 0<len(body)<=2*1024*1024:raise ConsoleError('S19 file must contain 1-2097152 bytes')
    lines=body.splitlines();wire=[];finished=False;data=False
    for number,line in enumerate(lines,1):
        line=line.strip().upper()
        if not line:continue
        if finished:raise ConsoleError(f'S19 line {number}: record after S9')
        if len(line)<10 or line[:2] not in (b'S0',b'S1',b'S9') or not re.fullmatch(rb'S[019][0-9A-F]+',line):
            raise ConsoleError(f'S19 line {number}: expected S0/S1/S9 hexadecimal record')
        try:raw=bytes.fromhex(line[2:].decode('ascii'))
        except ValueError:raise ConsoleError(f'S19 line {number}: odd hexadecimal length') from None
        if len(raw)!=raw[0]+1 or raw[0]<3 or sum(raw)&255!=255:
            raise ConsoleError(f'S19 line {number}: length/checksum mismatch')
        address=int.from_bytes(raw[1:3],'big');size=len(raw)-4
        if line[1:2]==b'1':
            if not size or not 0x200<=address<=address+size-1<=0x66FF:
                raise ConsoleError(f'S19 line {number}: RAM destination must fit 0200-66FF')
            data=True
        elif line[1:2]==b'9':
            if size:raise ConsoleError(f'S19 line {number}: S9 must have no data')
            finished=True
        wire.append(line+b'\r\n')
    if not finished or not data:raise ConsoleError('S19 needs data records and a final S9')
    return b''.join(wire)


def s19_image(path):
    path=Path(path).expanduser().resolve()
    if path.suffix.lower() not in ('.s19','.srec'):raise ConsoleError('Choose an ASCII .s19 or .srec RAM file')
    body=checked_s19(path.read_bytes())
    return path,body,hashlib.sha256(body).hexdigest()


def ram_image(path,kit=None):
    """Snapshot bytes before sending L; reject known ROMs and incompatible frames."""
    path=Path(path).expanduser().resolve()
    body=path.read_bytes()
    if path.suffix.lower()!='.bin':raise ConsoleError('Raw L needs a binary .bin RAM image, not S19/text')
    if not 0<len(body)<=RAM_LIMIT:raise ConsoleError('RAM BIN must contain 1-25344 bytes for 0200-64FF')
    if body[0]==3:raise ConsoleError('First byte is Ctrl-C: F would cancel this BIN')
    if ((body[:4]==b'SN\x02\0' and len(body)==4096) or body[:3]==b'MI\x01'
            or body[:4] in (b'ES\x01\x40',b'VX\x01\x40')):
        raise ConsoleError('This is a flash component, not a RAM BIN for recovery L')
    digest=hashlib.sha256(body).hexdigest()
    if kit is not None:
        manifest=Path(kit)/'firmware/minimal-manifest.json'
        if manifest.exists():
            records=json.loads(manifest.read_text())['artifacts']
            record=records.get(path.name)
            if record is not None:
                if record['address']!='0200' or record['entry']!='0200':
                    raise ConsoleError('Selected release component is not a RAM tool')
                if len(body)!=record['bytes'] or digest!=record['sha256']:
                    raise ConsoleError('Release RAM tool does not match its manifest')
    return path,body,digest


class Session:
    """Call only from one I/O owner. Tests supply fake ports and a fake clock."""
    def __init__(self,emit=lambda *event:None,*,clock=time.monotonic,chunk=16,pause=.003):
        self.emit,self.clock=emit,clock
        self.chunk,self.pause=chunk,pause
        self.port=None
        self.mode='idle'
        self.prompt=None
        self.tail=bytearray()
        self.transfer=None
        self.last_transfer=None
        self.deadline=0
        self.next_chunk=0
        self.close_pending=False
        self.text_pending=bytearray()
        self.next_text=0

    @property
    def busy(self):return self.mode!='idle'

    def attach(self,port):
        if self.port is not None:raise ConsoleError('Disconnect before changing ports')
        self.port=port;self.prompt=None;self.tail.clear();self.close_pending=False
        self.emit('connected',True)

    def _write(self,body):
        if self.port is None:raise ConsoleError('Connect first (F10)')
        body=bytes(body)
        if self.port.write(body)!=len(body):raise IOError('Short serial write')
        self.emit('tx',body)

    def _forget_prompt(self):
        self.prompt=None;self.tail.clear()

    def receive(self,body):
        if not body:return
        self.emit('rx',body)
        self.tail.extend(body)
        if len(self.tail)>512:del self.tail[:-512]
        self.prompt=('rec' if self.tail.endswith(REC) else 'send-bin' if self.tail.endswith(SEND_BIN)
                     else 'send-s19' if self.tail.endswith(SEND_S19) else
                     'mon' if re.search(rb'B[0-3]> $',self.tail) else None)
        if self.mode in ('s19-sending','s19-result'):
            if b'S19 stopped $' in self.tail:
                self.mode='s19-result';self.deadline=self.clock()+10
            if self.prompt in ('mon','rec'):self._finish_s19()
        if self.mode=='waiting' and self.prompt=='send-bin':
            self.mode='sending';self.next_chunk=self.clock()
            self.emit('status','SEND BIN received; sending exact bytes')

    def terminal(self,body):
        if self.busy:raise ConsoleError('File transfer owns the port; terminal input is paused')
        if self.port is None:raise ConsoleError('Connect first (F10)')
        self.text_pending.extend(body);self._forget_prompt()

    def start(self,path,body,digest,*,from_recovery):
        if self.port is None:raise ConsoleError('Connect first (F10)')
        if self.busy:raise ConsoleError('A transfer is already in progress')
        if self.text_pending:raise ConsoleError('Wait for queued terminal text and a new board prompt')
        if not 0<len(body)<=RAM_LIMIT or body[0]==3 or hashlib.sha256(body).hexdigest()!=digest:
            raise ConsoleError('Invalid RAM snapshot')
        expected='rec' if from_recovery else 'send-bin'
        if self.prompt!=expected:
            raise ConsoleError('Wait for REC> before F4/preset loading' if from_recovery else
                               'F3 needs SEND BIN; type L at REC>, or use F4')
        self.transfer=dict(path=str(path),body=bytes(body),sha256=digest,sent=0)
        self.emit('busy',True)
        self._forget_prompt()
        if from_recovery:
            self.mode='waiting';self.deadline=self.clock()+15
            self._write(b'L\r')
            self.emit('status','Sent L; waiting for SEND BIN (no payload sent yet)')
        else:
            self.mode='sending';self.next_chunk=self.clock()

    def start_s19(self,path,body,digest):
        if self.port is None:raise ConsoleError('Connect first (F10)')
        if self.busy or self.text_pending:raise ConsoleError('Wait for the current transfer/terminal text')
        if self.prompt!='send-s19':raise ConsoleError('S19 send needs the RAM loader SEND S19 prompt; no L or YES is sent')
        if checked_s19(body)!=body or hashlib.sha256(body).hexdigest()!=digest:raise ConsoleError('Invalid S19 snapshot')
        self.transfer=dict(path=str(path),body=bytes(body),sha256=digest,sent=0,format='S19',cancelled=False)
        self.mode='s19-sending';self.next_chunk=self.clock();self._forget_prompt()
        self.emit('busy',True);self.emit('status','Sending checked RAM S19; entry will not run')

    def _finish_s19(self,error=None):
        transfer=self.transfer
        accepted=not error and b'S19 loaded; entry $' in self.tail and transfer['sent']==len(transfer['body']) and not transfer['cancelled']
        result=dict(transfer,body=None,host_complete=transfer['sent']==len(transfer['body']),
                    board_accepted=bool(accepted),board_readback_verified=False)
        if accepted:self.last_transfer=(transfer['path'],transfer['body'],transfer['sha256'])
        self.transfer=None;self.mode='idle';self.emit('busy',False);self.emit('transfer',result)
        if accepted:self.emit('status','Board accepted RAM S19; entry not run; no independent readback yet')
        elif transfer['cancelled']:self.emit('status','S19 canceled; earlier complete records may remain')
        else:self.emit('error',error or 'Board stopped S19 before acceptance; earlier complete records may remain')
        if self.close_pending:self.disconnect()

    def cancel(self):
        if self.mode in ('s19-sending','s19-result'):
            self._write(b'\x03');self._forget_prompt();self.transfer['cancelled']=True
            self.mode='s19-result';self.deadline=self.clock()+10
            self.emit('status','S19 Ctrl-C sent; waiting for the board prompt')
            return True
        if self.mode in ('sending','settling') and self.transfer['sent']:
            self.emit('status','Ctrl-C is literal after the first byte; finishing the transfer')
            return False
        # Before payload, Ctrl-C cancels the receiver/line; never inject it into a BIN.
        self.text_pending.clear();self._write(b'\x03');self._forget_prompt()
        if self.transfer is not None:self.emit('transfer',dict(self.transfer,body=None,cancelled=True))
        self.transfer=None;self.mode='idle'
        self.emit('busy',False)
        self.emit('status','Ctrl-C sent before payload; wait for the board prompt')
        if self.close_pending:self.disconnect()
        return True

    def disconnect(self):
        if self.mode in ('s19-sending','s19-result'):
            self.close_pending=True
            if self.mode=='s19-sending':self.cancel()
            self.emit('status','Waiting for S19 result/cancellation before disconnect')
            return False
        if self.mode in ('sending','settling') and self.transfer['sent']:
            self.close_pending=True
            self.emit('status','Disconnect deferred until BIN and idle-to-run interval finish')
            return False
        if self.mode=='waiting' or (self.mode=='sending' and self.transfer and not self.transfer['sent']):
            self.cancel()
        port,self.port=self.port,None
        if port is not None:port.close()
        self.mode='idle';self.transfer=None;self._forget_prompt();self.close_pending=False
        self.text_pending.clear();self.emit('busy',False)
        self.emit('connected',False)
        return True

    def fail(self,error):
        s19=bool(self.transfer and self.transfer.get('format')=='S19')
        partial=bool(self.transfer and (self.transfer['sent'] or self.mode in ('sending','settling')))
        port,self.port=self.port,None
        if port is not None:
            try:port.close()
            except OSError:pass
        self.mode='idle';self.transfer=None;self._forget_prompt();self.close_pending=False
        self.text_pending.clear();self.emit('busy',False)
        message=str(error)
        if partial:message+=('; earlier complete S19 records may remain; entry was not auto-run.' if s19 else
                            '; incomplete raw BIN may run after idle. Inspect/reset the board before continuing.')
        self.emit('connected',False);self.emit('error',message)

    def tick(self):
        if self.port is None:return
        available=min(4096,self.port.in_waiting)
        if available:self.receive(self.port.read(available))
        now=self.clock()
        if self.mode=='s19-sending' and now>=self.next_chunk:
            offset=self.transfer['sent'];part=self.transfer['body'][offset:offset+self.chunk]
            self._write(part);self.transfer['sent']+=len(part);self.next_chunk=self.clock()+self.pause
            self.emit('progress',self.transfer['sent'],len(self.transfer['body']))
            if self.transfer['sent']==len(self.transfer['body']):
                self.mode='s19-result';self.deadline=self.clock()+30
                self.emit('status','S19 bytes sent; waiting for board acceptance and prompt')
        elif self.mode=='s19-result' and now>=self.deadline:
            self._finish_s19('No S19 completion prompt; inspect the board before retrying')
        if self.mode=='idle' and self.text_pending and now>=self.next_text:
            self._write(self.text_pending[:self.chunk]);del self.text_pending[:self.chunk]
            self.next_text=self.clock()+self.pause
        if self.mode=='waiting' and now>=self.deadline:
            self.mode='idle';self.transfer=None;self._forget_prompt()
            self.emit('busy',False)
            self.emit('error','No SEND BIN received; no payload sent. Check the board prompt.')
            if self.close_pending:self.disconnect()
        elif self.mode=='sending' and now>=self.next_chunk:
            transfer=self.transfer;offset=transfer['sent']
            part=transfer['body'][offset:offset+self.chunk]
            self._write(part)
            transfer['sent']+=len(part)
            self.next_chunk=self.clock()+self.pause
            self.emit('progress',transfer['sent'],len(transfer['body']))
            if transfer['sent']==len(transfer['body']):
                self.mode='settling';self.deadline=self.clock()+3.5
                self.emit('status','All host bytes sent; waiting for F idle-to-run (~3 seconds)')
        elif self.mode=='settling' and getattr(self.port,'out_waiting',0):
            # write() may return with bytes still queued, especially at low baud.
            self.deadline=self.clock()+3.5
        elif self.mode=='settling' and now>=self.deadline:
            result=dict(self.transfer,body=None,host_complete=True,board_readback_verified=False)
            self.last_transfer=(self.transfer['path'],self.transfer['body'],self.transfer['sha256'])
            self.mode='idle';self.transfer=None
            self.emit('busy',False)
            self.emit('transfer',result)
            self.emit('status','Host transfer complete; raw L provides no length/CRC/readback verification')
            if self.close_pending:self.disconnect()
