ASM ?= wdc02as
LINKER ?= wdcln

SRC_DIR := src
BUILD_DIR := BUILD
VERSION := v1.2
RELEASE_DIR := $(BUILD_DIR)/$(VERSION)
OBJ_DIR := $(BUILD_DIR)/obj
LST_DIR := $(BUILD_DIR)/lst
SYM_DIR := $(BUILD_DIR)/sym
S19_DIR := $(RELEASE_DIR)/s19
BIN_DIR := $(RELEASE_DIR)/bin
TEST_DIR := $(RELEASE_DIR)/test
INCLUDE_DIR := $(RELEASE_DIR)/include

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
	$(SRC_DIR)/str8-console-eq.inc \
	$(SRC_DIR)/str8-directory-eq.inc \
	$(SRC_DIR)/str8-jump-eq.inc \
	$(SRC_DIR)/str8-record-eq.inc \
	$(SRC_DIR)/str8-ram-abi.inc \
	$(SRC_DIR)/str8-version.inc \
	$(SRC_DIR)/str8-worker-eq.inc
WORKER_INCLUDES := \
	$(SRC_DIR)/str8-jump-eq.inc \
	$(SRC_DIR)/str8-ram-abi.inc \
	$(SRC_DIR)/str8-record-eq.inc \
	$(SRC_DIR)/str8-worker-eq.inc

STR8_OBJ := $(OBJ_DIR)/str8n.obj
DELAY_OBJ := $(OBJ_DIR)/util-delay.obj
WORKER_OBJ := $(OBJ_DIR)/str8n-worker.obj

STR8_S19 := $(S19_DIR)/str8n-v1.2-f000.s19
WORKER_S19 := $(S19_DIR)/str8n-v1.2-worker-0200.s19
TOP_BIN_TOOL := tools/build_str8n_top_bin.ps1
LAYOUT_CHECK_TOOL := tools/check_str8n_layout.ps1
MANIFEST_TOOL := tools/write_str8n_manifest.ps1
PUBLIC_CONTRACT_TOOL := tools/write_str8n_public_contract.ps1
RANGE_MATRIX_TOOL := tools/test_s19_range_matrix.ps1
RAM_LOAD_TOOL := tools/test_ram_load_contract.ps1
RAM_ABI_CHECK_TOOL := tools/check_ram_abi_sources.ps1
BANK_MAINT_SRC := tools/bank-maint/str8n-v1.2-bank-maint-2000.asm
BANK_MAINT_OBJ := $(OBJ_DIR)/str8n-v1.2-bank-maint-2000.obj
BANK_MAINT_S19 := $(S19_DIR)/str8n-v1.2-bank-maint-2000.s19
BANK_MAINT_CHECK_TOOL := tools/check_bank_maint_s19.ps1
CONSOLE_ABI_TEST_SRC := tools/console-abi-test/str8n-v1.2-console-abi-test-2000.asm
CONSOLE_ABI_TEST_OBJ := $(OBJ_DIR)/str8n-v1.2-console-abi-test-2000.obj
CONSOLE_ABI_TEST_S19 := $(S19_DIR)/str8n-v1.2-console-abi-test-2000.s19
TOP_UPDATE_SRC := tools/top-update/str8n-v1.2-top-update-2000.asm
TOP_UPDATE_INC_TOOL := tools/make_top_update_image_inc.ps1
TOP_UPDATE_INC := $(RELEASE_DIR)/generated/str8n-v1.2-top-image.inc
TOP_UPDATE_CHECK_TOOL := tools/check_top_update_s19.ps1
TOP_UPDATE_OBJ := $(OBJ_DIR)/str8n-v1.2-top-update-2000.obj
TOP_UPDATE_S19 := $(S19_DIR)/str8n-v1.2-top-update-2000.s19
DIRECTORY_REFRESH_OBJ := $(OBJ_DIR)/str8n-v1.2-directory-refresh-2000.obj
DIRECTORY_REFRESH_S19 := $(S19_DIR)/str8n-v1.2-directory-refresh-2000.s19
RYORS_28K_S19 ?= ../R-YORS/SRC/BUILD/s19/ryors-v1.2-asm-himon-bank3-8-e.s19
RYORS_FULL_BANK_TOOL := tools/build_ryors_full_bank_s19.ps1
RYORS_FULL_BANK_S19 := $(S19_DIR)/ryors-v1.2-asm-himon-str8n-bank0-2-8-f.s19
TOP_BIN := $(BIN_DIR)/str8n-v1.2-bank3-f000-ffff.bin
MANIFEST := $(BUILD_DIR)/str8n-manifest.json
PUBLIC_CONTRACT := $(INCLUDE_DIR)/str8n-public.inc

