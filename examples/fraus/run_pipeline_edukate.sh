set -euo pipefail

srclang=${1:-cs}
trglang=${2:-de}
outdir=${3:-output/${trglang}}
tmpdir=${4:-${outdir}/tmp}
tmdir=${5:-${tmpdir}/00.merged_TMs}
global_tmdir=${6:-}
tikal=~/apps/okapi-framework/tikal.sh

mkdir -p "$outdir" "$tmpdir"

pipeline() {
    fullpath=$1
    file=${fullpath##*/}
    echo "Processing ${file}"
    
    if [ ! -f "$fullpath" ]; then
        echo "File $fullpath does not exist."
        return 1
    fi
    if [ -f "${outdir}/${file}.${trglang}" ]; then
        echo "File $fullpath exists already, skipping."
        return 0
    fi

    echo "Extracting JSON Textdocs from Fraus XML ${file}"
    python3 edUKate/scripts/extract_textdocs.py --split-to-sents basic --doc-level "/DOC/ExercisePages" < ${fullpath} > ${tmpdir}/${file}.${srclang}.textdocs.jsonl

    echo "Extracting content from JSON Textdocs ${file}"
    jq -r '.content[].text | gsub("\n"; "\\n")' ${tmpdir}/${file}.${srclang}.textdocs.jsonl > ${tmpdir}/${file}.${srclang}.textdocs.txt

    echo "Wrapping Textdocs content in <doc> and <tu> tags to obtain valid simplified XML ${file}"
    echo '<?xml version="1.0" encoding="utf-8"?>' > ${tmpdir}/${file}.${srclang}.textdocs.xml
    echo '<doc>' >> ${tmpdir}/${file}.${srclang}.textdocs.xml
    awk '{ print "<tu>" $0 "</tu>" }' ${tmpdir}/${file}.${srclang}.textdocs.txt >> ${tmpdir}/${file}.${srclang}.textdocs.xml
    echo '</doc>' >> ${tmpdir}/${file}.${srclang}.textdocs.xml

    echo "Extracting content for translation from simplified XML ${file}"
    format="okf_xml@fraus-textdocs.fprm"
    $tikal -xm ${tmpdir}/${file}.${srclang}.textdocs.xml -fc $format -sl ${srclang} -to ${tmpdir}/${file}.${srclang}.textdocs.xml

    echo "Translating from ${srclang} to ${trglang} ${file}"
    basefile=${file%%.*}
    global_tm_args=()
    if [ -n "${global_tmdir}" ] && [ -f "${global_tmdir}/src/global.txt" ]; then
        global_tm_args=(--global-tm "${global_tmdir}/src/global.txt" "${global_tmdir}/trg/global.txt")
    fi
    lindat_model_name="llmtranslate-1:edukate_${srclang}${trglang}_v1"
    translate_markup ${tmpdir}/${file}.${srclang}.textdocs.xml.${srclang} ${srclang} ${trglang} ${lindat_model_name} ${tmpdir}/${file}.${trglang}.textdocs.xml.${trglang} --tm ${tmdir}/src/${basefile}.txt ${tmdir}/trg/${basefile}.txt "${global_tm_args[@]}"
    #python fix_text_outside_g.py ${tmpdir}/${file}.${trglang}.textdocs.xml.${trglang} ${tmpdir}/${file}.${trglang}.textdocs.xml.${trglang}.fixed_g

    echo "Reconstructing simplified XML using the translated content ${file}"
    $tikal -lm ${tmpdir}/${file}.${srclang}.textdocs.xml -fc $format -sl ${srclang} -tl ${trglang} -overtrg -from ${tmpdir}/${file}.${trglang}.textdocs.xml.${trglang} -to ${tmpdir}/${file}.${trglang}.textdocs.xml

    echo "Unwrapping <doc> and <tu> tags to obtain translated Textdocs content ${file}"
    cat ${tmpdir}/${file}.${trglang}.textdocs.xml | grep '<tu>' | sed 's|<tu>||g; s|</tu>||g' > ${tmpdir}/${file}.${trglang}.textdocs.txt

    echo "Fixing potential issues in the structure of the translated Textdocs content ${file}"
    python3 fix_textdocs_structure.py ${tmpdir}/${file}.${trglang}.textdocs.txt ${tmpdir}/${file}.${trglang}.textdocs.fixed.txt

    echo "Reconstructing the Textdocs JSON structure using the translated content ${file}"
    python3 replace_textdocs_texts.py ${tmpdir}/${file}.${trglang}.textdocs.fixed.txt < ${tmpdir}/${file}.${srclang}.textdocs.jsonl > ${tmpdir}/${file}.${trglang}.textdocs.jsonl

    echo "Reconstructing the original XML structure using the translated Textdocs ${file}"
    python3 edUKate/scripts/import_textdoc_to_orig.py ${tmpdir}/${file}.${trglang}.textdocs.jsonl < ${fullpath} > ${outdir}/${file}
    # sed "s/^<p>\(.*\)<\/p>$/\1/" ${tmpdir}/${file}.${trglang}.p.html > ${tmpdir}/${file}.${trglang}.html
    # $tikal -lm ${tmpdir}/${file} -fc $format -sl ${srclang} -tl ${trglang} -overtrg -from ${tmpdir}/${file}.${trglang}.html -to ${outdir}/${file}
}

# Files to process: passed as extra arguments after srclang/trglang/outdir/tmpdir/tmdir/global_tmdir, or default
files=("${@:7}")
if [ ${#files[@]} -eq 0 ]; then
    files=(../../../redmine_data/edukate-dev/edu01892.xml)
fi

for file in "${files[@]}"; do
    base=$(basename "$file" .xml)
    if [[ " ${SKIP_FILES:-} " == *" ${base} "* ]]; then
        echo "Skipping ${base} (in SKIP_FILES)"
        continue
    fi
    time pipeline "$file"
done
