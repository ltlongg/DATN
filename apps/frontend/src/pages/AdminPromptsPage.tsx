import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import {
  createPromptVersion,
  getPrompt,
  getPromptVersion,
  listPrompts,
  promotePromptVersion,
} from "@/api/prompts";
import { PageHeader } from "@/components/PageHeader";
import { Spinner } from "@/components/Spinner";
import { DiffModal } from "@/features/prompts/DiffModal";
import { PromptEditor } from "@/features/prompts/PromptEditor";
import { PromptTree } from "@/features/prompts/PromptTree";
import { VersionHistory } from "@/features/prompts/VersionHistory";

interface CompareState {
  open: boolean;
  title: string;
  oldText: string;
  newText: string;
}
const NO_COMPARE: CompareState = { open: false, title: "", oldText: "", newText: "" };

export default function AdminPromptsPage() {
  const qc = useQueryClient();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [compare, setCompare] = useState<CompareState>(NO_COMPARE);

  const list = useQuery({ queryKey: ["adm-prompts"], queryFn: listPrompts });
  const detail = useQuery({
    queryKey: ["adm-prompt", selectedKey],
    queryFn: () => getPrompt(selectedKey as string),
    enabled: !!selectedKey,
  });

  // Chọn prompt đầu tiên khi danh sách nạp xong.
  useEffect(() => {
    if (!selectedKey && list.data && list.data.length > 0) setSelectedKey(list.data[0].key);
  }, [list.data, selectedKey]);

  // Nạp content production vào editor khi ĐỔI prompt (không clobber khi refetch cùng key).
  const detailKey = detail.data?.key;
  useEffect(() => {
    if (detail.data) {
      setContent(detail.data.production_content ?? "");
      setNote("");
      setError(null);
    }
  }, [detailKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["adm-prompts"] });
    qc.invalidateQueries({ queryKey: ["adm-prompt", selectedKey] });
  };
  const createMut = useMutation({
    mutationFn: () => createPromptVersion(selectedKey as string, { content, note: note || null }),
    onSuccess: invalidate,
  });
  const promoteMut = useMutation({
    mutationFn: (versionNo: number) => promotePromptVersion(selectedKey as string, versionNo),
    onSuccess: invalidate,
  });

  async function handleSave() {
    setError(null);
    try {
      await createMut.mutateAsync();
      setNote("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không lưu được phiên bản mới.");
    }
  }

  async function handleRollback(versionNo: number) {
    setError(null);
    try {
      const updated = await promoteMut.mutateAsync(versionNo);
      setContent(updated.production_content ?? "");
      setNote("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không khôi phục được phiên bản này.");
    }
  }

  async function handleCompare(versionNo: number) {
    try {
      const v = await getPromptVersion(selectedKey as string, versionNo);
      setCompare({
        open: true,
        title: `So sánh production ↔ v${versionNo}`,
        oldText: detail.data?.production_content ?? "",
        newText: v.content,
      });
    } catch {
      setError("Không tải được nội dung phiên bản để so sánh.");
    }
  }

  const pending = createMut.isPending || promoteMut.isPending;
  const dirty = detail.data ? content !== (detail.data.production_content ?? "") : false;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Quản lý Prompt"
        desc="Sửa system prompt và áp dụng ngay; mỗi lần lưu tạo một phiên bản mới trong lịch sử. Agent luôn fallback về hằng code nếu DB thiếu."
      />

      {list.isLoading ? (
        <Spinner />
      ) : list.isError ? (
        <p className="text-sm text-rose-700">Không tải được danh sách prompt.</p>
      ) : !list.data || list.data.length === 0 ? (
        <p className="rounded-md bg-paper p-3 text-sm text-ink-soft">
          Chưa có prompt nào — chạy <code>scripts/seed_prompts.py</code> để khởi tạo từ code.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,2fr)_minmax(0,1.1fr)]">
          <div className="rounded-lg border border-paper-border bg-paper-card p-3">
            <PromptTree items={list.data} selectedKey={selectedKey} onSelect={setSelectedKey} />
          </div>

          <div className="rounded-lg border border-paper-border bg-paper-card p-4">
            {detail.isLoading || !detail.data ? (
              <Spinner />
            ) : (
              <PromptEditor
                detail={detail.data}
                content={content}
                note={note}
                dirty={dirty}
                pending={pending}
                error={error}
                onContentChange={setContent}
                onNoteChange={setNote}
                onSave={handleSave}
              />
            )}
          </div>

          <div className="rounded-lg border border-paper-border bg-paper-card p-3">
            {detail.data && (
              <VersionHistory
                versions={detail.data.versions}
                activeVersionNo={
                  detail.data.versions.find((v) => v.status === "production")?.version_no ?? null
                }
                pending={pending}
                onRollback={handleRollback}
                onCompare={handleCompare}
              />
            )}
          </div>
        </div>
      )}

      <DiffModal
        open={compare.open}
        title={compare.title}
        oldText={compare.oldText}
        newText={compare.newText}
        onClose={() => setCompare(NO_COMPARE)}
      />
    </div>
  );
}
