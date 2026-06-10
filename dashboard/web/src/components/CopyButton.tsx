"use client";

import { useState } from "react";

export function CopyButton({
  text,
  label = "Copy",
  disabled = false,
  title,
}: {
  text: string;
  label?: string;
  disabled?: boolean;
  title?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (disabled) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  }

  if (!text || text === "—") return null;

  return (
    <button
      type="button"
      onClick={() => void copy()}
      disabled={disabled}
      title={title}
      className={`text-xs px-2 py-1 rounded-md border border-liaison-outline-variant text-liaison-primary ${
        disabled
          ? "opacity-40 cursor-not-allowed"
          : "hover:bg-liaison-surface-container"
      }`}
    >
      {copied ? "Copied" : label}
    </button>
  );
}
