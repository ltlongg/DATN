/** Ô số liệu dùng chung cho các dashboard admin (chi phí, chất lượng, token). `sub` là dòng
 * chú thích nhỏ dưới giá trị (vd tỷ lệ %). */
export function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-paper-border bg-paper-card p-3">
      <p className="text-xs text-ink-soft">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
      {sub && <p className="text-xs text-ink-soft">{sub}</p>}
    </div>
  );
}