.NOTPARALLEL:
.PHONY: all resident workers programmer-bin manifest bank-maint console-abi-test top-update onboard-directory-refresh ryors-full-bank layout-check embedded-layout-check range-matrix-check ram-load-contract-check ram-abi-check clean help dirs FORCE

all: manifest range-matrix-check ram-load-contract-check ram-abi-check console-abi-test top-update onboard-directory-refresh

resident: $(STR8_S19)

workers: $(WORKER_S19)

programmer-bin: $(TOP_BIN)

manifest: $(MANIFEST)

bank-maint: $(BANK_MAINT_S19)

console-abi-test: $(CONSOLE_ABI_TEST_S19)

top-update: ram-abi-check layout-check range-matrix-check ram-load-contract-check bank-maint programmer-bin $(TOP_UPDATE_S19)

onboard-directory-refresh: ram-abi-check layout-check range-matrix-check ram-load-contract-check bank-maint programmer-bin $(DIRECTORY_REFRESH_S19)

ryors-full-bank: $(RYORS_FULL_BANK_S19)

layout-check: $(STR8_S19) $(WORKER_S19) $(LAYOUT_CHECK_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(LAYOUT_CHECK_TOOL)

embedded-layout-check: layout-check

range-matrix-check: $(RANGE_MATRIX_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RANGE_MATRIX_TOOL) -WorkDir "$(TEST_DIR)/range-matrix"

ram-load-contract-check: $(STR8_S19) $(RAM_LOAD_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RAM_LOAD_TOOL) -MapPath "$(S19_DIR)/str8n-v1.2-f000.map"

ram-abi-check: $(RAM_ABI_CHECK_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RAM_ABI_CHECK_TOOL)

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

$(BANK_MAINT_OBJ): $(BANK_MAINT_SRC) | dirs
	$(ASM) -G -L -S -W $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-v1.2-bank-maint-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-v1.2-bank-maint-2000.sym)

$(CONSOLE_ABI_TEST_OBJ): $(CONSOLE_ABI_TEST_SRC) $(SRC_DIR)/str8-console-eq.inc | dirs
	$(ASM) -G -L -S -W -I $(SRC_DIR) $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-v1.2-console-abi-test-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-v1.2-console-abi-test-2000.sym)

$(TOP_UPDATE_INC): $(TOP_BIN) $(TOP_UPDATE_INC_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_INC_TOOL) -BinPath "$(TOP_BIN)" -OutPath "$@"

$(TOP_UPDATE_OBJ): $(TOP_UPDATE_SRC) $(TOP_UPDATE_INC) | dirs
	$(ASM) -G -L -S -W -I $(RELEASE_DIR)/generated -DSTR8_DIRECTORY_REFRESH=0 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-v1.2-top-update-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-v1.2-top-update-2000.sym)

$(DIRECTORY_REFRESH_OBJ): $(TOP_UPDATE_SRC) $(TOP_UPDATE_INC) | dirs
	$(ASM) -G -L -S -W -I $(RELEASE_DIR)/generated -DSTR8_DIRECTORY_REFRESH=1 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-v1.2-directory-refresh-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-v1.2-directory-refresh-2000.sym)

$(STR8_S19): $(STR8_OBJ) $(DELAY_OBJ) | dirs
	$(LINKER) $(STR8_LINKFLAGS) $@ $(STR8_OBJ) $(DELAY_OBJ)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S903F0000C'; Set-Content -LiteralPath $$p -Value $$lines"

$(WORKER_S19): $(WORKER_OBJ) | dirs
	$(LINKER) $(WORKER_LINKFLAGS) $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9030200FA'; Set-Content -LiteralPath $$p -Value $$lines"

