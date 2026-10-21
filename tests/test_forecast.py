import numpy as np
import pandas as pd

from radar import forecast


def test_capture_counts_blocks_in_the_riskiest_share():
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 1])
    score = np.array([0.9, 0.8, 0.1, 0.2, 0.3, 0.1, 0.1, 0.1, 0.1, 0.05])
    result = forecast.capture(y, score, share=0.2)  # checks the 2 riskiest lines
    assert result == {"share_of_blocks_caught": round(1 / 3, 3), "precision": 0.5}


def test_past_rate_stays_near_average_without_history():
    frame = pd.DataFrame(
        {
            f"{who}_{kind}": [0, 100]
            for who in forecast.HISTORY
            for kind in ("known_before", "blocked_before")
        }
    )
    frame["vendor_blocked_before"] = [0, 90]
    rates = forecast.add_past_rates(frame, prior=0.25)
    assert rates.loc[0, "vendor_past_rate"] == 0.25
    assert abs(rates.loc[1, "vendor_past_rate"] - (90 + 2.5) / 110) < 1e-9


def test_unknown_categories_become_missing():
    booster = forecast.Booster(forecast.FACTS)
    booster.categories = {c: ["a"] for c in forecast.CATEGORICAL}
    later = pd.DataFrame({c: ["b"] for c in forecast.CATEGORICAL} | {c: [1.0] for c in forecast.FACTS})
    assert booster.matrix(later)["sub_spend_area"].isna().all()


def test_training_only_uses_lines_whose_window_had_closed():
    moment = pd.Timestamp("2018-06-01", tz="UTC")
    lines = pd.DataFrame(
        {"first_invoice_document_at": pd.to_datetime(["2018-03-01", "2018-04-10"], utc=True)}
    )
    kept = forecast.known_by(lines, moment)
    assert list(kept.index) == [0]  # 10 April + 60 days is after 1 June
