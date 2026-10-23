        MODULE XIP_UTILITIES
        XDEF X28_END
        INCLUDE "kernel.inc"
        INCLUDE "system.inc"
        CODE
X28_HEADER: DB "UX",3,42
        JMP MM_START
        JMP SM_ENTRY
        JMP WK_ENTRY
        JMP ED_START
        JMP X28_APPS
X28_GATE_IMAGE:
        INCLUDE "gate-image.inc"
X28_WORK_STUB:
        INCLUDE "work-stub.inc"
        INCLUDE "../maintenance/maint.inc"
        INCLUDE "../storage/sram.inc"
        INCLUDE "../workspace/work.inc"
        INCLUDE "../edu/edu.inc"
        INCLUDE "dispatch.inc"
        INCLUDE "../storage/source-adapter.inc"
        INCLUDE "../maintenance/source-protection.inc"
X28_END:
        ENDMOD
