"""Record completed rc1 hardware checks without resuming campaigns."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';RUN=Q/'rc1-2604-2609-hardware-2026-10-18-r1';read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    boards={}
    for board in ('2604','2609'):
        report=RUN/(board+'-checks/report.json');r=read(report);install=read(RUN/(board+'-install/report.json'))
        assert r['passed'] and r['both_monitor_slots_passed'] and r['all_supported_apps_checked'] and set(r['slots'])=={'A','B'}
        assert all(v['passed'] and v['RTC']['control']==install['rtc_control_before'] and v['RTC']['trim_register']==install['rtc_trim_before'] for v in r['slots'].values())
        assert r['RAM_loader_acknowledged'] and not r['host_RAM_restoration_verified'] and not r['clock_set'] and not r['trim_changed'] and not r['soak_resumed'] and not r['RTC_sampling_resumed']
        if board=='2609':assert all(v['cpu_before']['cpu']==v['cpu_after']['cpu']=='65C816 E=1' for v in r['slots'].values())
        boards[board]=dict(report=str(report),sha256=sha(report),version='2.0rc1',generation=49,both_MON_A_B_passed=True,applications=['CLOCK 1.11','ASM 0.5','MAINT','SRAM','WORK','EDU','UCHESS'],final_preferred_monitor=r['final_preferred_monitor'],RTC_control_unchanged=install['rtc_control_before'],RTC_trim_register_unchanged=install['rtc_trim_before'],saved_RAM_loader_acknowledged=True,host_RAM_readback_verified=False)
        publish(RUN/(board+'-install/activation-completed.json'),dict(board=board,physical_reset_pending=False,owner_reset_confirmed=True,hardware_report=str(report),hardware_report_sha256=sha(report),both_slots_and_apps_passed=True))
    active=read(Q/'active-rtc-campaign.json');statepath=Path(active['campaign_state']);state=read(statepath);assert set(active['powered_off_boards'])=={'2205','2512'} and not state['soak_active'] and not state['RTC_sampling_active'] and not state['automatic_workload_restart_permitted']
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']=='5db3f89e0bcdd1ec1bd9d1958c6abbc8530977783a2f1bb195bc80220af4913e'
    receipt=dict(passed=True,version='2.0rc1',generation=49,published_zip_sha256=read(RUN/'preparation.json')['published_zip_sha256'],boards=boards,hardware_installation_complete=True,CPU_65C02_and_65C816_emulation_same_published_firmware=True,clocks_and_trims_unchanged=True,soaks_and_RTC_sampling_stopped=True,powered_off_boards=['2205','2512'],deferred=['RTC qualification','native 816 applications/tests','ACIA','crypto'],finished_utc=datetime.now(timezone.utc).isoformat())
    publish(RUN/'hardware-checkpoint.json',receipt);publish(Q/'rc1-hardware-current.json',dict(receipt=str(RUN/'hardware-checkpoint.json'),sha256=sha(RUN/'hardware-checkpoint.json')))
    for board in boards:state.setdefault('firmware_current',{})[board]='2.0rc1 generation49; both MON A/B and all apps hardware checked; idle'
    state['rc1_hardware_checkpoint']=str(RUN/'hardware-checkpoint.json');state['rc1_hardware_checkpoint_sha256']=sha(RUN/'hardware-checkpoint.json');publish(statepath,state)
    print(json.dumps(dict(passed=True,boards=list(boards),version='2.0rc1',generation=49,both_slots_and_apps=True,clocks_trims_unchanged=True,soaks_RTC_sampling_stopped=True,checkpoint=str(RUN/'hardware-checkpoint.json')),indent=2))
if __name__=='__main__':main()
