# Bộ dữ liệu đánh giá (eval) — tham chiếu nhanh

Bốn file JSON, mỗi file là một mảng item in dọc (indent 2) cho dễ đọc và dễ soi diff.
**Toàn bộ nhãn do người soạn tay và đã verify trên `dataset/chunks_llm.json`** — không có
item nào sinh tự động bằng LLM.

Riêng `runs/*.jsonl` (output mỗi lần chạy) vẫn là JSONL: máy sinh, ghi theo dòng, không ai
đọc tay. Cả ba script đều nhận **cả hai** định dạng nên đổi qua lại không phá gì.

Thiết kế, giao thức đo và công thức metric: xem [`docs/plan/evaluation-plan.md`](../../docs/plan/evaluation-plan.md).

| File | Item | Đo node nào |
|---|---:|---|
| `guardrails.json` | 36 | `guard_input` |
| `plan_routing.json` | 40 | `plan` (rewrite, route, mode, phân rã bước) |
| `retrieval_qa.json` | 100 | `retrieve` + `synthesize` |
| `negative.json` | 24 | toàn luồng — hành vi khi KHÔNG có đáp án |

`retrieval_qa.json` chia theo **số chunk cần để trả lời** — đây mới là trục đọc Recall
đúng cách, không phải `type`:

| Nhóm | Item | Nhận biết |
|---|---:|---|
| single_chunk | 57 | `len(gold_chunk_ids) == 1` |
| multi_chunk | 27 | `len(gold_chunk_ids) >= 2`, một lượt retrieval |
| multi_hop | 16 | `type == "multihop"`, cần hai lượt |

Kiểm toàn vẹn trước mỗi lần đo (bắt chunk_id chết, key_fact lệch, nhãn multi-hop sai):

```powershell
python apps/agent-service/scripts/validate_eval_dataset.py
```

Dò thêm ứng viên multi-hop mới (đề xuất tự động, người vẫn phải kiểm và viết câu hỏi):

```powershell
python apps/agent-service/scripts/find_multihop_candidates.py --top 40
# dò riêng một vùng corpus (533 = mốc bắt đầu mục kháng chiến chống Mỹ)
python apps/agent-service/scripts/find_multihop_candidates.py --focus-min-index 533 --out dataset/eval/_multihop_candidates_late.json
```

Kết quả ghi ra `_multihop_candidates.json` — **là sản phẩm trung gian để soi lại**, không
phải bộ eval. Đừng nạp file này vào bất kỳ phép đo nào.

## Chạy đánh giá

Hai bước, xem chi tiết ở §6 của plan:

```powershell
# 1. chạy hệ, lưu output thô (mỗi cấu hình ablation một file)
$env:PYTHONPATH="."
python scripts/collect_eval_runs.py --mode hybrid --out ../../dataset/eval/runs/hybrid.jsonl

# 2. chấm bằng RAGAS (+ Recall@k/MRR theo chunk_id)
python scripts/run_ragas_eval.py --runs ../../dataset/eval/runs/hybrid.jsonl --adapt-vi
```

`dataset/eval/runs/` là output của mỗi lần chạy — **không phải nhãn**, đừng sửa tay.

---

## `retrieval_qa.json`

| Field | Ý nghĩa |
|---|---|
| `id` | `qa-NNN` |
| `question` | Câu hỏi như người dùng gõ |
| `type` | `factoid` \| `synthesis` \| `comparison` \| `multihop` \| `relation` \| `temporal_spatial` |
| `difficulty` | `easy` \| `medium` \| `hard` |
| `topic` | Mục trong corpus, để nhóm kết quả |
| `gold_chunk_ids` | Chunk **đủ để trả lời**. Dùng cho Recall/nDCG |
| `supporting_chunk_ids` | Chunk bổ trợ — tính là relevant ở mức thấp hơn, KHÔNG phạt nếu thiếu |
| `key_facts` | Mệnh đề **trích nguyên văn** từ chunk gold. Chấm fact coverage bằng so khớp chuỗi |
| `gold_answer` | Câu trả lời mẫu, dùng cho LLM-judge và cho người đọc đối chiếu |
| `expected_confidence` | `cao` \| `vừa` \| `thấp` \| `không đủ dữ liệu` |
| `expected_mode` | `hybrid` nếu câu hỏi có tên riêng, `traditional` nếu không (luật của prompt `plan`) |
| `expected_step_count` | 1, hoặc 2 khi có mắt xích ẩn |
| `notes` | Vì sao item này tồn tại — đọc trước khi sửa nhãn |

Riêng `type: multihop` có thêm: `bridge_entity`, `hop1_chunk_ids`, `hop2_chunk_ids`,
`single_chunk_contains_both` (luôn `false`, đã verify bằng script).

## `plan_routing.json`

`history` (list `{role, content}`), `expected_route`, `expected_mode`,
`expected_step_count`, `gold_standalone_query`, `gold_entities`.

- `expected_step_count: 0` khi `route != needs_retrieval` (steps phải rỗng).
- `gold_standalone_query: ""` với ca `ambiguous` — không có câu viết lại đúng nào.
- `gold_entities` chỉ chứa tên riêng có **nguyên văn** trong `gold_standalone_query`.

## `guardrails.json`

`expected_action` (`allow`/`block`), `expected_categories` (theo `GuardrailCategory`),
`trap` (loại bẫy — dùng để nhóm khi phân tích lỗi), `history` khi ca phụ thuộc ngữ cảnh.

Lưu ý luật: câu **ngoài phạm vi** (toán, thời tiết) vẫn là `allow` — chặn ở tầng này là
lỗi, việc định tuyến thuộc về node `plan`.

## `negative.json`

`kind`: `out_of_corpus` \| `unanswerable_detail` \| `false_premise` \| `lexical_trap` \|
`ambiguous` \| `out_of_scope`.
`expected_behavior`: `refuse_honest` \| `correct_premise` \| `clarify` \| `polite_redirect`.
`must_not_contain`: chuỗi mà câu trả lời **không được** chứa — chấm hallucination tự động.
`evidence`: bằng chứng corpus thiếu/ngược lại, kèm chunk_id. **Đọc field này trước khi
cãi nhãn.**
