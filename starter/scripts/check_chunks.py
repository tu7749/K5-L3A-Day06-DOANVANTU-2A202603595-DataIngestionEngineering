from src.sections import load_corpus
from src.chunking import fixed_size, by_paragraph
ps = load_corpus()
A = [c for p in ps for c in fixed_size(p, 500, 50)]
B = [c for p in ps for c in by_paragraph(p, 1000)]
for n, cs in (("A", A), ("B", B)):
    L = sorted(len(c.text) for c in cs)
    print(n, len(cs), "min", L[0], "median", L[len(L)//2], "max", L[-1])
print(B[10].text)
