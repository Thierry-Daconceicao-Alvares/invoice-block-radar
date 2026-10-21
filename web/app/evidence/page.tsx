import { CaptureCurves, Drivers } from "@/components/EvidenceCharts";
import type { Cause, Scores } from "@/lib/api";
import { CAUSES, fmt } from "@/lib/api";
import { evaluation } from "@/lib/data";

export const metadata = { title: "Evidence · Invoice Block Radar" };

function ScoreTable({ scores, keys, best }: { scores: Record<string, Scores>; keys: [string, string][]; best: string }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Method</th>
            {keys.map(([, label]) => (
              <th key={label} className="num">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(scores).map(([name, s]) => (
            <tr key={name} className={name === best ? "best" : ""}>
              <td>{name}</td>
              {keys.map(([key]) => (
                <td key={key} className="num">
                  {key === "roc_auc" || key === "pr_auc" ? s[key].toFixed(2) : fmt.pct(s[key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function EvidencePage() {
  const e = await evaluation();
  const model = e.forecast.test_scores["LightGBM model"];
  const kept = e.triage.test_scores["vendor + buyer history (used)"];
  const rejectedValid = e.triage.validation_scores["LightGBM model (rejected)"];
  const rejectedTest = e.triage.test_scores["LightGBM model (rejected)"];
  const causes: Cause[] = ["waiting_for_goods", "routine_check", "likely_mismatch"];

  return (
    <>
      <section className="head">
        <p className="eyebrow">Evidence</p>
        <h1>Every claim on this site, measured on months the models never saw.</h1>
        <p className="lead">
          Models learn from January to July 2018, are tuned on August, and are scored once on September and October.
          Each one is compared with what a team could do without it.
        </p>
      </section>

      <section className="panel">
        <div>
          <h2>1. The forecaster catches twice as many blocks as a random check</h2>
          <p className="sub">
            {fmt.int(e.forecast.lines.test)} order lines of September-October 2018, {fmt.pct(e.forecast.block_rate_test)}{" "}
            of them blocked. If the team checks the riskiest 20% of new lines, the model points to{" "}
            {fmt.pct(model.share_of_blocks_caught)} of the future blocks, and {fmt.pct(model.precision)} of the lines it
            flags really block.
          </p>
        </div>
        <div className="grid-2">
          <CaptureCurves
            curves={e.forecast_curves}
            xLabel="New order lines checked, riskiest first"
            yLabel="Future blocks caught"
            label="Share of future blocks caught by each method"
          />
          <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
            <ScoreTable
              scores={e.forecast.test_scores}
              best="LightGBM model"
              keys={[
                ["share_of_blocks_caught", "Caught in first 20%"],
                ["precision", "Precision"],
                ["roc_auc", "ROC AUC"],
              ]}
            />
            <p className="note">
              The gain over the vendor's own history is real but moderate. Part of a block depends on what the vendor
              will put on the invoice later, which nobody knows when the order is created.
            </p>
          </div>
        </div>
        <h3 className="mini">What the forecaster looks at (mean |SHAP| on the test months)</h3>
        <Drivers drivers={e.forecast.drivers_mean_abs_shap} />
      </section>

      <section className="panel">
        <div>
          <h2>2. Triage: a simple score kept, a model rejected</h2>
          <p className="sub">
            Among blocks raised after the goods arrived, which ones really need a correction? A LightGBM model looked
            excellent on August (ROC AUC {rejectedValid.roc_auc.toFixed(2)}) and fell to {rejectedTest.roc_auc.toFixed(2)}{" "}
            on September-October. The average of the vendor's and the buyer's past correction rates held at{" "}
            {kept.roc_auc.toFixed(2)}, so it is the one in use. The choice was made on August; on these months the
            vendor&apos;s history alone did slightly better at the 20% mark, and that is shown as it came out.
          </p>
        </div>
        <div className="grid-2">
          <CaptureCurves
            curves={e.triage_curves}
            xLabel="Blocked invoices opened, most suspicious first"
            yLabel="Real corrections found"
            label="Share of real corrections found by each triage order"
          />
          <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
            <ScoreTable
              scores={e.triage.test_scores}
              best="vendor + buyer history (used)"
              keys={[
                ["corrections_in_first_20pct", "Found in first 20%"],
                ["roc_auc", "ROC AUC"],
              ]}
            />
            <p className="note">
              Also left out on purpose: credit notes dated before the block. Their date is the one the vendor typed,
              not when the company received them, so they can carry information from after the block.
            </p>
          </div>
        </div>
      </section>

      <section className="panel">
        <div>
          <h2>3. The detective&apos;s reading against how {fmt.int(e.detective.blocks)} blocks really ended</h2>
          <p className="sub">Every block raised in September-October 2018.</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>The detective said</th>
                <th className="num">Blocks</th>
                <th className="num">Really waited for goods</th>
                <th className="num">Released, nothing corrected</th>
                <th className="num">Really needed a correction</th>
                <th className="num">Median days blocked</th>
              </tr>
            </thead>
            <tbody>
              {causes.map((c) => {
                const r = e.detective.by_predicted_cause[c];
                return (
                  <tr key={c}>
                    <td>
                      <span className={`pill ${CAUSES[c].tone}`}>{CAUSES[c].label}</span>
                    </td>
                    <td className="num">{fmt.int(r.blocks)}</td>
                    <td className="num">{fmt.pct(r.really_waited_for_goods)}</td>
                    <td className="num">{fmt.pct(r.released_with_no_correction)}</td>
                    <td className="num">{fmt.pct(r.really_needed_a_correction, 1)}</td>
                    <td className="num">{r.median_days_blocked}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="note">
          It recognises {fmt.pct(e.detective.goods_waits_recognised)} of the blocks that were only waiting for goods,
          and sends {fmt.pct(e.detective.corrections_sent_to_the_buyer)} of the real corrections to the buyer&apos;s pile.
        </p>
      </section>

      <section className="grid-2">
        <div className="panel">
          <h2>4. The writer never gets the last word</h2>
          <p>
            <span className="num" style={{ fontSize: 28 }}>
              {e.writer.passed_all_checks}/{e.writer.notes}
            </span>{" "}
            notes written by <span className="mono">{e.writer.model}</span> passed every check (median{" "}
            {e.writer.median_seconds} s per note).
          </p>
          <ul>
            {e.writer.checks.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <p className="note">
            The facts come from rules in code; the model only phrases them. Its answers were recorded by a GitHub
            workflow and are replayed here, so this site holds no API key.
          </p>
        </div>
        <div className="panel">
          <h2>5. How the data was kept honest</h2>
          <ul>
            <li>Row counts checked against the published log: 251,734 items, 1,595,923 events.</li>
            <li>Vendor-typed dates outside 2017-2019 (1948, 1993…) flagged and kept out of every duration.</li>
            <li>A block is read from its release: the log records 57,136 releases but only 124 block settings.</li>
            <li>History features count only invoices settled before the order was created, checked by a dbt test.</li>
            <li>Training, tuning and test periods never overlap, checked by a dbt test.</li>
            <li>A first payment-delay figure of two weeks shrank to 3 to 4 days once compared within the same vendor.</li>
          </ul>
        </div>
      </section>
    </>
  );
}
