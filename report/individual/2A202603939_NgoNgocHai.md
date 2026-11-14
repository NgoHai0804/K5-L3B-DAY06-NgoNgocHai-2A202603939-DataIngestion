# Báo cáo cá nhân — Day 6

- Học viên: NgoNgocHai · MSSV 2A202603939 · Lớp L3B
- Repo: https://github.com/NgoHai0804/K5-L3B-DAY06-NgoNgocHai-2A202603939-DataIngestion

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** Legal NLP — 2 survey arXiv: `nlp-legal-survey-2410.21306` (29 trang) và `legal-nlp-india-survey-2107.06056` (16 trang), tổng **45 trang nội dung** (≥30), giấy phép **CC BY 4.0**. Quy tắc đếm: trang có ≥200 ký tự sau chuẩn hóa; loại bìa/mục lục/references; trang ít text (<200 ký tự) ghi ở `empty_or_ocr_broken_pages` (india trang 4). Manifest: `data/manifest.json`.
- **Chuẩn hóa, lỗi và giới hạn:** `normalize_text` chuẩn hóa NFC + gộp khoảng trắng, giữ xuống dòng. Hạn chế lớn: pypdf gần như không tạo ranh giới đoạn `\n\n` nên `by_paragraph` thoái hoá thành cửa sổ 800 ký tự, làm giảm hiệu quả của chunking theo đoạn.
- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:** OpenRouter `qwen/qwen3-embedding-8b` (OpenAI-compatible, **4096 chiều**); PostgreSQL 16 + pgvector **0.8.7**, metric **cosine** (`<=>`). Lệnh chạy (từ `starter/`): `.\.venv\Scripts\python.exe -m src.run`. Chi phí ≈ **$0** (<$0.01 cho ~130k token embedding).
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:** bắt buộc `document_id`, `source`, `page`; bổ sung `section` (cấp trang, suy từ heading trong manifest), `year`/`document_type` (cấp tài liệu). Giá trị lấy từ manifest, không bịa. `section` chọn vì cho phép lọc theo phạm vi chủ đề (dùng ở cấu hình C).

## Cấu hình và benchmark

- **A / B / C:** A = fixed-size 500 ký tự / overlap 50, **không lọc**; B = theo đoạn (max 800), **không lọc**; C = giống B nhưng **lọc** `document_id` + `section` khi câu có filter. A–B chỉ khác **chunking**; B–C chỉ khác **filter**; giữ nguyên corpus, model, metric, bộ câu hỏi và `top_k=3`.
- **Bộ câu hỏi:** 27 câu, tách **19 dev / 8 test** trước khi chạy; 4 câu có metadata filter (q21, q22 ∈ dev; q24, q25 ∈ test). Kiểm chứng evidence: mỗi `evidence_quote` tồn tại ở trang gold sau chuẩn hóa.
- **Tiêu chí chọn chiến lược (chốt trước khi xem test):** ưu tiên Evidence Hit@3 → grounding → tài nguyên.

## Kết quả

Bảng 1 — Retrieval & tài nguyên:

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian (ingest) | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 13/19 | 15/19 | 386 | 25.9s | ≈0 |
| A | test | 6/8 | 8/8 | 386 | — | ≈0 |
| B | dev | 13/19 | 15/19 | 230 | 27.8s | ≈0 |
| B | test | 6/8 | 6/8 | 230 | — | ≈0 |
| C | dev | 13/19 | 15/19 | 230 | 41.1s | ≈0 |
| C | test | 6/8 | 6/8 | 230 | — | ≈0 |

Bảng 2 — Audit thủ công (người chấm: tác giả; có nguy cơ thiên lệch):

| Strategy | Coherence /2 | Metadata đủ & đúng (n/N) | Filter tuân thủ | Grounding 0/1/2 (số câu) và TB /2 |
|---|---|---|---|---|
| A | 1.1 | 15/15 | N/A | 8 / 2 / 5 — TB 0.80 |
| B | 1.1 | 15/15 | N/A | 8 / 2 / 5 — TB 0.80 |
| C | 1.1 | 15/15 | 2/2 | 8 / 2 / 5 — TB 0.80 |

**Mẫu & trace:** `results/traces.json`; coherence = 10 vị trí cố định (điểm giữa 10 trang, 5 trang đầu mỗi tài liệu) → `results/audit_coherence.json`; metadata & grounding = 5 câu test × top-3 → `results/audit_metadata.json`, `results/audit_grounding.json`.

