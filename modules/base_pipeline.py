from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import BinaryIO, Iterable

import numpy as np
import pandas as pd


BUCKETS = [
    "under_1", "1_5", "5_10", "10_15", "15_20", "20_30", "30_40",
    "40_50", "50_100", "100_200", "200_400", "400_600", "600_800",
    "800_1000", "over_1000",
]

TEJ_RATIO_PATTERNS = {
    "under_1": r"^1\s*張以下.*比率",
    "1_5": r"^1\s*-\s*5\s*張.*比率",
    "5_10": r"^5\s*-\s*10\s*張.*比率",
    "10_15": r"^10\s*-\s*15\s*張.*比率",
    "15_20": r"^15\s*-\s*20\s*張.*比率",
    "20_30": r"^20\s*-\s*30\s*張.*比率",
    "30_40": r"^30\s*-\s*40\s*張.*比率",
    "40_50": r"^40\s*-\s*50\s*張.*比率",
    "50_100": r"^50\s*-\s*100\s*張.*比率",
    "100_200": r"^100\s*-\s*200\s*張.*比率",
    "200_400": r"^200\s*-\s*400\s*張.*比率",
    "400_600": r"^400\s*-\s*600\s*張.*比率",
    "600_800": r"^600\s*-\s*800\s*張.*比率",
    "800_1000": r"^800\s*-\s*1000\s*張.*比率",
    "over_1000": r"^1000\s*張以上.*比率",
}


def clean_code(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("　", " ")
    text = re.sub(r"\.(TW|TWO)$", "", text, flags=re.I)
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text.zfill(4) if text.isdigit() and len(text) < 4 else text


def _read_bytes(source: str | Path | BinaryIO) -> bytes:
    if hasattr(source, "getvalue"):
        return source.getvalue()
    if hasattr(source, "read"):
        return source.read()
    return Path(source).read_bytes()


def read_csv_flexible(source: str | Path | BinaryIO, header_tokens: Iterable[str]) -> pd.DataFrame:
    raw = _read_bytes(source)
    last_error = None
    for encoding in ("utf-8-sig", "cp950", "big5", "utf-8"):
        try:
            text = raw.decode(encoding)
            rows = list(csv.reader(io.StringIO(text)))
            header_idx = 0
            for idx, row in enumerate(rows[:30]):
                joined = "|".join(str(cell).strip() for cell in row)
                if any(token in joined for token in header_tokens):
                    header_idx = idx
                    break
            return pd.read_csv(io.StringIO(text), skiprows=header_idx, dtype=str)
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            last_error = exc
    raise ValueError(f"無法讀取 CSV：{last_error}")


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False),
        errors="coerce",
    )


def _add_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    for bucket in BUCKETS:
        if bucket not in frame:
            frame[bucket] = np.nan
        frame[bucket] = _numeric(frame[bucket])
    # 散戶 50 張以下包含零股／1 張以下級距，與「50 張以下」的自然定義一致。
    frame["retail_50"] = frame[BUCKETS[:8]].sum(axis=1, min_count=1)
    frame["large_400"] = frame[BUCKETS[11:]].sum(axis=1, min_count=1)
    frame["super_1000"] = frame["over_1000"]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["code"] = frame["code"].map(clean_code)
    return frame.dropna(subset=["date"]).drop_duplicates(["date", "code"], keep="last")


def parse_tdcc(source: str | Path | BinaryIO) -> pd.DataFrame:
    raw = read_csv_flexible(source, ["資料日期", "持股分級"])
    required = {"資料日期", "證券代號", "持股分級", "人數", "股數", "占集保庫存數比例%"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"集保檔缺少欄位：{', '.join(sorted(missing))}")
    raw["持股分級"] = _numeric(raw["持股分級"])
    raw["比例"] = _numeric(raw["占集保庫存數比例%"])
    raw["人數值"] = _numeric(raw["人數"])
    raw["股數值"] = _numeric(raw["股數"])
    wide = raw.pivot_table(index=["資料日期", "證券代號"], columns="持股分級", values="比例", aggfunc="sum")
    wide = wide.rename(columns={i + 1: bucket for i, bucket in enumerate(BUCKETS)}).reset_index()
    wide = wide.rename(columns={"資料日期": "date", "證券代號": "code"})
    totals = raw.groupby(["資料日期", "證券代號"], as_index=False).agg(holders=("人數值", "sum"), shares=("股數值", "sum"))
    totals = totals.rename(columns={"資料日期": "date", "證券代號": "code"})
    wide = wide.merge(totals, on=["date", "code"], how="left")
    return _add_metrics(wide)


def parse_tej(source: str | Path | BinaryIO) -> pd.DataFrame:
    raw = pd.read_excel(source, engine="openpyxl")
    compact = {col: re.sub(r"\s+", "", str(col)) for col in raw.columns}
    ratio_columns = {}
    for bucket, pattern in TEJ_RATIO_PATTERNS.items():
        for original, normalized in compact.items():
            if re.search(pattern, normalized):
                ratio_columns[bucket] = original
                break
    missing = set(BUCKETS) - set(ratio_columns)
    if missing:
        raise ValueError(f"TEJ 檔缺少級距比率：{', '.join(sorted(missing))}")
    frame = pd.DataFrame({
        "code": raw["代號"].map(clean_code),
        "name": raw.get("名稱", ""),
        "date": raw["年月日"],
        "holders": _numeric(raw["集保總人數"]),
        "shares": _numeric(raw["集保總張數(千股)"]) * 1000,
    })
    for bucket, column in ratio_columns.items():
        frame[bucket] = _numeric(raw[column])
    return _add_metrics(frame)


