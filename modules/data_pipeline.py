"""公開資料介面；XQ 使用可容納不等欄數的專用解析器。"""
import csv
import io
from pathlib import Path
from typing import BinaryIO
import numpy as np
import pandas as pd
from .base_pipeline import *
from .base_pipeline import _numeric, _read_bytes


def parse_xq(source: str | Path | BinaryIO) -> pd.DataFrame:
    payload = _read_bytes(source)
    rows = None
    for encoding in ("utf-8-sig", "cp950", "big5", "utf-8"):
        try:
            rows = list(csv.reader(io.StringIO(payload.decode(encoding))))
            break
        except UnicodeDecodeError:
            continue
    if rows is None:
        raise ValueError("無法辨識 XQ CSV 編碼")
    header_idx = next((i for i, row in enumerate(rows[:30]) if "代碼" in row and ("商品" in row or "商品名稱" in row)), None)
    if header_idx is None:
        raise ValueError("找不到 XQ 的代碼／商品標題列")
    width = max(len(row) for row in rows[header_idx:])
    original_header = [str(x).strip() for x in rows[header_idx]]
    header = original_header + [f"Unnamed_{i}" for i in range(len(original_header), width)]
    body = [row + [""] * (width-len(row)) for row in rows[header_idx+1:] if any(str(x).strip() for x in row)]
    raw = pd.DataFrame(body, columns=header)
    aliases = {"code":["代碼","證券代號"],"name":["商品","商品名稱","名稱"],"price":["成交","成交價","股價","收盤價"],"volume":["總量","成交量"],"revenue_yoy":["月營收年增率","月營收YoY","月營收年增率%","營收年增率"]}
    out = pd.DataFrame(index=raw.index)
    for key, choices in aliases.items():
        match = next((c for c in raw.columns if str(c).strip() in choices), None)
        out[key] = raw[match] if match else np.nan
    out["code"] = out["code"].map(clean_code)
    for col in ("price","volume","revenue_yoy"): out[col] = _numeric(out[col])
    industry_cols = [c for c in raw.columns if "產業" in str(c) or str(c).startswith("Unnamed_")]
    if industry_cols:
        out["industry"] = raw[industry_cols].replace("",np.nan).bfill(axis=1).iloc[:,0]
        out["industry_tags"] = raw[industry_cols].fillna("").apply(lambda row:"、".join(dict.fromkeys(x.strip() for x in row.astype(str) if x.strip() and x.strip().lower()!="nan")),axis=1)
    else:
        out["industry"]="未分類"; out["industry_tags"]=""
    out["industry"] = out["industry"].fillna("未分類").astype(str).str.strip().replace("","未分類")
    return out.drop_duplicates("code",keep="first")
