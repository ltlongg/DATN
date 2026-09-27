import { useState } from "react";
import { Calculator } from "lucide-react";

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
    <div className="card flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
      <label className="flex items-center gap-3 text-sm">
        <Calculator size={16} className="text-ink-faint" aria-hidden />
        <span className="font-medium text-ink">Giá ước tính ($/1K token)</span>
        <input
          type="number"
          min={0}
          step="0.001"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          className="input h-9 w-28"
        />
        {valid && (
          <span data-testid="cost-estimate" className="text-base font-semibold tabular-nums text-brand">
            ≈ ${estimate.toFixed(2)}
          </span>
        )}
      </label>
      <p className="text-xs text-ink-faint">
        Chỉ là ước tính bạn tự nhập, không phản ánh giá thật của nhà cung cấp model.
      </p>
    </div>
  );
}
