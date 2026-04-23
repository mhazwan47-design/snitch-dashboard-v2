import React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }) {
  return <div className={cn("rounded-3xl border", className)} {...props} />;
}

export function CardHeader({ className, ...props }) {
  return <div className={cn("p-6", className)} {...props} />;
}

export function CardTitle({ className, ...props }) {
  return <h3 className={cn("font-semibold", className)} {...props} />;
}

export function CardDescription({ className, ...props }) {
  return <p className={cn("text-sm", className)} {...props} />;
}

export function CardContent({ className, ...props }) {
  return <div className={cn("p-6 pt-0", className)} {...props} />;
}
