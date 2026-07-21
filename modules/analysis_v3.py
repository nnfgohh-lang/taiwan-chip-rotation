from __future__ import annotations

import pandas as pd

from .analysis_v2 import *


PERIOD_WEEKS = {"前 1 週": 1, "前 1 月": 4, "前 1 季": 13, "前 1 年": 52}


def build_stock_snapshot_average(chip: pd.DataFrame, xq: pd.DataFrame, current_date: pd.Timestamp, period: str):
    """取觀察日前最近 N 個資料週，計算逐股歷史平均。"""
    current_date = pd.Timestamp(current_date)
    current = chip[chip["date"] == current_date].copy()
    prior_dates = sorted(pd.to_datetime(chip.loc[chip["date"] < current_date, "date"].unique()), reverse=True)
    selected_dates = prior_dates[:PERIOD_WEEKS[period]]
    history = chip[chip["date"].isin(selected_dates)].copy()
    if history.empty:
        return current.merge(xq, on="code", how="left", suffixes=("", "_xq")), None, None, 0
    measures = ["large_400", "retail_50", "mid_50_400", "large_400_1000", "super_1000", "holders"]
    baseline = history.groupby("code", as_index=False)[measures].mean()
    baseline = baseline.rename(columns={col: f"avg_{col}" for col in measures})
    counts = history.groupby("code")["date"].nunique().rename("history_weeks").reset_index()
    merged = current.merge(baseline, on="code", how="left").merge(counts, on="code", how="left")
    merged = merged.merge(xq, on="code", how="left", suffixes=("", "_xq"))
    merged["large_change"] = merged["large_400"] - merged["avg_large_400"]
    merged["retail_decrease"] = merged["avg_retail_50"] - merged["retail_50"]
    merged["holders_decrease"] = merged["avg_holders"] - merged["holders"]
    merged["comparable"] = merged["avg_large_400"].notna()
    merged["history_weeks"] = merged["history_weeks"].fillna(0).astype(int)
    if "name_xq" in merged:
        merged["name"] = merged["name_xq"].fillna(merged.get("name", ""))
    merged["industry"] = merged["industry"].fillna("未分類")
    return merged, history["date"].min(), history["date"].max(), len(selected_dates)
