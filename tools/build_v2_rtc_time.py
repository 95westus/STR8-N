"""Build small read-only TIME monitor hook; no board access or flashing."""
import json
import build_v2_rtc_journal as journal
import build_bank_maint_rtc as maintenance

OUT=journal.ROOT/'BUILD/v2-rtc-time'
original_profile=journal.profile

def profile(source):
    original_profile(source)
    p=source/'str8n-v2.asm';t=p.read_text()
    t=t.replace('V2_DISPATCH:           JSR AP_TRY', '''V2_DISPATCH:           LDA SVC_BANNER_PTR+1
                        BEQ TIME_SKIP
                        JSR $890A
                        BCS V2_PROMPT
TIME_SKIP:              JSR AP_TRY''')
    p.write_text(t)
    p=source/'service-kernel.inc';p.write_text(p.read_text().replace('SVC_BANNER_MAGIC DB "BT",1,2','SVC_BANNER_MAGIC DB "BT",1,3'))
    p=source/'str8n-v2-text.json';data=json.loads(p.read_text())
    for row in data:
        if row['name']=='V2_HELP':row['text']='TIME\r\n'+row['text']
    p.write_text(json.dumps(data,indent=2)+'\n')

def main():
    journal.OUT=OUT;journal.VERSION='2.0b10';journal.GENERATION=19
    journal.BANNER_SOURCE='rtc-time-banner.asm';journal.profile=profile;journal.main()
    maintenance.OUT=OUT/'maint';maintenance.KERNEL_OUT=OUT;maintenance.VERSION='1.7';maintenance.JOURNAL=True;maintenance.main()
    previous=json.loads((journal.ROOT/'BUILD/v2-rtc-messages/build.json').read_text())
    meta=json.loads((OUT/'build.json').read_text());meta.update(monitor_time=True,time_hook_bytes=10,time_entry=0x890A,time_read_only=True,time_monitor_growth=meta['monitor_bytes']['a0']-previous['monitor_bytes']['a0'])
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':main()
