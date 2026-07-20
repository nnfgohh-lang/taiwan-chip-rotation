from pathlib import Path
import hmac

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.custom_groups import (
    BUCKET_LIMITS, GROUP_KEYS, GROUP_NAMES, PERIOD_WEEKS, aggregate_industries,
    build_stock_snapshot_average, combine_chip_sources, group_labels, parse_tdcc,
    parse_tej, parse_xq,
)

DATA = Path(__file__).parent / "data"
st.set_page_config(page_title="台股籌碼動能雷達", page_icon=":material/radar:", layout="wide")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#050A14;color:#EAF4FF}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#07162B,#080C17);border-right:1px solid #168BFF55}
.block-container{padding-top:1.3rem;max-width:1500px}.hero{padding:20px 24px;border:1px solid #168BFF88;border-radius:16px;background:linear-gradient(110deg,#0a2445,#101830 65%,#421022)}
.note{padding:12px 16px;border-left:3px solid #168BFF;background:#168BFF16;border-radius:7px;color:#C9DCF2}
</style>""", unsafe_allow_html=True)


def require_password():
    if st.session_state.get("authenticated"):
        return
    st.title("台股籌碼動能雷達")
    st.caption("此網站受密碼保護")
    with st.form("login"):
        password = st.text_input("密碼", type="password")
        submitted = st.form_submit_button("登入", type="primary", width="stretch")
    if submitted:
        if hmac.compare_digest(password, "zhuyi"):
            st.session_state.authenticated = True
            st.rerun()
        st.error("密碼錯誤，請重新輸入。")
    st.stop()


require_password()


@st.cache_data(show_spinner=False, ttl=300)
def local_data(signature):
    tej = [parse_tej(path) for path in sorted((DATA / "tej").glob("*.xlsx"))]
    tdcc = [parse_tdcc(path) for path in sorted((DATA / "tdcc").glob("*.csv"))]
    xq_files = sorted((DATA / "xq").glob("*.csv"))
    return combine_chip_sources(tej, tdcc), parse_xq(xq_files[-1]) if xq_files else pd.DataFrame()


def data_signature():
    files = [path for folder in ("tej", "tdcc", "xq") for path in (DATA / folder).glob("*") if path.is_file()]
    return tuple((path.name, path.stat().st_size, path.stat().st_mtime_ns) for path in sorted(files))


def equal_range(series, center):
    values = series.replace([np.inf, -np.inf], np.nan).dropna()
    span = max(abs(values.min() - center), abs(values.max() - center), .05) if len(values) else 1
    return [center - span * 1.12, center + span * 1.12]


def bubble_chart(groups, selected_label, retail_label):
    chart = groups.dropna(subset=["analysis_change", "consensus"]).copy()
    chart["coverage_text"] = (chart.coverage * 100).map(lambda value: f"{value:.2f}%")
    fig = px.scatter(
        chart, x="analysis_change", y="consensus", size="selected_count", color="retail_decrease",
        text="industry", size_max=62, color_continuous_scale=[[0, "#168BFF"], [.5, "#6E68D9"], [1, "#FF7A2F"]],
        custom_data=["industry", "rank", "selected_count", "universe_count", "coverage_text", "retail_decrease", "avg_revenue_yoy", "leaders"],
    )
    fig.update_traces(textposition="top center", hovertemplate=(
        "<b>%{customdata[0]}</b>｜第 %{customdata[1]} 名<br>" + selected_label + "相對期間平均：%{x:,.2f} ppts<br>"
        "共識分數：%{y:,.2f}<br>入選／母體：%{customdata[2]:,} / %{customdata[3]:,}<br>覆蓋率：%{customdata[4]}<br>"
        + retail_label + "相對平均減少：%{customdata[5]:,.2f} ppts<br>平均營收 YoY：%{customdata[6]:,.2f}%<br>增持前五：%{customdata[7]}<extra></extra>"
    ))
    center_y = float(chart.consensus.median())
    range_x, range_y = equal_range(chart.analysis_change, 0), equal_range(chart.consensus, center_y)
    fig.add_vline(x=0, line_dash="dot", line_color="#7087a7")
    fig.add_hline(y=center_y, line_dash="dot", line_color="#7087a7")
    fig.update_layout(height=620, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#091426", font_color="#dbe9f6", xaxis=dict(title=f"{selected_label}－期間平均（ppts）", range=range_x), yaxis=dict(title="族群共識分數", range=range_y), coloraxis_colorbar=dict(title="散戶減少（ppts）"), clickmode="event+select")
    return fig


st.markdown('<div class="hero"><small>OWNERSHIP FLOW INTELLIGENCE</small><br><h1>台股籌碼動能雷達</h1>自訂持股分群，追蹤產業籌碼流向</div>', unsafe_allow_html=True)
with st.sidebar:
    header_col, logout_col = st.columns([3, 1])
    header_col.header("分析設定")
    if logout_col.button("登出"):
        st.session_state.authenticated = False
        st.rerun()
    mode = st.radio("資料來源", ["使用專案內建資料", "手動上傳資料"])
    if mode == "手動上傳資料":
        tej_files = st.file_uploader("TEJ Excel（可多選）", type="xlsx", accept_multiple_files=True)
        tdcc_files = st.file_uploader("集保股權分散表 CSV（可多選）", type="csv", accept_multiple_files=True)
        xq_file = st.file_uploader("XQ 選股結果 CSV", type="csv")
        if (not tej_files and not tdcc_files) or xq_file is None:
            st.info("請上傳至少一份籌碼資料與一份 XQ 檔案。")
            st.stop()
        try:
            chip = combine_chip_sources([parse_tej(f) for f in tej_files], [parse_tdcc(f) for f in tdcc_files])
            xq = parse_xq(xq_file)
        except Exception as exc:
            st.error(f"讀取資料失敗：{exc}")
            st.stop()
    else:
        try:
            chip, xq = local_data(data_signature())
        except Exception as exc:
            st.error(f"讀取資料失敗：{exc}")
            st.stop()

    st.divider()
    st.subheader("持股分級設定")
    retail_limit = st.selectbox("散戶上限（張）", BUCKET_LIMITS, index=BUCKET_LIMITS.index(50))
    mid_limit = st.selectbox("中實戶上限（張）", BUCKET_LIMITS, index=BUCKET_LIMITS.index(400))
    large_limit = st.selectbox("大戶上限（張）", BUCKET_LIMITS, index=BUCKET_LIMITS.index(1000))
    thresholds = (retail_limit, mid_limit, large_limit)
    if not (retail_limit < mid_limit < large_limit):
        st.error("門檻順序錯誤：散戶上限必須小於中實戶上限，中實戶上限必須小於大戶上限。")
        st.stop()
    labels = group_labels(thresholds)
    st.caption("；".join(labels.values()))
    analysis_group = st.radio("主要分析群組", GROUP_KEYS, index=2, format_func=lambda key: GROUP_NAMES[key])
    st.caption("門檻依集保公開資料的原始級距提供，確保重算結果準確。")

    dates = sorted(pd.to_datetime(chip.date.unique()), reverse=True)
    current = st.selectbox("觀察日期", dates, format_func=lambda date: pd.Timestamp(date).strftime("%Y-%m-%d"))
    period = st.selectbox("平均比較期間", list(PERIOD_WEEKS))
    st.divider()
    min_price = st.number_input("最低股價（元）", 0., value=30., step=5.)
    min_volume = st.number_input("最低成交量（張）", 0, value=300, step=100)
    min_revenue = st.number_input("最低月營收 YoY（%）", value=0., step=5.)
    min_group = st.number_input("族群最低入選家數", 1, value=3)
    aligned = st.toggle("只看主要群組增加且散戶減少", True)

stocks, start, end, weeks, regrouped_chip = build_stock_snapshot_average(chip, xq, pd.Timestamp(current), period, thresholds, analysis_group)
if start is None:
    st.error(f"觀察日前沒有足夠資料可計算「{period}」平均。")
    st.stop()
universe = xq[(xq.price.fillna(-np.inf) >= min_price) & (xq.volume.fillna(-np.inf) >= min_volume)]
stocks = stocks[(stocks.price.fillna(-np.inf) >= min_price) & (stocks.volume.fillna(-np.inf) >= min_volume) & (stocks.revenue_yoy.isna() | (stocks.revenue_yoy >= min_revenue))]
if aligned:
    stocks = stocks[(stocks.analysis_change > 0) & (stocks.retail_decrease > 0)]
groups = aggregate_industries(stocks, universe)
if groups.empty:
    st.warning("目前條件沒有符合的產業族群，請放寬篩選條件。")
    st.stop()
groups = groups[groups.selected_count >= min_group]
if groups.empty:
    st.warning("沒有族群達到最低入選家數。")
    st.stop()

selected_label, retail_label = labels[analysis_group], labels["retail"]
period_text = f"{pd.Timestamp(start):%Y-%m-%d}～{pd.Timestamp(end):%Y-%m-%d}（{weeks} 週）"
metrics = [("觀察日期", pd.Timestamp(current).strftime("%Y-%m-%d")), ("平均比較期間", period_text), ("入選股票", f"{stocks.code.nunique():,} 檔"), ("入選族群", f"{len(groups):,} 個"), (f"{GROUP_NAMES[analysis_group]}相對平均差", f"{stocks.analysis_change.median():+,.2f} ppts")]
for column, (label, value) in zip(st.columns(5), metrics):
    column.metric(label, value)

st.subheader("產業族群互動泡泡圖")
st.markdown(f'<div class="note">X＝{selected_label}相對期間平均變化；Y＝覆蓋率 × ln(1＋入選家數)；大小＝入選家數；顏色＝{retail_label}減少幅度。點擊泡泡可切換個股明細。</div>', unsafe_allow_html=True)
event = st.plotly_chart(bubble_chart(groups, selected_label, retail_label), width="stretch", on_select="rerun", selection_mode="points", key="rotation")
industries = groups.industry.tolist()
if "selected_industry" not in st.session_state or st.session_state.selected_industry not in industries:
    st.session_state.selected_industry = industries[0]
try:
    if event.selection.points:
        st.session_state.selected_industry = event.selection.points[0]["customdata"][0]
except (AttributeError, KeyError, IndexError, TypeError):
    pass

ranking = pd.DataFrame({
    "排名": groups["rank"].map(lambda value: f"{value:,.0f}"), "次產業": groups["industry"],
    "共識分數": groups["consensus"].map(lambda value: f"{value:,.2f}"), "入選家數": groups["selected_count"],
    "母體家數": groups["universe_count"], "覆蓋率": (groups["coverage"] * 100).map(lambda value: f"{value:,.2f}%"),
    f"{GROUP_NAMES[analysis_group]}相對平均差（ppts）": groups["analysis_change"].map(lambda value: f"{value:+,.2f}"),
    "散戶相對平均減少（ppts）": groups["retail_decrease"].map(lambda value: f"{value:+,.2f}"),
    "平均營收 YoY": groups["avg_revenue_yoy"].map(lambda value: "—" if pd.isna(value) else f"{value:+,.2f}%"),
})
st.subheader("產業排行榜")
st.dataframe(ranking, hide_index=True, width="stretch")

selected = st.selectbox("查看族群", industries, key="selected_industry")
detail = stocks[stocks.industry == selected].sort_values("analysis_change", ascending=False)
selected_field = f"group_{analysis_group}"
detail_display = pd.DataFrame({
    "代碼": detail["code"], "名稱": detail["name"], "股價（元）": detail["price"].map(lambda value: f"{value:,.2f}"),
    "成交量（張）": detail["volume"].map(lambda value: f"{value:,.0f}"),
    "月營收 YoY": detail["revenue_yoy"].map(lambda value: "—" if pd.isna(value) else f"{value:+,.2f}%"),
    f"最新{GROUP_NAMES[analysis_group]}持股": detail[selected_field].map(lambda value: f"{value:,.2f}%"),
    f"平均{GROUP_NAMES[analysis_group]}持股": detail[f"avg_{selected_field}"].map(lambda value: f"{value:,.2f}%"),
    f"{GROUP_NAMES[analysis_group]}相對平均差": detail["analysis_change"].map(lambda value: f"{value:+,.2f} ppts"),
    "散戶相對平均減少": detail["retail_decrease"].map(lambda value: f"{value:+,.2f} ppts"),
    "採樣週數": detail["history_weeks"], "股東人數": detail["holders"], "所有次產業": detail["industry_tags"],
})
st.subheader(f"{selected}｜個股明細")
st.dataframe(detail_display, hide_index=True, width="stretch")

options = detail.apply(lambda row: f"{row.code} {row['name']}", axis=1).tolist()
if options:
    choice = st.selectbox("查看個股持股走勢", options)
    code = choice.split(" ", 1)[0]
    row = detail[detail.code == code].iloc[0]
    history = regrouped_chip[regrouped_chip.code == code].sort_values("date")
    st.subheader(f"{row['name']}（{code}）｜自訂四類持股走勢")
    structure = go.Figure()
    colors = {"retail": "#ff7c96", "mid": "#ffc857", "large": "#42d9ff", "super": "#42e8ca"}
    for key in GROUP_KEYS:
        structure.add_trace(go.Scatter(x=history.date, y=history[f"group_{key}"], name=labels[key], mode="lines+markers", line=dict(color=colors[key], width=2.6), hovertemplate="%{y:,.2f}%<extra>%{fullData.name}</extra>"))
    structure.update_layout(height=460, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#091426", font_color="#dbe9f6", yaxis_title="持股比例（%）", xaxis_title="資料日期", hovermode="x unified", legend=dict(orientation="h", y=1.15))
    st.plotly_chart(structure, width="stretch")
    latest = history.iloc[-1]
    st.caption("最新結構：" + "｜".join(f"{GROUP_NAMES[key]} {latest[f'group_{key}']:,.2f}%" for key in GROUP_KEYS))

st.download_button("下載目前族群個股 CSV", detail_display.to_csv(index=False).encode("utf-8-sig"), f"{selected}_個股明細.csv", "text/csv")
with st.expander("指標定義與品質說明"):
    st.markdown(f"- 目前分群：{'；'.join(labels.values())}。\n- 門檻限用集保原始級距邊界，避免拆分級距造成估算誤差。\n- 比較值＝最新週持股比例－比較期間各週平均；散戶減少採反向計算。\n- 前 1 週／1 月／1 季／1 年採最近 1／4／13／52 個資料週平均。")
