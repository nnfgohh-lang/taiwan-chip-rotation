from __future__ import annotations

import numpy as np
import pandas as pd

from .data_pipeline import *


def enrich_structure(frame: pd.DataFrame) -> pd.DataFrame:
    """加入四層持股結構；四層互斥且合計約為 100%。"""
    result = frame.copy()
    result["retail_50"] = result[["under_1", "1_5", "5_10", "10_15", "15_20", "20_30", "30_40", "40_50"]].sum(axis=1, min_count=1)
    result["mid_50_400"] = result[["50_100", "100_200", "200_400"]].sum(axis=1, min_count=1)
    result["large_400_1000"] = result[["400_600", "600_800", "800_1000"]].sum(axis=1, min_count=1)
    result["super_1000"] = result["over_1000"]
    result["large_400"] = result["large_400_1000"] + result["super_1000"]
    return result


def combine_chip_sources(tej_frames: list[pd.DataFrame], tdcc_frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [*tej_frames, *tdcc_frames]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True).drop_duplicates(["date", "code"], keep="last")
    return enrich_structure(combined).sort_values(["date", "code"])


def build_stock_snapshot_average(chip: pd.DataFrame, xq: pd.DataFrame, current_date: pd.Timestamp, period: str):
    """以期間內所有過往週的平均值，和最新觀察週比較。"""
    current_date = pd.Timestamp(current_date)
    start_date = current_date - pd.Timedelta(days=PERIOD_DAYS[period])
    current = chip[chip["date"] == current_date].copy()
    history = chip[(chip["date"] < current_date) & (chip["date"] >= start_date)].copy()
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
    return merged, history["date"].min(), history["date"].max(), history["date"].nunique()
