# Day 06 — Báo cáo tiến độ chi tiết

- **Học viên:** Đoàn Văn Tú — 2A202603595
- **Repo:** https://github.com/tu7749/K5-L3A-Day06-DOANVANTU-2A202603595-DataIngestionEngineering
- **Cập nhật:** 13/11/2026, 18:49 (giờ Việt Nam)
- **Trạng thái:** pipeline đã chạy đầy đủ trên tập **dev** cho 3 cấu hình A/B/C. **Chưa chạy test**, chưa chấm nhãn thủ công, chưa viết báo cáo cuối.

> Mọi số liệu trong file này lấy từ lần chạy thật (`strategy_stats.json`, `traces_dev.jsonl`, output các script chẩn đoán). Mục nào chưa chạy được ghi rõ "chưa có".

---

## 1. Tổng quan nhanh

| Hạng mục | Trạng thái |
|---|---|
| Hạ tầng (Docker, PostgreSQL + pgvector, venv) | Xong |
| Corpus (đọc, chuẩn hóa, tách section) | Xong, đã đóng băng |
| Manifest | Đã sinh bằng script, **còn 3 chỗ TODO cần tự điền** |
| Benchmark 20 câu + protocol | Xong, đã commit trước khi chạy retrieval |
| Chunking A/B | Xong |
| Embedding thật + vector store | Xong |
| Chạy dev A/B/C + trace + chẩn đoán lỗi | Xong |
| Chọn cấu hình theo protocol (trước test) | Xong: **C** |
| Chạy test | **Chưa** |
| Chấm thủ công coherence / metadata / grounding | **Chưa** (phiếu coherence đã sinh, chưa có nhãn) |
| `experiment_log.csv`, `STUDENT.md`, README, báo cáo | **Chưa** |

---

## 2. Môi trường và công cụ

| Thành phần | Giá trị |
|---|---|
| Python | 3.13.13 (`.venv`) |
| PostgreSQL / pgvector | 16.16 / 0.8.7 (Docker, project `day6_student_starter`) |
| Embedding | `BAAI/bge-small-en-v1.5`, chạy local (sentence-transformers 6.3.0, torch 2.15.0) |
| Số chiều / giới hạn token | 384 / 512 |
| Query / document | query thêm tiền tố `Represent this sentence for searching relevant passages: `; document không thêm; vector chuẩn hóa |
| Metric / kiểu tìm kiếm | cosine, tìm chính xác (không dùng index xấp xỉ) |
| Chi phí | 0 USD (model local) |
| Thư mục làm việc | `.../K5-L3A-Day06-.../starter` trên MacBook |

Cách mở lại phiên làm việc (từ `starter/`):

