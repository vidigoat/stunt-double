"use client";

import { useEffect, useRef, useState } from "react";
import { num, usd } from "@/lib/api";

/** Animates from the previous value to the new one (ease-out, ~0.8s). Respects reduced motion. */
export function CountUp({ value, format = "num" }: { value: number; format?: "num" | "usd" }) {
  const [shown, setShown] = useState(value);
  const from = useRef(0);
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const start = from.current;
    if (reduce || start === value) { setShown(value); from.current = value; return; }
    const t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const p = Math.min(1, (t - t0) / 800);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(Math.round(start + (value - start) * eased));
      if (p < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => { cancelAnimationFrame(raf); from.current = value; };
  }, [value]);
  return <>{format === "usd" ? usd(shown) : num(shown)}</>;
}
