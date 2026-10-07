"""Build unflashed boot EUI display, keeping TIME and earlier candidates."""
import json
import build_v2_rtc_time as time_build
import build_v2_rtc_journal as journal
import build_bank_maint_rtc as maintenance
OUT=journal.ROOT/'BUILD/v2-rtc-eui'

def profile(source):
    time_build.profile(source)
    p=source/'service-kernel.inc';p.write_text(p.read_text().replace('SVC_BANNER_MAGIC DB "BT",1,3','SVC_BANNER_MAGIC DB "BT",2,3'))

def main():
    journal.OUT=OUT;journal.VERSION='2.0b11';journal.GENERATION=20
    journal.BANNER_SOURCE='rtc-eui-banner.asm';journal.JOURNAL_SOURCE='journal-eui.asm';journal.TRANSPORT_SOURCE='eeprom-eui-transfer.inc';journal.profile=profile;journal.main()
    maintenance.OUT=OUT/'maint';maintenance.KERNEL_OUT=OUT;maintenance.VERSION='1.7';maintenance.JOURNAL=True;maintenance.main()
    meta=json.loads((OUT/'build.json').read_text());meta.update(boot_eui=True,eui_read_only=True,monitor_time=True,time_hook_bytes=10,time_monitor_growth=20,time_entry=0x890A,clock_version='1.3')
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':main()
