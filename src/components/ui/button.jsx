import React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

export function Button({
  className,
  variant = "default",
  asChild = false,
  ...props
}) {
  const Comp = asChild ? Slot : "button";

  const variants = {
    default: "bg-slate-100 text-slate-950 hover:bg-white",
    outline: "border border-slate-700 text-slate-200 hover:bg-slate-900 bg-transparent",
  };

  return (
    <Comp
      className={cn(
        "inline-flex items-center justify-center rounded-2xl px-4 py-2 text-sm font-medium transition-colors",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
