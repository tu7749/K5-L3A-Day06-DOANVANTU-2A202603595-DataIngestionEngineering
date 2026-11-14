# Day06 — Data Ingestion Engineering

**Học viên:** Đoàn Văn Tú · **MSSV:** 2A202603595 · **Lớp:** L3A

Dự án xây dựng pipeline đọc, chuẩn hóa, chia chunk, tạo embedding và truy xuất kiến thức từ hai chương của sách *Principles of Management* (OpenStax). Ba cấu hình A/B/C được so sánh trên cùng corpus và benchmark để đánh giá tác động của chunking và metadata filter.

Embedding chạy local bằng `BAAI/bge-small-en-v1.5`; vector được lưu trong PostgreSQL + pgvector. Pipeline và đánh giá cuối cùng không yêu cầu API key. Grounding đánh giá mức độ đầy đủ của bằng chứng trong top-3, không phải chất lượng câu trả lời do LLM sinh.

## 1. Cấu trúc và đường dẫn

Các đường dẫn dưới đây tính từ thư mục gốc repository:

| Đường dẫn | Nội dung |
|---|---|
| `starter/src/` | Mã nguồn pipeline ingestion, chunking, embedding, lưu trữ và đánh giá |
| `starter/scripts/check_setup.py` | Kiểm tra kết nối PostgreSQL và pgvector |
| `starter/requirements.txt` | Dependencies Python |
| `starter/docker-compose.yml` | Cấu hình database local |
| `starter/.env.example` | Mẫu cấu hình môi trường |
| `data/raw/principles-management.pdf` | PDF nguồn trích 80 trang |
| `data/processed/sections.jsonl` | Corpus đã chuẩn hóa, 75 bản ghi section × trang |
| `data/manifest.json` | Nguồn, giấy phép, phạm vi trang và hash dữ liệu |
| `benchmark/questions.json` | 20 câu hỏi, split và gold evidence |
| `benchmark/protocol.md` | Quy trình đánh giá và quy tắc chấm |
| `artifacts/experiment_log.csv` | Cấu hình, giả thuyết và kết quả A/B/C |
| `results/` | Thống kê, metrics, trace và phiếu audit |
| `report/individual/2A202603595_DoanVanTu.md` | Báo cáo cá nhân |

Dữ liệu và kết quả đặt tại **`data/` và `results/` ở gốc repo**, không phải `starter/data/` hay `starter/results/`. Các lệnh Python bên dưới chạy từ **`starter/`**; từ vị trí đó, đường dẫn tới dữ liệu là `../data/`.

## 2. Dữ liệu

