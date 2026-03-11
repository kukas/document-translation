set -euo pipefail

srclang=${1:-cs}
trglang=${2:-de}
tikal=~/apps/okapi-framework/tikal.sh
outdir="output"

tmdir=../../../redmine_data/cs-de/dev

mkdir -p $outdir

pipeline() {
    fullpath=$1
    file=${fullpath##*/}
    echo "Processing ${file}"
    
    if [ ! -f "$fullpath" ]; then
        echo "File $fullpath does not exist."
        return 1
    fi
    if [ -f "${outdir}/${file}.uk" ]; then
        echo "File $fullpath exists already, skipping."
        return 0
    fi

    echo "Unescaping ${file}"
    python unescape_fraus.py --skip-xml-declaration ${fullpath} ${outdir}/${file}

    echo "Extracting text from XML ${file}"
    format="okf_xml@fraus.fprm"
    $tikal -xm ${outdir}/${file} -fc $format -sl ${srclang} -to ${outdir}/${file}

    echo "Unescaping HTML ${file}"
    python escape_tool.py --unescape ${outdir}/${file}.${srclang} ${outdir}/${file}.${srclang}.html

    awk '{ print "<p>" $0 "</p>" }' ${outdir}/${file}.${srclang}.html > ${outdir}/${file}.${srclang}.p.html

    echo "Extracting text from HTML ${file}"
    format_2="okf_html"
    $tikal -xm ${outdir}/${file}.${srclang}.p.html -fc $format_2 -sl ${srclang} -to ${outdir}/${file}.${srclang}.second_extraction

    basefile=${file%%.*}
    translate_markup ${outdir}/${file}.${srclang}.second_extraction.${srclang} ${srclang} ${trglang} ${outdir}/${file}.${trglang}.second_extraction.${trglang} --tm ${tmdir}/src/${basefile}.txt ${tmdir}/trg/${basefile}.txt

    $tikal -lm ${outdir}/${file}.${srclang}.p.html -fc $format_2 -sl ${srclang} -tl ${trglang} -overtrg -from ${outdir}/${file}.${trglang}.second_extraction.${trglang} -to ${outdir}/${file}.${trglang}.p.html
    sed "s/^<p>\(.*\)<\/p>$/\1/" ${outdir}/${file}.${trglang}.p.html > ${outdir}/${file}.${trglang}.html
    $tikal -lm ${outdir}/${file} -fc $format -sl ${srclang} -tl ${trglang} -overtrg -from ${outdir}/${file}.${trglang}.html -to ${outdir}/${file}.${trglang}

    # python unescape_fraus.py --skip-xml-declaration ${outdir}/${file}.reconstructed ${outdir}/${file}.reconstructed.normalized
    # tikal -lm ${outdir}/${file} -fc $format -sl cs -tl uk -overtrg -from ${outdir}/${file}.cs.unescaped.notags -to ${outdir}/${file}.uk
}

# Files to process: passed as extra arguments after srclang/trglang, or default
files=("${@:3}")
if [ ${#files[@]} -eq 0 ]; then
    files=(../../../redmine_data/edukate-dev/edu01892.xml)
fi

for file in "${files[@]}"; do
    time pipeline "$file"
done
