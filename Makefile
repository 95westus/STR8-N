ASM ?= wdc02as
LINKER ?= wdcln

SRC_DIR := src
BUILD_DIR := BUILD
VERSION := v1.29
VERSION_TEXT := 1.29
RELEASE_DIR := $(BUILD_DIR)/$(VERSION)
STR8_IN65_VERSION := v1.29
STR8_IN65_VERSION_TEXT := 1.29
STR8_IN65_RELEASE_DIR := $(BUILD_DIR)/$(STR8_IN65_VERSION)
STR8_IN65_S19_DIR := $(STR8_IN65_RELEASE_DIR)/s19
STR8_IN65_BIN_DIR := $(STR8_IN65_RELEASE_DIR)/bin
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
RELEASE_DEFINES := -DSTR8_V1_LAYOUT -DSTR8_V1_INSTALLER_DRY -DSTR8_V1_INSTALLER_TXN -DSTR8_IN65_COLD_BOOT -DSTR8_IN65_VERSION_129 -DSTR8_IN65_EDU_QUIET_START
STR8_IN65_DEFINES := $(RELEASE_DEFINES)

STR8_SRC := $(SRC_DIR)/str8.asm
WORKER_SRC := $(SRC_DIR)/str8-worker.asm
DELAY_SRC := $(SRC_DIR)/util-delay.asm
STR8_INCLUDES := \
	$(SRC_DIR)/str8-config-eq.inc \
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
STR8_IN65_OBJ := $(OBJ_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65.obj
DELAY_OBJ := $(OBJ_DIR)/util-delay.obj
WORKER_OBJ := $(OBJ_DIR)/str8n-worker.obj

STR8_S19 := $(S19_DIR)/str8n-$(VERSION)-f000.s19
STR8_MAP := $(STR8_S19:.s19=.map)
STR8_IN65_S19 := $(STR8_IN65_S19_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-f000.s19
STR8_IN65_MAP := $(STR8_IN65_S19:.s19=.map)
WORKER_S19 := $(S19_DIR)/str8n-$(VERSION)-worker-0200.s19
WORKER_MAP := $(WORKER_S19:.s19=.map)
TOP_BIN_TOOL := tools/build_str8n_top_bin.ps1
LAYOUT_CHECK_TOOL := tools/check_str8n_layout.ps1
MANIFEST_TOOL := tools/write_str8n_manifest.ps1
PUBLIC_CONTRACT_TOOL := tools/write_str8n_public_contract.ps1
RANGE_MATRIX_TOOL := tools/test_s19_range_matrix.ps1
RAM_LOAD_TOOL := tools/test_ram_load_contract.ps1
RAM_ABI_CHECK_TOOL := tools/check_ram_abi_sources.ps1
BANK_MAINT_SRC := tools/bank-maint/str8n-v1.23-bank-maint-2000.asm
BANK_MAINT_RENAME_SRC := tools/bank-maint/str8n-v1.23-bank-maint-rename.inc
BANK_MAINT_OBJ := $(OBJ_DIR)/str8n-$(VERSION)-bank-maint-2000.obj
BANK_MAINT_S19 := $(S19_DIR)/str8n-$(VERSION)-bank-maint-2000.s19
BANK_MAINT_CHECK_TOOL := tools/check_bank_maint_s19.ps1
BANK_MAINT_MENU_SRC := tools/bank-maint/str8n-v1.23-bank-maint-menu-2000.asm
BANK_MAINT_MENU_OBJ := $(OBJ_DIR)/str8n-$(VERSION)-bank-maint-menu-2000.obj
BANK_MAINT_MENU_S19 := $(S19_DIR)/str8n-$(VERSION)-bank-maint-menu-2000.s19
BANK_MAINT_MENU_A := tools/bank-maint/str8n-$(VERSION)-bank-maint-menu-2000.a
BANK_MAINT_MENU_A_TOOL := tools/make_bank_maint_menu_a.ps1
STR8_IN65_BANK_MAINT_SRC := tools/str8-in65/str8n-$(STR8_IN65_VERSION)-str8-in65-bank-maint-2000.asm
STR8_IN65_BANK_MAINT_FLAGS_SRC := tools/bank-maint/str8n-v1.28-str8-in65-bank-maint-flags.inc
STR8_IN65_BANK_MAINT_OBJ := $(OBJ_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-bank-maint-2000.obj
STR8_IN65_BANK_MAINT_S19 := $(STR8_IN65_S19_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-bank-maint-2000.s19
CONSOLE_ABI_TEST_SRC := tools/console-abi-test/str8n-v1.23-console-abi-test-2000.asm
CONSOLE_ABI_TEST_OBJ := $(OBJ_DIR)/str8n-$(VERSION)-console-abi-test-2000.obj
CONSOLE_ABI_TEST_S19 := $(S19_DIR)/str8n-$(VERSION)-console-abi-test-2000.s19
CONSOLE_ABI_TEST_MAP := $(CONSOLE_ABI_TEST_S19:.s19=.map)
TOP_UPDATE_SRC := tools/top-update/str8n-v1.23-top-update-2000.asm
TOP_UPDATE_INC_TOOL := tools/make_top_update_image_inc.ps1
TOP_UPDATE_INC := $(RELEASE_DIR)/generated/str8n-$(VERSION)-top-image.inc
TOP_UPDATE_CHECK_TOOL := tools/check_top_update_s19.ps1
TOP_UPDATE_OBJ := $(OBJ_DIR)/str8n-$(VERSION)-top-update-2000.obj
TOP_UPDATE_S19 := $(S19_DIR)/str8n-$(VERSION)-top-update-2000.s19
DIRECTORY_REFRESH_OBJ := $(OBJ_DIR)/str8n-$(VERSION)-directory-refresh-2000.obj
DIRECTORY_REFRESH_S19 := $(S19_DIR)/str8n-$(VERSION)-directory-refresh-2000.s19
RYORS_28K_S19 ?= ../R-YORS/SRC/BUILD/s19/ryors-v1.2-himon-asm-bank3-8-e.s19
RYORS_FULL_BANK_TOOL := tools/build_ryors_full_bank_s19.ps1
RYORS_FULL_BANK_S19 := $(S19_DIR)/ryors-v1.2-str8n-himon-asm-bank0-2-8-f.s19
WDCMONV2_ARCHIVE_SRC := tools/wdcmonv2/wdcmonv2str8n-archive-2000.asm
WDCMONV2_ARCHIVE_OBJ := $(OBJ_DIR)/str8n-$(VERSION)-wdcmonv2-archive-2000.obj
WDCMONV2_ARCHIVE_S19 := $(S19_DIR)/str8n-$(VERSION)-wdcmonv2-archive-2000.s19
WDCMONV2_ARCHIVE_MAP := $(WDCMONV2_ARCHIVE_S19:.s19=.map)
WDCMONV2_ARCHIVE_CHECK := tools/wdcmonv2/check_wdcmonv2_archive.ps1
WDCMONV2_ARCHIVE_EXTRACT := tools/wdcmonv2/extract_wdcmonv2_archive.ps1
WDCMONV2_INSTALL_SRC := tools/wdcmonv2/wdcmonv2str8n-install-2000.asm
WDCMONV2_INSTALL_OBJ := $(OBJ_DIR)/str8n-$(VERSION)-wdcmonv2-install-2000.obj
WDCMONV2_INSTALL_S19 := $(S19_DIR)/str8n-$(VERSION)-wdcmonv2-install-2000.s19
WDCMONV2_INSTALL_MAP := $(WDCMONV2_INSTALL_S19:.s19=.map)
WDCMONV2_INSTALL_CHECK := tools/wdcmonv2/check_wdcmonv2_install.ps1
WDCMONV2_INSTALL_INC_TOOL := tools/wdcmonv2/make_wdcmonv2_install_image_inc.ps1
WDCMONV2_INSTALL_INC := $(RELEASE_DIR)/generated/str8n-$(VERSION)-wdcmonv2-install-image.inc
WDCMONV2_INSTALL_TOP_BIN := $(BIN_DIR)/str8n-$(VERSION)-wdcmonv2-bank3-f000-ffff.bin
STR8_IN65_TOP_BIN := $(STR8_IN65_BIN_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-bank3-f000-ffff.bin
STR8_IN65_GENERATED_INC := $(STR8_IN65_RELEASE_DIR)/generated/str8n-$(STR8_IN65_VERSION)-str8-in65-test-image.inc
STR8_IN65_CANDIDATE_BIN := $(STR8_IN65_BIN_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-wdcmonv2-bank3-f000-ffff.bin
STR8_IN65_INSTALL_OBJ := $(OBJ_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-wdcmonv2-install-2000.obj
STR8_IN65_INSTALL_S19 := $(STR8_IN65_S19_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-wdcmonv2-install-2000.s19
STR8_IN65_INSTALL_MAP := $(STR8_IN65_INSTALL_S19:.s19=.map)
STR8_IN65_STOCK_RESTORE_OBJ := $(OBJ_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-factory-restore-2000.obj
STR8_IN65_STOCK_RESTORE_S19 := $(STR8_IN65_S19_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-factory-restore-2000.s19
STR8_IN65_STOCK_RESTORE_MAP := $(STR8_IN65_STOCK_RESTORE_S19:.s19=.map)
STR8_IN65_STOCK_RESTORE_CHECK := tools/str8-in65/check_stock_restore_s19.ps1
STR8_IN65_TOP_UPDATE_INC := $(STR8_IN65_RELEASE_DIR)/generated/str8n-$(STR8_IN65_VERSION)-str8-in65-top-image.inc
STR8_IN65_TOP_UPDATE_OBJ := $(OBJ_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-top-update-2000.obj
STR8_IN65_TOP_UPDATE_S19 := $(STR8_IN65_S19_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-top-update-2000.s19
STR8_IN65_IMAGE_TOOL := tools/str8-in65/build_str8_in65_test_image.ps1
STR8_IN65_BASE_128K ?=
STR8_IN65_TEST_128K := $(STR8_IN65_RELEASE_DIR)/local/str8n-$(STR8_IN65_VERSION)-str8-in65-cold-reset-test-128k.bin
STR8_IN65_TEST_RECEIPT := $(STR8_IN65_TEST_128K:.bin=.receipt.txt)
STR8_IN65_PROMOTION_CHECK := tools/str8-in65/check_str8_in65_promotion.ps1
WDCMONV2_HOST_LOADER := tools/wdcmonv2/start_wdcmonv2_ram.ps1
WDCMONV2_QUICK_MIGRATE := tools/wdcmonv2/MIGRATE-WDC-TO-STR8N.ps1
WDCMONV2_PACKAGE_TOOL := tools/wdcmonv2/make_wdcmonv2_migration_package.ps1
WDCMONV2_PACKAGE_CHECK := tools/wdcmonv2/check_wdcmonv2_migration_package.ps1
WDCMONV2_PACKAGE_VERIFY := tools/wdcmonv2/verify_wdcmonv2_migration_kit.ps1
WDCMONV2_PACKAGE_DIR := $(RELEASE_DIR)/wdcmonv2-str8n-migration-kit
WDCMONV2_PACKAGE_ZIP := $(RELEASE_DIR)/str8n-$(VERSION)-wdcmonv2-str8n-migration-kit.zip
TOP_BIN := $(BIN_DIR)/str8n-$(VERSION)-bank3-f000-ffff.bin
MANIFEST := $(BUILD_DIR)/str8n-manifest.json
PUBLIC_CONTRACT := $(INCLUDE_DIR)/str8n-public.inc

.NOTPARALLEL:
.PHONY: all resident workers programmer-bin str8-in65-test-top str8-in65-test-image str8-in65-ram-installer str8-in65-stock-restore str8-in65-factory-restore str8-in65-top-update str8-in65-bank-maint str8-in65-promotion-check manifest bank-maint bank-maint-menu console-abi-test top-update onboard-directory-refresh ryors-full-bank wdcmonv2-archive wdcmonv2-install wdcmonv2-host-check wdcmonv2-package layout-check embedded-layout-check range-matrix-check ram-load-contract-check ram-abi-check clean help dirs FORCE

all: manifest range-matrix-check ram-load-contract-check ram-abi-check console-abi-test top-update onboard-directory-refresh wdcmonv2-archive wdcmonv2-install wdcmonv2-host-check str8-in65-promotion-check

resident: $(STR8_S19)

workers: $(WORKER_S19)

programmer-bin: $(TOP_BIN)

# Deliberately excluded from `all`, manifest, migration kit, and release ZIP.
# This retains the exact accepted STR8-iN/65 migration policy while canonical
# STR8-N v1.29 is the promoted STR8-iN/65 production image.
str8-in65-test-top: $(STR8_IN65_CANDIDATE_BIN)

str8-in65-test-image: $(STR8_IN65_CANDIDATE_BIN) $(STR8_IN65_IMAGE_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(STR8_IN65_IMAGE_TOOL) -BaseImagePath "$(STR8_IN65_BASE_128K)" -TopBinPath "$(STR8_IN65_CANDIDATE_BIN)" -OutPath "$(STR8_IN65_TEST_128K)" -ReceiptPath "$(STR8_IN65_TEST_RECEIPT)"

str8-in65-ram-installer: $(STR8_IN65_INSTALL_S19)

# Board-lab baseline reconstruction only.  This is not part of `all`, the
# manifest, or the consumer migration kit.
str8-in65-stock-restore: $(STR8_IN65_STOCK_RESTORE_S19)

str8-in65-factory-restore: $(STR8_IN65_STOCK_RESTORE_S19)

str8-in65-top-update: $(STR8_IN65_TOP_UPDATE_S19)

str8-in65-bank-maint: $(STR8_IN65_BANK_MAINT_S19)

str8-in65-promotion-check: $(TOP_BIN) $(STR8_IN65_TOP_BIN) $(STR8_IN65_CANDIDATE_BIN) $(STR8_IN65_PROMOTION_CHECK)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(STR8_IN65_PROMOTION_CHECK) -CanonicalTopPath "$(TOP_BIN)" -AcceptedTopPath "$(STR8_IN65_TOP_BIN)" -MigrationTopPath "$(STR8_IN65_CANDIDATE_BIN)"

manifest: $(MANIFEST)

bank-maint: $(BANK_MAINT_S19)

bank-maint-menu: $(BANK_MAINT_MENU_S19) $(BANK_MAINT_MENU_A)

console-abi-test: $(CONSOLE_ABI_TEST_S19)

top-update: ram-abi-check layout-check range-matrix-check ram-load-contract-check bank-maint programmer-bin $(TOP_UPDATE_S19)

onboard-directory-refresh: ram-abi-check layout-check range-matrix-check ram-load-contract-check bank-maint programmer-bin $(DIRECTORY_REFRESH_S19)

ryors-full-bank: $(RYORS_FULL_BANK_S19)

wdcmonv2-archive: $(WDCMONV2_ARCHIVE_S19)

wdcmonv2-install: $(WDCMONV2_INSTALL_S19)

wdcmonv2-host-check: $(WDCMONV2_HOST_LOADER) $(WDCMONV2_ARCHIVE_S19) $(WDCMONV2_INSTALL_S19)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_HOST_LOADER) -SelfTest
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_HOST_LOADER) -ImagePath "$(WDCMONV2_ARCHIVE_S19)" -ValidateOnly
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_HOST_LOADER) -ImagePath "$(WDCMONV2_INSTALL_S19)" -ValidateOnly

wdcmonv2-package: $(WDCMONV2_PACKAGE_ZIP)

layout-check: $(STR8_S19) $(WORKER_S19) $(LAYOUT_CHECK_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(LAYOUT_CHECK_TOOL)

embedded-layout-check: layout-check

range-matrix-check: $(RANGE_MATRIX_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RANGE_MATRIX_TOOL) -WorkDir "$(TEST_DIR)/range-matrix"

ram-load-contract-check: $(STR8_S19) $(RAM_LOAD_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RAM_LOAD_TOOL) -MapPath "$(STR8_MAP)"

ram-abi-check: $(RAM_ABI_CHECK_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RAM_ABI_CHECK_TOOL)

dirs:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "@('$(OBJ_DIR)','$(LST_DIR)','$(SYM_DIR)','$(S19_DIR)','$(BIN_DIR)','$(STR8_IN65_S19_DIR)','$(STR8_IN65_BIN_DIR)') | ForEach-Object { New-Item -ItemType Directory -Force -Path $$_ | Out-Null }"

$(STR8_OBJ): $(STR8_SRC) $(STR8_INCLUDES) | dirs
	$(ASM) $(ASFLAGS) $(RELEASE_DEFINES) $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n.sym)

$(STR8_IN65_OBJ): $(STR8_SRC) $(STR8_INCLUDES) | dirs
	$(ASM) $(ASFLAGS) $(STR8_IN65_DEFINES) $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65.sym)

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

$(BANK_MAINT_OBJ): $(BANK_MAINT_SRC) $(BANK_MAINT_RENAME_SRC) | dirs
	$(ASM) -G -L -S -W -I tools/bank-maint -DSTR8_BANK_MAINT_TOP=0 -DSTR8_IN65_BANK_MAINT=0 -DSTR8_IN65_VERSION_129=1 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(VERSION)-bank-maint-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(VERSION)-bank-maint-2000.sym)

$(BANK_MAINT_MENU_OBJ): $(BANK_MAINT_MENU_SRC) $(BANK_MAINT_SRC) $(BANK_MAINT_RENAME_SRC) $(TOP_UPDATE_SRC) $(TOP_UPDATE_INC) | dirs
	$(ASM) -G -L -S -W -I tools/bank-maint -I tools/top-update -I $(RELEASE_DIR)/generated -DSTR8_IN65_BANK_MAINT=0 -DSTR8_IN65_VERSION_129=1 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(VERSION)-bank-maint-menu-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(VERSION)-bank-maint-menu-2000.sym)

$(STR8_IN65_BANK_MAINT_OBJ): $(STR8_IN65_BANK_MAINT_SRC) $(BANK_MAINT_SRC) $(BANK_MAINT_RENAME_SRC) $(STR8_IN65_BANK_MAINT_FLAGS_SRC) | dirs
	$(ASM) -G -L -S -W -I tools/bank-maint $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-bank-maint-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-bank-maint-2000.sym)

$(CONSOLE_ABI_TEST_OBJ): $(CONSOLE_ABI_TEST_SRC) $(SRC_DIR)/str8-console-eq.inc | dirs
	$(ASM) -G -L -S -W -I $(SRC_DIR) $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(VERSION)-console-abi-test-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(VERSION)-console-abi-test-2000.sym)

$(TOP_UPDATE_INC): $(TOP_BIN) $(TOP_UPDATE_INC_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_INC_TOOL) -BinPath "$(TOP_BIN)" -OutPath "$@" -Identity "STR8-N $(VERSION_TEXT)"

$(TOP_UPDATE_OBJ): $(TOP_UPDATE_SRC) $(TOP_UPDATE_INC) | dirs
	$(ASM) -G -L -S -W -I $(RELEASE_DIR)/generated -DSTR8_TOP_EMBED=0 -DSTR8_DIRECTORY_REFRESH=0 -DSTR8_IN65_VERSION_129=1 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(VERSION)-top-update-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(VERSION)-top-update-2000.sym)

$(STR8_IN65_TOP_UPDATE_INC): $(STR8_IN65_CANDIDATE_BIN) $(TOP_UPDATE_INC_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_INC_TOOL) -BinPath "$(STR8_IN65_CANDIDATE_BIN)" -OutPath "$@" -Identity "STR8-N $(STR8_IN65_VERSION_TEXT)"

$(STR8_IN65_TOP_UPDATE_OBJ): $(TOP_UPDATE_SRC) $(STR8_IN65_TOP_UPDATE_INC) | dirs
	$(ASM) -G -L -S -W -I $(STR8_IN65_RELEASE_DIR)/generated -DSTR8_TOP_EMBED=0 -DSTR8_DIRECTORY_REFRESH=0 -DSTR8_IN65_TOP_IMAGE -DSTR8_IN65_VERSION_129 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-top-update-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-top-update-2000.sym)

$(DIRECTORY_REFRESH_OBJ): $(TOP_UPDATE_SRC) $(TOP_UPDATE_INC) | dirs
	$(ASM) -G -L -S -W -I $(RELEASE_DIR)/generated -DSTR8_TOP_EMBED=0 -DSTR8_DIRECTORY_REFRESH=1 -DSTR8_IN65_VERSION_129=1 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(VERSION)-directory-refresh-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(VERSION)-directory-refresh-2000.sym)

$(WDCMONV2_ARCHIVE_OBJ): $(WDCMONV2_ARCHIVE_SRC) | dirs
	$(ASM) -G -L -S -W $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(VERSION)-wdcmonv2-archive-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(VERSION)-wdcmonv2-archive-2000.sym)

$(WDCMONV2_INSTALL_INC): $(TOP_BIN) $(WDCMONV2_INSTALL_INC_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_INSTALL_INC_TOOL) -TopBinPath "$(TOP_BIN)" -OutPath "$@" -CandidateBinPath "$(WDCMONV2_INSTALL_TOP_BIN)"

$(WDCMONV2_INSTALL_OBJ): $(WDCMONV2_INSTALL_SRC) $(WDCMONV2_INSTALL_INC) | dirs
	$(ASM) -G -L -S -W -I $(RELEASE_DIR)/generated -DSTR8_IN65_VERSION_129=1 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(VERSION)-wdcmonv2-install-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(VERSION)-wdcmonv2-install-2000.sym)