```bash
source .venv/bin/activate
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

---

## 3. Corpus

### 3.1 Nguồn

- *Principles of Management* (OpenStax), PDF trích 80 trang: `data/raw/principles-management.pdf`.
- `document_id`: `openstax_management_ch13_ch14`.
- Trang trong PDF 80 trang bắt đầu từ 1; `printed_page = page + 360`.

### 3.2 Phạm vi và kết quả xử lý

| Chương | Tên | Trang PDF được chọn | Số trang |
|---|---|---|---:|
| 13 | Leadership | 2–31 | 30 |
| 14 | Work Motivation for Performance | 41–74 | 34 |
| | **Tổng** | | **64** |

Loại: trang 1, 32–40, 75–80 (giới thiệu, thuật ngữ, tổng kết, bài tập, case).

Kết quả `ingestion_stats.json` (lần chạy cuối, sau khi loại header chạy):

| Chỉ số | Giá trị |
|---|---:|
| Trang PDF đọc | 80 |
| Trang được chọn | 64 |
| Trang có nội dung section | **64** |
| Trang không trích xuất được text | 0 |
| Số bản ghi (section × trang) | 75 |
| Tổng ký tự | 218.405 |
| Ký tự phần mở đầu chương bị loại | 2.063 |

Số bản ghi theo section: 13.1=3, 13.2=5, 13.3=6, 13.4=4, 13.5=4, 13.6=5, 13.7=4, 13.8=5, 13.9=2, 14.1=4, 14.2=14, 14.3=16, 14.4=3.

### 3.3 Các bước chuẩn hóa

1. Chuẩn hóa Unicode NFC, thay ligature, bỏ soft hyphen và khoảng trắng đặc biệt, nối từ bị ngắt dòng, gộp khoảng trắng.
2. Loại dòng lặp `Access for free at openstax.org` (phát hiện tự động ở dòng đầu/cuối trang).
3. Loại header chạy của trang bằng hai regex, ví dụ `366 13 • Leadership` và `13.4 • The Trait Approach to Leadership 375`.
4. Dựng lại đoạn văn bằng heuristic `reflow` (nối các dòng dài, ngắt đoạn sau dòng ngắn).
5. Tách section theo tiêu đề (`13.1 The Nature of Leadership`...). Một trang có thể gồm hai section; nội dung được gán theo vị trí tiêu đề, không gán cả trang.
6. Nội dung trước tiêu đề đầu tiên của mỗi chương (phần cuối case mở đầu, chú thích Exhibit) bị loại, không đưa vào corpus.
7. Kiểm tra: cả 13 section được nhận diện đúng trang bắt đầu đã chốt (không có dòng cảnh báo `!!`).

### 3.4 Mốc đóng băng

- SHA-256 `sections.jsonl`: `650ad4f08c2ad0c7ba438059824c0866612a0a21a6ece8001be7f207934009dd`
- Từ mốc này **không sửa** `ingestion.py`, `sections.py` hay chuẩn hóa nữa, vì `evidence_quote` của benchmark phải khớp đúng văn bản này.

### 3.5 Hạn chế đã biết của corpus

- `reflow` là heuristic nên có thể ngắt đoạn nhầm (nghi ngờ ở trang 26, xem mục 7).
- Chunk không vượt qua ranh giới trang hay section, nên câu bị ngắt giữa hai trang sẽ bị tách đôi (ví dụ trang 56: `Such actions enhance intrinsic rewards.` thành chunk riêng).
- Còn 6 chunk B ngắn dưới 100 ký tự: tiêu đề thật (`Implications of Equity Theory`), nhãn `CONCEPT CHECK`, một câu bị tách do ngắt trang.
- Khối `CONCEPT CHECK` và dòng `(Attribution: ... CC-BY 4.0 license)` (13 trang) được giữ nguyên vì là nội dung thật của PDF.

---

## 4. Chunking và lưu trữ

### 4.1 Ba cấu hình

| Cấu hình | Chunking | Truy xuất |
|---|---|---|
| A | Cố định 500 ký tự, overlap 50 | Không lọc |
| B | Theo đoạn, tối đa 1000 ký tự, không overlap | Không lọc |
| C | Giống hệt B (dùng chung chunk và vector của B) | Lọc metadata khi câu hỏi có filter; câu không có filter thì chạy như B |

- B–C chỉ khác đúng một yếu tố: có áp filter hay không.
- **A–B khác cả cách chia lẫn kích thước (500 và 1000)**, nên không tách riêng được tác động của từng yếu tố. Phải ghi rõ trong báo cáo.
- Chunk được tạo trên từng bản ghi (một section trên một trang), kế thừa metadata, `chunk_id` ổn định dạng `openstax_management_ch13_ch14:p004:s13.1:par000`.

### 4.2 Metadata mỗi chunk

`document_id`, `source`, `page`, `printed_page`, `chapter` (số nguyên), `chapter_title`, `section_id` (chuỗi, ví dụ `"13.7"`), `section_title`, `language`, `char_count`, `chunker`, `chunk_index`.

Trường dùng để lọc: `chapter`, `section_id` (giá trị lấy trực tiếp từ cấu trúc sách, không suy đoán).

### 4.3 Thống kê chunk (từ `strategy_stats.json`, chạy lúc 18:39)

| Chỉ số | A | B (và C) |
|---|---:|---:|
| Số chunk | 518 | 307 |
| Tổng ký tự | 240.395 | 217.994 |
| Tổng token (bge tokenizer) | 49.615 | 44.177 |
| Ký tự min / p25 / median / p75 / max | 69 / 499 / 500 / 500 / 500 | 29 / 545 / 779 / 910 / 1000 |
| Ký tự trung bình | 464,1 | 710,1 |
| Thời gian ingest | 3,6 giây | 2,56 giây |
| Chunk vượt giới hạn token | 0 | 0 |
| Chi phí | 0 USD | 0 USD |

Lưu ý khi diễn giải: A chạy trước nên thời gian ingest của A gồm cả phần khởi động model; không dùng để kết luận A chậm hơn. Đây là một lần đo.

### 4.4 Kiểm tra lưu trữ

- Nạp lại cùng corpus hai lần: số dòng không đổi (307 = 307 với B), không nhân đôi.
- Khi corpus đổi, `upsert` xóa các chunk cũ không còn tồn tại (cùng chiến lược và tài liệu): số dòng giảm từ 313 xuống 307 sau khi loại header chạy.
- Bảng `ingest_chunks`, khóa chính `(strategy, chunk_id)`, cột `vector(384)`, tìm bằng toán tử cosine distance, đồng điểm xếp theo `chunk_id` tăng dần.
- Chỉ lưu strategy `A` và `B`; C không có dữ liệu riêng.

---

## 5. Benchmark

File: `benchmark/questions.json` (20 câu) và `benchmark/protocol.md`. Đã commit trước khi chạy retrieval (`Freeze benchmark and protocol before retrieval`, commit `647bbdb`).

| Tập | ID | Số câu | Chương 13 | Chương 14 | Có filter |
|---|---|---:|---:|---:|---:|
| Dev | q01–q15 | 15 | 8 | 7 | 2 (q07, q15) |
| Test | q16–q20 | 5 | 2 | 3 | 2 (q16, q19) |
| Tổng | | 20 | 10 | 10 | 4 |

- Loại câu: 7 direct, 4 paraphrase, 5 condition, 4 filter.
- Cả 13 section có ít nhất một câu.
- Filter: q07 `{"section_id": "13.7"}`, q15 `{"section_id": "14.2"}`, q16 `{"chapter": 13}`, q19 `{"section_id": "14.4"}`.
- `alt_gold` là rỗng cho cả 20 câu (chưa đăng ký bằng chứng thay thế).
- Kiểm tra tự động (`--validate-only`): đủ trường, đúng split, evidence khớp nguyên văn tại trang gold.
- Bốn câu filter có chữ "Within Section X" / "Chapter 13" ngay trong câu hỏi, nên A/B cũng có thể hưởng lợi từ cụm này. Protocol đã ghi nhận (`leak_risk = medium`).

**Tiêu chí chọn cấu hình (chốt trước khi xem test):** Evidence Hit@3 trên dev, nếu hòa thì Hit@1, nếu hòa thì thời gian truy xuất trung vị, nếu vẫn hòa thì chọn cấu hình đơn giản hơn.

**Lưu ý về gold:** nhãn và đáp án do AI hỗ trợ soạn, đối chiếu tự động với `sections.jsonl`. Tác giả cần đọc lại ý nghĩa từng `expected_answer` và xác nhận trước lần chạy chính thức; đây chưa phải đánh giá độc lập bởi người thứ hai.

---

## 6. Kết quả trên dev (15 câu)

### 6.1 Bảng chính

| Cấu hình | Hit@1 | Evidence Hit@3 | Đúng trang @3 | Filter tuân thủ |
|---|---:|---:|---:|---|
| A | 4/15 | 6/15 | 13/15 | 1/2 (không áp filter) |
| B | 9/15 | 11/15 | 13/15 | 0/2 (không áp filter) |
| C | 10/15 | 12/15 | 14/15 | 2/2 |

- Hit = chunk đúng nguồn/trang gold **và** chứa nguyên văn `evidence_quote` (sau khi gộp khoảng trắng). "Đúng trang @3" là chỉ số phụ để chẩn đoán, không thay Hit@3.
- Chỉ số filter của A/B chỉ cho biết top-3 tình cờ nằm trong phạm vi; con số có ý nghĩa là của C.
- Thời gian truy xuất: khoảng 8–11 ms mỗi câu (`search_ms` trong trace); tổng 15 câu: A 0,16 s, B 0,13 s, C 0,13 s (một lần đo).

### 6.2 Kết quả từng câu (Hit@3 / hạng chunk đầu tiên chứa đủ evidence)

| Câu | Loại | A | B | C |
|---|---|---|---|---|
| q01 | direct | hit, hạng 1 | hit, hạng 1 | hit, hạng 1 |
| q02 | direct | miss | hit, hạng 1 | hit, hạng 1 |
| q03 | paraphrase | miss (hạng 5) | hit, hạng 1 | hit, hạng 1 |
| q04 | direct | hit, hạng 1 | hit, hạng 1 | hit, hạng 1 |
| q05 | condition | hit, hạng 2 | hit, hạng 1 | hit, hạng 1 |
| q06 | condition | miss (hạng 8) | miss (hạng 12) | miss (hạng 12) |
| q07 | filter | miss | miss (hạng 6) | **hit, hạng 1** |
| q08 | paraphrase | miss | miss | miss |
| q09 | paraphrase | hit, hạng 1 | hit, hạng 1 | hit, hạng 1 |
| q10 | direct | hit, hạng 1 | hit, hạng 1 | hit, hạng 1 |
| q11 | condition | miss | hit, hạng 2 | hit, hạng 2 |
| q12 | paraphrase | miss | hit, hạng 2 | hit, hạng 2 |
| q13 | direct | miss | hit, hạng 1 | hit, hạng 1 |
| q14 | direct | hit, hạng 2 | hit, hạng 1 | hit, hạng 1 |
| q15 | filter | miss (hạng 20) | miss (hạng 11) | miss (hạng 8) |

### 6.3 Chẩn đoán lỗi (`scripts/diagnose_dev.py`, tìm top-200)

`None` = không chunk nào chứa trọn evidence (lỗi chunking); số lớn hơn 3 = chunk đủ evidence tồn tại nhưng bị xếp thấp (lỗi xếp hạng).

| Cấu hình | Câu trượt top-3 | Lỗi chunk cắt mất evidence | Lỗi xếp hạng |
|---|---:|---|---|
| A | 9 | 6 (q02, q07, q08, q11, q12, q13) | 3 (q03 hạng 5, q06 hạng 8, q15 hạng 20) |
| B | 4 | 1 (q08) | 3 (q06 hạng 12, q07 hạng 6, q15 hạng 11) |
| C | 3 | 1 (q08) | 2 (q06 hạng 12, q15 hạng 8) |

Output gốc nên lưu làm bằng chứng: `python -m scripts.diagnose_dev > ../results/dev_failure_diagnosis.txt 2>/dev/null`.

### 6.4 Diễn giải

- **A→B:** chunk theo đoạn 1000 ký tự giải quyết gần hết lỗi cắt mất evidence (6 câu xuống 1 câu) nhưng **không giảm lỗi xếp hạng** (3 câu ở cả hai). Chunking chỉ chữa được loại lỗi thứ nhất. Vì A và B khác cả cách chia lẫn kích thước, chỉ kết luận được ở mức "đoạn 1000 ký tự tốt hơn cửa sổ cố định 500 ký tự", không quy riêng cho cách chia.
- **B→C:** chỉ cải thiện **một câu** (q07: chunk evidence từ hạng 6 lên hạng 1 khi lọc `section_id = 13.7`). q15 vẫn trượt dù lọc đúng section 14.2 (hạng 11 → 8). Filter thu hẹp phạm vi nhưng không sửa được xếp hạng sai. Với n = 15, chênh lệch một câu không đủ để suy rộng.
- **Cấu hình được chọn theo protocol: C** (Hit@3 = 12/15 cao nhất). Phải ghi kèm giới hạn: C hơn B đúng một câu, lợi ích chỉ áp dụng khi người dùng cung cấp filter.

---

## 7. Phân tích lỗi (nguyên liệu cho báo cáo)

| Câu | Cấu hình | Nguyên nhân | Loại |
|---|---|---|---|
| q02 | A | Chunk `p004:s13.2:fix000` kết thúc ở `(see Exhibit 13.3` nên thiếu phần cuối evidence; chunk đúng trang xếp hạng 1 nhưng không hit | Cửa sổ cố định cắt ngang evidence |
| q06 | A, B, C | Chunk chứa evidence nằm đầu trang 22 và bắt đầu giữa câu; cụm "path-goal" nằm ở trang 21 nên embedding của chunk thiếu ngữ cảnh mà câu hỏi dựa vào | Chunk không vượt ranh giới trang, mất ngữ cảnh |
| q08 | A, B, C | Evidence gồm hai câu liền nhau ở trang 26, bị chia vào hai chunk kề nhau (chunk sau mở đầu bằng "Instead,"). **Cần mở bản ghi trang 26 trong `sections.jsonl` xác nhận đây là ngắt đoạn thật hay do `reflow` ngắt nhầm** | Evidence chia qua nhiều chunk |
| q15 | B, C | Chunk đúng trang 56 nhưng không phải đoạn chứa "competence, autonomy, relatedness"; câu hỏi dùng "intrinsic motivation, interesting jobs" khác mặt chữ với evidence | Embedding nhỏ xếp thấp (lỗi mô hình, không phải lỗi dữ liệu) |
| q07 | B (đã được C sửa) | Không lọc nên chunk của 13.5/13.6 chen vào top-3 | Lợi ích của filter |

Hai ví dụ gợi ý đưa vào báo cáo theo template: **q02/A** (cắt cố định) và **q06/cả ba** (mất ngữ cảnh do ranh giới trang).

---

## 8. Sự cố đã gặp và cách xử lý (ghi cho phần "cách dùng AI và kiểm chứng")

| Sự cố | Nguyên nhân | Xử lý |
|---|---|---|
| `TypeError` tiềm ẩn ở `load_pdf` | Bản code đầu dùng trường `is_empty`/`error` không có trong `DocumentPage` | Chuyển thông tin sang `metadata`, thay `ingestion.py` |
| `FileNotFoundError` khi chạy `sections` | Code dùng `starter/data/` còn PDF nằm ở `data/raw/` ở gốc repo | Tính đường dẫn từ gốc repo bằng `Path(__file__).resolve().parents[2]` |
| Terminal treo ở `heredoc>` | Dòng `EOF` bị thụt lề khi dán | Dùng script file hoặc dán đúng sát lề trái |
| Dán code Python vào zsh | Nhầm nơi dán | Dán vào file `.py` bằng editor |
| 4 chunk header chạy chen vào corpus | Số trang in thay đổi nên bộ lọc lặp không bắt được | Thêm 2 regex `RUNNING` rồi chạy lại, chốt hash mới |
| `alt_gold` lệch tên khóa giữa protocol và code | Protocol dùng `gold_source_id`/`gold_page`, code đọc `source_id`/`page` | `patch_run.py` chấp nhận cả hai |
| Thiếu tie-break và thời gian từng câu | Protocol yêu cầu nhưng code chưa có | `patch_run.py` thêm `ORDER BY distance, chunk_id` và `search_ms` |

Cách kiểm chứng đã dùng: chạy kiểm tra từng bước và đọc output thật, kiểm tra evidence khớp nguyên văn tại trang gold, kiểm tra số dòng sau nạp lại hai lần, đọc trace các câu sai, chạy chẩn đoán phân loại lỗi. Cần ghi trong báo cáo: code pipeline do AI hỗ trợ viết, tác giả chạy và kiểm tra; gold do AI hỗ trợ soạn.

---

## 9. Việc còn lại

### 9.1 Làm ngay (không phụ thuộc test)

- [ ] **Chấm coherence:** điền `label_0_2` và `reason` trong `results/coherence_audit.csv` (20 dòng: 10 vị trí × A, B; C dùng chunk của B). Thang: 0 = cắt giữa ý/thiếu chủ thể; 1 = hiểu một phần; 2 = tự hiểu được và trọn ý. Chunk bắt đầu giữa câu do ngắt trang nên được điểm thấp ở cả A và B.
- [ ] **Điền `data/manifest.json`** ba chỗ `TODO`: giấy phép nguyên văn từ trang bản quyền của **đúng file PDF này**, `accessed_at`, `snapshot_or_version`.
- [ ] **Rà soát gold:** đọc lại `expected_answer` và `evidence_quote` của 20 câu, xác nhận đồng ý.
- [ ] Mở trang 26 trong `sections.jsonl` để xác nhận nguyên nhân q08.
- [ ] Lưu bằng chứng chẩn đoán và mốc dev:

```bash
python -m scripts.diagnose_dev > ../results/dev_failure_diagnosis.txt 2>/dev/null
cp ../results/strategy_stats.json ../results/strategy_stats_dev.json
cd ..
git add -A
git commit -m "Dev results and failure diagnosis; chọn C theo protocol mục 8"
cd starter
```

Bước `cp` cần thiết vì lần chạy test sẽ ghi đè `strategy_stats.json`.

### 9.2 Chạy test (đúng một lần)

```bash
python -m src.run --split test
```

- Lệnh ghi vào `results/test_runs.log`. Nếu phải chạy lại, ghi rõ lý do trong báo cáo và nói rằng test không còn độc lập.
- Sinh thêm `metadata_audit.csv` và `grounding_audit.csv` (top-3 của 5 câu test × A/B/C).
- Sau khi có kết quả test không được chỉnh cấu hình theo test.

### 9.3 Chấm thủ công sau test

- [ ] **Metadata** (`metadata_audit.csv`): với mỗi bản ghi top-3, kiểm tra `source`, `page`, `chapter`, `section_id` so với nguồn; ghi số đủ và đúng / tổng và từng lỗi. Riêng hai câu filter test (q16, q19): báo số câu có kết quả không rỗng và mọi kết quả tuân thủ filter / 2.
- [ ] **Grounding** (`grounding_audit.csv`): chấm top-3 của 5 câu test theo thang 0/1/2 (không có bằng chứng / có nhưng thiếu điều kiện / đủ để trả lời và truy nguồn). Báo số câu ở từng mức và trung bình /2.
- Người chấm là tác giả; ghi rõ nguy cơ thiên lệch. Không suy ra nhãn chỉ từ khớp chuỗi.

### 9.4 Hồ sơ nộp

- [ ] `artifacts/experiment_log.csv`: điền bằng số liệu thật (cần xem dòng tiêu đề của file để điền đúng cột).
- [ ] `STUDENT.md`: họ tên, MSSV 2A202603595, lớp L3A, chủ đề và corpus, link repo, commit chốt bài.
- [ ] `README.md`: lệnh setup/chạy, đường dẫn dữ liệu và kết quả.
- [ ] Báo cáo `report/individual/2A202603595_DOANVANTU.md` theo `REPORT_TEMPLATE.md`.
- [ ] Kiểm tra `.gitignore` (không commit `.env`, `.venv/`, secret), xác nhận repo mở được cho người chấm, nộp link theo kênh giảng viên chỉ định.

### 9.5 Thí nghiệm bổ sung tùy chọn (còn dư thời gian)

Gọi là mở rộng D; **chỉ đánh giá trên dev**, ghi rõ trong báo cáo, không thay cấu hình đã chốt:

1. **A-1000:** cửa sổ cố định 1000 ký tự (overlap 100) để tách tác động của kích thước khỏi cách chia khi so với B.
2. **Gắn tiêu đề vào text khi embed** (ví dụ `section_title` đứng đầu chunk) để thử chữa lỗi mất ngữ cảnh kiểu q06. Lưu ý đây thay đổi văn bản được embed nên phải nêu rõ.
3. **Hybrid với BM25** (mở rộng tùy chọn của GUIDE): chọn tham số trên dev, ghi cả trường hợp làm xấu kết quả.

---

## 10. Ánh xạ sang rubric (100 điểm)

| Hạng mục | Điểm | Tình trạng bằng chứng |
|---|---:|---|
| Corpus và xử lý | 20 | Có: 64 trang nội dung, truy vết nguồn/trang, thống kê. **Thiếu:** 3 TODO trong manifest (giấy phép nguyên văn, ngày tải, version) |
| Ba chiến lược và lưu trữ | 20 | Có: 3 cấu hình, so sánh có kiểm soát, embedding thật, pgvector, filter, nạp lại không trùng. **Thiếu:** `experiment_log.csv` |
| Benchmark và retrieval | 20 | Có: 20 câu, evidence xác minh, dev/test chốt trước, trace dev. **Thiếu:** trace và chỉ số test |
| Năm khía cạnh và phân tích | 25 | Có: retrieval dev, phân tích data strategy (A–B, B–C), ví dụ lỗi. **Thiếu:** nhãn coherence, metadata, grounding; số liệu test |
| Tái lập và báo cáo | 15 | Có: lệnh chạy, model/chi phí, artifacts. **Thiếu:** báo cáo cuối, README, `STUDENT.md` |

---

## 11. Giới hạn cần nêu trong báo cáo

- Corpus hẹp (một cuốn sách, 2 chương); test chỉ 5 câu nên độ bất định cao; split theo câu hỏi trong cùng corpus, không phải đánh giá chuyển miền.
- Gold do AI hỗ trợ soạn; tác giả tự chấm nhãn thủ công (nguy cơ thiên lệch).
- A và B khác cả cách chia lẫn kích thước; lợi ích của C dựa trên một câu (q07).
- Chunk không vượt ranh giới trang/section; `reflow` là heuristic.
- Thời gian ingest và truy xuất chỉ đo một lần, có yếu tố khởi động model.
- Giấy phép: chưa xác minh từ chính file PDF; một nguồn khác ghi giấy phép CC BY-NC-SA 4.0 cho bản audiobook của sách này, cần đối chiếu và chép nguyên văn từ PDF.
- Kết quả chỉ áp dụng cho corpus này, không suy rộng.

---

## 12. Danh sách file chính

```text
data/raw/principles-management.pdf       # PDF 80 trang
data/processed/sections.jsonl            # corpus đã chuẩn hóa (đóng băng, hash ở mục 3.4)
data/manifest.json                       # còn 3 TODO
benchmark/questions.json                 # 20 câu
benchmark/protocol.md
starter/src/{ingestion,sections,chunking,embeddings,store,evaluation,run}.py
starter/scripts/{check_chunks,check_short,smoke_test,make_manifest,patch_run,diagnose_dev}.py
artifacts/strategies.json
results/ingestion_stats.json
results/strategy_stats.json              # sẽ bị ghi đè khi chạy test -> đã/cần copy sang _dev
results/traces_dev.jsonl
results/metrics_dev.csv
results/coherence_audit.csv              # đã sinh, chưa có nhãn
results/errors.jsonl
```

Chưa tồn tại: `results/traces_test.jsonl`, `metrics_test.csv`, `metadata_audit.csv`, `grounding_audit.csv`, `test_runs.log`, `dev_failure_diagnosis.txt`, `strategy_stats_dev.json`, báo cáo cuối.