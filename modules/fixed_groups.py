from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis_v2 import *

PERIOD_WEEKS = {"前 1 週": 1, "前 1 月": 4, "前 1 季": 13, "前 1 年": 52}


def apply_fixed_groups(frame: pd.DataFrame) -> pd.DataFrame:
    """Expose fixed 50- retail and 400+ large-holder fields for the UI."""
    result = frame.copy()
    result["group_retail"] = result["retail_50"]
    result["group_large"] = result["large_400"]
    return result


def build_stock_snapshot_average(
    chip: pd.DataFrame,
    xq: pd.DataFrame,
    current_date: pd.Timestamp,
    period: str,
):
    current_date = pd.Timestamp(current_date)
    current = apply_fixed_groups(chip[chip["date"] == current_date])
    prior_dates = sorted(
        pd.to_datetime(chip.loc[chip["date"] < current_date, "date"].unique()),
        reverse=True,
    )
    selected_dates = prior_dates[:PERIOD_WEEKS[period]]
    history = apply_fixed_groups(chip[chip["date"].isin(selected_dates)])
    if history.empty:
        return current.merge(xq, on="code", how="left", suffixes=("", "_xq")), None, None, 0
    measures = ["group_retail", "group_large", "holders"]
    baseline = history.groupby("code", as_index=False)[measures].mean()
    baseline = baseline.rename(columns={column: f"avg_{column}" for column in measures})
    counts = history.groupby("code")["date"].nunique().rename("history_weeks").reset_index()
    merged = current.merge(baseline, on="code", how="left").merge(counts, on="code", how="left")
    merged = merged.merge(xq, on="code", how="left", suffixes=("", "_xq"))
    merged["analysis_change"] = merged["group_large"] - merged["avg_group_large"]
    merged["retail_decrease"] = merged["avg_group_retail"] - merged["group_retail"]
    merged["holders_decrease"] = merged["avg_holders"] - merged["holders"]
    merged["comparable"] = merged["avg_group_large"].notna()
    merged["history_weeks"] = merged["history_weeks"].fillna(0).astype(int)
    if "name_xq" in merged:
        merged["name"] = merged["name_xq"].fillna(merged.get("name", ""))
    merged["industry"] = merged["industry"].fillna("未分類")
    return merged, history["date"].min(), history["date"].max(), len(selected_dates)


def aggregate_industries(stocks: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    if stocks.empty:
        return pd.DataFrame()
    denominator = universe.groupby("industry")["code"].nunique().rename("universe_count")
    rows = []
    for industry, group in stocks.groupby("industry"):
        comparable = group[group["comparable"]]
        count = group["code"].nunique()
        universe_count = int(denominator.get(industry, count))
        coverage = count / universe_count if universe_count else 0
        rows.append({
            "industry": industry,
            "selected_count": count,
            "universe_count": universe_count,
            "coverage": coverage,
            "consensus": coverage * np.log1p(count),
            "analysis_change": comparable["analysis_change"].median(),
            "retail_decrease": comparable["retail_decrease"].median(),
            "increase_ratio": (comparable["analysis_change"] > 0).mean() if len(comparable) else np.nan,
            "comparable_count": len(comparable),
            "comparable_rate": len(comparable) / count if count else 0,
            "avg_revenue_yoy": group["revenue_yoy"].mean(),
            "total_volume": group["volume"].sum(min_count=1),
            "leaders": "、".join(comparable.nlargest(5, "analysis_change")["name"].fillna(comparable["code"]).astype(str)),
        })
    result = pd.DataFrame(rows).sort_values(["consensus", "analysis_change"], ascending=False, na_position="last")
    result["rank"] = np.arange(1, len(result) + 1)
    return result
