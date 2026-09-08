import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import { getSystemConfig, updateSystemConfig } from "@/api/config";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import type { SystemConfig, SystemConfigUpdate } from "@/types/admin";

const configKey = ["adm-system-config"] as const;

type FieldKey = keyof SystemConfigUpdate;

interface FieldSpec {
  key: FieldKey;
  label: string;
  def: number;
  integer: boolean;
  min: number;
  max?: number;
  step?: number;
  help?: string;
}

const RETRIEVAL_FIELDS: FieldSpec[] = [
  { key: "rag_top_k", label: "RAG top-k", def: 20, integer: true, min: 1, help: "Số chunk vector lấy về (traditional + hybrid)." },
  { key: "graph_top_k", label: "Graph top-k", def: 20, integer: true, min: 1, help: "Số chunk lấy từ knowledge graph." },
  { key: "hybrid_candidate_k", label: "Hybrid candidate-k", def: 30, integer: true, min: 1, help: "Kích thước pool sau khi fuse RRF (hybrid)." },
  { key: "hybrid_rrf_k", label: "Hybrid RRF k", def: 60, integer: true, min: 1, help: "Hằng số RRF khi gộp nhiều nguồn (hybrid)." },
  { key: "rerank_top_k", label: "Rerank top-k", def: 8, integer: true, min: 1, help: "Số chunk giữ lại sau rerank (phải ≤ candidate-k)." },
  { key: "bm25_top_k", label: "BM25 top-k", def: 20, integer: true, min: 1, help: "Số candidate sparse BM25." },
  { key: "graph_max_seed_entities", label: "Graph max seed", def: 5, integer: true, min: 1, help: "Số thực thể seed tối đa mỗi câu hỏi." },
  { key: "graph_max_chunks_per_seed", label: "Graph max chunk/seed", def: 20, integer: true, min: 1, help: "Cap số chunk mỗi seed (chặn hub bùng nổ)." },
  { key: "graph_hub_source_count_threshold", label: "Graph hub threshold", def: 80, integer: true, min: 1, help: "Ngưỡng coi 1 thực thể là hub (hạ điểm)." },
  { key: "graph_max_context_items", label: "Graph max context", def: 12, integer: true, min: 1, help: "Số mục graph_context tối đa đưa vào prompt." },
  { key: "graph_max_path_hops", label: "Graph max path hops", def: 3, integer: true, min: 1, help: "Cận số bước khi tìm đường giữa 2 seed." },
  { key: "graph_path_hit_weight", label: "Graph path hit weight", def: 1.5, integer: false, min: 0, step: 0.1, help: "Điểm cho chunk nằm trên đường nối 2 seed." },
];

// Không có nhóm synthesize: 3 bước online chạy model reasoning, chúng từ chối `temperature`
// và dùng `reasoning_effort` — hằng "low" trong agent-service, không phơi ra admin.
const ALL_FIELDS = RETRIEVAL_FIELDS;

/** Giá trị form là string (cho phép gõ dở); parse + validate khi lưu. */
type FormValues = Record<FieldKey, string>;

function toForm(cfg: SystemConfig): FormValues {
  const out = {} as FormValues;
  for (const f of ALL_FIELDS) out[f.key] = String(cfg[f.key]);
  return out;
}

function validateField(spec: FieldSpec, raw: string): string | null {
  const n = Number(raw);
  if (raw.trim() === "" || Number.isNaN(n)) return "Bắt buộc nhập số.";
  if (spec.integer && !Number.isInteger(n)) return "Phải là số nguyên.";
  if (n < spec.min) return `Phải ≥ ${spec.min}.`;
  if (spec.max !== undefined && n > spec.max) return `Phải ≤ ${spec.max}.`;
  return null;
}

/** Lỗi theo từng field + ràng buộc chéo rerank_top_k ≤ hybrid_candidate_k (khớp DB CHECK). */
function computeErrors(values: FormValues): Partial<Record<FieldKey, string>> {
  const errors: Partial<Record<FieldKey, string>> = {};
  for (const spec of ALL_FIELDS) {
    const err = validateField(spec, values[spec.key]);
    if (err) errors[spec.key] = err;
  }
  const rerank = Number(values.rerank_top_k);
  const candidate = Number(values.hybrid_candidate_k);
  if (
    !errors.rerank_top_k &&
    !errors.hybrid_candidate_k &&
    rerank > candidate
  ) {
    errors.rerank_top_k = "Không được lớn hơn Hybrid candidate-k.";
  }
  return errors;
}

function FieldInput({
  spec,
  value,
  error,
  onChange,
}: {
  spec: FieldSpec;
  value: string;
  error?: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm font-medium text-ink">{spec.label}</span>
      <input
        type="number"
        step={spec.step ?? 1}
        value={value}
        aria-label={spec.label}
        onChange={(e) => onChange(e.target.value)}
        className={`rounded-md border px-3 py-2 text-sm ${
          error ? "border-rose-500" : "border-paper-border"
        }`}
      />
      {error ? (
        <span className="text-xs text-rose-700">{error}</span>
      ) : (
        spec.help && (
          <span className="text-xs text-ink-soft">
            {spec.help} Mặc định: {spec.def}.
          </span>
        )
      )}
    </label>
  );
}

export function ConfigForm() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: configKey, queryFn: getSystemConfig });
  const [values, setValues] = useState<FormValues | null>(null);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Nạp giá trị server vào form 1 lần khi query xong.
  useEffect(() => {
    if (query.data) setValues(toForm(query.data));
  }, [query.data]);

  const errors = useMemo(
    () => (values ? computeErrors(values) : {}),
    [values],
  );
  const hasError = Object.keys(errors).length > 0;

  const mutation = useMutation({
    mutationFn: updateSystemConfig,
    onSuccess: (data) => {
      qc.setQueryData(configKey, data);
      setValues(toForm(data));
      setSaved(true);
      setSaveError(null);
    },
    onError: (e) => {
      setSaved(false);
      setSaveError(e instanceof ApiError ? e.message : "Không lưu được cấu hình.");
    },
  });

  if (query.isLoading) return <Spinner />;
  if (query.isError || !values) return <EmptyState>Không tải được cấu hình hệ thống.</EmptyState>;

  const set = (key: FieldKey, v: string) => {
    setValues((prev) => (prev ? { ...prev, [key]: v } : prev));
    setSaved(false);
  };

  const handleSave = () => {
    if (hasError) return;
    const patch = {} as SystemConfigUpdate;
    for (const f of ALL_FIELDS) patch[f.key] = Number(values[f.key]);
    mutation.mutate(patch);
  };

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">Retrieval</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {RETRIEVAL_FIELDS.map((spec) => (
            <FieldInput
              key={spec.key}
              spec={spec}
              value={values[spec.key]}
              error={errors[spec.key]}
              onChange={(v) => set(spec.key, v)}
            />
          ))}
        </div>
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={hasError || mutation.isPending}
          className="rounded-md bg-brand px-4 py-2 text-sm text-brand-fg hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
        >
          {mutation.isPending ? "Đang lưu…" : "Lưu & áp dụng"}
        </button>
        {saved && (
          <span className="text-sm text-emerald-700">
            Đã lưu — có hiệu lực trong tối đa 60 giây (cache nội bộ agent-service).
          </span>
        )}
        {saveError && <span className="text-sm text-rose-700">{saveError}</span>}
      </div>
    </div>
  );
}
