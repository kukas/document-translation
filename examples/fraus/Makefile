SHELL=/bin/bash

# ── configurable variables ────────────────────────────────────────────────────
SRCLANG    ?= cs
TRGLANG    ?= de

# Dataset split: dev or test (controls SRCFILES and TM_SRC_DIR defaults)
SPLIT      ?= dev

# Source XML file(s) – override on the command line, e.g.
#   make SRCFILES="../../../redmine_data/edukate-dev/edu01884.xml"
SRCFILES   ?= ../../../redmine_data/edukate-$(SPLIT)/edu*.xml

# Source TM directory (contains src/ and trg/ sub-dirs with per-page TM files)
TM_SRC_DIR ?= ../../../redmine_data/$(SRCLANG)-$(TRGLANG)/$(SPLIT)

# Space-separated list of document IDs (without .xml) to skip in the pipeline
SKIP_FILES ?= edu03248 edu30838 edu30056 \
              edu01957 edu30835 edu34989

OUT_DIR    ?= output/$(SPLIT)/$(TRGLANG)
TMP_DIR    ?= tmp/intermediate/$(SPLIT)/$(TRGLANG)
TM_DIR     ?= tmp/merged_TMs/$(SPLIT)/$(TRGLANG)
GLOBAL_TM_DIR ?= tmp/global_TM/$(TRGLANG)
EXTRA_TM_DIR  ?= extra_TM

MERGED_TM_DIR = $(TM_DIR)

# ── top-level targets ─────────────────────────────────────────────────────────
.PHONY: all merge_tms merge_global_tm pipeline check_structure clean

## Run the full pipeline (merge_tms → pipeline)
all: pipeline

## Stage 1 – merge per-page TM files into per-document TMs
merge_tms: $(MERGED_TM_DIR)/.merged

$(MERGED_TM_DIR)/.merged:
	mkdir -p $(MERGED_TM_DIR)
	bash merge_exercise_TMs.sh $(TM_SRC_DIR) $(MERGED_TM_DIR)
	touch $@

## Stage 2 – run the translation pipeline on the source XML files
pipeline: merge_tms merge_global_tm
	SKIP_FILES="$(SKIP_FILES)" bash run_pipeline_edukate.sh $(SRCLANG) $(TRGLANG) $(OUT_DIR) $(TMP_DIR) $(TM_DIR) $(GLOBAL_TM_DIR) $(SRCFILES)

## Merge all per-document TMs for the current TRGLANG (both splits) into a single global TM
# Also appends any extra TMs found in EXTRA_TM_DIR (if present).
merge_global_tm:
	mkdir -p $(GLOBAL_TM_DIR)/src $(GLOBAL_TM_DIR)/trg
	truncate -s 0 $(GLOBAL_TM_DIR)/src/global.txt $(GLOBAL_TM_DIR)/trg/global.txt
	@for split in dev test; do \
	    dir=tmp/merged_TMs/$$split/$(TRGLANG); \
	    if [ -d "$$dir/src" ] && ls $$dir/src/*.txt >/dev/null 2>&1; then \
	        echo "Adding $$split TMs from $$dir"; \
	        cat $$dir/src/*.txt >> $(GLOBAL_TM_DIR)/src/global.txt; \
	        cat $$dir/trg/*.txt >> $(GLOBAL_TM_DIR)/trg/global.txt; \
	    fi; \
	done
	@if [ -f "$(EXTRA_TM_DIR)/$(SRCLANG).txt" ]; then \
	    echo "Appending extra TMs from $(EXTRA_TM_DIR)"; \
	    cat $(EXTRA_TM_DIR)/$(SRCLANG).txt >> $(GLOBAL_TM_DIR)/src/global.txt; \
	    cat $(EXTRA_TM_DIR)/$(TRGLANG).txt >> $(GLOBAL_TM_DIR)/trg/global.txt; \
	fi
	@echo "Global TM written to $(GLOBAL_TM_DIR) ($$(wc -l < $(GLOBAL_TM_DIR)/src/global.txt) lines)"

## Stage 3 – compare every translated output XML with its source XML
# For each source file  path/to/foo.xml  the pipeline writes  $(OUT_DIR)/foo.xml.
# We loop over SRCFILES, derive the output path, and run compare_xml_structure.py.
check_structure:
	@ok=0; fail=0; \
	for src in $(SRCFILES); do \
	    base=$$(basename "$$src"); \
	    out=$(OUT_DIR)/$$base; \
	    if [ ! -f "$$out" ]; then \
	        echo "SKIP  $$base  (output not found: $$out)"; \
	        continue; \
	    fi; \
	    if python compare_xml_structure.py --skip-xml-declaration "$$src" "$$out" --verbose; then \
	        echo "OK    $$base"; \
	        ok=$$((ok+1)); \
	    else \
	        echo "FAIL  $$base"; \
	        fail=$$((fail+1)); \
	    fi; \
	done; \
	echo ""; \
	echo "Structure check: $$ok OK, $$fail FAILED."; \
	[ $$fail -eq 0 ]

## Remove all generated files
clean:
	rm -rf $(OUT_DIR) $(GLOBAL_TM_DIR)
