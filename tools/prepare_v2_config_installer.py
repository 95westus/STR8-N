"""Apply a24c1-only backup policy while keeping the qualified alpha24 source frozen."""
from pathlib import Path
from build_bank_maint_v2 import long_branches

POLICY = Path(__file__).parent / 'wdcmonv2/a24c1-backup-policy.asm'


def prepare(source):
    text = source.replace('2.0a24', '2.0a24c1').replace('2.0A24', '2.0A24C1')
    begin = text.index('                        LDA             #$00', text.index('W2I_ID_OK:'))
    end = text.index('                        LDX             #<W2I_MSG_SEND_CANDIDATE', begin)
    text = text[:begin] + POLICY.read_text() + '\nW2I_RECEIVE_READY:\n' + text[end:]
    begin = text.index('W2I_COPY_B3_TO_B0:')
    end = text.index('W2I_FLASH_TO_STAGE:', begin)
    loops = text[begin:end].replace('LDA             #$80', 'LDA             W2I_BACK_FIRST')
    loops = loops.replace('LDA             #$00', 'LDA             W2I_BACK_BANK')
    loops = loops.replace('                        BNE             ?SECTOR',
                          '                        CMP             W2I_BACK_END\n'
                          '                        BNE             ?SECTOR')
    text = text[:begin] + loops + text[end:]
    begin = text.index('W2I_RECOVERY:')
    end = text.index('W2I_ABORT_XY:', begin)
    recovery = text[begin:end].replace('                        LDA             #$00',
        '                        LDA             W2I_NO_BACKUP\n'
        '                        BNE             W2I_RECOVERY\n'
        '                        LDA             W2I_BACK_LAST\n'
        '                        CMP             #$F0\n'
        '                        BNE             W2I_RECOVERY\n'
        '                        LDA             W2I_BACK_BANK')
    text = text[:begin] + recovery + text[end:]
    text = text.replace('W2I_INSTALL_CONFIRMED:\n', '''W2I_INSTALL_CONFIRMED:
                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_HASH_BANK
                        JSR             W2I_HASH_EQUALS_SOURCE
                        BCS             W2I_SOURCE_UNCHANGED
                        LDX             #<W2I_MSG_BACK_FAILED
                        LDY             #>W2I_MSG_BACK_FAILED
                        JMP             W2I_ABORT_XY
W2I_SOURCE_UNCHANGED:
''')
    text = text.replace('B3 STOCK -> B0; STR8-N 2.0a24c1 -> B3:F',
                        'SELECT BACKUP BANK/RANGE; STR8-N 2.0a24c1 -> B3:F')
    text = text.replace('OLD B3:F RESTORED FROM B0:F; RESET',
                        'OLD B3:F RESTORED FROM SELECTED BACKUP; RESET')
    # Correct inherited recovery guidance for partial/no-backup choices.
    text = text.replace('R=RETRY STR8-N, O=RESTORE OLD B3:F FROM B0:F',
                        'R=RETRY; O=OLD F ONLY IF BACKED UP')
    text = text.replace('B3:F FAIL: R=RETRY STR8 O=RESTORE OLD> ',
                        'B3:F FAIL: R=RETRY; O=OLD F ONLY IF BACKED UP> ')
    return long_branches(text)
