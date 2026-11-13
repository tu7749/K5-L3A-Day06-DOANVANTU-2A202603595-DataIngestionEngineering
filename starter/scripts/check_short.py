from src.sections import load_corpus
from src.chunking import by_paragraph

ps = load_corpus()
B = [c for p in ps for c in by_paragraph(p, 1000)]
short = [c for c in B if len(c.text) < 100]
print("B chunk < 100 ký tự:", len(short))
for c in short[:15]:
    print(c.chunk_id, repr(c.text))
attr = [p.page for p in ps if "Attribution" in p.text]
print("trang có dòng Attribution:", len(attr), attr[:10])