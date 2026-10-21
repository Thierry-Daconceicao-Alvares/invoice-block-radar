import { CaptureCurves } from "@/components/EvidenceCharts";
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
  const f = e.forecast;
  const chosen = f.test.scores[f.chosen];
  const random = f.test.scores["random pick"];
  const months = Object.keys(f.rolling_check.months);
  const triageChosen = Object.keys(e.triage.test_scores).find((k) => k.includes("chosen on August"))!;
  const d = e.detective;
  const base = d.base_rates_goods_received;
  const causes: Cause[] = ["waiting_for_goods", "routine_check", "likely_mismatch"];

  return (
    <>
      <section className="head">
        <p className="eyebrow">Evidence</p>
        <h1>Every claim on this site, measured on months that were never used to choose.</h1>
        <p className="lead">
          Methods are chosen on earlier months only, learning just from outcomes a team would already have known,
          then scored once on September and October 2018. The outcome is “invoice blocked within 60 days”, and
          only lines invoiced at least 60 days before the log ends are scored, so no outcome is cut short.
        </p>
      </section>

      <section className="panel">
        <div>
          <h2>1. At order time, a simple history rate beats the machine-learning models</h2>
          <p className="sub">
            Five candidates were compared month by month from May to August, each month learning only from lines
            whose 60-day window had closed. The live block rate of the vendor (for the same company and match type)
            won every month. On {fmt.int(f.test.lines)} lines of September-October, {fmt.pct(f.test.block_rate)}{" "}
            of them blocked, checking the riskiest 20% catches {fmt.pct(chosen.share_of_blocks_caught)} of future
            blocks, against {fmt.pct(random.share_of_blocks_caught)} for a random check.
          </p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Blocks caught in the riskiest 20%</th>
                {months.map((m) => (
                  <th key={m} className="num">
                    {new Date(`${m}-01`).toLocaleString("en-GB", { month: "short" })}
                  </th>
                ))}
                <th className="num">Mean</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(f.rolling_check.mean_share_caught).map(([name, mean]) => (
                <tr key={name} className={name === f.chosen ? "best" : ""}>
                  <td>{name}</td>
                  {months.map((m) => (
                    <td key={m} className="num">
                      {fmt.pct(f.rolling_check.months[m].scores[name].share_of_blocks_caught)}
                    </td>
                  ))}
                  <td className="num">{fmt.pct(mean)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="grid-2">
          <CaptureCurves
            curves={e.forecast_curves}
            xLabel="New order lines checked, riskiest first"
            yLabel="Future blocks caught"
            label="Share of future blocks caught by each method, September-October 2018"
          />
          <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
            <h3 className="mini">September-October 2018, scored once</h3>
            <ScoreTable
              scores={f.test.scores}
              best={f.chosen}
              keys={[
                ["share_of_blocks_caught", "Caught in first 20%"],
                ["precision", "Precision"],
                ["roc_auc", "ROC AUC"],
              ]}
            />
            <p className="note">
              The LightGBM models learned patterns of the earlier months that did not carry over. A first version
              looked better (42% caught), until two flaws were fixed: its history counted some blocks before they
              were known, and it learned from recent lines whose outcome was not known yet. It is kept here as it
              came out.
            </p>
          </div>
        </div>
      </section>

      <section className="panel">
        <div>
          <h2>2. Triage of blocked invoices: chosen on August, confirmed on new months</h2>
          <p className="sub">
            Among blocks raised after the goods arrived ({fmt.pct(e.triage.correction_rate_test)} of them really
            needed a correction in September-October), which should be opened first? Three scores were compared on
            August, on the share of real corrections found in the first 20% of the pile. The average of the
            vendor&apos;s and the buyer&apos;s past correction rates won narrowly; LightGBM was close. On
            September-October the chosen score finds{" "}
            {fmt.pct(e.triage.test_scores[triageChosen].corrections_in_first_20pct)} of the corrections in the first
            20%; the vendor&apos;s history alone did a little better there, shown as it came out.
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
            <h3 className="mini">August (used to choose)</h3>
            <ScoreTable
              scores={e.triage.validation_scores}
              best={triageChosen}
              keys={[
                ["corrections_in_first_20pct", "Found in first 20%"],
                ["roc_auc", "ROC AUC"],
              ]}
            />
            <h3 className="mini">September-October (scored once)</h3>
            <ScoreTable
              scores={e.triage.test_scores}
              best={triageChosen}
              keys={[
                ["corrections_in_first_20pct", "Found in first 20%"],
                ["roc_auc", "ROC AUC"],
              ]}
            />
            <p className="note">
              Left out on purpose: credit notes dated before the block. Their date is the one the vendor typed, not
              when the company received them, so they can carry information from after the block.
            </p>
          </div>
        </div>
      </section>

      <section className="panel">
        <div>
          <h2>3. The detective&apos;s reading, against the base rates</h2>
          <p className="sub">
            Every block raised in September-October 2018 ({fmt.int(d.blocks)}). Of the {fmt.int(base.blocks)} blocks
            raised after the goods arrived, {fmt.pct(base.needed_a_correction, 1)} needed a correction and{" "}
            {fmt.pct(base.released_with_no_correction)} were released with nothing corrected: those are the rates to
            beat.
          </p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>The detective said</th>
                <th className="num">Blocks</th>
                <th className="num">Released, nothing corrected</th>
                <th className="num">Really needed a correction</th>
                <th className="num">Median days blocked</th>
              </tr>
            </thead>
            <tbody>
              {causes.map((c) => {
                const r = d.by_predicted_cause[c];
                return (
                  <tr key={c}>
                    <td>
                      <span className={`pill ${CAUSES[c].tone}`}>{CAUSES[c].label}</span>
                    </td>
                    <td className="num">{fmt.int(r.blocks)}</td>
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
          The buyer&apos;s pile is {fmt.pct(d.buyer_pile_share_of_goods_received_blocks)} of the blocks raised after
          the goods arrived and holds {fmt.pct(d.corrections_sent_to_the_buyer)} of the real corrections,{" "}
          {d.buyer_pile_concentration}× their share. Most of its blocks still end with nothing corrected, which is
          why the vendor email is a draft for the buyer to send only once the check confirms a mismatch. “Waiting
          for goods” is read from the missing goods receipt, the same fact it is checked against, so it is right
          by construction and says little about skill.
        </p>
      </section>

      <section className="grid-2">
        <div className="panel">
          <h2>4. The writer never gets the last word</h2>
          <p>
            <span className="num" style={{ fontSize: 28 }}>
              {e.writer.passed_all_checks}/{e.writer.notes}
            </span>{" "}
            notes written by <span className="mono">{e.writer.model}</span> passed every check in code (median{" "}
            {e.writer.median_seconds} s per note).
          </p>
          <ul>
            {e.writer.checks.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <p className="note">
            These are rules on content and format, with tests that try to get past them; they keep a note inside
            the facts, they do not prove the wording is good. The facts come from rules in code; the model only
            phrases them. Answers were recorded by a GitHub workflow and are replayed here, so this site holds no
            API key.
          </p>
        </div>
        <div className="panel">
          <h2>5. How the data was kept honest</h2>
          <ul>
            <li>Row counts checked against the published log: 251,734 items, 1,595,923 events.</li>
            <li>Vendor-typed dates outside 2017-2019 (1948, 1993…) flagged and kept out of every duration.</li>
            <li>A block is read from its release: the log records 57,136 releases but only 124 block settings.</li>
            <li>History features count an outcome only from the moment it was known; a dbt test recounts them.</li>
            <li>Training, tuning and test periods never overlap, also checked by a dbt test.</li>
            <li>
              Blocked invoices looked paid two weeks later than others; compared within the same vendor the gap is 3
              to 4 days (the rest comes from payment terms).
            </li>
            <li>Every run gives the same numbers: rows are read in a fixed order and the models are seeded.</li>
            <li>The dbt tests run on the full log locally; the CI runs the Python tests and builds the interface.</li>
          </ul>
        </div>
      </section>
    </>
  );
}
