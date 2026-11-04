"""Physical keys/extracted candidate3 on2512; RAM only, RTC-priority lease."""
import hashlib,importlib.util,json,queue,re,sys,time,traceback
from pathlib import Path
from datetime import datetime
import install_named_edu_2512 as ins
from serial_test_coordination import drift_pending
t=ins.t;d=ins.d;Q=ins.Q
BASE=t.ROOT/'BUILD/unified-g10-candidate3-20261101-r3'
KIT=BASE/'fresh-extraction/STR8N-MON-g00000010-candidate3';FND=KIT/'foundation'
OUT=Q/'2512-candidate3-physical-keys-20261102-r3'
REC=t.REC;MON=t.MON;READY=b'SEND S19 (S0/S1/S9); Ctrl-C cancels\r\n';SEND=b'SEND BIN\r\n'
INPUT=b'Press one key to test input> ';CHOICES=b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def admit():
    receipt=json.loads((BASE/'EXTRACTION-PREPARATION-RECEIPT.json').read_text());assert receipt['passed']
    assert hashlib.sha256(Path(receipt['archive']).read_bytes()).hexdigest()==receipt['sha256']
    mf=json.loads((KIT/'CANDIDATE-MANIFEST.json').read_text())
    for name,info in mf['files'].items():
      b=(KIT/name).read_bytes();assert len(b)==info['bytes'] and t.sha(b)==info['sha256'],name
    assert mf['terminal']=='0.1.2' and mf['F_frozen']
    return mf

def wait_for_operator():
    """Visible readiness gate: no serial adapter, lease or owner RAM borrowed."""
    import tkinter as tk
    from tkinter import ttk
    root=tk.Tk();root.title('2512 Candidate3 — Start here');root.geometry('1050x400')
    status=tk.StringVar(value='No board connection is open. Click Start trial when you can see this window.')
    ttk.Label(root,textvariable=status,wraplength=1000,padding=12,font=('Segoe UI',12)).pack(fill='x')
    for label,path in [('Shift+F2: S19 file',KIT/'examples/KEY-S19-3500.s19'),
                       ('F2: BIN file',FND/'firmware/payload/STR8N-F-DEMO-RAM.bin')]:
      ttk.Label(root,text=label,padding=(12,3)).pack(anchor='w')
      row=ttk.Frame(root);row.pack(fill='x',padx=12)
      field=ttk.Entry(row);field.insert(0,str(path));field.configure(state='readonly');field.pack(side='left',fill='x',expand=True)
      def copy(p=str(path)):root.clipboard_clear();root.clipboard_append(p)
      ttk.Button(row,text='Copy path',command=copy).pack(side='right',padx=5)
    ttk.Label(root,text='Buttons are allowed for Connect, Cancel and ordinary BIN actions.\nOnly Shift+F2 and Shift+F3 require physical keys (Fn may also be needed).\nFile picker: Copy path, paste into File name, then Open.',padding=12).pack(anchor='w')
    clicked=False;cancelled=False;started=time.monotonic()
    def start():
      nonlocal clicked
      clicked=True;button.configure(state='disabled')
      status.set('Waiting for the RTC window. No board connection yet; the test console opens after preparation.')
    def cancel():
      nonlocal cancelled
      cancelled=True;root.destroy()
    button=ttk.Button(root,text='Start trial when ready',command=start);button.pack(pady=8)
    root.protocol('WM_DELETE_WINDOW',cancel)
    def poll():
      if time.monotonic()-started>1800:cancel();return
      if clicked:
        try:ins.window(1080)
        except AssertionError:pass
        else:root.destroy();return
      root.after(500,poll)
    root.after(500,poll);root.mainloop()
    if cancelled:raise InterruptedError('Operator gate closed; no serial port opened or RAM borrowed')

