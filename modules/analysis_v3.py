from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis_v2 import *

PERIOD_WEEKS = {"前 1 週": 1, "前 1 月": 4, "前 1 季": 13, "前 1 年": 52}
BUCKET_LIMITS = [1, 5, 10, 15, 20, 30, 40, 50, 100, 200, 400, 600, 800, 1000]
BUCKET_COLUMNS = ["under_1", "1_5", "5_10", "10_15", "15_20", "20_30", "30_40", "40_50", "50_100", "100_200", "200_400", "400_600", "600_800", "800_1000", "over_1000"]
GROUP_KEYS = ["retail", "mid", "large", "super"]
GROUP_NAMES = {"retail": "散戶", "mid": "中實戶", "large": "大戶", "super": "超級大戶"}


def group_labels(thresholds: tuple[int, int, int]) -> dict[str, str]:
    retail, mid, large = thresholds
    return {"retail": f"散戶（{retail} 張以下）", "mid": f"中實戶（{retail}–{mid} 張）", "large": f"大戶（{mid}–{large} 張）", "super": f"超級大戶（{large} 張以上）"}


def apply_custom_groups(frame: pd.DataFrame, thresholds: tuple[int, int, int]) -> pd.DataFrame:
    retail, mid, large = thresholds
    if not (retail < mid < large):
        raise ValueError("持股門檻必須依序遞增：散戶 < 中實戶 < 大戶。")
    if any(value not in BUCKET_LIMITS for value in thresholds):
        raise ValueError("持股門檻必須使用集保資料提供的級距邊界。")
    cuts = [BUCKET_LIMITS.index(value) + 1 for value in thresholds]
    ranges = [BUCKET_COLUMNS[:cuts[0]], BUCKET_COLUMNS[cuts[0]:cuts[1]], BUCKET_COLUMNS[cuts[1]:cuts[2]], BUCKET_COLUMNS[cuts[2]:]]
    result = frame.copy()
    for key, columns in zip(GROUP_KEYS, ranges):
        result[f"group_{key}"] = result[columns].sum(axis=1, min_count=1)
    return result


def build_stock_snapshot_average(chip: pd.DataFrame, xq: pd.DataFrame, current_date: pd.Timestamp, period: str, thresholds: tuple[int, int, int] = (50, 400, 1000), analysis_group: str = "large"):
    if analysis_group not in GROUP_KEYS:
        raise ValueError("未知的主要分析群組。")
    regrouped = apply_custom_groups(chip, thresholds)
    current_date = pd.Timestamp(current_date)
    current = regrouped[regrouped["date"] == current_date].copy()
    prior_dates = sorted(pd.to_datetime(regrouped.loc[regrouped["date"] < current_date, "date"].unique()), reverse=True)
    selected_dates = prior_dates[:PERIOD_WEEKS[period]]
    history = regrouped[regrouped["date"].isin(selected_dates)].copy()
    if history.empty:
        return current.merge(xq, on="code", how="left", suffixes=("", "_xq")), None, None, 0, regrouped
    measures = [*(f"group_{key}" for key in GROUP_KEYS), "holders"]
    baseline = history.groupby("code", as_index=False)[measures].mean().rename(columns={column: f"avg_{column}" for column in measures})
    counts = history.groupby("code")["date"].nunique().rename("history_weeks").reset_index()
    merged = current.merge(baseline, on="code", how="left").merge(counts, on="code", how="left").merge(xq, on="code", how="left", suffixes=("", "_xq"))
    selected = f"group_{analysis_group}"
    merged["analysis_change"] = merged[selected] - merged[f"avg_{selected}"]
    merged["retail_decrease"] = merged["avg_group_retail"] - merged["group_retail"]
    merged["concentration_score"] = merged["analysis_change"] + merged["retail_decrease"]
    merged["holders_decrease"] = merged["avg_holders"] - merged["holders"]
    merged["comparable"] = merged[f"avg_{selected}"].notna()
    merged["history_weeks"] = merged["history_weeks"].fillna(0).astype(int)
    if "name_xq" in merged:
        merged["name"] = merged["name_xq"].fillna(merged.get("name", ""))
    merged["industry"] = merged["industry"].fillna("未分類")
    return merged, history["date"].min(), history["date"].max(), len(selected_dates), regrouped


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
        rows.append({"industry": industry, "selected_count": count, "universe_count": universe_count, "coverage": coverage, "consensus": coverage * np.log1p(count), "analysis_change": comparable["analysis_change"].median(), "retail_decrease": comparable["retail_decrease"].median(), "increase_ratio": (comparable["analysis_change"] > 0).mean() if len(comparable) else np.nan, "comparable_count": len(comparable), "comparable_rate": len(comparable) / count if count else 0, "avg_revenue_yoy": group["revenue_yoy"].mean(), "total_volume": group["volume"].sum(min_count=1), "leaders": "、".join(comparable.nlargest(5, "analysis_change")["name"].fillna(comparable["code"]).astype(str))})
    result = pd.DataFrame(rows).sort_values(["consensus", "analysis_change"], ascending=False, na_position="last")
    result["rank"] = np.arange(1, len(result) + 1)
    return result
