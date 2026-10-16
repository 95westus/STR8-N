"""Stop only the identified soak worker at a restored, port-free boundary."""
import argparse,datetime,json,os,signal,subprocess,time
from pathlib import Path
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--used-percent',type=float);p.add_argument('--threshold-percent',type=float,default=20);p.add_argument('--after-hours',type=float);a=p.parse_args()
 if a.after_hours is None and (a.used_percent is None or a.used_percent<a.threshold_percent):raise ValueError('Usage cutoff has not been reached')
 if not 0<a.threshold_percent<=100:raise ValueError('Invalid usage threshold')
 if a.after_hours is not None and a.after_hours<=0:raise ValueError('Invalid duration')
 active=json.loads((ROOT/'output/qualification/active-beta23-soak.json').read_text());root=Path(active['root']);pid=active['pid']
 assert root.resolve().is_relative_to((ROOT/'output/qualification').resolve())
 config=json.loads((root/'config.json').read_text())
 start=datetime.datetime.fromisoformat(config['start_utc']).timestamp()
 if a.after_hours is not None:
  deadline=start+a.after_hours*3600
  while time.time()<deadline:
   if json.loads((root/'status.json').read_text())['state'] in ('completed','stopped-usage-limit','stopped-on-failure'):return
   time.sleep(max(0,min(30,deadline-time.time())))
 # Acquire only after the current unit has restored memory and closed its port.
 # Priority prevents the worker starting another unit while we verify/stop it.
 with serial_lease('drift',timeout=600):
  state=json.loads((root/'status.json').read_text())
  if state['state'] in ('completed','stopped-usage-limit','stopped-on-failure'):return
  assert all(not json.loads(f.read_text()).get('needs_restore') for f in root.glob('*/restore-state.json')),'Unresolved restoration; refuse termination'
  code=f"Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}' | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
  result=subprocess.run(['powershell','-NoProfile','-Command',code],capture_output=True,text=True,check=True)
  process=json.loads(result.stdout);command=process['CommandLine']
  assert process['ProcessId']==pid and 'tools/run_beta23_soak.py' in command and str(root) in command,'Soak process identity mismatch'
  os.kill(pid,signal.SIGTERM)
  state=json.loads((root/'status.json').read_text());state.update(state='completed' if a.after_hours is not None else 'stopped-usage-limit',used_percent=a.used_percent,threshold_percent=a.threshold_percent,updated=time.time(),restoration_verified=True,ports_released=True,elapsed_hours=(time.time()-start)/3600)
  if a.after_hours is not None:state.update(target_hours=a.after_hours,completion_reason='user-shortened-duration')
  (root/'status.json').write_text(json.dumps(state,indent=2)+'\n')
  print('STOPPED soak at restored boundary:',state['state'])
if __name__=='__main__':main()
