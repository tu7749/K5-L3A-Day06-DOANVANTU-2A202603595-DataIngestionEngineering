# Benchmark protocol — Day06 Data Ingestion Engineering

## 1. Mục tiêu và trạng thái

Đánh giá ảnh hưởng của chunking và metadata filter tới truy xuất bằng chứng trong corpus OpenStax, Chương 13–14. Bộ benchmark gồm 20 câu tiếng Anh: 15 dev và 5 test.

Protocol này được soạn trước khi chạy retrieval trong cuộc hội thoại này. Chưa có kết quả Hit@1/Hit@3 được dùng để chỉnh câu hỏi. Nếu người thực hiện đã chạy hoặc xem kết quả test ở nơi khác, phải ghi rõ; không báo đó là holdout độc lập.

Gold được AI hỗ trợ biên soạn bằng cách đối chiếu trực tiếp với sections.jsonl. Kiểm tra tự động đã xác nhận 20/20 trích dẫn tồn tại nguyên văn tại đúng nguồn/trang. Tác giả bài làm cần rà soát ý nghĩa và xác nhận nhãn trước lần chạy chính thức; đây chưa phải đánh giá độc lập bởi người thứ hai.

## 2. Corpus và truy vết

- File PDF trong repo: data/raw/principles-management.pdf.
- Nguồn text đã dùng để tạo gold: sections.jsonl do học viên cung cấp.
- document_id: openstax_management_ch13_ch14.
- Phạm vi đã chọn: trang PDF 2–31 và 41–74.
- gold_page: số trang trong PDF trích 80 trang, bắt đầu từ 1.
- Số trang in tương ứng: gold_page + 360.
- SHA-256 của sections.jsonl đã đối chiếu: 650ad4f08c2ad0c7ba438059824c0866612a0a21a6ece8001be7f207934009dd.

Khóa corpus trước benchmark. Nếu text thay đổi, kiểm tra lại toàn bộ evidence và ghi phiên bản mới. Giấy phép và nguồn PDF được quản lý tại data/manifest.json.

## 3. Định dạng và phân chia

File chuẩn: benchmark/questions.json, một JSON array gồm 20 object. Không đổi đuôi thành .jsonl nếu chưa chuyển sang một object mỗi dòng.

Mỗi object có đúng 11 trường:

| Trường | Kiểu / ý nghĩa |
|---|---|
| id | Chuỗi q01–q20 |
| split | dev hoặc test |
| type | direct, paraphrase, condition hoặc filter |
| question | Câu hỏi đầu vào |
| expected_answer | Đáp án tham chiếu, chỉ dùng khi đánh giá |
| gold_source_id | ID tài liệu chứa bằng chứng |
| gold_page | Số nguyên, trang PDF trích |
| evidence_quote | Trích nguyên văn từ text chuẩn hóa |
| alt_gold | Danh sách bằng chứng thay thế đã xác minh |
| filter | null hoặc object metadata |
| leak_risk | low hoặc medium; nhận định khi thiết kế, không phải điểm đo |

| Tập | ID | Số câu | Chương 13 | Chương 14 | Có filter |
|---|---|---:|---:|---:|---:|
| Dev | q01–q15 | 15 | 8 | 7 | 2 |
| Test | q16–q20 | 5 | 2 | 3 | 2 |
| Tổng | q01–q20 | 20 | 10 | 10 | 4 |

Phân bố loại câu: 7 direct, 4 paraphrase, 5 condition, 4 filter. Đây là nhãn chính; câu filter vẫn có thể yêu cầu phân biệt hoặc giải thích.

Tất cả 13 section từ 13.1–13.9 và 14.1–14.4 có ít nhất một câu trên toàn bộ benchmark. Đây là split theo câu hỏi trong cùng corpus, không phải đánh giá chuyển miền hoặc tài liệu chưa thấy. Một số section xuất hiện ở cả dev và test; cần ghi hạn chế này.

## 4. Filter và kiểm soát rò rỉ

| ID | Filter đầu vào | Cơ sở |
|---|---|---|
| q07 | {"section_id": "13.7"} | Câu hỏi nêu rõ Section 13.7 |
| q15 | {"section_id": "14.2"} | Câu hỏi nêu rõ Section 14.2 |
| q16 | {"chapter": 13} | Câu hỏi nêu rõ Chapter 13 |
| q19 | {"section_id": "14.4"} | Câu hỏi nêu rõ Section 14.4 |

Filter là phạm vi người dùng cung cấp trước retrieval. Không suy ra filter từ gold_source_id, gold_page, evidence_quote hoặc đáp án.

