set -euo pipefail

srclang=${1:-cs}
trglang=${2:-de}
outdir=${3:-output/${trglang}}
tmpdir=${4:-${outdir}/tmp}
tmdir=${5:-${tmpdir}/00.merged_TMs}
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

    echo "Unescaping ${file}"
    python unescape_fraus.py --skip-xml-declaration ${fullpath} ${tmpdir}/${file}

    echo "Extracting text from XML ${file}"
    format="okf_xml@fraus.fprm"
    $tikal -xm ${tmpdir}/${file} -fc $format -sl ${srclang} -to ${tmpdir}/${file}

    echo "Unescaping HTML ${file}"
    python escape_tool.py --unescape ${tmpdir}/${file}.${srclang} ${tmpdir}/${file}.${srclang}.html

    awk '{ print "<p>" $0 "</p>" }' ${tmpdir}/${file}.${srclang}.html > ${tmpdir}/${file}.${srclang}.p.html

    echo "Extracting text from HTML ${file}"
    format_2="okf_html@fraus.fprm"
    $tikal -xm ${tmpdir}/${file}.${srclang}.p.html -fc $format_2 -sl ${srclang} -to ${tmpdir}/${file}.${srclang}.second_extraction

    basefile=${file%%.*}
    translate_markup ${tmpdir}/${file}.${srclang}.second_extraction.${srclang} ${srclang} ${trglang} ${tmpdir}/${file}.${trglang}.second_extraction.${trglang} --tm ${tmdir}/src/${basefile}.txt ${tmdir}/trg/${basefile}.txt
    python fix_text_outside_g.py ${tmpdir}/${file}.${trglang}.second_extraction.${trglang} ${tmpdir}/${file}.${trglang}.fixed_g.${trglang}

    $tikal -lm ${tmpdir}/${file}.${srclang}.p.html -fc $format_2 -sl ${srclang} -tl ${trglang} -overtrg -from ${tmpdir}/${file}.${trglang}.fixed_g.${trglang} -to ${tmpdir}/${file}.${trglang}.p.html
    sed "s/^<p>\(.*\)<\/p>$/\1/" ${tmpdir}/${file}.${trglang}.p.html > ${tmpdir}/${file}.${trglang}.html
    $tikal -lm ${tmpdir}/${file} -fc $format -sl ${srclang} -tl ${trglang} -overtrg -from ${tmpdir}/${file}.${trglang}.html -to ${outdir}/${file}

    # python unescape_fraus.py --skip-xml-declaration ${tmpdir}/${file}.reconstructed ${tmpdir}/${file}.reconstructed.normalized
    # tikal -lm ${tmpdir}/${file} -fc $format -sl cs -tl uk -overtrg -from ${tmpdir}/${file}.cs.unescaped.notags -to ${outdir}/${file}.uk
}

# Files to process: passed as extra arguments after srclang/trglang/outdir/tmpdir/tmdir, or default
files=("${@:6}")
if [ ${#files[@]} -eq 0 ]; then
    files=(../../../redmine_data/edukate-dev/edu01892.xml)
fi

for file in "${files[@]}"; do
    time pipeline "$file"
done