$(STR8_IN65_INSTALL_OBJ): $(WDCMONV2_INSTALL_SRC) $(STR8_IN65_GENERATED_INC) | dirs
	$(ASM) -G -L -S -W -I $(STR8_IN65_RELEASE_DIR)/generated -DW2I_STR8_IN65_IMAGE -DSTR8_IN65_VERSION_129 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-wdcmonv2-install-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-wdcmonv2-install-2000.sym)

$(STR8_IN65_STOCK_RESTORE_OBJ): $(WDCMONV2_INSTALL_SRC) | dirs
	$(ASM) -G -L -S -W -DW2I_RESTORE_STOCK=1 -DSTR8_IN65_VERSION_129=1 $<
	@if exist $(subst /,\,$(<:.asm=.obj)) move /Y $(subst /,\,$(<:.asm=.obj)) $(subst /,\,$@)
	@if exist $(subst /,\,$(<:.asm=.lst)) move /Y $(subst /,\,$(<:.asm=.lst)) $(subst /,\,$(LST_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-factory-restore-2000.lst)
	@if exist $(subst /,\,$(<:.asm=.sym)) move /Y $(subst /,\,$(<:.asm=.sym)) $(subst /,\,$(SYM_DIR)/str8n-$(STR8_IN65_VERSION)-str8-in65-factory-restore-2000.sym)

$(STR8_S19): $(STR8_OBJ) $(DELAY_OBJ) | dirs
	$(LINKER) $(STR8_LINKFLAGS) $@ $(STR8_OBJ) $(DELAY_OBJ)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S903F0000C'; Set-Content -LiteralPath $$p -Value $$lines"

$(STR8_IN65_S19): $(STR8_IN65_OBJ) $(DELAY_OBJ) | dirs
	$(LINKER) $(STR8_LINKFLAGS) $@ $(STR8_IN65_OBJ) $(DELAY_OBJ)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S903F0000C'; Set-Content -LiteralPath $$p -Value $$lines"

$(WORKER_S19): $(WORKER_OBJ) | dirs
	$(LINKER) $(WORKER_LINKFLAGS) $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9030200FA'; Set-Content -LiteralPath $$p -Value $$lines"

$(BANK_MAINT_S19): $(BANK_MAINT_OBJ) $(BANK_MAINT_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(BANK_MAINT_CHECK_TOOL) -S19Path "$@" -VersionText "$(VERSION_TEXT)"

$(BANK_MAINT_MENU_S19): $(BANK_MAINT_MENU_OBJ) $(BANK_MAINT_CHECK_TOOL) $(TOP_UPDATE_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(BANK_MAINT_CHECK_TOOL) -S19Path "$@" -SourcePath "$(BANK_MAINT_SRC)" -VersionText "$(VERSION_TEXT)" -MenuTop
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_CHECK_TOOL) -S19Path "$@" -TopBinPath "$(TOP_BIN)" -VersionText "$(VERSION_TEXT)"

$(STR8_IN65_BANK_MAINT_S19): $(STR8_IN65_BANK_MAINT_OBJ) $(BANK_MAINT_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(BANK_MAINT_CHECK_TOOL) -S19Path "$@" -VersionText "$(STR8_IN65_VERSION_TEXT)" -In65 -FlagsSourcePath "$(STR8_IN65_BANK_MAINT_FLAGS_SRC)"

$(BANK_MAINT_MENU_A): $(BANK_MAINT_MENU_S19) $(BANK_MAINT_MENU_A_TOOL)
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(BANK_MAINT_MENU_A_TOOL) -S19Path "$<" -OutPath "$@"

$(CONSOLE_ABI_TEST_S19): $(CONSOLE_ABI_TEST_OBJ) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"

$(TOP_UPDATE_S19): $(TOP_UPDATE_OBJ) $(TOP_UPDATE_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_CHECK_TOOL) -S19Path "$@" -TopBinPath "$(TOP_BIN)" -VersionText "$(VERSION_TEXT)"

$(STR8_IN65_TOP_UPDATE_S19): $(STR8_IN65_TOP_UPDATE_OBJ) $(TOP_UPDATE_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_CHECK_TOOL) -S19Path "$@" -TopBinPath "$(STR8_IN65_CANDIDATE_BIN)" -VersionText "$(STR8_IN65_VERSION_TEXT)"

$(DIRECTORY_REFRESH_S19): $(DIRECTORY_REFRESH_OBJ) $(TOP_UPDATE_CHECK_TOOL) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_UPDATE_CHECK_TOOL) -S19Path "$@" -TopBinPath "$(TOP_BIN)" -VersionText "$(VERSION_TEXT)" -DirectoryRefresh

$(WDCMONV2_ARCHIVE_S19): $(WDCMONV2_ARCHIVE_OBJ) $(WDCMONV2_ARCHIVE_CHECK) $(WDCMONV2_ARCHIVE_EXTRACT) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_ARCHIVE_CHECK) -SourcePath "$(WDCMONV2_ARCHIVE_SRC)" -S19Path "$@" -MapPath "$(WDCMONV2_ARCHIVE_MAP)" -ExtractorPath "$(WDCMONV2_ARCHIVE_EXTRACT)"

$(WDCMONV2_INSTALL_S19): $(WDCMONV2_INSTALL_OBJ) $(WDCMONV2_INSTALL_CHECK) $(TOP_BIN) $(WDCMONV2_INSTALL_TOP_BIN) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_INSTALL_CHECK) -SourcePath "$(WDCMONV2_INSTALL_SRC)" -S19Path "$@" -MapPath "$(WDCMONV2_INSTALL_MAP)" -TopBinPath "$(TOP_BIN)" -CandidateBinPath "$(WDCMONV2_INSTALL_TOP_BIN)" -VersionText "$(VERSION_TEXT)"

