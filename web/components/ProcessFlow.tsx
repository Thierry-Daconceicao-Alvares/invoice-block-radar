"use client";

import type { EChartsOption } from "echarts";
import { useCallback } from "react";

import Chart, { token } from "@/components/Chart";
import type { ProcessMap } from "@/lib/api";
import { fmt } from "@/lib/api";

// Where each step sits on the drawing (x: left to right in time, y: lane).
const PLACES: Record<string, { x: number; y: number; label: string }> = {
  "Create Purchase Requisition Item": { x: 2, y: 30, label: "Requisition" },
  "Create Purchase Order Item": { x: 15, y: 30, label: "Order line created" },
  "Receive Order Confirmation": { x: 28, y: 52, label: "Order confirmed" },
  "Change Quantity": { x: 28, y: 8, label: "Quantity changed" },
  "Vendor creates invoice": { x: 43, y: 44, label: "Vendor invoice dated" },
  "Record Goods Receipt": { x: 43, y: 16, label: "Goods received" },
  "Record Service Entry Sheet": { x: 56, y: 2, label: "Service entry" },
  "Record Invoice Receipt": { x: 61, y: 30, label: "Invoice recorded" },
  "Remove Payment Block": { x: 79, y: 30, label: "Block released" },
  "Clear Invoice": { x: 96, y: 30, label: "Invoice paid" },
};

export default function ProcessFlow({ map }: { map: ProcessMap }) {
  const option = useCallback((): EChartsOption => {
    const ink = token("--ink");
    const muted = token("--muted");
    const accent = token("--accent");
    const hold = token("--hold");
    const ok = token("--ok");
    const surface = token("--surface");
    const max = Math.max(...map.edges.map((e) => e.transitions));
    const colorOf = (activity: string) =>
      activity === "Remove Payment Block" ? hold : activity === "Clear Invoice" ? ok : accent;

    const edges = map.edges
      .filter((e) => PLACES[e.source] && PLACES[e.target])
      .map((e) => {
        const a = PLACES[e.source];
        const b = PLACES[e.target];
        const weight = e.transitions / max;
        const intoBlock = e.target === "Remove Payment Block";
        return {
          coords: [
            [a.x, a.y],
            [b.x, b.y],
          ],
          value: e.transitions,
          days: e.median_days,
          names: [PLACES[e.source].label, PLACES[e.target].label],
          lineStyle: {
            width: 1 + weight * 9,
            opacity: 0.18 + weight * 0.45,
            color: intoBlock ? hold : muted,
            curveness: a.x > b.x ? 0.35 : 0.12,
          },
          effect: {
            show: true,
            period: Math.max(2.5, 9 - weight * 6),
            trailLength: 0.25,
            symbolSize: 3 + weight * 4,
            color: intoBlock ? hold : accent,
          },
        };
      });

    return {
      animationDuration: 600,
      grid: { left: 10, right: 10, top: 30, bottom: 30 },
      xAxis: { type: "value", min: -4, max: 102, show: false },
      yAxis: { type: "value", min: -6, max: 62, show: false, inverse: true },
      tooltip: {
        backgroundColor: surface,
        borderColor: token("--line"),
        textStyle: { color: ink, fontFamily: "Archivo Variable, sans-serif" },
        formatter: (p: unknown) => {
          const params = p as { seriesType: string; data: Record<string, unknown> };
          const d = params.data;
          if (params.seriesType === "lines") {
            const names = d.names as string[];
            return `${names[0]} → ${names[1]}<br/><b>${fmt.int(d.value as number)}</b> times · median ${d.days} days`;
          }
          return `${d.name}<br/><b>${fmt.int(d.items as number)}</b> blocked items pass here`;
        },
      },
      series: [
        {
          type: "lines",
          coordinateSystem: "cartesian2d" as const,
          polyline: false,
          zlevel: 1,
          data: edges as never,
        },
        {
          type: "scatter",
          zlevel: 2,
          symbolSize: (value: number[]) => value[2],
          data: map.nodes
            .filter((n) => PLACES[n.activity])
            .map((n) => ({
              value: [PLACES[n.activity].x, PLACES[n.activity].y, 10 + Math.sqrt(n.items) / 9],
              name: PLACES[n.activity].label,
              items: n.items,
              itemStyle: { color: colorOf(n.activity), borderColor: surface, borderWidth: 3 },
            })),
          label: {
            show: true,
            position: "bottom",
            distance: 8,
            color: ink,
            fontSize: 12,
            fontFamily: "Archivo Variable, sans-serif",
            formatter: (p: unknown) => (p as { data: { name: string } }).data.name,
          },
        },
      ],
    };
  }, [map]);

  return <Chart option={option} height={380} label="Animated map of how blocked invoices move from order to payment" />;
}
