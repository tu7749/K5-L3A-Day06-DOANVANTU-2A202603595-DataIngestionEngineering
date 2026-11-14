from pathlib import Path

p = Path("src/run.py")
s = p.read_text(encoding="utf-8")
pairs = [
    ('        for h in t["hits"]:\n            m = h["metadata"]\n',
     '        for rank, h in enumerate(t["hits"], 1):\n            m = h["metadata"]\n'),
    ('h["rank"], h["chunk_id"], h["source"]', 'rank, h["chunk_id"], h["source"]'),
    ('''f"[{h['rank']}] (p{h['page']}) {h['text']}" for h in t["hits"])''',
     '''f"[{i}] (p{h['page']}) {h['text']}" for i, h in enumerate(t["hits"], 1))'''),
]
for old, new in pairs:
    print("OK" if old in s else "KHÔNG THẤY", old[:50].replace("\n", " "))
    s = s.replace(old, new)
p.write_text(s, encoding="utf-8")