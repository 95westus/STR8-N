"""Unflashed identity binding in the already allocated B3:9 sector."""
import json
import build_v2_rtc_eui as eui
import build_v2_rtc_journal as journal
import build_bank_maint_rtc as maintenance
OUT=journal.ROOT/'BUILD/v2-rtc-binding'

def profile(source):
    eui.profile(source)
    p=source/'service-kernel.inc';p.write_text(p.read_text().replace('SVC_BANNER_MAGIC DB "BT",2,3','SVC_BANNER_MAGIC DB "BT",3,3'))

def merge_identity_tail(prior,candidate):
    """Preserve binding records when replacing compatible sealed code."""
    assert len(prior)==len(candidate)==4096
    assert candidate[:4]==b'PJ\x04\x01' and journal.banner.base.apps.fw.crc(candidate[:3072])==0
    if prior[:4]==b'PJ\x04\x01':
        assert journal.banner.base.apps.fw.crc(prior[:3072])==0
        return candidate[:3072]+prior[3072:]
    assert prior in (bytes([255])*4096,) or (prior[:2]==b'PJ' and prior[2] in (1,2,3) and journal.banner.base.apps.fw.crc(prior)==0)
    return candidate

def main():
    journal.OUT=OUT;journal.VERSION='2.0b12';journal.GENERATION=21
    journal.BANNER_SOURCE='rtc-binding-banner.asm';journal.JOURNAL_SOURCE='journal-binding.asm';journal.TRANSPORT_SOURCE='eeprom-eui-transfer.inc';journal.JOURNAL_CODE_END=0x9C00;journal.profile=profile;journal.main()
    maintenance.OUT=OUT/'maint';maintenance.KERNEL_OUT=OUT;maintenance.VERSION='1.7';maintenance.JOURNAL=True;maintenance.main()
    meta=json.loads((OUT/'build.json').read_text());meta.update(boot_eui=True,eui_binding=True,identity_records='B3:9C00-9FFF',identity_slots=32,identity_record_bytes=32,journal_code_seal_end=0x9C00,monitor_time=True,time_entry=0x890A,time_monitor_growth=20,clock_version='1.4')
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':main()
