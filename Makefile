ASM ?= wdc02as
LINKER ?= wdcln

SRC_DIR := src
BUILD_DIR := BUILD
OBJ_DIR := $(BUILD_DIR)/obj
LST_DIR := $(BUILD_DIR)/lst
SYM_DIR := $(BUILD_DIR)/sym
S19_DIR := $(BUILD_DIR)/s19
BIN_DIR := $(BUILD_DIR)/bin

ASFLAGS := -G -L -S -W -I $(SRC_DIR)
STR8_LINKFLAGS := -g -s -t -cF000 -hm19 -j -o
WORKER_LINKFLAGS := -g -s -t -c0200 -hm19 -j -o
# Historical symbol names select the sole flashable release path; the proof
# branches remain source-only references and are not separate shipped builds.
RELEASE_DEFINES := -DSTR8_V1_LAYOUT -DSTR8_V1_INSTALLER_DRY -DSTR8_V1_INSTALLER_TXN

STR8_SRC := $(SRC_DIR)/str8.asm
WORKER_SRC := $(SRC_DIR)/str8-worker.asm
DELAY_SRC := $(SRC_DIR)/util-delay.asm
STR8_INCLUDES := \
	$(SRC_DIR)/himon-image-eq.inc \
	$(SRC_DIR)/str8-directory-eq.inc \
	$(SRC_DIR)/str8-jump-eq.inc \
	$(SRC_DIR)/str8-record-eq.inc \
	$(SRC_DIR)/str8-version.inc \
	$(SRC_DIR)/str8-worker-eq.inc
WORKER_INCLUDES := \
	$(SRC_DIR)/str8-jump-eq.inc \
	$(SRC_DIR)/str8-record-eq.inc \
	$(SRC_DIR)/str8-worker-eq.inc

STR8_OBJ := $(OBJ_DIR)/str8n.obj
DELAY_OBJ := $(OBJ_DIR)/util-delay.obj
WORKER_OBJ := $(OBJ_DIR)/str8n-worker.obj

STR8_S19 := $(S19_DIR)/str8n-f000.s19
WORKER_S19 := $(S19_DIR)/str8n-worker-0200.s19
TOP_BIN_TOOL := tools/build_str8n_top_bin.ps1
LAYOUT_CHECK_TOOL := tools/check_str8n_layout.ps1
MANIFEST_TOOL := tools/write_str8n_manifest.ps1
RANGE_MATRIX_TOOL := tools/test_s19_range_matrix.ps1
RAM_LOAD_TOOL := tools/test_ram_load_contract.ps1
TOP_BIN := $(BIN_DIR)/str8n-bank3-f000-ffff.bin
MANIFEST := $(BUILD_DIR)/str8n-manifest.json

.NOTPARALLEL:
.PHONY: all resident workers programmer-bin manifest layout-check embedded-layout-check range-matrix-check ram-load-contract-check clean help dirs FORCE

all: manifest range-matrix-check ram-load-contract-check

resident: $(STR8_S19)

workers: $(WORKER_S19)

programmer-bin: $(TOP_BIN)

manifest: $(MANIFEST)

layout-check: $(STR8_S19) $(WORKER_S19) $(LAYOUT_CHECK_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(LAYOUT_CHECK_TOOL)

embedded-layout-check: layout-check

range-matrix-check: $(RANGE_MATRIX_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RANGE_MATRIX_TOOL)

ram-load-contract-check: $(STR8_S19) $(RAM_LOAD_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RAM_LOAD_TOOL) -MapPath "$(S19_DIR)/str8n-f000.map"

dirs:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "@('$(OBJ_DIR)','$(LST_DIR)','$(SYM_DIR)','$(S19_DIR)','$(BIN_DIR)') | ForEach-Object { New-Item -ItemType Directory -Force -Path $$_ | Out-Null }"

$(STR8_OBJ): $(STR8_SRC) $(STR8_INCLUDES) | dirs
	$(ASM) $(ASFLAGS) $(RELEASE_DEFINES) $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n.sym)

$(DELAY_OBJ): $(DELAY_SRC) | dirs
	$(ASM) $(ASFLAGS) $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/util-delay.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/util-delay.sym)

$(WORKER_OBJ): $(WORKER_SRC) $(WORKER_INCLUDES) | dirs
	$(ASM) $(ASFLAGS) $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-worker.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-worker.sym)

$(STR8_S19): $(STR8_OBJ) $(DELAY_OBJ) | dirs
	$(LINKER) $(STR8_LINKFLAGS) $@ $(STR8_OBJ) $(DELAY_OBJ)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S903F0000C'; Set-Content -LiteralPath $$p -Value $$lines"

$(WORKER_S19): $(WORKER_OBJ) | dirs
	$(LINKER) $(WORKER_LINKFLAGS) $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9030200FA'; Set-Content -LiteralPath $$p -Value $$lines"

$(TOP_BIN): layout-check $(TOP_BIN_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_BIN_TOOL) -Str8MapPath "$(S19_DIR)/str8n-f000.map" -Str8S19Path "$(STR8_S19)" -WorkerMapPath "$(S19_DIR)/str8n-worker-0200.map" -WorkerS19Path "$(WORKER_S19)" -BinPath "$@"

$(MANIFEST): $(TOP_BIN) $(WORKER_S19) $(MANIFEST_TOOL) FORCE
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(MANIFEST_TOOL) -Str8MapPath "$(S19_DIR)/str8n-f000.map" -WorkerMapPath "$(S19_DIR)/str8n-worker-0200.map" -TopBinPath "$(TOP_BIN)" -WorkerS19Path "$(WORKER_S19)" -ManifestPath "$@"

FORCE:

help:
	@echo make          - build and validate resident, unified worker, and programmer BIN
	@echo make resident - build the V2 resident at F000
	@echo make workers  - build the one unified RAM worker
	@echo make programmer-bin - build the Bank-3 F000-FFFF T48 BIN
	@echo make manifest - build the verified artifact manifest used by R-YORS
	@echo make layout-check - require the protected-sector layout and 8-byte margin
	@echo make embedded-layout-check - alias for layout-check
	@echo make range-matrix-check - validate every documented 4K-aligned install size
	@echo make ram-load-contract-check - validate linked L-command RAM and S9 boundaries
	@echo make clean    - remove STR8N/BUILD only

clean:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path -LiteralPath '$(BUILD_DIR)') { Remove-Item -LiteralPath '$(BUILD_DIR)' -Recurse -Force }"