- Nguồn: [Principles of Management — OpenStax](https://openstax.org/details/books/principles-management).
- Phạm vi: Chương 13 — Leadership và Chương 14 — Work Motivation for Performance.
- File trích: trang vật lý 375–454 của bản PDF đầy đủ đã đối chiếu, tương ứng trang in 361–440.
- Corpus sử dụng: trang 2–31 và 41–74 của PDF trích, tổng cộng **64 trang nội dung**, **13 section**, **75 bản ghi**, **218.405 ký tự** sau chuẩn hóa.
- `page` là số trang trong PDF trích, bắt đầu từ 1; `printed_page = page + 360`.
- Source ID: `openstax_management_ch13_ch14`.

Nếu PDF chưa có trong repo, tải bản đầy đủ từ trang sách, trích đúng phạm vi và đặt tên `data/raw/principles-management.pdf`. Đối chiếu nội dung và số trang với manifest; bản PDF được OpenStax cập nhật có thể khác bản dùng trong thí nghiệm. Corpus chuẩn hóa dùng để tái lập kết quả là `data/processed/sections.jsonl`.

Trang bản quyền của bản đầy đủ đã đối chiếu ghi **CC BY-NC-SA 4.0**. Thông báo giấy phép, nguồn xác minh và ghi chú riêng của OpenStax về sử dụng nội dung trong LLM được lưu tại `data/manifest.json`. Ghi công: *Principles of Management — OpenStax, Rice University. Access for free at openstax.org.*

## 3. Setup

### Yêu cầu

- Python **3.13.13** là phiên bản đã dùng trong bài.
- Docker Desktop đang chạy và có Docker Compose.
- Mạng để tải dependencies, Docker image và embedding model lần đầu.
- Không cần API key cho pipeline local.

### Tạo môi trường Python

Từ thư mục gốc repo:

```bash
cd starter
python3.13 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install -r requirements.txt
```

Nếu Python được cài bằng `uv` tại đường dẫn đã dùng trên máy macOS Apple Silicon, có thể thay lệnh tạo môi trường bằng:

```bash
"$HOME/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python" -m venv .venv
```

Nếu đã có `.venv` đúng phiên bản, chỉ cần `source .venv/bin/activate`. Không tạo chồng Python mới lên môi trường cũ khác phiên bản.

Nếu `requirements.txt` vẫn là bản starter cơ bản và chưa có thư viện embedding local:

```bash
python -m pip install sentence-transformers
```

Các phiên bản dependencies thực tế của lần đo cần được đối chiếu với thống kê đã lưu; cài phiên bản mới hơn có thể làm thay đổi kết quả hoặc thời gian chạy.

### Cấu hình và khởi động database

Vẫn ở `starter/`:

```bash
if [ ! -f .env ]; then
  cp .env.example .env
fi

docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Giữ `DATABASE_URL` trong `.env` khớp với Docker Compose. Cấu hình starter dùng cổng local `55433`; không commit `.env`.

Kết quả kiểm tra của môi trường đã dùng:

```text
Database: day6_lab | PostgreSQL: 16.16 | pgvector: 0.8.7
Setup OK.
```

`Setup OK` chỉ xác nhận database và extension hoạt động; đây chưa phải kết quả benchmark.

## 4. Chạy pipeline và benchmark

### Kiểm tra đầu vào

Từ `starter/`:

```bash
ls ../data/raw/principles-management.pdf
ls ../data/processed/sections.jsonl
ls ../data/manifest.json
ls ../benchmark/questions.json
ls ../benchmark/protocol.md
```

Sử dụng mã nguồn pipeline đã hoàn thiện của bài nộp. Bản starter gốc của đề bài còn TODO nên không thể tái lập kết quả chỉ bằng việc setup database.

### Chạy dev

```bash
python -m src.run --split dev
```

Pipeline thực hiện ingestion, tạo embedding, lưu chunk/vector và truy xuất trên 15 câu dev. Lần chạy đầu cần tải model; các lần sau có thể dùng cache local.

Chọn cấu hình dựa trên kết quả dev, ưu tiên Evidence Hit@3, sau đó Hit@1 và các tiêu chí trong `benchmark/protocol.md`. Cấu hình được chọn trong bài là **C**.

### Chạy test sau khi cố định cấu hình

```bash
python -m src.run --split test
```

Test gồm 5 câu q16–q20. Với bộ kết quả đã nộp, không cần chạy lại test để đọc report hoặc hoàn thiện nhãn audit. Nếu chạy lại để tái lập, ghi rõ lý do và giữ lịch sử lần chạy; không dùng kết quả test để điều chỉnh cấu hình rồi xem đó là đánh giá độc lập.

Lần test được báo cáo đã hoàn tất retrieval nhưng gặp `KeyError: 'rank'` khi xuất phiếu audit. Các phiếu được khôi phục từ trace đã lưu, không truy xuất lại. Nếu repo có script khôi phục tương ứng, lệnh đã dùng là:

```bash
python -m scripts.export_test_audits
```

Script này tạo các file audit có hậu tố `_recovered.csv`, nhãn ban đầu để trống. Không thay thế phiếu đã chấm bằng phiếu trống. Các bản audit cuối cùng được lưu với tên chuẩn trong `results/`.

### Dừng database và giữ dữ liệu

```bash
docker compose -p day6_student_starter stop
```

## 5. Ba cấu hình so sánh

| Cấu hình | Chunking | Overlap | Filter | Số chunk |
|---|---|---:|---|---:|
| A | Cửa sổ cố định 500 ký tự | 50 ký tự | Không | 518 |
| B | Theo đoạn, tối đa 1.000 ký tự | 0 | Không | 307 |
| C | Dùng chung chunk/vector với B | 0 | Chapter hoặc section được cung cấp trong query | 307 |

Cả ba dùng `BAAI/bge-small-en-v1.5`, vector 384 chiều và cosine search. Query dùng tiền tố `Represent this sentence for searching relevant passages: `. Filter không được suy từ đáp án hoặc metadata gold.

B và C chỉ khác việc áp dụng filter. A và B khác cả cách chia, kích thước và overlap nên không thể quy toàn bộ chênh lệch cho riêng phương pháp chia đoạn.

## 6. Kết quả và cách đánh giá

Benchmark gồm **20 câu: 15 dev và 5 test**, với 10 câu cho mỗi chương. Có 4 câu filter, trong đó 2 câu thuộc test.

| Cấu hình | Dev Hit@1 | Dev Evidence Hit@3 | Test Hit@1 | Test Evidence Hit@3 |
|---|---:|---:|---:|---:|
| A | 4/15 | 6/15 | 3/5 | 5/5 |
| B | 9/15 | 11/15 | 2/5 | 5/5 |
| C | 10/15 | 12/15 | 2/5 | 5/5 |

Báo cáo phân tích đủ năm khía cạnh:

1. **Retrieval accuracy:** Hit@1 và Evidence Hit@3, phân biệt evidence hit với chỉ đúng trang.
2. **Chunk coherence:** trung bình A = 1,00/2; B/C = 1,20/2, trên 10 vị trí mẫu mỗi cấu hình chunking.
3. **Metadata usefulness:** 45/45 kết quả top-3 test được kiểm tra có nguồn/trang/chương/section đúng; C đáp ứng phạm vi ở 2/2 câu filter test.
4. **Grounding quality:** 15/15 bộ top-3 test được chấm mức 2, đánh giá bằng chứng đủ hỗ trợ đáp án tham chiếu.
5. **Data strategy impact:** so sánh A/B về chia chunk và B/C về metadata filter, kèm số chunk, thời gian và hạn chế.

Đoàn Văn Tú duyệt và chốt nhãn sau rà soát có hỗ trợ AI. Đánh giá cuối cùng không dùng API judge. Mẫu coherence tập trung ở đầu Chương 13; test chỉ có 5 câu nên kết quả không đại diện mọi tài liệu hoặc truy vấn.

## 7. Các file kết quả

| File trong `results/` | Vai trò |
|---|---|
| `traces_dev.jsonl`, `traces_test.jsonl` | Top-3, text, metadata và thời gian truy xuất |
| `metrics_dev.csv`, `metrics_test.csv` | Chỉ số retrieval theo cấu hình |
| `strategy_stats_dev.json`, `ingestion_stats.json` | Thống kê chunk, token và ingestion |
| `coherence_audit.csv` | Nhãn mạch lạc và lý do cho 20 mẫu A/B |
| `metadata_audit.csv` | Đối chiếu 45 kết quả top-3 test |
| `grounding_audit.csv` | Nhãn grounding cho 15 cặp cấu hình–câu hỏi test |

Nhãn C về coherence dùng lại B vì chung chunk. Tên file khi tải lên có thể có hậu tố `(1)`, `(2)`; khi đặt vào repo cần đổi về tên chuẩn đã liệt kê. Các phiếu audit cần duyệt và lưu riêng, không coi việc chạy retrieval là đã hoàn tất chấm nhãn.

## 8. Lưu ý tái lập

- Chạy lệnh Python từ `starter/` và kích hoạt đúng `.venv`.
- Giữ nguyên corpus, benchmark và cấu hình khi đối chiếu kết quả đã báo cáo.
- Không đưa `expected_answer`, `evidence_quote` hoặc gold page vào đầu vào retrieval.
- Không commit `.env`, API key, `.venv/` hoặc cache model.
- Phí API embedding của pipeline là 0 USD; chưa tính điện và phần cứng.
- Chi tiết phương pháp, lỗi quan sát được và giới hạn nằm trong [báo cáo cá nhân](report/individual/2A202603595_DoanVanTu.md).