- A/B dùng nguyên question nhưng không áp dụng metadata filter.
- C dùng cùng question và áp dụng filter nếu khác null.
- Khi filter=null, C truy xuất như B.
- Chỉ gửi question vào embed_query; không gửi toàn bộ object gold.
- Các trường gold, expected_answer, alt_gold, leak_risk chỉ thuộc lớp đánh giá.
- Không đưa tên file chứa gold hoặc vị trí ký tự của evidence vào query.

leak_risk=medium cho bốn câu filter vì chúng cung cấp phạm vi tường minh, giúp giảm không gian tìm kiếm; đây là can thiệp có chủ đích, không phải đưa đáp án vào query. q06 và q17 cũng được đánh dấu medium vì cùng liên quan đến supportive leadership dù hỏi điều kiện khác nhau. Các câu còn lại là low về nguy cơ lộ đáp án/phạm vi ngoài chủ đích. Nhãn này không bảo đảm không có trùng từ vựng hoặc thiên lệch.

Báo riêng các câu filter khi phân tích, không suy rộng lợi ích của C ra mọi câu hỏi.

## 5. Gold và evidence

Mỗi evidence_quote là đoạn liên tục được sao chép chính xác từ một record trong sections.jsonl. Một số quote gồm nhiều câu để giữ đủ điều kiện; không ép thành một câu nếu sẽ mất ý.

alt_gold hiện là [] cho cả 20 câu. Điều đó nghĩa là chưa đăng ký bằng chứng thay thế, không có nghĩa nguồn chính là đáp án hợp lệ duy nhất. Kiểm tra tự động đã tìm các lần xuất hiện nguyên văn khác; chưa chứng minh đã tìm hết các cách diễn đạt tương đương.

Một phần tử alt_gold, khi được xác minh, có dạng:

```json
{
  "gold_source_id": "openstax_management_ch13_ch14",
  "gold_page": 1,
  "evidence_quote": "Đoạn bằng chứng thay thế nguyên văn."
}
```

Số trang 1 ở ví dụ trên chỉ minh họa schema, không phải gold thật.

Nếu phát hiện bằng chứng tương đương trong khi chấm:
1. Đối chiếu nguồn và xác nhận hỗ trợ đầy đủ đáp án.
2. Lưu lý do, nguồn/trang và người xác nhận.
3. Áp dụng quyết định nhất quán cho A/B/C, lưu kết quả trước/sau nếu sửa nhãn.
4. Không chỉnh query hoặc cấu hình theo test để cải thiện điểm.

## 6. Thiết lập A/B/C

| Cấu hình | Chunking | Filter |
|---|---|---|
| A | Fixed-size | Không |
| B | Theo đoạn/section, có giới hạn độ dài | Không |
| C | Cùng chunk và embedding với B | Theo filter được cung cấp |

Ghi giá trị thực tế của chunk size, overlap, model/provider/revision, số chiều, cách xử lý query/document, vector store/version, metric cosine và chế độ tìm kiếm vào artifacts/experiment_log.csv hoặc file cấu hình trước khi chạy.

Giữ cùng corpus, model, store và metric giữa A/B/C. B–C chỉ thay filter. Không giả định các tham số gợi ý trước đó là tham số thực tế đã chạy.

Mỗi truy vấn lấy top_k=3. Nếu filter chỉ còn dưới ba kết quả, lưu số thực tế; không tự bổ sung kết quả ngoài filter. Quy định xử lý đồng điểm ổn định, ví dụ ưu tiên chunk_id tăng dần.

## 7. Chỉ số retrieval

Một chunk là hit khi:
- Nguồn và trang khớp gold chính hoặc alt_gold hợp lệ; và
- Chunk chứa đủ bằng chứng hỗ trợ đáp án, qua đối chiếu quote hoặc xác nhận tương đương.

Không tính hit chỉ vì đúng trang. Có thể chuẩn hóa Unicode và khoảng trắng đồng nhất cho quote/chunk khi so khớp; không bỏ từ hoặc điều kiện làm thay đổi nghĩa.

- Hit@1 = số câu có top-1 là hit / tổng số câu.
- Evidence Hit@3 = số câu có ít nhất một hit trong top-3 / tổng số câu.

Báo n/N và phần trăm riêng dev/test cho từng cấu hình. Với evidence bị chia qua nhiều chunk mà không chunk nào đủ, chỉ số chính là miss. Có thể phân tích hợp nhiều chunk riêng, không thay định nghĩa chính.

Lỗi provider/database phải được ghi và chạy lại trước khi báo một lượt benchmark hoàn chỉnh; không âm thầm bỏ câu lỗi khỏi mẫu số. Query chạy thành công nhưng không có kết quả được tính miss.

