export function BarList({
  rows,
  total,
}: {
  rows: { id: string; label: string; count: number }[];
  total: number;
}) {
  return (
    <div className="stack-lg" style={{ gap: "0.6rem" }}>
      {rows.map((row) => (
        <div key={row.id}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
            <span>{row.label}</span>
            <span className="muted">{row.count}</span>
          </div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${total === 0 ? 0 : Math.round((row.count / total) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
