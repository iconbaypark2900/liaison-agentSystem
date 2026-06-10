import type { ReactNode } from "react";

export function Panel({
  eyebrow,
  title,
  purpose,
  children,
  className = "",
}: {
  eyebrow?: string;
  title?: string;
  purpose?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel flex flex-col min-h-0 ${className}`}>
      {eyebrow ? <p className="panel-eyebrow">{eyebrow}</p> : null}
      {title ? <h2 className="panel-title">{title}</h2> : null}
      {purpose ? (
        <p className="text-sm text-liaison-on-surface-variant mt-1 mb-3">{purpose}</p>
      ) : null}
      <div className="flex-1 min-h-0 overflow-auto">{children}</div>
    </section>
  );
}
