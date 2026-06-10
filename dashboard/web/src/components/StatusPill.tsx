const STYLES = {
  pass: "bg-liaison-teal/20 text-liaison-teal border-liaison-teal/40",
  warn: "bg-liaison-warn/20 text-liaison-warn border-liaison-warn/40",
  fail: "bg-liaison-error/20 text-liaison-error border-liaison-error/40",
  ready: "bg-liaison-teal/20 text-liaison-teal border-liaison-teal/40",
  unknown: "bg-liaison-surface-container text-liaison-on-surface-variant border-liaison-outline-variant",
};

export function StatusPill({
  status,
  children,
  title,
}: {
  status: keyof typeof STYLES;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide border ${STYLES[status] ?? STYLES.unknown}`}
    >
      {children}
    </span>
  );
}
