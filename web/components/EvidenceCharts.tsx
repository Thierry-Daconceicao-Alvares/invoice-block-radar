"use client";

import type { EChartsOption } from "echarts";
import { useCallback } from "react";

import Chart, { token } from "@/components/Chart";

export function CaptureCurves({
  curves,
  xLabel,
  yLabel,
  label,
}: {
  curves: Record<string, [number, number][]>;
  xLabel: string;
  yLabel: string;
  label: string;
}) {
  const option = useCallback((): EChartsOption => {
    const styles = [
      { color: token("--accent"), width: 3, type: "solid" as const },
      { color: token("--hold"), width: 2, type: "solid" as const },
      { color: token("--hold"), width: 1.6, type: "dashed" as const },
      { color: token("--muted"), width: 1.6, type: "dashed" as const },
      { color: token("--ok"), width: 1.4, type: "dashed" as const },
      { color: token("--muted"), width: 1.4, type: "dotted" as const },
    ];
    const muted = token("--muted");
    return {
      textStyle: { fontFamily: "Archivo Variable, sans-serif", color: muted },
      legend: { top: 0, left: 0, textStyle: { color: token("--ink") }, itemWidth: 22 },
      grid: { left: 52, right: 18, top: 64, bottom: 46 },
      tooltip: {
        trigger: "axis",
        backgroundColor: token("--surface"),
        borderColor: token("--line"),
        textStyle: { color: token("--ink") },
        valueFormatter: (v) => `${Number(v).toFixed(0)}%`,
      },
      xAxis: {
        type: "value",
        min: 0,
        max: 100,
        name: xLabel,
        nameLocation: "middle",
        nameGap: 28,
        axisLabel: { formatter: "{value}%" },
        splitLine: { lineStyle: { color: token("--chart-grid") } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        name: yLabel,
        nameLocation: "middle",
        nameGap: 38,
        axisLabel: { formatter: "{value}%" },
        splitLine: { lineStyle: { color: token("--chart-grid") } },
      },
      series: Object.entries(curves).map(([name, points], i) => ({
        name,
        type: "line",
        showSymbol: false,
        data: points,
        lineStyle: styles[i % styles.length],
        itemStyle: { color: styles[i % styles.length].color },
        markLine:
          i === 0
            ? {
                silent: true,
                symbol: "none",
                label: { formatter: "first 20%", color: token("--fix") },
                lineStyle: { color: token("--fix"), type: "solid", opacity: 0.5 },
                data: [{ xAxis: 20 }],
              }
            : undefined,
      })),
    };
  }, [curves, xLabel, yLabel]);
  return <Chart option={option} height={380} label={label} />;
}
