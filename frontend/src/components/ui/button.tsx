import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean;
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(
          "inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-cyan-glow/50 disabled:cursor-not-allowed disabled:opacity-50",
          variant === "primary" && "bg-cyan-400 text-slate-950 shadow-glow hover:-translate-y-0.5 hover:bg-cyan-300",
          variant === "secondary" && "border border-white/10 bg-white/8 text-white hover:border-cyan-300/50 hover:bg-cyan-300/10",
          variant === "ghost" && "text-slate-300 hover:bg-white/8 hover:text-white",
          variant === "danger" && "bg-alert text-white shadow-alert hover:bg-rose-400",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";