$(STR8_IN65_INSTALL_S19): $(STR8_IN65_INSTALL_OBJ) $(WDCMONV2_INSTALL_CHECK) $(STR8_IN65_TOP_BIN) $(STR8_IN65_CANDIDATE_BIN) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_INSTALL_CHECK) -SourcePath "$(WDCMONV2_INSTALL_SRC)" -S19Path "$@" -MapPath "$(STR8_IN65_INSTALL_MAP)" -TopBinPath "$(STR8_IN65_TOP_BIN)" -CandidateBinPath "$(STR8_IN65_CANDIDATE_BIN)" -VersionText "$(STR8_IN65_VERSION_TEXT)"

$(STR8_IN65_STOCK_RESTORE_S19): $(STR8_IN65_STOCK_RESTORE_OBJ) $(STR8_IN65_STOCK_RESTORE_CHECK) $(WDCMONV2_HOST_LOADER) | dirs
	$(LINKER) -g -s -t -hm19 -j -o $@ $<
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$@'; $$lines=Get-Content -LiteralPath $$p; $$lines[-1]='S9032000DC'; Set-Content -LiteralPath $$p -Value $$lines"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(STR8_IN65_STOCK_RESTORE_CHECK) -SourcePath "$(WDCMONV2_INSTALL_SRC)" -S19Path "$@" -MapPath "$(STR8_IN65_STOCK_RESTORE_MAP)" -VersionText "$(STR8_IN65_VERSION_TEXT)"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_HOST_LOADER) -ImagePath "$@" -ValidateOnly

