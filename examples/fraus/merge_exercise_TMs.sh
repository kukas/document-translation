#!/bin/bash

input_dir=$1
output_dir=$2

for side in src trg; do
    mkdir -p "${output_dir}/${side}"
    for tm in ${input_dir}/${side}/*.txt; do
        # Extract the base filename without extension and strip the -xx page number suffix
        basefile=$(basename "$tm" .txt | sed 's/-[0-9]\+$//')
        cat "$tm" >> "${output_dir}/${side}/${basefile}.txt"
    done
done