"use client";

import type { EChartsOption } from "echarts";
import { useCallback } from "react";

import Chart, { token } from "@/components/Chart";
import type { Overview } from "@/lib/api";
import { RELEASE_REASONS, fmt } from "@/lib/api";

function base(): Partial<EChartsOption> {
  const muted = token("--muted");
  return {
    textStyle: { fontFamily: "Archivo Variable, sans-serif", color: muted },
    tooltip: {
      backgroundColor: token("--surface"),
      borderColor: token("--line"),
      textStyle: { color: token("--ink") },
    },
  };
}

export function ReleaseReasons({ overview }: { overview: Overview }) {
  const option = useCallback((): EChartsOption => {
    const rows = [...overview.release_reasons].reverse();
    const total = rows.reduce((s, r) => s + r.blocks, 0);
    const colors: Record<string, string> = {
      released_after_review: token("--accent"),
      waiting_for_goods: token("--hold"),
      invoice_corrected: token("--fix"),
      order_corrected: token("--fix"),
    };
    return {
      ...base(),
      grid: { left: 210, right: 70, top: 10, bottom: 10 },
      xAxis: { type: "value", show: false },
      yAxis: {
        type: "category",
        data: rows.map((r) => RELEASE_REASONS[r.release_reason]),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: token("--ink"), fontSize: 13 },
      },
      tooltip: {
        ...(base().tooltip as object),
        formatter: (p: unknown) => {
          const r = rows[(p as { dataIndex: number }).dataIndex];
          return `${RELEASE_REASONS[r.release_reason]}<br/>${fmt.int(r.blocks)} blocks · median ${r.median_days_blocked} days<br/>${fmt.pct(r.released_by_a_person)} released by a person`;
        },
      },
      series: [
        {
          type: "bar",
          barWidth: 18,
          data: rows.map((r) => ({
            value: r.blocks,
            itemStyle: { color: colors[r.release_reason], borderRadius: [0, 4, 4, 0] },
          })),
          label: {
            show: true,
            position: "right",
            color: token("--ink"),
            fontFamily: "IBM Plex Mono, monospace",
            formatter: (p: unknown) => fmt.pct((p as { value: number }).value / total),
          },
        },
      ],
    };
  }, [overview]);
  return <Chart option={option} height={200} label="How the payment blocks ended" />;
}

export function MonthlyRate({ overview }: { overview: Overview }) {
  const option = useCallback((): EChartsOption => {
    const rows = overview.monthly_block_rate;
    const hold = token("--hold");
    return {
      ...base(),
      grid: { left: 44, right: 16, top: 16, bottom: 30 },
      xAxis: {
        type: "category",
        data: rows.map((r) => new Date(`${r.month}-01`).toLocaleString("en-GB", { month: "short" })),
        axisLine: { lineStyle: { color: token("--line") } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 0.4,
        splitNumber: 4,
        axisLabel: { formatter: (v: number) => fmt.pct(v) },
        splitLine: { lineStyle: { color: token("--chart-grid") } },
      },
      tooltip: {
        ...(base().tooltip as object),
        trigger: "axis",
        formatter: (p: unknown) => {
          const i = (p as { dataIndex: number }[])[0].dataIndex;
          return `${rows[i].month}<br/><b>${fmt.pct(rows[i].block_rate, 1)}</b> of ${fmt.int(rows[i].invoiced_lines)} invoiced lines blocked`;
        },
      },
      series: [
        {
          type: "line",
          data: rows.map((r) => r.block_rate),
          smooth: 0.2,
          symbolSize: 7,
          lineStyle: { width: 2.5, color: hold },
          itemStyle: { color: hold },
          areaStyle: { color: hold, opacity: 0.12 },
        },
      ],
    };
  }, [overview]);
  return <Chart option={option} height={220} label="Share of invoiced order lines blocked, by month the order was created" />;
}