$(BANK_MAINT_S19): $(BANK_MAINT_OBJ) $(BANK_MAINT_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(BANK_MAINT_CHECK_TOOL) -S19Path "$@"

$(CONSOLE_ABI_TEST_S19): $(CONSOLE_ABI_TEST_OBJ) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"

$(TOP_UPDATE_S19): $(TOP_UPDATE_OBJ) $(TOP_UPDATE_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_CHECK_TOOL) -S19Path "$@" -TopBinPath "$(TOP_BIN)"

$(DIRECTORY_REFRESH_S19): $(DIRECTORY_REFRESH_OBJ) $(TOP_UPDATE_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_CHECK_TOOL) -S19Path "$@" -TopBinPath "$(TOP_BIN)" -DirectoryRefresh

$(RYORS_FULL_BANK_S19): $(RYORS_28K_S19) $(TOP_BIN) $(RYORS_FULL_BANK_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RYORS_FULL_BANK_TOOL) -PayloadS19Path "$(RYORS_28K_S19)" -TopBinPath "$(TOP_BIN)" -S19Path "$@"

$(TOP_BIN): layout-check $(TOP_BIN_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_BIN_TOOL) -Str8MapPath "$(S19_DIR)/str8n-v1.2-f000.map" -Str8S19Path "$(STR8_S19)" -WorkerMapPath "$(S19_DIR)/str8n-v1.2-worker-0200.map" -WorkerS19Path "$(WORKER_S19)" -BinPath "$@"

$(PUBLIC_CONTRACT): $(SRC_DIR)/str8-ram-abi.inc $(SRC_DIR)/str8-jump-eq.inc $(SRC_DIR)/str8-console-eq.inc $(SRC_DIR)/str8-record-eq.inc $(SRC_DIR)/str8-worker-eq.inc $(PUBLIC_CONTRACT_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(PUBLIC_CONTRACT_TOOL) -SourceDir "$(SRC_DIR)" -OutPath "$@"

$(MANIFEST): $(TOP_BIN) $(WORKER_S19) $(BANK_MAINT_S19) $(CONSOLE_ABI_TEST_S19) $(TOP_UPDATE_S19) $(DIRECTORY_REFRESH_S19) $(PUBLIC_CONTRACT) $(MANIFEST_TOOL) FORCE
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(MANIFEST_TOOL) -Str8MapPath "$(S19_DIR)/str8n-v1.2-f000.map" -WorkerMapPath "$(S19_DIR)/str8n-v1.2-worker-0200.map" -ConsoleAbiTestMapPath "$(S19_DIR)/str8n-v1.2-console-abi-test-2000.map" -TopBinPath "$(TOP_BIN)" -WorkerS19Path "$(WORKER_S19)" -BankMaintS19Path "$(BANK_MAINT_S19)" -ConsoleAbiTestS19Path "$(CONSOLE_ABI_TEST_S19)" -TopUpdateS19Path "$(TOP_UPDATE_S19)" -DirectoryRefreshS19Path "$(DIRECTORY_REFRESH_S19)" -PublicContractPath "$(PUBLIC_CONTRACT)" -ManifestPath "$@"

FORCE:

help:
	@echo make          - build and validate resident, unified worker, and programmer BIN
	@echo release files - write BIN, S19, and S19 tests below BUILD/v1.2
	@echo manifest path - keep BUILD/str8n-manifest.json for R-YORS compatibility
	@echo make resident - build the v1.2 resident at F000
	@echo make workers  - build the one unified RAM worker
	@echo make programmer-bin - build the Bank-3 F000-FFFF T48 BIN
	@echo directory refresh - merge that BIN into a verified 128K programmer readback with tools/build_directory_refresh_image.ps1
	@echo make manifest - build the verified artifact manifest used by R-YORS
	@echo make bank-maint - build and validate the STR8-N 1.2 RAM bank-maintenance S19
	@echo make console-abi-test - build the L-loadable raw console ABI hardware probe
	@echo make top-update - build the guarded L-loadable Bank-3 sector-F updater
	@echo make onboard-directory-refresh - build the guarded L-loadable directory-pocket refresh
	@echo make ryors-full-bank - compose ASM plus HIMON plus current STR8-N as Bank 0-2 8-F S19
	@echo make layout-check - require the protected-sector layout and 8-byte margin
	@echo make embedded-layout-check - alias for layout-check
	@echo make range-matrix-check - validate every documented 4K-aligned install size
	@echo make ram-load-contract-check - validate linked L-command RAM and S9 boundaries
	@echo make ram-abi-check - reject active allocations in user RAM $1A00-$1FFF
	@echo make clean    - remove STR8N/BUILD only

clean:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path -LiteralPath '$(BUILD_DIR)') { Remove-Item -LiteralPath '$(BUILD_DIR)' -Recurse -Force }"
