export function KpiCard({
  label,
  value,
  delta,
  tone = "default",
}: {
  label: string;
  value: string | number;
  delta?: string;
  tone?: "default" | "good" | "bad";
}) {
  const color =
    tone === "good"
      ? "text-liaison-teal"
      : tone === "bad"
        ? "text-liaison-error"
        : "text-liaison-on-surface";
  return (
    <div className="rounded-xl p-4 border border-liaison-outline-variant bg-liaison-surface-low hover:shadow-md transition-shadow">
      <p className="text-[10px] text-liaison-on-surface-variant uppercase font-bold tracking-widest">
        {label}
      </p>
      <p className={`text-2xl font-headline font-bold mt-1 tabular-nums ${color}`}>
        {value}
      </p>
      {delta ? (
        <p className="text-xs text-liaison-on-surface-variant mt-1">{delta}</p>
      ) : null}
    </div>
  );
}