## Dùng AI & kiểm chứng

- **Công cụ AI:** Kilo Code (VS Code) — hỗ trợ viết pipeline `starter/src/*`, sinh bộ câu hỏi, script chấm audit và soạn tài liệu. Tôi đọc lại và hiểu toàn bộ code/kết quả trước khi nộp.
- **Cách kiểm chứng:** (1) chạy thật pipeline trên OpenRouter + pgvector rồi đối chiếu `results/`; (2) xác minh từng `evidence_quote` tồn tại ở trang gold sau chuẩn hóa; (3) đối chiếu `source`/`page`/`section` của top-3 với `data/manifest.json`; (4) tự đọc chunk và gán nhãn coherence/grounding; (5) kiểm tra idempotent bằng cách chạy lại và đếm `chunks` trong DB.
- **Trung thực:** mọi con số lấy từ `results/stats.json`; không tạo số liệu hay nhãn giả.

## Phân tích và kết luận

- **A–B (chỉ đổi chunking):** B giảm 40% chunk (386→230) và thời gian ingest, nhưng coherence **không** tăng (1.1 = 1.1) và retrieval test **giảm** (A 8/8 vs B 6/8 Evidence Hit@3; dev ngang nhau 13/19 · 15/19). Nguyên nhân: text pypdf thiếu ranh giới đoạn nên `by_paragraph` ≈ cửa sổ 800; chunk 500 khớp trọn `evidence_quote` thường xuyên hơn.
- **B–C (chỉ đổi filter):** filter chỉ tác động 4 câu có filter; dev và test đều **không đổi** (13/19, 6/8). Filter compliance 2/2, không gây hại → hữu ích về kiểm soát phạm vi nhưng nằm trong nhiễu do quá ít câu filter.
- **Sửa benchmark (khai báo):** `evidence_quote` của **q23** ban đầu trỏ sai sang câu "90th percentile" (không khớp đáp án "48th/15th percentile"); đã sửa thành câu đúng trên trang 8 và **chạy lại** pipeline — mọi số liệu phản ánh lần chạy sau khi sửa (B/C test Hit@3 5/8 → 6/8).
- **2 ví dụ sai:**
  1. **q24** (test, gold `legal-nlp-india-survey-2107.06056` trang 15): với B/C, top-1 **chứa đáp án** "Section 378 under Indian Penal Code" nhưng proxy báo miss vì `evidence_quote` ("Predicting the relevant act of the law based on") bị cắt ở ranh giới chunk ("ing the relevant act of the law based on") → bằng chứng bị tách giữa các chunk.
  2. **q25** (test, gold `legal-nlp-india-survey-2107.06056` trang 13): với **A**, top-1 trả về bảng relations thay vì câu "This activity is manual and a lot of…"; đáp án rơi xuống top-2 → xếp hạng nhiễu khi chunk 500 cắt rời đoạn.
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:** theo tiêu chí đã chốt, **A** cho Evidence Hit@3 test tốt nhất (8/8) nhưng tốn ~1.7× chunk/thời gian; nếu ưu tiên tài nguyên thì **B/C** ngang dev với ít chunk hơn. Chỉ kết luận trong phạm vi corpus này (2 survey tiếng Anh, trang dày chữ).
- **Hạn chế:** test nhỏ (8 câu, chỉ 4 câu filter); proxy hit khớp chuỗi chính xác nên bỏ sót bằng chứng tương đương; `section` cấp trang nên trang nhiều tiểu mục bị gán một nhãn; embedding API không hoàn toàn xác định (B/C chênh ±1 giữa các lần chạy); nhãn thủ công do chính tác giả chấm nên có thiên lệch; thời gian đo chỉ gồm bước embed+upsert, chưa tính tải model.
- **Nếu làm lại/mở rộng:** (1) dùng bộ đọc giữ ranh giới đoạn tốt hơn (PyMuPDF hoặc chunk theo heading arXiv); (2) thêm câu có filter và cân bằng dev/test; (3) thử hybrid (BM25 + dense) và một model embedding khác (ví dụ `text-embedding-3-large`) như thí nghiệm phụ; (4) tự động hoá hit theo "bằng chứng tương đương" (so khớp ngữ nghĩa) thay vì khớp chuỗi.
