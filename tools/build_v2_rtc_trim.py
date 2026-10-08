"""Prepare normal digital trim administration; no board access or deployment."""
import json
import build_v2_rtc_binding as binding
import build_v2_rtc_journal as journal
import build_bank_maint_rtc as maintenance
OUT=journal.ROOT/'BUILD/v2-rtc-trim'

def profile(source):
    binding.profile(source)
    p=source/'service-kernel.inc';p.write_text(p.read_text().replace('SVC_BANNER_MAGIC DB "BT",3,3','SVC_BANNER_MAGIC DB "BT",4,3'))

def merge_identity_tail(prior,candidate):
    assert len(prior)==len(candidate)==4096 and candidate[:4]==b'PJ\x05\x01'
    assert journal.banner.base.apps.fw.crc(candidate[:3072])==0
    assert prior[:4] in (b'PJ\x04\x01',b'PJ\x05\x01') and journal.banner.base.apps.fw.crc(prior[:3072])==0
    return candidate[:3072]+prior[3072:]

def main():
    journal.OUT=OUT;journal.VERSION='2.0b13';journal.GENERATION=22
    journal.BANNER_SOURCE='rtc-trim-banner.asm';journal.JOURNAL_SOURCE='journal-trim.asm';journal.TRANSPORT_SOURCE='eeprom-trim-transfer.inc';journal.JOURNAL_CODE_END=0x9C00;journal.profile=profile;journal.main()
    maintenance.OUT=OUT/'maint';maintenance.KERNEL_OUT=OUT;maintenance.VERSION='1.7';maintenance.JOURNAL=True;maintenance.main()
    meta=json.loads((OUT/'build.json').read_text());meta.update(eui_binding=True,trim_control=True,clock_version='1.5',journal_code_seal_end=0x9C00,monitor_time=True,time_entry=0x890A)
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':main()