class GUI:
    def __init__(self,console,report,save):
      import tkinter as tk
      from tkinter import ttk
      self.tk=tk;self.root=tk.Tk();self.pending=bytearray();self.events=[];self.native=[];self.tx=bytearray()
      self.expected=None;self.seen=False;self.action_done=False;self.auto=False;self.abort=None;self.report=report;self.save=save;self.context=MON
      self.end=time.monotonic()+900
      def factory(port,baud):
        from serial.tools.list_ports import comports
        assert port=='COM4' and baud==115200
        assert any(p.device==port and p.serial_number=='A10MQFLCA' for p in comports()),'2512 USB identity mismatch'
        return console.serial_port(port,baud)
      self.app=console.make_app(self.root,kit=FND,port='COM4',worker_factory=lambda e:console.Worker(e,factory=factory))
      self.instructions=tk.StringVar(value='Preparing preserving trial; use only the indicated physical key.')
      ttk.Label(self.root,textvariable=self.instructions,padding=12,wraplength=1000,font=('Segoe UI',12)).pack(before=self.root.winfo_children()[0],fill='x')
      self.path_hint=tk.StringVar()
      pathrow=ttk.Frame(self.root);pathrow.pack(before=self.root.winfo_children()[1],fill='x',padx=12)
      self.path_field=ttk.Entry(pathrow,textvariable=self.path_hint,state='readonly')
      self.path_field.pack(side='left',fill='x',expand=True)
      def copy_path():self.root.clipboard_clear();self.root.clipboard_append(self.path_hint.get())
      ttk.Button(pathrow,text='Copy file path',command=copy_path).pack(side='right',padx=5)
      self.root.title('2512 Candidate3 physical-key acceptance')
      original_put=self.app.events.put
      def tee(event):self.events.append(event);original_put(event)
      self.app.events.put=tee
      self.event_index=0;self.log=(OUT/'GUI-events.jsonl').open('x',encoding='utf-8')
      def observe(event):
        if event.keysym.startswith('F'):
          key=('Shift+' if event.state&1 else '')+event.keysym
          if key==self.expected:
            self.native.append(dict(key=key,state=event.state,time=t.utc()));self.seen=True
            self.report['native_keys']=self.native.copy();self.save()
      # Observe all app widgets so path-entry/button focus cannot hide a real
      # key event. No keyboard events are generated by this harness.
      def attach(widget):
        widget.bindtags(('PhysicalKeyObserver',)+widget.bindtags())
        for child in widget.winfo_children():attach(child)
      attach(self.root)
      self.root.bind_class('PhysicalKeyObserver','<KeyPress>',observe)
      action=self.app.action;s19action=self.app.s19_action;command=self.app.command
      def guarded(key,fn,*args):
        if not self.auto and (key!=self.expected or key.startswith('Shift+') and not self.seen):
          self.app.status.set('Follow the current prompt; Shift shortcuts need a physical key');return 'break'
        result=fn(*args);self.action_done=True;return result
      self.app.action=lambda k:guarded(k,action,k)
      self.app.s19_action=lambda a:guarded('Shift+F2' if a=='choose' else 'Shift+F3',s19action,a)
      def control(name,*args):
        if name=='terminal' and not self.auto:
          self.app.status.set('Free typing paused; follow the physical-key prompts');return
        if name=='connect':assert args==('COM4',115200)
        if name in ('connect','disconnect','start','s19') and not self.auto:
          needed='Shift+F3' if name=='s19' else 'F4' if name=='start' else 'F10'
          if self.expected!=needed or needed.startswith('Shift+') and not self.seen:
            self.app.status.set('Follow the current prompt; Shift shortcuts need a physical key');return
          self.action_done=True
        if name=='start':assert Path(args[0]).resolve()==(FND/'firmware/payload/STR8N-F-DEMO-RAM.bin').resolve()
        if name=='s19':assert Path(args[0]).resolve()==(KIT/'examples/KEY-S19-3500.s19').resolve()
        return command(name,*args)
      self.app.command=control
      self.root.protocol('WM_DELETE_WINDOW',lambda:self.stop('Window close requested'))
      self.root.state('zoomed')
      self.root.after(500,self.watch)

    def stop(self,reason):self.abort=reason
    def watch(self):
      try:
        ins.window(150)
        assert time.monotonic()<self.end,'Keyboard trial timed out'
      except Exception as e:
        self.abort=str(e);self.instructions.set('Ending trial; restoring owner RAM. Please stop typing.')
        # Destroying the parent also dismisses its native file dialog. The
        # serial worker stays alive for orderly shutdown in close().
        try:self.root.destroy()
        except self.tk.TclError:pass
        return
      self.root.after(500,self.watch)

    def pump(self):
      if self.abort:raise InterruptedError(self.abort)
      self.root.update()
      for event in self.events[self.event_index:]:
        kind,*args=event
        self.log.write(json.dumps(dict(time=t.utc(),kind=kind,data=[a.hex() if isinstance(a,bytes) else a for a in args]))+'\n')
        if kind=='rx':self.pending.extend(args[0])
        if kind=='tx':self.tx.extend(args[0])
      self.event_index=len(self.events);self.log.flush();time.sleep(.005)

    def wait(self,predicate,seconds=90):
      end=time.monotonic()+seconds
      while time.monotonic()<end:
        self.pump()
        if predicate():return
      raise TimeoutError('GUI: '+self.app.status.get()+' RX '+repr(self.pending[-180:]))

    def until(self,token,seconds=45):
      self.wait(lambda:token in self.pending,seconds);i=self.pending.index(token)+len(token)
      b=bytes(self.pending[:i]);del self.pending[:i];self.context=token;return b

    def raw(self,b):
      self.auto=True
      try:self.app.command('terminal',b)
      finally:self.auto=False

    def cmd(self,line,token):self.raw(line.encode()+b'\r');return self.until(token)

    def key(self,key,instruction,predicate=None):
      needs_ack=predicate is None;predicate=predicate or (lambda:True)
      self.expected=key;self.seen=False;self.action_done=False;self.instructions.set(instruction)
      self.root.title('2512 Candidate3 — '+key);self.app.text.focus_force();self.root.update()
      self.report['phase']='waiting-'+key;self.save();print('READY '+key+': '+instruction,flush=True)
      self.wait(lambda:predicate() and (self.seen and self.action_done if key.startswith('Shift+') else self.action_done or not needs_ack),seconds=600 if key=='F10' else 300)
      self.report.setdefault('operator_actions',[]).append(dict(action=key,source='physical-key' if self.seen else 'button',time=t.utc()))
      self.expected=None;self.save()

    def dump(self,a,b):
      face=self.cmd(f'D {a:04X} {b:04X}',MON);data={}
      for line in face.decode('ascii').splitlines():
        m=re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
        if m:data.update((int(m[1],16)+i,v) for i,v in enumerate(bytes.fromhex(m[2])))
      return bytes(data[x] for x in range(a,b+1))

    def run(self):
      self.key('F10','Click F10 Connect / disconnect (or press F10). Wait for the next prompt.',lambda:self.app.connected)
      self.raw(b'\r');self.until(MON)
      s19=(KIT/'examples/KEY-S19-3500.s19').resolve()
      self.path_hint.set(str(s19))
      self.key('Shift+F2','Click Copy file path. Press Shift+F2 (Fn too if needed); paste into File name and Open.',lambda:bool(self.app.selected_s19.get()))
      assert Path(self.app.selected_s19.get()).resolve()==s19 and not self.app.selected.get()
      self.cmd('S19',READY);start=len(self.tx)
      self.key('F12','SEND S19 is waiting. Click F12 Ctrl-C (or press F12) to cancel.')
      self.until(MON);assert self.tx[start:]==b'\x03';self.report['SEND_S19_initial_cancel']=True;self.save()
      self.cmd('S19',READY);start=len(self.events)
      self.key('Shift+F3','Press Shift+F3 to send the chosen RAM S19. It will not autorun.')
      self.until(MON);self.wait(lambda:not self.app.busy)
      transfers=[e[1] for e in self.events[start:] if e[0]=='transfer']
      assert len(transfers)==1 and transfers[0]['board_accepted'] and not transfers[0]['cancelled'],transfers
      assert self.dump(0x3500,0x3503)==b'KEYS'
      self.report['S19_independent_RAM_verified']=True;self.report['S19_transfer']=transfers[0];self.save()
      self.cmd('Q',REC);self.cmd('L',SEND);start=len(self.tx)
      self.key('F12','SEND BIN is waiting. Click F12 Ctrl-C (or press F12) to cancel.')
      self.until(REC);assert self.tx[start:]==b'\x03';self.report['SEND_BIN_initial_cancel']=True;self.save()
      demo=(FND/'firmware/payload/STR8N-F-DEMO-RAM.bin').resolve()
      self.path_hint.set(str(demo))
      self.key('F2','Click Copy file path, then F2 Choose BIN. Paste into File name and Open.',lambda:bool(self.app.selected.get()))
      assert Path(self.app.selected.get()).resolve()==demo
      self.key('F4','Click F4 REC L + BIN (or press F4) for the normal RAM load; then wait.')
      face=self.until(INPUT,45);self.wait(lambda:not self.app.busy)
      assert b'1234 + 0001 = 1235' in face and b'CPU code (02=65C02, 16=65C816): 02' in face,face
      self.raw(b'K');face=self.until(CHOICES);assert b'Received key byte, hex: 4B' in face,face
      self.raw(b'S');self.until(REC);self.report['BIN_DEMO_execution_and_return']=True
      self.report['DEMO_public_software_boot_return']=1;self.save()
      self.key('F10','Click F10 Connect / disconnect to disconnect. Owner RAM will be restored automatically.',lambda:not self.app.connected)
      self.report['GUI_sequence_passed']=True;self.save()

    def close(self):
      # Finish any already-started BIN payload before releasing the adapter.
      deadline=time.monotonic()+60
      while self.app.worker.session.busy and time.monotonic()<deadline:time.sleep(.02)
      assert not self.app.worker.session.busy,'Transfer still active; do not disconnect'
      self.app.worker.commands.put(('stop',()))
      self.app.worker.join(5);assert not self.app.worker.is_alive()
      self.log.close()
      try:self.root.destroy()
      except self.tk.TclError:pass

