"""Dựng alias_map.json (tầng 2b): gom entity trùng mà normalize không bắt được.

Luồng:
  1. Đọc cache `dataset/graph_extractions.json`, gom entity theo norm_name (tầng 1+2a),
     lấy tên hiển thị + type + vài description + số lần nhắc.
  2. Sinh CẶP ỨNG VIÊN bằng chuỗi, CHẶN theo type (không so khác loại):
       - cùng dạng-rút-gọn (bỏ dấu + gạch nối + space), hoặc
       - fuzzy ratio cao (SequenceMatcher) trên dạng-rút-gọn.
     (Dạng-rút-gọn CHỈ để tìm ứng viên — không dùng làm khóa, không bỏ dấu ở dữ liệu thật.)
  3. LLM TRỌNG TÀI từng cặp, KÈM description (cái phân biệt "Phú Yên tỉnh" vs "Phù Yên
     huyện"). Verdict cache lại theo cặp + ALIAS_JUDGE_VERSION -> chạy lại không trả phí 2 lần.
  4. Cặp same+confidence=cao -> union-find thành cụm -> chọn canonical (nhắc nhiều nhất,
     hòa thì tên dài hơn). same+vừa -> ghi alias_review.md cho người duyệt.
  5. Gộp seed thủ công `dataset/alias_seed.json` (cụm [[canonical, alias...], ...]) cho
     alias ngữ nghĩa LLM/chuỗi khó tự tin ("Hồ Chí Minh"/"Nguyễn Ái Quốc"/"Bác Hồ").
  6. Ghi `dataset/alias_map.json` (resolver + merge dùng) + `dataset/alias_review.md`.

Chạy (PowerShell, từ apps/agent-service):
    $env:PYTHONIOENCODING="utf-8"
    ..\..\venv\Scripts\python.exe scripts/build_alias_map.py --workers 8
    # validate rẻ trước: thêm --max-pairs 40
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_AGENT_SERVICE = Path(__file__).resolve().parents[1]
if str(_AGENT_SERVICE) not in sys.path:
    sys.path.insert(0, str(_AGENT_SERVICE))

_REPO_ROOT = _AGENT_SERVICE.parents[1]
_DATASET = _REPO_ROOT / "dataset"
_CACHE = _DATASET / "graph_extractions.json"
_VERDICTS = _DATASET / "alias_verdicts.json"
_SEED = _DATASET / "alias_seed.json"
_OUT_MAP = _DATASET / "alias_map.json"
_OUT_REVIEW = _DATASET / "alias_review.md"

from app.indexing.graph.normalize import normalize_name  # noqa: E402
from app.prompts.alias_judge import (  # noqa: E402
    ALIAS_JUDGE_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.schemas.alias import AliasVerdict  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_alias_map")

def _load_verdicts() -> dict:
    """Đọc cache verdict, chịu lỗi: file thiếu/rỗng/hỏng -> {} (không nổ, chạy lại từ đầu)."""
    if not _VERDICTS.exists():
        return {}
    raw = _VERDICTS.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("%s hỏng, bỏ qua cache cũ và trích lại.", _VERDICTS.name)
        return {}

def _save_verdicts(verdicts: dict) -> None:
    """Ghi atomic (tmp + replace) để bị ngắt giữa chừng không làm rỗng/hỏng file cache."""
    tmp = _VERDICTS.with_suffix(_VERDICTS.suffix + ".tmp")
    tmp.write_text(json.dumps(verdicts, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_VERDICTS)

def _load_seed() -> dict:
    """Đọc seed thủ công, chịu lỗi như verdict: thiếu/rỗng/hỏng -> {} (chạy tiếp, không seed).

    Cảnh báo TO khi rỗng/hỏng chứ không im lặng: seed là phán quyết của người, mất nó
    thì alias ngữ nghĩa ("Nguyễn Ái Quốc"->"Hồ Chí Minh") biến khỏi map mà map vẫn ghi ra
    bình thường — dễ tưởng là chạy ngon.
    """
    if not _SEED.exists():
        return {}
    raw = _SEED.read_text(encoding="utf-8").strip()
    if not raw:
        log.warning("%s RỖNG -> bỏ qua seed thủ công (map sẽ thiếu alias ngữ nghĩa).", _SEED.name)
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("%s HỎNG (%s) -> bỏ qua seed thủ công.", _SEED.name, exc)
        return {}

def _strip_strong(s: str) -> str:
    """Dạng rút gọn CHỈ để tìm ứng viên: bỏ dấu + gạch nối + khoảng trắng. KHÔNG làm khóa."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d")
    return re.sub(r"[\s\-]", "", s)

