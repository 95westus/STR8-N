ASM ?= wdc02as
LINKER ?= wdcln
PYTHON ?= python
CURRENT_OUT ?= BUILD/current
BUILD_CHECK_OUT ?= tmp/current-build-check
INSTALLER_CHECK_OUT ?= tmp/current-installer-check
DEPS_02 ?= BUILD/v1.30/local/test-deps
DEPS_816 ?= BUILD/test-deps-816
.DEFAULT_GOAL := all

.PHONY: all current check current-check installer-check installer-help help

all: current

current:
	"$(PYTHON)" -B tools/build_current.py --out "$(CURRENT_OUT)" --assembler "$(ASM)" --linker "$(LINKER)"

check: current-check installer-check

current-check:
	"$(PYTHON)" -B tools/test_current_build.py --out "$(BUILD_CHECK_OUT)"

installer-check:
	"$(PYTHON)" -B tools/test_current_installer.py --out "$(INSTALLER_CHECK_OUT)" --deps-02 "$(DEPS_02)" --deps-816 "$(DEPS_816)"

installer-help:
	"$(PYTHON)" -B tools/install_current.py --help

help:
	@echo make - build src/current and verify the established firmware baselines
	@echo make current CURRENT_OUT=BUILD/current-r2 - select a fresh build directory
	@echo make current-check BUILD_CHECK_OUT=tmp/build-check-r2 - isolated offline build checks
	@echo make installer-check INSTALLER_CHECK_OUT=tmp/installer-check-r2 - offline installer and CPU-model checks
	@echo make check - run both offline suites; select fresh output directories for repeats
	@echo make installer-help - show the shared installer command line without opening ports
