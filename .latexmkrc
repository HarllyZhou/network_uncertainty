# Keep the PDF next to the .tex source. Send intermediate files
# (.aux, .log, .bbl, .fls, synctex, …) to ./.latex/
$pdf_mode = 1;
$out_dir = '.';
$aux_dir = '.latex';
$emulate_aux = 1;

# Run bibtex from the .tex directory so relative paths such as
# ../draft/network_uncertainty.bib and ../draft/aer.bst still resolve.
# TeX Live's default openout_any=p refuses writes into a subdirectory.
$bibtex_fudge = 0;
$bibtex = 'openout_any=a bibtex %O %S';

$pdflatex = 'pdflatex -synctex=1 -interaction=nonstopmode -file-line-error %O %S';

# latexmk moves synctex next to the PDF; put it back with the aux files.
$success_cmd = 'mkdir -p .latex; if [ -f %R.synctex.gz ]; then mv -f %R.synctex.gz .latex/; fi';
