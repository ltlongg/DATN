import { useState } from "react";

/**
 * Ước tính $ = tokens/1000 × giá tự nhập. HOÀN TOÀN client-side, KHÔNG gọi API, KHÔNG lưu
 * backend, KHÔNG phải giá thật của nhà cung cấp (xem backend-additions §4).
 */
export function CostEstimateInput({ totalTokens }: { totalTokens: number }) {
  const [price, setPrice] = useState("");
  const p = Number(price);
  const valid = price.trim() !== "" && !Number.isNaN(p) && p >= 0;
  const estimate = valid ? (totalTokens / 1000) * p : 0;

  return (
    <div className="rounded-lg border border-paper-border bg-paper-card p-3">
      <label className="flex items-center gap-2 text-sm">
        <span className="text-ink-soft">Giá ước tính ($/1K token)</span>
        <input
          type="number"
          min={0}
          step="0.001"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          className="w-28 rounded-md border border-paper-border px-2 py-1 outline-none focus:border-brand"
        />
        {valid && (
          <span data-testid="cost-estimate" className="font-semibold text-ink">
            ≈ ${estimate.toFixed(2)}
          </span>
        )}
      </label>
      <p className="mt-1 text-xs text-ink-soft">
        Chỉ là ước tính bạn tự nhập, không phản ánh giá thật của nhà cung cấp model.
      </p>
    </div>
  );
}
