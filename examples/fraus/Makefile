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
SKIP_FILES ?= edu03248 edu30838 edu30056 edu31714 edu32072 edu33382 \
              edu01957 edu30835 edu30837 edu33527 edu34989

OUT_DIR    ?= output/$(SPLIT)/$(TRGLANG)
TMP_DIR    ?= tmp/intermediate/$(SPLIT)/$(TRGLANG)
TM_DIR     ?= tmp/merged_TMs/$(SPLIT)/$(TRGLANG)

MERGED_TM_DIR = $(TM_DIR)

# ── top-level targets ─────────────────────────────────────────────────────────
.PHONY: all merge_tms pipeline check_structure clean

## Run the full pipeline (merge_tms → pipeline)
all: pipeline

## Stage 1 – merge per-page TM files into per-document TMs
merge_tms: $(MERGED_TM_DIR)/.merged

$(MERGED_TM_DIR)/.merged:
	mkdir -p $(MERGED_TM_DIR)
	bash merge_exercise_TMs.sh $(TM_SRC_DIR) $(MERGED_TM_DIR)
	touch $@

## Stage 2 – run the translation pipeline on the source XML files
pipeline: merge_tms
	SKIP_FILES="$(SKIP_FILES)" bash run_pipeline_edukate.sh $(SRCLANG) $(TRGLANG) $(OUT_DIR) $(TMP_DIR) $(TM_DIR) $(SRCFILES)

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
	rm -rf $(OUT_DIR)
