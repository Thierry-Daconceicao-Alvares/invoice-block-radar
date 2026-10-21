"use client";

import type { EChartsOption } from "echarts";
import { useCallback } from "react";

import Chart, { token } from "@/components/Chart";

const DRIVER_LABELS: Record<string, string> = {
  sub_spend_area: "What is bought",
  pair_past_rate: "Past block rate: vendor x company x match type",
  vendor_past_rate: "Past block rate of the vendor",
  buyer_past_rate: "Past block rate of the buyer",
  vendor_paid_before: "Invoices already paid to the vendor",
  pair_paid_before: "Invoices already paid: vendor x company x match type",
  lines_in_document: "Lines in the same purchase order",
  buyer_paid_before: "Invoices already handled by the buyer",
  area_paid_before: "Invoices already paid in the spend area",
  area_past_rate: "Past block rate of the spend area",
  po_value_eur: "Order line value",
};

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

export function Drivers({ drivers }: { drivers: Record<string, number> }) {
  const option = useCallback((): EChartsOption => {
    const rows = Object.entries(drivers)
      .filter(([, v]) => v > 0.04)
      .reverse();
    return {
      textStyle: { fontFamily: "Archivo Variable, sans-serif" },
      grid: { left: 290, right: 40, top: 6, bottom: 6 },
      xAxis: { type: "value", show: false },
      yAxis: {
        type: "category",
        data: rows.map(([k]) => DRIVER_LABELS[k] ?? k),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: token("--ink"), fontSize: 12 },
      },
      series: [
        {
          type: "bar",
          barWidth: 13,
          data: rows.map(([, v]) => v),
          itemStyle: { color: token("--accent"), borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: "right", color: token("--muted"), fontSize: 11, formatter: (p) => Number(p.value).toFixed(2) },
        },
      ],
    };
  }, [drivers]);
  return <Chart option={option} height={300} label="Inputs the forecaster relies on most, by mean absolute SHAP value" />;
}
