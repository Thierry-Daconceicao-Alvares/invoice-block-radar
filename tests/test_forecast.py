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
            for kind in ("paid_before", "blocked_before")
        }
    )
    frame["vendor_blocked_before"] = [0, 90]
    rates = forecast.add_past_rates(frame, prior=0.25)
    assert rates.loc[0, "vendor_past_rate"] == 0.25
    assert abs(rates.loc[1, "vendor_past_rate"] - (90 + 2.5) / 110) < 1e-9


def test_unknown_categories_become_missing():
    train = pd.DataFrame({c: ["a"] for c in forecast.FEATURES})
    later = pd.DataFrame({c: ["b"] for c in forecast.FEATURES})
    for frame in (train, later):
        for column in forecast.NUMERIC:
            frame[column] = 1.0
    _, categories = forecast.prepare(train)
    x, _ = forecast.prepare(later, categories)
    assert x["sub_spend_area"].isna().all()
