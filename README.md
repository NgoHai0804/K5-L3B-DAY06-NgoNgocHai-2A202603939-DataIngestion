# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## Dữ liệu (corpus)

- **Chủ đề:** Natural Language Processing trong lĩnh vực pháp lý (legal NLP) — tasks, datasets, models, challenges, benchmarks.
- **Vị trí corpus:** `data/raw/` · **Manifest:** [`data/manifest.json`](data/manifest.json).
- **Quy ước vị trí:** corpus và manifest đặt dưới `data/` ở repo root; `run.py`, manifest và README dùng cùng quy ước này.
- **Nguồn — giấy phép CC BY 4.0** (được phép dùng/tái phân phối, ghi công):

  | source_id | Tài liệu | Năm | Trang nội dung |
  |---|---|---:|---:|
  | `nlp-legal-survey-2410.21306` | NLP for the Legal Domain: A Survey (arXiv:2410.21306v3) | 2024 | 29 |
  | `legal-nlp-india-survey-2107.06056` | Indian Legal NLP Benchmarks: A Survey (arXiv:2107.06056v1) | 2021 | 16 |
  | **Tổng** | | | **45 (≥ 30)** |

- **Quy tắc đếm trang:** trang có ≥200 ký tự sau chuẩn hóa; loại bìa/mục lục/trống/references. Trang references bị loại khỏi đếm; trang hình/bảng ít text ghi ở `empty_or_ocr_broken_pages` (Bước 3 sẽ ghi thêm log).
- **Phạm vi metadata filter:** cấp tài liệu `document_id`, `source`, `year`, `document_type`; cấp trang `section` (suy ra từ heading khi ingest). Hai tài liệu + nhiều section cho ≥2 phạm vi phân biệt.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

### Ba cấu hình A/B/C

| Cấu hình | Chunking | Chunk size | Overlap | Metadata | Filter | Embedding | Store / metric |
|---|---|---:|---:|---|---|---|---|
| **A** | Fixed-size | 500 ký tự | 50 | `document_id, source, page, section, year` | Không lọc | `qwen/qwen3-embedding-8b` (4096) | pgvector / cosine |
| **B** | Theo đoạn/heading | max 800 ký tự | — | giống A | Không lọc | cùng model | pgvector / cosine |
| **C** | Theo đoạn (giống B) | max 800 ký tự | — | giống B | Lọc khi câu hỏi có filter | cùng model | pgvector / cosine |

- **A–B** chỉ khác **cách chunk** (fixed-size ↔ theo đoạn) → cô lập ảnh hưởng của chunking.
- **B–C** chỉ khác **metadata filter** (không lọc ↔ có lọc) → cô lập ảnh hưởng của filter.
- Giữ nguyên corpus, embedding model, metric, bộ câu hỏi và `top_k = 3` cho cả ba.
- C chỉ lọc cho câu có `filter`; câu không có filter chạy như B và ghi `filter_applied: null` trong trace.
- Giá trị filter (`document_id`, `section`) lấy từ [`data/manifest.json`](data/manifest.json) và đã kiểm chứng theo trang nguồn; whitelist filter nằm trong `starter/src/store.py`.
- Hiện thực: `_strategies()` trong `starter/src/run.py`. Đã nạp đủ ba index vào pgvector (A = 386, B = 230, C = 230 chunk).

### Kết quả dev / test (Bước 5)

Lệnh chạy: `.\.venv\Scripts\python.exe -m src.run` trong `starter/`. Trace đầy đủ ở [`results/traces.json`](results/traces.json), thống kê ở [`results/stats.json`](results/stats.json), log ingest ở [`results/ingest_log.json`](results/ingest_log.json).

| Cấu hình | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Ingest | Chi phí |
|---|---|---:|---:|---:|---:|---:|
| A | dev | 13/19 | 15/19 | 386 | 52.1s | ≈0 |
| A | test | 6/8 | 8/8 | 386 | — | ≈0 |
| B | dev | 13/19 | 15/19 | 230 | 29.4s | ≈0 |
| B | test | 5/8 | 5/8 | 230 | — | ≈0 |
| C | dev | 14/19 | 15/19 | 230 | 22.4s | ≈0 |
| C | test | 5/8 | 5/8 | 230 | — | ≈0 |