$(WDCMONV2_INSTALL_TOP_BIN): $(WDCMONV2_INSTALL_INC)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Test-Path -LiteralPath '$@' -PathType Leaf)) { throw 'Missing generated migration candidate: $@' }"

$(WDCMONV2_PACKAGE_ZIP): $(WDCMONV2_ARCHIVE_S19) $(WDCMONV2_INSTALL_S19) $(TOP_BIN) $(STR8_S19) $(STR8_IN65_BANK_MAINT_S19) $(WDCMONV2_INSTALL_INC) $(WDCMONV2_HOST_LOADER) $(WDCMONV2_QUICK_MIGRATE) $(WDCMONV2_PACKAGE_TOOL) $(WDCMONV2_PACKAGE_CHECK) $(WDCMONV2_PACKAGE_VERIFY) $(WDCMONV2_ARCHIVE_SRC) $(WDCMONV2_INSTALL_SRC) $(WDCMONV2_ARCHIVE_EXTRACT) docs/STR8_IN65_QUICKSTART.txt docs/WDCMONV2_MIGRATION.md docs/WDCMONV2_MIGRATION_BOARD_TEST.md docs/WDCMONV2_MIGRATION_PROVENANCE.md docs/STR8_IN65_BANK_MAINTENANCE.md docs/HIMON_ASMF2_AFTER_STR8N.md LICENSE | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_HOST_LOADER) -SelfTest
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_HOST_LOADER) -ImagePath "$(WDCMONV2_ARCHIVE_S19)" -ValidateOnly
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_HOST_LOADER) -ImagePath "$(WDCMONV2_INSTALL_S19)" -ValidateOnly
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_PACKAGE_TOOL) -ArchiveS19Path "$(WDCMONV2_ARCHIVE_S19)" -InstallS19Path "$(WDCMONV2_INSTALL_S19)" -CandidateBinPath "$(TOP_BIN)" -CanonicalS19Path "$(STR8_S19)" -BankMaintS19Path "$(STR8_IN65_BANK_MAINT_S19)" -InstallIncludePath "$(WDCMONV2_INSTALL_INC)" -KitDirectory "$(WDCMONV2_PACKAGE_DIR)" -ZipPath "$@"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_PACKAGE_CHECK) -KitDirectory "$(WDCMONV2_PACKAGE_DIR)" -ZipPath "$@" -ArchiveS19Path "$(WDCMONV2_ARCHIVE_S19)" -InstallS19Path "$(WDCMONV2_INSTALL_S19)" -TopBinPath "$(TOP_BIN)" -CandidateBinPath "$(TOP_BIN)" -CanonicalS19Path "$(STR8_S19)" -BankMaintS19Path "$(STR8_IN65_BANK_MAINT_S19)"
	@powershell -NoProfile -ExecutionPolicy Bypass -File "$(WDCMONV2_PACKAGE_DIR)/VERIFY-PACKAGE.ps1"

