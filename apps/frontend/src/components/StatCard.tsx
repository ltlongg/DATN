/** Ô số liệu dùng chung cho các dashboard admin (chi phí, chất lượng, token). `sub` là dòng
 * chú thích nhỏ dưới giá trị (vd tỷ lệ %). */
export function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card px-4 py-3.5">
      <p className="text-xs font-medium text-ink-soft">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight text-ink">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-ink-soft">{sub}</p>}
    </div>
  );
}
