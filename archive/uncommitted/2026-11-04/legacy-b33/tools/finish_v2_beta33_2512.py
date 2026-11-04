"""Resume verification of the already installed beta33; never installs flash."""
import re
import time
import deploy_v2_beta33_2512 as d


def main():
    d.audit()
    out=d.OUT/'hardware'
    original=(out/'ram-prior.bin').read_bytes()
    plan=d.read(d.OUT/'upgrade/plan.json')
    proof=d.read(d.OUT/'upgrade/functional.json')
    prior_report=d.read(out/'report.json')
    result=dict(board='2512',version='2.0b33',passed=False,application_ram_restored=False,
                resumed_after='Store succeeded and selected B1; original harness expected B3',
                initial_harness_report=prior_report)
    logpath=out/f'serial-resume-{time.time_ns()}.jsonl'
    with d.serial_lease('beta33-2512-finish',priority=True),logpath.open('x') as log:
        link=d.m.Link(d.io.port('2512'),log)
        def cmd(line,prompt=b'> '):
            text=link.command(line,prompt)
            if prompt==b'> ':assert re.search(rb'\r\nB[0-3]> $',text),repr(text[-160:])
            print('LIVE',line,flush=True)
            return text
        def b3():cmd('B3')
        def banks(stage):
            for b in range(4):
                prompt=f'\r\nB{b}> '.encode();cmd(f'B{b}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert d.sha(data)==proof['demo_hashes'][b],f'{stage} B{b} mismatch'
                (out/f'{stage}-b{b}.bin').write_bytes(data)
                print('PASS',stage,'full B'+str(b),flush=True)
            b3()
        try:
            d.establish_b3(link)
            # The failed harness had already sent every restore S-record.
            # Verify those bytes before running any further test workers.
            restored=d.io.dump_ram(link)
            assert restored==original,'Initial load-only restoration mismatch'
            (out/'ram-restored-before-resume.bin').write_bytes(restored)
            d.save(out/'ram-restore-needed.json',dict(needed=False,sha256=d.sha(restored)))
            result['initial_ram_restoration_verified']=True
            banks('resumed-preflight')
            # Tests below use RAM; the full prior image remains authoritative.
            d.save(out/'ram-restore-needed.json',dict(needed=True,sha256=d.sha(original)))
            transcript=bytearray(cmd('T 1'));b3()
            assert b'HELLO0200' in transcript and b'0200-0216' in transcript
            body=(d.OUT/'upgrade/demo-body.bin').read_bytes()
            link.write_ram(0x0200,bytes(23));assert link.dump(0x0200,0x0216)==bytes(23)
            text=cmd('R 1 HELLO0200 L');assert b'Done' in text;transcript.extend(text);b3()
            assert link.dump(0x0200,0x0216)==body
            text=cmd('R 1 HELLO0200');assert b'OK\r\n' in text;transcript.extend(text);b3()
            (out/'restore-verification.txt').write_bytes(transcript)
            from run_v2_beta32_soak import batch
            for name,line in [('providers','MAINT;Q;SRAM;Q;WORK;Q;EDU;Q'),('clock','SRAM;G CLK;STATUS;Q'),('apps','APPS;VERSION')]:
                receipt=out/f'batch-{name}.txt'
                text=receipt.read_bytes() if receipt.exists() else batch(link,line)
                assert b'BATCH done' in text and b'BATCH stopped' not in text
                receipt.write_bytes(text)
                if name=='clock':assert b'CLOCK 1.9' in text and b'Running: yes' in text
                if name=='providers':assert all(t in text for t in (b'MAINT 2.4',b'SRAM 1.4',b'WORK 1.4',b'EDU 1.4'))
            text=cmd('BATCH ASM;VERSION',b'BATCH stopped: unsupported')+link.until(b'\r\nB3> ')
            assert b'ASM>' not in text
            (out/'batch-asm-refused.txt').write_bytes(text)
            text=cmd('BATCH SRAM;BOGUS;Q',b'BATCH stopped: command failed')+link.until(b'SRAM> ')
            cmd('Q');(out/'batch-error.txt').write_bytes(text)
            text=cmd('BATCH MAINT;NAME TEST;Q',b'Type YES: ')
            link.send(b'\x1b');text+=link.until(b'BATCH canceled')+link.until(b'BM> ')
            cmd('Q');(out/'batch-esc.txt').write_bytes(text)
            link.send(b'J3\r');text=link.until(b'A/B/S,Enter default [3s]: ')
            link.send(b'A');text+=link.until(b'\r\nB3> ')
            assert b'2.0b28' in text and link.dump(0x7D30,0x7D30)==b'\xA0'
            (out/'fallback-boot.txt').write_bytes(text)
            text=cmd('J3');assert b'2.0b33' in text and plan['expected_wear_peak'].encode() in text
            assert text.count(b'FLASH: wear check ')==1 and link.dump(0x7D30,0x7D30)==b'\xB0'
            (out/'final-boot.txt').write_bytes(text)
            for name in ('VERSION','TIME','APPS','T 1','M1','W','C'):
                text=cmd(name);(out/f'query-{name.replace(" ","-")}.txt').write_bytes(text);b3()
                if name=='VERSION':assert b'Board: 2512' in text and b'MONITOR B gen 0000002D VALID default' in text
                if name=='TIME':assert b'(-05:00)' in text
            banks('final')
            array=d.io.array_read(link,'Final retained SRAM')
            assert d.sha(array)==proof['sram_sha256'];(out/'final-sram.bin').write_bytes(array)
            after=d.io.retained(link,out,'after')
            for name in ('eeprom','eeprom-protected','eeprom-status','rtc-sram'):
                assert after[name]==(out/f'before-{name}.bin').read_bytes(),name
            before=(out/'before-rtc-registers.bin').read_bytes()
            assert after['rtc-registers'][7:]==before[7:]
            assert after['rtc-registers'][3]&0x38==before[3]&0x38
            # Prove the first hardware transcript, including the successful
            # assembly, execution and Store, rather than inferring from flash.
            rx=b''.join(bytes.fromhex(row['hex']) for row in map(d.json.loads,(out/'serial.jsonl').read_text().splitlines()) if row['direction']=='RX')
            assert b'OK 12544 bytes, origin $0200, buffer $0200' in rx
            assert b'Output full' in rx and b'OK 23 bytes, origin $0200, buffer $0200' in rx
            assert b'G 0200\r\nOK\r\n' in rx
            assert b'S 1 AUTO 0200 0216 HELLO0200\r\nSAVE B01:8000\r\nDone\r\nB1> ' in rx
            assert (out/'full-code-window.bin').read_bytes()==b'\xAB'*12544
            result.update(passed=True,monitor='B',generation=45,fallback='2.0b28 A',asm='0.4',
                asm_source_entered_on_board=True,org_0200_verified=True,direct_assembly_to_origin_verified=True,
                store_table_restore_verified=True,demo_record='B1:8000 HELLO0200',
                contiguous_code_window_verified=True,output_capacity=12544,overflow_refused=True,
                native_utilities_verified=True,batch_completion_error_escape_verified=True,clock='1.9',j3_verified=True,
                complete_flash_verified=True,sram_preserved=True,rtc_eeprom_history_identity_preserved=True,
                fixed_recovery_preserved=True,b0_preserved=True,erase_counts_accounted=True,soak_started=False,
                final_flash_hashes=proof['demo_hashes'],build_sha256=plan['build_sha256'])
        except Exception as error:result['error']=repr(error);raise
        finally:
            try:
                d.establish_b3(link)
                d.io.restore_ram(link,original,out)
                result['application_ram_restored']=True
            finally:
                link.serial.close();d.save(out/'verification-resumed.json',result)
    print('PASS beta33 on 2512, ASM full window + S/T/R, retained data and original RAM',flush=True)


if __name__=='__main__':main()