$(RYORS_FULL_BANK_S19): $(RYORS_28K_S19) $(TOP_BIN) $(RYORS_FULL_BANK_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(RYORS_FULL_BANK_TOOL) -PayloadS19Path "$(RYORS_28K_S19)" -TopBinPath "$(TOP_BIN)" -S19Path "$@"

$(TOP_BIN): layout-check $(TOP_BIN_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_BIN_TOOL) -Str8MapPath "$(STR8_MAP)" -Str8S19Path "$(STR8_S19)" -WorkerMapPath "$(WORKER_MAP)" -WorkerS19Path "$(WORKER_S19)" -BinPath "$@"

$(STR8_IN65_TOP_BIN): $(STR8_IN65_S19) $(WORKER_S19) $(LAYOUT_CHECK_TOOL) $(TOP_BIN_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(LAYOUT_CHECK_TOOL) -Str8MapPath "$(STR8_IN65_MAP)" -Str8S19Path "$(STR8_IN65_S19)" -WorkerMapPath "$(WORKER_MAP)" -WorkerS19Path "$(WORKER_S19)"
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(TOP_BIN_TOOL) -Str8MapPath "$(STR8_IN65_MAP)" -Str8S19Path "$(STR8_IN65_S19)" -WorkerMapPath "$(WORKER_MAP)" -WorkerS19Path "$(WORKER_S19)" -BinPath "$@"

$(STR8_IN65_GENERATED_INC): $(STR8_IN65_TOP_BIN) $(WDCMONV2_INSTALL_INC_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(WDCMONV2_INSTALL_INC_TOOL) -TopBinPath "$(STR8_IN65_TOP_BIN)" -OutPath "$@" -CandidateBinPath "$(STR8_IN65_CANDIDATE_BIN)"

$(STR8_IN65_CANDIDATE_BIN): $(STR8_IN65_GENERATED_INC)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Test-Path -LiteralPath '$@' -PathType Leaf)) { throw 'Missing generated STR8-iN/65 candidate: $@' }"

$(PUBLIC_CONTRACT): $(SRC_DIR)/str8-config-eq.inc $(SRC_DIR)/str8-ram-abi.inc $(SRC_DIR)/str8-jump-eq.inc $(SRC_DIR)/str8-console-eq.inc $(SRC_DIR)/str8-record-eq.inc $(SRC_DIR)/str8-worker-eq.inc $(PUBLIC_CONTRACT_TOOL) | dirs
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(PUBLIC_CONTRACT_TOOL) -SourceDir "$(SRC_DIR)" -OutPath "$@"

$(MANIFEST): $(TOP_BIN) $(WORKER_S19) $(BANK_MAINT_S19) $(CONSOLE_ABI_TEST_S19) $(TOP_UPDATE_S19) $(DIRECTORY_REFRESH_S19) $(WDCMONV2_ARCHIVE_S19) $(WDCMONV2_INSTALL_S19) $(PUBLIC_CONTRACT) $(MANIFEST_TOOL) FORCE
	@powershell -NoProfile -ExecutionPolicy Bypass -File $(MANIFEST_TOOL) -Str8MapPath "$(STR8_MAP)" -WorkerMapPath "$(WORKER_MAP)" -ConsoleAbiTestMapPath "$(CONSOLE_ABI_TEST_MAP)" -TopBinPath "$(TOP_BIN)" -WorkerS19Path "$(WORKER_S19)" -BankMaintS19Path "$(BANK_MAINT_S19)" -ConsoleAbiTestS19Path "$(CONSOLE_ABI_TEST_S19)" -TopUpdateS19Path "$(TOP_UPDATE_S19)" -DirectoryRefreshS19Path "$(DIRECTORY_REFRESH_S19)" -Wdcmonv2ArchiveMapPath "$(WDCMONV2_ARCHIVE_MAP)" -Wdcmonv2ArchiveS19Path "$(WDCMONV2_ARCHIVE_S19)" -Wdcmonv2InstallMapPath "$(WDCMONV2_INSTALL_MAP)" -Wdcmonv2InstallS19Path "$(WDCMONV2_INSTALL_S19)" -Wdcmonv2InstallTopBinPath "$(WDCMONV2_INSTALL_TOP_BIN)" -PublicContractPath "$(PUBLIC_CONTRACT)" -ManifestPath "$@"

FORCE:

help:
	@echo make          - build and validate resident, unified worker, and programmer BIN
	@echo release files - write BIN, S19, and S19 tests below BUILD/$(VERSION)
	@echo manifest path - BUILD/str8n-manifest.json records the standalone STR8-N release
	@echo make resident - build the $(VERSION) resident at F000
	@echo make workers  - build the one unified RAM worker
	@echo make programmer-bin - build the Bank-3 F000-FFFF T48 BIN
	@echo make str8-in65-test-top - build the isolated STR8-iN/65 cold-reset test top; not shipped
	@echo make str8-in65-test-image STR8_IN65_BASE_128K=C:\path\stock.bin - merge only that top into a local 128K image
	@echo make str8-in65-ram-installer - build the guarded RAM installer carrying only the STR8-iN/65 fixed top
	@echo make str8-in65-factory-restore - build the board-lab-only B0-to-B3 restore, then erase B0
	@echo make str8-in65-top-update - build the L-loadable STR8-iN/65-only B3:F updater; not shipped
	@echo make str8-in65-bank-maint - build the v1.29 interactive directory/search-flag RAM tool
	@echo directory refresh - merge that BIN into a verified 128K programmer readback with tools/build_directory_refresh_image.ps1
	@echo make manifest - build the verified standalone STR8-N artifact manifest
	@echo make bank-maint - build and validate the STR8-N $(VERSION_TEXT) RAM bank-maintenance S19
	@echo make bank-maint-menu - build menu Bank Maintenance with guarded B3:F update and ASM-F2 .a carrier
	@echo make console-abi-test - build the L-loadable raw console ABI hardware probe
	@echo make top-update - build the guarded L-loadable Bank-3 sector-F updater
	@echo make onboard-directory-refresh - build the guarded L-loadable directory-pocket refresh
	@echo make ryors-full-bank - compose ASM plus HIMON plus current STR8-N as Bank 0-2 8-F S19
	@echo make wdcmonv2-archive - build and validate the read-only stock-monitor bank archive S19
	@echo make wdcmonv2-install - build and validate the guarded stock-monitor-to-STR8-N installer S19
	@echo make wdcmonv2-package - package only the WDCMONv2-to-STR8-N migration; HIMON/ASM-F2 are separate loads
	@echo make wdcmonv2-host-check - self-test the binary monitor bridge and validate both migration S19 files
	@echo make wdcmonv2-package - build an allowlisted publishable migration ZIP with no WDC firmware or local archives
	@echo make layout-check - require the resident to end at or before the fixed worker
	@echo make embedded-layout-check - alias for layout-check
	@echo make range-matrix-check - validate every documented 4K-aligned install size
	@echo make ram-load-contract-check - validate linked L-command RAM and S9 boundaries
	@echo make ram-abi-check - reject active allocations in user RAM $1A00-$1FFF
	@echo make clean    - remove STR8N/BUILD only

clean:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path -LiteralPath '$(BUILD_DIR)') { Remove-Item -LiteralPath '$(BUILD_DIR)' -Recurse -Force }"