def run():
    mf=admit();print('Candidate3 pins accepted; Start-here window opens without a board connection',flush=True)
    wait_for_operator()
    start=time.monotonic()
    while True:
      try:ins.window(1080);break
      except AssertionError:
        if time.monotonic()-start>900:raise TimeoutError('RTC window unavailable; no port opened')
        time.sleep(1)
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    sys.path.insert(0,str(FND/'tools'))
    core=module('candidate3_console_core',FND/'tools/console_core.py');sys.modules['console_core']=core
    console=module('candidate3_console',FND/'tools/nf_console.py')
    recovery=module('candidate3_recovery',FND/'tools/nf_recovery.py')
    assert console.VERSION=='0.1.2' and Path(core.__file__).is_relative_to(KIT)
    class Session(d.Session):
      def load(self,body,digest,prompt):
        assert self.context==REC and t.sha(body)==digest;recovery.PROMPT=prompt
        self.client=recovery.RecoveryClient(t.live.LoggedRecoveryStream(self.link),timeout=60)
        self.client.load(body,digest,REC_observed=True);self.context=prompt
    reader=(FND/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=Q/'device-operations/2512.json';s=g=None;ram=zp=prefix=None;borrowed=False;marker=None
    r=dict(board='2512',passed=False,checks=[],F_writes=0,flash_erases=0,journal_appends=0,setting_writes=0,
      RTC_SET=0,trim_writes=0,PF_ACK=0,SPI_writes=0,resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,
      owner_RAM_restored=False,owner_ZP_restored=False,port_released=False,GUI_sequence_passed=False,kit=str(KIT))
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def rec():
      if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(REC);s.context=REC
      elif s.context==MON:s.command('Q',(REC,))
      assert s.context==REC
    save()
    with t.serial_lease('2512-candidate3-physical-keys',timeout=30):
      ins.window(1080);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['block_snapshot'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'controller-serial.jsonl').open('x') as log:
        try:
          s=Session(OUT,log,'2512');s.link.send(b'\r');s.until((MON,REC),seconds=12)
          if s.context==MON:s.command('Q',(REC,))
          s.command('B',(MON,));assert b'STR8-N MON B  gen 00000010' in s.command('VERSION')
          prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
          (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
          mark(candidate3_key_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
          rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
          ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
          banks={b:s.client.flash(b) for b in (1,2,3)}
          assert all(t.sha(v)==marker['current_physical_bank_sha256'][f'B{b}'] for b,v in banks.items())
          for item in json.loads((KIT/'NATIVE-COMPONENTS.json').read_text())['targets']:
            body=(KIT/item['file']).read_bytes();off=int(item['address'],16)-0x8000
            assert banks[item['bank']][off:off+len(body)]==body,item['file']
          r['live_19_extracted_components_exact']=True;r['B3_before_sha256']=t.sha(banks[3]);save()
          s.client.send(b'Q');s.client.until(REC);s.context=REC;s.command('B',(MON,))
          assert b'CLOCK' in s.command('APPS');s.command('MAINT LOAD',(t.WB,));s.command('Q',(MON,))
          s.link.close();s=None
          g=GUI(console,r,save);g.run()
        except BaseException as e:r['error']=repr(e);r['traceback']=traceback.format_exc();save();raise
        finally:
          try:
            if g:g.close()
            if borrowed:
              if s is None:
                s=Session(OUT,log,'2512');s.link.send(b'\r');s.until((REC,MON,READY,SEND,INPUT,CHOICES),seconds=12)
                if s.context in (READY,SEND):s.link.send(b'\x03');s.until((MON,REC))
                if s.context==INPUT:s.link.send(b'K');s.until((CHOICES,))
                if s.context==CHOICES:s.link.send(b'S');s.until((REC,))
              rec();s.service(reader)
              if ram is None:
                memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
              try:
                after3=s.client.flash(3)
                r['B3_images_F_settings_history_exact']=t.sha(after3)==r.get('B3_before_sha256',marker['current_physical_bank_sha256']['B3'])
              finally:
                r.update(s.client.restore_owner(ram,zp));s.context=REC
              assert r['B3_images_F_settings_history_exact'],'B3 mismatch; owner RAM was still restored'
          finally:
            if s:s.link.close()
            r['port_released']=True
            if borrowed:
              restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
              mark(candidate3_key_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',
                last_candidate3_key_trial=str(OUT/'report.json'))
            save()
    r['passed']=r['GUI_sequence_passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['B3_images_F_settings_history_exact']
    save();assert r['passed'];print('PASS Candidate3 native keys/live extraction; owner RAM restored; F golden; REC>; COM4 released',flush=True)

if __name__=='__main__':run()