def parse_xq(source: str | Path | BinaryIO) -> pd.DataFrame:
    raw = read_csv_flexible(source, ["代碼", "商品"])
    raw.columns = [str(col).strip().replace("\t", "") for col in raw.columns]
    aliases = {
        "code": ["代碼", "證券代號"], "name": ["商品", "商品名稱", "名稱"],
        "price": ["成交", "成交價", "股價", "收盤價"], "volume": ["總量", "成交量"],
        "revenue_yoy": ["月營收年增率", "月營收YoY", "月營收年增率%", "營收年增率"],
    }
    out = pd.DataFrame(index=raw.index)
    for key, choices in aliases.items():
        match = next((col for col in raw.columns if str(col).strip() in choices), None)
        out[key] = raw[match] if match else np.nan
    out["code"] = out["code"].map(clean_code)
    for col in ("price", "volume", "revenue_yoy"):
        out[col] = _numeric(out[col])
    known = {item for values in aliases.values() for item in values} | {"序號", "策略"}
    industry_cols = [col for col in raw.columns if col not in known and ("產業" in col or str(col).startswith("Unnamed"))]
    if "細產業" in raw.columns and "細產業" not in industry_cols:
        industry_cols.insert(0, "細產業")
    # XQ 匯出常把第二個以上的產業放進無欄名欄位；主族群取第一個非空標籤。
    if industry_cols:
        out["industry"] = raw[industry_cols].bfill(axis=1).iloc[:, 0]
        out["industry_tags"] = raw[industry_cols].fillna("").apply(
            lambda row: "、".join(dict.fromkeys(x.strip() for x in row.astype(str) if x.strip() and x.strip().lower() != "nan")), axis=1
        )
    else:
        out["industry"] = "未分類"
        out["industry_tags"] = ""
    out["industry"] = out["industry"].fillna("未分類").astype(str).str.strip().replace("", "未分類")
    return out.drop_duplicates("code", keep="first")


def combine_chip_sources(tej_frames: list[pd.DataFrame], tdcc_frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [*tej_frames, *tdcc_frames]
    if not frames:
        return pd.DataFrame()
    # 集保放在後方，因此同日期同股票時優先採用官方集保資料。
    return pd.concat(frames, ignore_index=True).drop_duplicates(["date", "code"], keep="last").sort_values(["date", "code"])


PERIOD_DAYS = {"前 1 週": 7, "前 1 月": 28, "前 1 季": 91, "前 1 年": 365}


def select_comparison_date(dates: pd.Series, current_date: pd.Timestamp, period: str) -> pd.Timestamp | None:
    target = current_date - pd.Timedelta(days=PERIOD_DAYS[period])
    candidates = pd.Series(pd.to_datetime(dates).unique()).dropna()
    candidates = candidates[candidates < current_date]
    if candidates.empty:
        return None
    return candidates.iloc[(candidates - target).abs().argmin()]


def build_stock_snapshot(chip: pd.DataFrame, xq: pd.DataFrame, current_date: pd.Timestamp, period: str):
    comparison_date = select_comparison_date(chip["date"], current_date, period)
    current = chip[chip["date"] == current_date].copy()
    if comparison_date is None:
        return current.merge(xq, on="code", how="left", suffixes=("", "_xq")), None
    previous = chip[chip["date"] == comparison_date][["code", "large_400", "retail_50", "super_1000", "holders"]].copy()
    previous = previous.rename(columns={col: f"prev_{col}" for col in previous.columns if col != "code"})
    merged = current.merge(previous, on="code", how="left").merge(xq, on="code", how="left", suffixes=("", "_xq"))
    merged["large_change"] = merged["large_400"] - merged["prev_large_400"]
    # 正值代表散戶持股下降，便於與大戶增持同方向解讀。
    merged["retail_decrease"] = merged["prev_retail_50"] - merged["retail_50"]
    merged["holders_decrease"] = merged["prev_holders"] - merged["holders"]
    merged["comparable"] = merged["prev_large_400"].notna()
    merged["name"] = merged.get("name_xq", merged.get("name", "")).fillna(merged.get("name", ""))
    merged["industry"] = merged["industry"].fillna("未分類")
    return merged, comparison_date


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
        increase_ratio = (comparable["large_change"] > 0).mean() if len(comparable) else np.nan
        consensus = coverage * np.log1p(count)
        rows.append({
            "industry": industry, "selected_count": count, "universe_count": universe_count,
            "coverage": coverage, "consensus": consensus,
            "large_change": comparable["large_change"].median(),
            "retail_decrease": comparable["retail_decrease"].median(),
            "increase_ratio": increase_ratio, "comparable_count": len(comparable),
            "comparable_rate": len(comparable) / count if count else 0,
            "avg_revenue_yoy": group["revenue_yoy"].mean(), "total_volume": group["volume"].sum(min_count=1),
            "leaders": "、".join(comparable.nlargest(5, "large_change")["name"].fillna(comparable["code"]).astype(str)),
        })
    result = pd.DataFrame(rows).sort_values(["consensus", "large_change"], ascending=False, na_position="last")
    result["rank"] = np.arange(1, len(result) + 1)
    return result
