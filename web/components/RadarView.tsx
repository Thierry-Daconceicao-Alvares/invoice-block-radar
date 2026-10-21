"use client";

import type { EChartsOption } from "echarts";
import { useCallback, useEffect, useState } from "react";

import Chart, { token } from "@/components/Chart";
import type { ForecastOptions, ForecastResult } from "@/lib/api";
import { fmt } from "@/lib/api";

type Line = Record<string, string | number | boolean | null>;

const FIELDS = [
  "vendor", "company", "item_category", "item_type", "document_type", "spend_area", "sub_spend_area",
  "spend_classification", "gr_based_iv", "goods_receipt_expected", "created_by", "from_requisition",
  "lines_in_document", "po_value_eur", "created_weekday",
];
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const HISTORY_LABELS: Record<string, string> = {
  vendor: "This vendor",
  buyer: "This buyer",
  area: "This spend area",
  pair: "This vendor, company and match type",
};

function pick(example: Line): Line {
  return Object.fromEntries(FIELDS.map((f) => [f, example[f] ?? null]));
}

export default function RadarView() {
  const [options, setOptions] = useState<ForecastOptions | null>(null);
  const [exampleId, setExampleId] = useState<string>("");
  const [line, setLine] = useState<Line | null>(null);
  const [result, setResult] = useState<ForecastResult | null>(null);
  const [edited, setEdited] = useState(false);

  useEffect(() => {
    fetch("/api/forecast/options")
      .then((r) => r.json())
      .then((o: ForecastOptions) => {
        setOptions(o);
        // open on a line that was blocked, so the first view shows the radar at work
        const first = o.examples.find((e) => e.was_blocked && Number(e.po_value_eur) > 5000) ?? o.examples[0];
        setExampleId(first.case_id);
        setLine(pick(first));
      });
  }, []);

  useEffect(() => {
    if (!line) return;
    const body = { ...line, created_weekday: Number(line.created_weekday ?? 0), example_id: exampleId };
    fetch("/api/forecast", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
      .then((r) => r.json())
      .then(setResult);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [line]);

  const set = (field: string, value: string | number | boolean) => {
    setEdited(true);
    setLine((current) => ({ ...(current ?? {}), [field]: value }));
  };

  const example = options?.examples.find((e) => e.case_id === exampleId);
  if (!options || !line) return <div className="panel">Loading the order lines…</div>;

  const select = (field: string, values: string[]) => (
    <select value={String(line[field] ?? "")} onChange={(e) => set(field, e.target.value)}>
      {values.map((v) => (
        <option key={v} value={v}>
          {v}
        </option>
      ))}
    </select>
  );

  return (
    <div className="radar">
      <form className="panel" onSubmit={(e) => e.preventDefault()}>
        <div>
          <h2>The order line</h2>
          <p className="sub">Start from a real line created in September or October 2018, then change anything.</p>
        </div>
        <label>
          Real order line
          <select
            id="example"
            value={exampleId}
            onChange={(e) => {
              const chosen = options.examples.find((x) => x.case_id === e.target.value)!;
              setExampleId(chosen.case_id);
              setLine(pick(chosen));
              setEdited(false);
            }}
          >
            {options.examples.map((e) => (
              <option key={e.case_id} value={e.case_id}>
                {e.case_id} · {String(e.vendor)} · {fmt.eur(Number(e.po_value_eur))}
              </option>
            ))}
          </select>
        </label>
        <div className="form-grid">
          <label>
            Vendor
            <input id="vendor" list="vendors" value={String(line.vendor ?? "")} onChange={(e) => set("vendor", e.target.value)} />
          </label>
          <label>
            Buyer
            <input id="buyer" list="buyers" value={String(line.created_by ?? "")} onChange={(e) => set("created_by", e.target.value)} />
          </label>
          <label>
            What is bought
            {select("sub_spend_area", options.categories.sub_spend_area)}
          </label>
          <label>
            Spend area
            {select("spend_area", options.categories.spend_area)}
          </label>
          <label>
            Match type
            {select("item_category", options.categories.item_category)}
          </label>
          <label>
            Company
            {select("company", options.categories.company)}
          </label>
          <label>
            Line value (EUR)
            <input id="value" type="number" min={0} value={Number(line.po_value_eur ?? 0)} onChange={(e) => set("po_value_eur", Number(e.target.value))} />
          </label>
          <label>
            Lines in the purchase order
            <input id="lines" type="number" min={1} value={Number(line.lines_in_document ?? 1)} onChange={(e) => set("lines_in_document", Number(e.target.value))} />
          </label>
          <label>
            Created on a
            <select value={Number(line.created_weekday ?? 0)} onChange={(e) => set("created_weekday", Number(e.target.value))}>
              {DAYS.map((d, i) => (
                <option key={d} value={(i + 1) % 7}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          <label className="toggle">
            <input type="checkbox" checked={Boolean(line.from_requisition)} onChange={(e) => set("from_requisition", e.target.checked)} />
            Came from a purchase requisition
          </label>
        </div>
        <datalist id="vendors">
          {options.vendors.slice(0, 2500).map((v) => (
            <option key={v} value={v} />
          ))}
        </datalist>
        <datalist id="buyers">
          {options.buyers.map((v) => (
            <option key={v} value={v} />
          ))}
        </datalist>
      </form>

      <section className="panel result" aria-live="polite">
        {result ? (
          <>
            <div>
              <h2>Risk that this line hits a payment block</h2>
              <p className="sub">
                Scored with what the company knew on{" "}
                {new Date(result.history_as_of).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}.
              </p>
            </div>
            <Gauge result={result} />
            <p className={`verdict ${result.band}`}>
              {result.band === "high"
                ? "Check this line now: confirm price, quantity and delivery with the vendor before the invoice comes."
                : result.band === "medium"
                  ? "Above the usual risk. Worth a look if the team has time."
                  : "Below the usual risk. Let it run."}
            </p>
            <Reasons result={result} />
            <div className="history">
              {Object.entries(result.history).map(([who, h]) => (
                <div key={who}>
                  <span className="note">{HISTORY_LABELS[who]}</span>
                  <span>
                    <span className="num">{fmt.int(h.blocked_before)}</span> blocked of{" "}
                    <span className="num">{fmt.int(h.paid_before)}</span> paid
                  </span>
                </div>
              ))}
            </div>
            {example && !edited && (
              <p className={`outcome ${example.was_blocked ? "fixed" : ""}`}>
                <b>What really happened:</b> this line {example.was_blocked ? "was blocked" : "was paid without a block"}.
              </p>
            )}
          </>
        ) : (
          <p>Scoring…</p>
        )}
      </section>
    </div>
  );
}

function Gauge({ result }: { result: ForecastResult }) {
  const option = useCallback((): EChartsOption => {
    const color = result.band === "high" ? token("--fix") : result.band === "medium" ? token("--hold") : token("--ok");
    return {
      series: [
        {
          type: "gauge",
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: 100,
          radius: "100%",
          center: ["50%", "58%"],
          progress: { show: true, width: 16, itemStyle: { color } },
          axisLine: { lineStyle: { width: 16, color: [[1, token("--surface-2")]] } },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false },
          pointer: { show: false },
          anchor: { show: false },
          title: {
            offsetCenter: [0, "62%"],
            color: token("--muted"),
            fontSize: 13,
            fontFamily: "Archivo Variable, sans-serif",
          },
          detail: {
            offsetCenter: [0, "-2%"],
            formatter: "{value}%",
            color: token("--ink"),
            fontSize: 40,
            fontFamily: "IBM Plex Mono, monospace",
          },
          data: [
            {
              value: Math.round(result.risk * 100),
              name: `${result.times_average}× the average line (${fmt.pct(result.average_risk)})`,
            },
          ],
        },
      ],
    };
  }, [result]);
  return <Chart option={option} height={230} label={`Risk ${Math.round(result.risk * 100)} percent`} />;
}

function Reasons({ result }: { result: ForecastResult }) {
  const option = useCallback((): EChartsOption => {
    const rows = [...result.reasons].reverse();
    return {
      textStyle: { fontFamily: "Archivo Variable, sans-serif" },
      grid: { left: 280, right: 50, top: 6, bottom: 6 },
      xAxis: { type: "value", show: false },
      yAxis: {
        type: "category",
        data: rows.map((r) => r.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: token("--ink"), fontSize: 12, width: 270, overflow: "truncate" },
      },
      series: [
        {
          type: "bar",
          barWidth: 14,
          data: rows.map((r) => ({
            value: r.effect,
            itemStyle: {
              color: r.effect > 0 ? token("--fix") : token("--ok"),
              borderRadius: r.effect > 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
            },
          })),
          label: {
            show: true,
            position: "right",
            color: token("--muted"),
            fontSize: 11,
            formatter: (p: unknown) => ((p as { value: number }).value > 0 ? "raises" : "lowers"),
          },
        },
      ],
    };
  }, [result]);
  return (
    <div>
      <h3 className="mini">Why: the five biggest effects (SHAP)</h3>
      <Chart option={option} height={180} label="The five inputs that move this line's risk the most" />
    </div>
  );
}
