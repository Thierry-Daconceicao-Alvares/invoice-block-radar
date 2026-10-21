"use client";

import * as echarts from "echarts";
import { useEffect, useRef } from "react";

// Reads the page's colour tokens so every chart follows the light or dark theme.
export function token(name: string): string {
  if (typeof window === "undefined") return "#888";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}

export function useThemeVersion(onChange: () => void) {
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [onChange]);
}

export default function Chart({
  option,
  height = 320,
  label,
}: {
  option: () => echarts.EChartsOption;
  height?: number;
  label: string;
}) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!box.current) return;
    const chart = echarts.init(box.current, undefined, { renderer: "canvas" });
    const draw = () => chart.setOption(option(), true);
    draw();
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(box.current);
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", draw);
    return () => {
      media.removeEventListener("change", draw);
      resize.disconnect();
      chart.dispose();
    };
  }, [option]);

  return <div ref={box} role="img" aria-label={label} style={{ width: "100%", height }} />;
}