Trace cần có ID câu, split, strategy, question, filter được áp dụng, rank, chunk_id, text, score, metadata, nhãn hit, lý do override và thời gian. Ghi rõ score là similarity hay distance.

## 8. Chọn cấu hình và chạy test

Chỉ dùng 15 câu dev để chọn cấu hình:
1. Ưu tiên Evidence Hit@3 cao hơn.
2. Nếu bằng nhau, ưu tiên Hit@1 cao hơn.
3. Nếu vẫn bằng nhau, ưu tiên thời gian truy xuất trung vị thấp hơn trong cùng điều kiện đo.
4. Nếu không có khác biệt thực tế, chọn cấu hình đơn giản hơn và ghi lý do.

Cố định câu hỏi, tham số và phiên bản trước khi chạy test. Sau đó chạy cùng 5 câu test trên A/B/C để báo cáo so sánh; không chọn lại cấu hình bằng điểm test. Chỉ xem q01–q15 khi tinh chỉnh. Nếu đã dùng test để chỉnh, ghi rõ và tạo test mới nếu cần đánh giá độc lập.

## 9. Audit thủ công

### Chunk coherence

Chọn trước cùng 10 vị trí nguồn, ví dụ ký tự nội dung đầu tiên của record section đầu tiên trên 10 trang hợp lệ đầu theo thứ tự tăng dần. Lưu page, section, offset và đoạn mốc trước khi đọc điểm retrieval.

Với mỗi chiến lược, chấm các chunk chứa vị trí đã chọn:
- 0: cắt giữa ý hoặc thiếu chủ thể, khó hiểu.
- 1: hiểu một phần nhưng thiếu ngữ cảnh.
- 2: tự hiểu được và giữ trọn ý.

Nếu overlap tạo nhiều chunk chứa một vị trí, ghi tất cả và lấy trung bình cho vị trí đó rồi trung bình 10 vị trí, tránh vị trí nhiều chunk có trọng số lớn hơn. B/C dùng cùng chunk nên có thể dùng cùng nhãn nội dung, nhưng phải chỉ rõ việc tái sử dụng.

### Metadata

Kiểm tra top-3 của 5 câu test cho mỗi cấu hình: source, page, chapter, section_id so với nguồn.
Báo số bản ghi có metadata đủ và đúng / tổng số bản ghi đã kiểm tra, kèm từng lỗi.

Trên hai câu test có filter, báo số câu có kết quả không rỗng và mọi kết quả trả về đều tuân thủ filter / 2. Báo riêng trường hợp dưới ba kết quả hoặc không có kết quả; không coi tập rỗng là thành công. A/B vẫn được kiểm tra mức phù hợp phạm vi dù không áp dụng filter.

### Grounding

Chấm top-3 của cùng 5 câu test cho từng cấu hình:
- 0: không có bằng chứng.
- 1: có bằng chứng nhưng thiếu điều kiện/ngữ cảnh.
- 2: đủ để trả lời và truy nguồn.

Báo số câu ở từng mức và trung bình /2 kèm lý do. Đây là độ đủ của bằng chứng, không phải độ chính xác câu trả lời LLM. Không thay audit bằng exact-match hoặc Hit@3.

### Tác động chiến lược

So sánh A–B và B–C về retrieval, coherence, metadata, grounding, số chunk, thời gian và chi phí. Nêu ít nhất hai ví dụ lỗi có ID câu và nguồn. Trình bày cả trường hợp filter không giúp hoặc làm xấu kết quả.

## 10. Giới hạn và đầu ra

- Corpus hẹp, cùng một sách; test 5 câu có độ bất định cao.
- 20 câu không đại diện mọi bảng biểu, case và tác vụ đa trang.
- Gold được thiết kế từ section text, chưa xem kết quả retrieval để chọn các câu dễ trúng.
- Evidence một trang phù hợp chỉ số hit chính nhưng chưa đo khả năng tổng hợp nhiều trang.
- Corpus, từ vựng và một số section được chia sẻ giữa dev/test.
- Tác giả tự audit có thể thiên lệch; ghi người chấm và cách kiểm chứng.
- Nhãn và đáp án do AI hỗ trợ cần được tác giả xác nhận, không ghi là đã được người độc lập chấm.

Lưu questions.json, protocol.md, cấu hình, trace dev/test, bảng metrics, audit thủ công, log lỗi và chi phí. Các đường dẫn đầu ra phải được ghi trong README; không tạo hoặc điền số liệu khi chưa chạy.