- **Bộ câu hỏi:** 27 câu (19 dev / 8 test); test = q05, q09, q16, q23, q24, q25, q26, q27. Chỉ số dạng n/N lấy từ `results/stats.json`.
- **Idempotent:** chạy lại pipeline lần hai → pgvector vẫn A = 386, B = 230, C = 230 (không nhân đôi); do id ổn định dạng `strategy:chunk_id`.
- **Phân bố độ dài chunk** (đo lại từ pgvector): A trung bình 474 (57–500); B/C trung bình 722 (19–800).
- **Chi phí:** ≈ 0 — embedding ~130k token qua OpenRouter `qwen/qwen3-embedding-8b` (không đáng kể), vector store chạy local.

### Chấm thủ công 5 khía cạnh (Bước 6)

Người chấm: **NgoNgocHai (tác giả)** — nhãn **thủ công, độc lập** với chỉ số tự động; nguy cơ thiên lệch do tự chấm và mẫu nhỏ. Nhãn chi tiết ở [`results/audit_coherence.json`](results/audit_coherence.json), [`results/audit_metadata.json`](results/audit_metadata.json), [`results/audit_grounding.json`](results/audit_grounding.json).

| Khía cạnh | A | B | C |
|---|---|---|---|
| Retrieval — Hit@1 (dev / test) | 13/19 · 6/8 | 13/19 · 5/8 | 14/19 · 5/8 |
| Retrieval — Evidence Hit@3 (dev / test) | 15/19 · 8/8 | 15/19 · 5/8 | 15/19 · 5/8 |
| Coherence (trung bình /2, 10 vị trí) | 1.1 | 1.1 | 1.1 |
| Metadata đủ & đúng (n/N) | 15/15 | 15/15 | 15/15 |
| Filter compliance | N/A | N/A | 2/2 |
| Grounding (trung bình /2, 5 câu test × top-3) | 0.80 | 0.80 | 0.80 |

- **Coherence:** A và B đều ~1.1/2 — hầu hết chunk cắt giữa từ vì text PDF (pypdf) gần như không có ranh giới đoạn `\n\n`, nên `by_paragraph` thoái hoá thành cửa sổ 800 ký tự.
- **Metadata:** 45/45 bản ghi (5 câu × top-3 × 3 cấu hình) có `source`/`page`/`section` đủ và đúng theo manifest; C tuân thủ filter 2/2.
- **Grounding:** cả ba ~0.80/2 — mỗi câu thường có 1 chunk đủ bằng chứng trong top-3; các chunk còn lại là nhiễu (thường kéo chunk từ tài liệu Ấn Độ sang).

### Tác động chiến lược dữ liệu (A–B và B–C)

- **A–B (chỉ đổi chunking):** B giảm chunk 386→230 (−40%) và thời gian ingest, nhưng coherence **không** cải thiện (1.1 = 1.1) và retrieval test **giảm** (A 8/8 vs B 5/8 Evidence Hit@3). Chunk 500 ký tự khớp trọn `evidence_quote` thường xuyên hơn chunk 800 → chunking theo đoạn không giúp trên corpus này.
- **B–C (chỉ đổi filter):** filter chỉ tác động 4 câu có filter. Dev: C +1 Hit@1 (13→14). Test: không đổi (5/8). Filter compliance 2/2, không gây hại → filter hữu ích nhưng hiệu ứng nằm trong nhiễu do quá ít câu filter.
- **Tiêu chí chọn (chốt trước khi xem test):** ưu tiên Evidence Hit@3 → grounding → tài nguyên. Theo đó **A** thắng Hit@3 test (8/8) nhưng tốn ~1.7× chunk/thời gian; nếu ưu tiên rẻ thì **B/C** (ngang dev, ít tài nguyên hơn).
- **Ví dụ lỗi:** (1) q23 — B/C lấy đúng chunk chứa đáp án "48th/15th percentile" ở top-1 nhưng proxy tự động báo **miss** vì gold quote là câu "90th percentile" khác (bằng chứng bị tách giữa các chunk); (2) q25 (A) — top-1 trả về bảng relations thay vì câu "This activity is manual…", đáp án rơi xuống top-2.
- **Giới hạn:** test chỉ 8 câu (4 câu filter); proxy hit khớp chuỗi nên bỏ sót bằng chứng tương đương; embedding API có thể lệch giữa các lần chạy (B/C chênh ±1).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
