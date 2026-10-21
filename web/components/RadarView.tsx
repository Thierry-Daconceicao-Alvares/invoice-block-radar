"use client";

import type { EChartsOption } from "echarts";
import { useCallback, useEffect, useState } from "react";

import Chart, { token } from "@/components/Chart";
import Waking from "@/components/Waking";
import { fetchJSON, isAbort } from "@/lib/client";
import type { ForecastOptions, ForecastResult } from "@/lib/api";
import { fmt } from "@/lib/api";

type Line = Record<string, string | number | boolean | null>;

const FIELDS = [
  "vendor", "company", "item_category", "item_type", "document_type", "spend_area", "sub_spend_area",
  "spend_classification", "gr_based_iv", "goods_receipt_expected", "created_by", "from_requisition",
  "lines_in_document", "po_value_eur", "created_weekday",
];

function pick(example: Line): Line {
  return Object.fromEntries(FIELDS.map((f) => [f, example[f] ?? null]));
}

export default function RadarView() {
  const [options, setOptions] = useState<ForecastOptions | null>(null);
  const [exampleId, setExampleId] = useState<string>("");
  const [line, setLine] = useState<Line | null>(null);
  const [result, setResult] = useState<ForecastResult | null>(null);
  const [edited, setEdited] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJSON<ForecastOptions>("/api/forecast/options")
      .then((o) => {
        setOptions(o);
        // open on a line that was blocked, so the first view shows the radar at work
        const first = o.examples.find((e) => e.was_blocked && Number(e.po_value_eur) > 5000) ?? o.examples[0];
        setExampleId(first.case_id);
        setLine(pick(first));
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  // Each edit cancels the previous request, so an older score never replaces a newer one.
  useEffect(() => {
    if (!line) return;
    const abort = new AbortController();
    const body = { ...line, created_weekday: Number(line.created_weekday ?? 0), example_id: exampleId };
    fetchJSON<ForecastResult>("/api/forecast", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: abort.signal,
    })
      .then((r) => {
        setResult(r);
        setError(null);
      })
      .catch((e: Error) => !isAbort(e) && setError(e.message));
    return () => abort.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [line]);

  const set = (field: string, value: string | number | boolean) => {
    setEdited(true);
    setLine((current) => ({ ...(current ?? {}), [field]: value }));
  };

  const example = options?.examples.find((e) => e.case_id === exampleId);
  if (error && !options) return <p className="callout">The API did not answer ({error}). Reload the page in a minute.</p>;
  if (!options || !line) return <Waking what="the order lines" />;

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
          <p className="sub">Start from a real line created in September or October 2018, then change it.</p>
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
            Vendor <span className="tag">moves the score</span>
            <input id="vendor" list="vendors" value={String(line.vendor ?? "")} onChange={(e) => set("vendor", e.target.value)} />
          </label>
          <label>
            Company <span className="tag">moves the score</span>
            {select("company", options.categories.company)}
          </label>
          <label>
            Match type <span className="tag">moves the score</span>
            {select("item_category", options.categories.item_category)}
          </label>
          <label>
            Buyer
            <input id="buyer" list="buyers" value={String(line.created_by ?? "")} onChange={(e) => set("created_by", e.target.value)} />
          </label>
          <label>
            What is bought
            {select("sub_spend_area", options.categories.sub_spend_area)}
          </label>
        </div>
        <p className="note">
          The score reads the history of the vendor for this company and match type. Buyer and what is bought are
          shown on the right for context; the value, the date and the size of the order did not help on earlier
          months, so they are not asked for.
        </p>
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
            <History result={result} />
            {example && !edited && (
              <p className={`outcome ${example.was_blocked ? "fixed" : ""}`}>
                <b>What really happened:</b> this line {example.was_blocked ? "was blocked" : "was paid without a block"}.
              </p>
            )}
          </>
        ) : error ? (
          <p className="callout">The API did not answer ({error}). Reload the page in a minute.</p>
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

function History({ result }: { result: ForecastResult }) {
  return (
    <div className="why">
      <h3 className="mini">Why: how earlier invoices went</h3>
      <p className="note">
        The score is the block rate of earlier invoices of {result.history[0].label}, whose outcome was known that day,
        pulled toward the average when there are few. The other rates are shown for context.
      </p>
      <ul className="rates">
        {result.history.map((h) => (
          <li key={h.who} className={h.used ? "used" : ""}>
            <span className="who">
              {h.label}
              {h.used && <span className="tag">used</span>}
            </span>
            <span className="bar" aria-hidden="true">
              <i style={{ width: `${Math.min(100, h.rate * 100)}%` }} />
              <b style={{ left: `${result.average_risk * 100}%` }} title="average" />
            </span>
            <span className="num">{fmt.pct(h.rate)}</span>
            <span className="note">
              {fmt.int(h.blocked_before)} of {fmt.int(h.known_before)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
