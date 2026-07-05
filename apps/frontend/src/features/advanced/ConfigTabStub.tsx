/**
 * Cấu hình hệ thống ĐÃ có thiết kế đầy đủ (docs/plan/system-config-plan.md) nhưng CHƯA build
 * — đụng orchestrator đang chạy ổn định, làm sau. "Sắp cập nhật" (không phải "sắp ra mắt")
 * để phân biệt: đã có spec, chỉ đang chờ tới lượt.
 */
export function ConfigTabStub() {
  return (
    <div className="rounded-lg border border-dashed border-paper-border p-8 text-center">
      <p className="text-lg font-semibold text-ink">Sắp cập nhật</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-ink-soft">
        Chọn chế độ truy hồi mặc định (Traditional / GraphRAG / Hybrid) và tinh chỉnh
        retrieval/synthesize. Tính năng đã có thiết kế đầy đủ, đang chờ tới lượt triển khai.
      </p>
    </div>
  );
}