def _build_records(limit: int) -> dict[str, dict]:
    cache = json.loads(_CACHE.read_text(encoding="utf-8"))
    rec: dict[str, dict] = {}
    for entry in cache.values():
        for e in entry.get("entities", []):
            norm = normalize_name(e["name"])
            r = rec.get(norm)
            if r is None:
                r = rec[norm] = {
                    "norm": norm, "name": e["name"], "type": e["type"],
                    "descs": [], "count": 0,
                }
            r["count"] += 1
            d = e.get("description")
            if d and d not in r["descs"] and len(r["descs"]) < 3:
                r["descs"].append(d)
    if limit:
        rec = dict(list(rec.items())[:limit])
    return rec

def _candidate_pairs(rec: dict[str, dict], ratio: float) -> list[tuple[str, str]]:
    """Cặp norm (sorted) cùng type: cùng dạng-rút-gọn hoặc fuzzy ratio cao."""
    ents = list(rec.values())
    for e in ents:
        e["strip"] = _strip_strong(e["norm"])

    pairs: set[tuple[str, str]] = set()

    # (a) cùng dạng-rút-gọn, cùng type.
    by_strip = defaultdict(list)
    for e in ents:
        by_strip[(e["type"], e["strip"])].append(e["norm"])
    for group in by_strip.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pairs.add(tuple(sorted((group[i], group[j]))))

    # (b) fuzzy, chặn theo (type, 2 ký tự đầu dạng-rút-gọn) cho khỏi nổ O(n^2).
    by_block = defaultdict(list)
    for e in ents:
        if len(e["strip"]) >= 3:
            by_block[(e["type"], e["strip"][:2])].append(e)
    for arr in by_block.values():
        for i in range(len(arr)):
            for j in range(i + 1, len(arr)):
                a, b = arr[i], arr[j]
                if a["strip"] == b["strip"] or abs(len(a["strip"]) - len(b["strip"])) > 3:
                    continue
                if SequenceMatcher(None, a["strip"], b["strip"]).ratio() >= ratio:
                    pairs.add(tuple(sorted((a["norm"], b["norm"]))))
    return sorted(pairs)

def _judge(pairs, rec, verdicts, workers, model):
    from app.core.llm import get_openai_client

    client = get_openai_client()
    todo = [p for p in pairs if f"{ALIAS_JUDGE_VERSION}|{p[0]}||{p[1]}" not in verdicts]
    log.info("Trọng tài: %d cặp cần hỏi LLM, %d dùng cache", len(todo), len(pairs) - len(todo))

    def _one(pair):
        a, b = rec[pair[0]], rec[pair[1]]
        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(a["type"], a, b)},
            ],
            response_format=AliasVerdict,
            temperature=0.0,
            timeout=60,
        )
        return pair, completion.choices[0].message.parsed

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_one, p): p for p in todo}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                _, v = fut.result()
            except Exception as exc:  # noqa: BLE001
                log.warning("Lỗi cặp %s: %s", p, exc)
                continue
            verdicts[f"{ALIAS_JUDGE_VERSION}|{p[0]}||{p[1]}"] = v.model_dump() if v else None
            done += 1
            if done % 50 == 0:
                _save_verdicts(verdicts)
                log.info("  ...đã hỏi %d/%d", done, len(todo))
    _save_verdicts(verdicts)

class _UF:
    def __init__(self):
        self.p: dict[str, str] = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)

def _pick_canonical(norms: list[str], rec: dict[str, dict]) -> str:
    """Canonical = nhắc nhiều nhất; hòa -> tên dài hơn; rồi alphabet."""
    return sorted(norms, key=lambda n: (-rec[n]["count"], -len(rec[n]["name"]), rec[n]["name"]))[0]

def _resolve_alias(norm: str, alias_map: dict[str, dict]) -> str:
    """Resolve đến canonical cuối, chịu được cả alias chain và map lỗi có vòng lặp."""
    current = norm
    seen: set[str] = set()
    while current in alias_map and current not in seen:
        seen.add(current)
        target = normalize_name(str(alias_map[current].get("canonical_norm", "")))
        if not target or target == current:
            break
        current = target
    return current

def _flatten_alias_map(alias_map: dict[str, dict]) -> dict[str, dict]:
    """Đưa mọi alias về canonical cuối trong đúng một lookup.

    Production ``resolve()`` chỉ tra map một lần, vì vậy artifact không được chứa
    chain ``A -> B -> C``. Self-map sau normalize là dư thừa; cycle nhiều node là
    lỗi cấu hình seed và phải dừng build thay vì âm thầm ghi map không ổn định.
    """
    flattened: dict[str, dict] = {}
    for alias in alias_map:
        current = alias
        seen: set[str] = set()
        canonical_name = str(alias_map[alias].get("canonical_name", alias))
        while current in alias_map:
            if current in seen:
                cycle = " -> ".join([*seen, current])
                raise ValueError(f"Alias map có vòng lặp: {cycle}")
            seen.add(current)
            entry = alias_map[current]
            target = normalize_name(str(entry.get("canonical_norm", "")))
            canonical_name = str(entry.get("canonical_name") or canonical_name)
            if not target or target == current:
                break
            current = target
        if alias != current:
            flattened[alias] = {
                "canonical_norm": current,
                "canonical_name": canonical_name,
            }
    return flattened

