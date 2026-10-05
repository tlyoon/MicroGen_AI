import glob, os
import fix_latex as fl

all_tex = glob.glob("*.tex")
clean_or_defective = [f for f in all_tex if f.startswith(("cleaned_", "defective_"))]
diffpattern = sorted(set(all_tex) - set(clean_or_defective))

for q in diffpattern:
    print(q)    
    fl.fix_latex(str(q))
            
[ os.remove(i) for i in clean_or_defective ]
[ os.remove(i) for i in glob.glob('*.aux') ]
[ os.remove(i) for i in glob.glob('*.log') ]
[ os.remove(i) for i in glob.glob('*.out') ]
[ os.remove(i) for i in glob.glob('*.toc') ]
[ os.remove(i) for i in glob.glob('*.nav') ]
[ os.remove(i) for i in glob.glob('*.synctex.gz') ]


