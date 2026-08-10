; Shared identity and extent of the transaction-uploaded mutation worker.
; The split-worker host gate freezes these values against the linked image.
STR8_JUMP_WORKER_START       EQU         $0200
STR8_JUMP_WORKER_END         EQU         $0291
STR8_JUMP_WORKER_SIZE        EQU         $0091
STR8_JUMP_WORKER_STORE       EQU         $FF1F
STR8_MUTATION_WORKER_SIG     EQU         $0203
STR8_MUTATION_WORKER_END     EQU         $042B
STR8_MUTATION_WORKER_SIG0    EQU         'I'
STR8_MUTATION_WORKER_SIG1    EQU         'W'
STR8_MUTATION_WORKER_SIG2    EQU         $01
STR8_MUTATION_WORKER_SIG3    EQU         $FE