def main() -> None:
    ap = argparse.ArgumentParser(description="Dựng alias_map.json bằng LLM trọng tài.")
    ap.add_argument("--ratio", type=float, default=0.86, help="Ngưỡng fuzzy sinh ứng viên.")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="Chỉ lấy N entity đầu (debug).")
    ap.add_argument("--max-pairs", type=int, default=0, help="Chỉ hỏi N cặp đầu (validate rẻ).")
    ap.add_argument("--model", default=None, help="Override model trọng tài.")
    args = ap.parse_args()

    from app.core.config import get_settings
    model = args.model or get_settings().graph_llm_model or get_settings().llm_model

    rec = _build_records(args.limit)
    pairs = _candidate_pairs(rec, args.ratio)
    if args.max_pairs:
        pairs = pairs[: args.max_pairs]
    log.info("Entity: %d | cặp ứng viên: %d | model: %s", len(rec), len(pairs), model)

    verdicts = _load_verdicts()
    _judge(pairs, rec, verdicts, args.workers, model)

    # Gom cụm từ same+cao; thu vừa cho review.
    uf = _UF()
    review: list[tuple[str, str, dict]] = []
    n_cao = 0
    for p in pairs:
        v = verdicts.get(f"{ALIAS_JUDGE_VERSION}|{p[0]}||{p[1]}")
        if not v or not v.get("same"):
            continue
        if v["confidence"] == "cao":
            uf.union(p[0], p[1])
            n_cao += 1
        elif v["confidence"] == "vừa":
            review.append((p[0], p[1], v))

    clusters: dict[str, list[str]] = defaultdict(list)
    for norm in list(uf.p):  # chỉ node từng được union mới có trong uf.p
        clusters[uf.find(norm)].append(norm)
    clusters = {root: members for root, members in clusters.items() if len(members) > 1}

    # Map variant -> canonical (từ cụm auto).
    alias_map: dict[str, dict] = {}
    for members in clusters.values():
        can = _pick_canonical(members, rec)
        for n in members:
            if n != can:
                alias_map[n] = {"canonical_norm": can, "canonical_name": rec[can]["name"]}

    # Seed thủ công (cụm [[canonical, alias, ...], ...]) — ưu tiên ghi đè.
    n_seed = 0
    for cluster in _load_seed().get("clusters", []):
        if not cluster:
            continue
        can_name = cluster[0]
        can_norm = normalize_name(can_name)
        # Canonical thủ công phải là node cuối, không được giữ cạnh auto cũ khiến
        # canonical lại trỏ sang alias khác và tạo A <-> B.
        alias_map.pop(can_norm, None)
        for alias_name in cluster[1:]:
            alias_map[normalize_name(alias_name)] = {
                "canonical_norm": can_norm, "canonical_name": can_name,
            }
            n_seed += 1

    alias_map = _flatten_alias_map(alias_map)

    # Verdict confidence vừa đã được người duyệt chấp nhận qua seed thì không còn là
    # việc chờ duyệt. Lọc sau khi merge seed để alias_review.md phản ánh trạng thái thật.
    review = [
        (a, b, verdict)
        for a, b, verdict in review
        if _resolve_alias(a, alias_map) != _resolve_alias(b, alias_map)
    ]

    _OUT_MAP.write_text(
        json.dumps({"version": 1, "judge_version": ALIAS_JUDGE_VERSION, "map": alias_map},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # File review cho người duyệt.
    lines = [f"# Alias review — {len(review)} cặp 'vừa' cần xác nhận\n",
             "Nếu đồng ý gộp: thêm cụm `[\"<canonical>\", \"<alias>\"]` vào "
             "`dataset/alias_seed.json` (mục `clusters`) rồi chạy lại script.\n"]
    for a, b, v in sorted(review, key=lambda x: x[2]["confidence"]):
        lines.append(f"\n- **{rec[a]['name']}**  ⟷  **{rec[b]['name']}**  → canonical: "
                     f"`{v['canonical']}`\n  - {v['reason']}")
    lines.append(f"\n\n---\n## Đã gộp tự động (confidence cao): {len(clusters)} cụm\n")
    for members in sorted(clusters.values(), key=lambda m: -len(m)):
        can = _pick_canonical(members, rec)
        others = [rec[n]["name"] for n in members if n != can]
        lines.append(f"- **{rec[can]['name']}** ← {', '.join(others)}")
    _OUT_REVIEW.write_text("\n".join(lines), encoding="utf-8")

    log.info("Cặp same+cao: %d -> %d cụm | seed: %d | cần duyệt (vừa): %d",
             n_cao, len(clusters), n_seed, len(review))
    log.info("Ghi: %s (%d biến thể) + %s", _OUT_MAP, len(alias_map), _OUT_REVIEW)

if __name__ == "__main__":
    main()
