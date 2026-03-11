SHELL=/bin/bash

# ── configurable variables ────────────────────────────────────────────────────
SRCLANG    ?= cs
TRGLANG    ?= de

# Source XML file(s) – override on the command line, e.g.
#   make SRCFILES="../../../redmine_data/edukate-dev/edu01884.xml"
SRCFILES   ?= ../../../redmine_data/edukate-dev/edu01892.xml

SPLIT_DIR  = output/00.split
OUT_DIR    = output

# ── derive split-file lists from source XMLs ──────────────────────────────────
# After splitting edu01892.xml we get edu01892-01.xml, edu01892-02.xml, …
# We use stamp files (*.split) to represent the (unknown-until-runtime) set of
# split outputs, then collect the second-extraction XLIFF files from that dir.

SPLIT_STAMPS = $(foreach f,$(SRCFILES),$(SPLIT_DIR)/$(notdir $(basename $(f))).split)

# ── top-level targets ─────────────────────────────────────────────────────────
.PHONY: all split pipeline clean

## Run the full pipeline (split → pipeline)
all: pipeline

## Stage 1 – split source XML files into per-ExercisePage files
split: $(SPLIT_STAMPS)

## Stage 2 – extract text from every split file
pipeline: split
	bash run_pipeline_edukate.sh $(SRCLANG) $(TRGLANG) $(SPLIT_DIR)/*.xml

## Remove all generated files
clean:
	rm -rf $(SPLIT_DIR) $(OUT_DIR)

# ── pattern rule: split one source XML ───────────────────────────────────────
# The stamp file is touched after splitting so Make knows the step is done.
$(SPLIT_DIR)/%.split: $(dir $(firstword $(SRCFILES)))%.xml
	mkdir -p $(SPLIT_DIR)
	python split_exercise_pages.py $< $(SPLIT_DIR)
	touch $@

# Fallback: find the source XML in any of the SRCFILES directories
$(SPLIT_DIR)/%.split: %.xml
	mkdir -p $(SPLIT_DIR)
	python split_exercise_pages.py $< $(SPLIT_DIR)
	touch $@
