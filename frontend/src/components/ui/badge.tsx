import * as React from "react";
import { cn } from "@/lib/utils";

export function Badge({
  className,
  tone = "cyan",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: "cyan" | "red" | "yellow" | "green" | "violet" | "slate" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold uppercase tracking-[0.16em]",
        tone === "cyan" && "border-cyan-300/30 bg-cyan-300/10 text-cyan-200",
        tone === "red" && "border-rose-400/35 bg-rose-500/10 text-rose-200",
        tone === "yellow" && "border-yellow-300/35 bg-yellow-400/10 text-yellow-200",
        tone === "green" && "border-emerald-300/35 bg-emerald-400/10 text-emerald-200",
        tone === "violet" && "border-violet-300/35 bg-violet-400/10 text-violet-200",
        tone === "slate" && "border-slate-400/20 bg-slate-400/10 text-slate-200",
        className
      )}
      {...props}
    />
  );
}
