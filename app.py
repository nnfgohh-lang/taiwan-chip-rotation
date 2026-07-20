from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from modules.analysis_v3 import PERIOD_WEEKS, aggregate_industries, build_stock_snapshot_average, combine_chip_sources, parse_tdcc, parse_tej, parse_xq

DATA=Path(__file__).parent/"data"
st.set_page_config(page_title="台股籌碼動能雷達",page_icon=":material/radar:",layout="wide")
st.markdown("""<style>:root{--blue:#168BFF;--red:#FF355D;--ink:#EAF4FF}[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 12% 0%,rgba(22,139,255,.18),transparent 33%),radial-gradient(circle at 90% 8%,rgba(255,53,93,.12),transparent 28%),linear-gradient(rgba(21,66,111,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(21,66,111,.08) 1px,transparent 1px),#050A14;background-size:auto,auto,34px 34px,34px 34px;color:var(--ink)}[data-testid="stSidebar"]{background:linear-gradient(180deg,#07162B,#080C17);border-right:1px solid rgba(22,139,255,.45);box-shadow:10px 0 30px rgba(0,0,0,.28)}.block-container{padding-top:1.3rem;max-width:1500px}.hero{position:relative;overflow:hidden;padding:20px 24px;border:1px solid rgba(22,139,255,.65);border-right-color:rgba(255,53,93,.65);border-radius:16px;background:linear-gradient(110deg,rgba(10,36,69,.96),rgba(16,24,48,.92) 60%,rgba(66,16,34,.72));box-shadow:0 0 28px rgba(22,139,255,.13),inset 0 0 30px rgba(255,53,93,.04)}.hero:after{content:"";position:absolute;right:-70px;top:-85px;width:210px;height:210px;border:1px solid rgba(255,53,93,.38);transform:rotate(45deg)}.hero b{font-size:2rem;text-shadow:0 0 18px rgba(22,139,255,.25)}.hero small{color:#61C4FF;letter-spacing:.18em}[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(11,29,54,.92),rgba(17,19,36,.92));border:1px solid rgba(22,139,255,.26);border-bottom-color:rgba(255,53,93,.28);padding:13px;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.24)}.note{padding:12px 16px;border-left:3px solid var(--blue);border-right:1px solid rgba(255,53,93,.45);background:linear-gradient(90deg,rgba(22,139,255,.12),rgba(255,53,93,.05));border-radius:7px;color:#C9DCF2}[data-testid="stDataFrame"],[data-testid="stPlotlyChart"]{border:1px solid rgba(22,139,255,.28);border-bottom-color:rgba(255,53,93,.28);border-radius:13px;overflow:hidden;box-shadow:0 10px 28px rgba(0,0,0,.2)}h2,h3{letter-spacing:.03em}</style>""",unsafe_allow_html=True)

@st.cache_data(show_spinner=False,ttl=300)
def local_data(signature):
    tej=[parse_tej(p) for p in sorted((DATA/"tej").glob("*.xlsx"))]
    tdcc=[parse_tdcc(p) for p in sorted((DATA/"tdcc").glob("*.csv"))]
    xq_files=sorted((DATA/"xq").glob("*.csv"))
    return combine_chip_sources(tej,tdcc),parse_xq(xq_files[-1]) if xq_files else pd.DataFrame()

def data_signature():
    files=[p for folder in ("tej","tdcc","xq") for p in (DATA/folder).glob("*") if p.is_file()]
    return tuple((p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(files))

def equal_range(series,center):
    s=series.replace([np.inf,-np.inf],np.nan).dropna(); span=max(abs(s.min()-center),abs(s.max()-center),.05) if len(s) else 1
    return [center-span*1.12,center+span*1.12]

def bubble_chart(groups):
    p=groups.dropna(subset=["large_change","consensus"]).copy(); p["coverage_text"]=(p.coverage*100).round(2).map(lambda value:f"{value:.2f}%")
    fig=px.scatter(p,x="large_change",y="consensus",size="selected_count",color="retail_decrease",text="industry",size_max=62,color_continuous_scale=[[0,"#168BFF"],[.5,"#6E68D9"],[1,"#FF355D"]],custom_data=["industry","rank","selected_count","universe_count","coverage_text","retail_decrease","avg_revenue_yoy","leaders"])
    fig.update_traces(textposition="top center",marker=dict(line=dict(width=1.3,color="#d2f5ff"),opacity=.88),hovertemplate="<b>%{customdata[0]}</b>｜第 %{customdata[1]} 名<br>大戶 400+ 相對期間平均：%{x:,.2f} ppts<br>共識分數：%{y:,.2f} 分<br>入選／母體：%{customdata[2]:,} 家 / %{customdata[3]:,} 家<br>覆蓋率：%{customdata[4]}<br>散戶 50- 相對平均減少：%{customdata[5]:,.2f} ppts<br>平均營收 YoY：%{customdata[6]:,.2f}%<br>增持前五：%{customdata[7]}<extra></extra>")
    xc,yc=0.,float(p.consensus.median()); xr,yr=equal_range(p.large_change,xc),equal_range(p.consensus,yc)
    for x0,x1,y0,y1,color in [(xr[0],xc,yr[0],yc,"rgba(255,107,129,.06)"),(xc,xr[1],yr[0],yc,"rgba(66,217,255,.06)"),(xr[0],xc,yc,yr[1],"rgba(130,139,160,.06)"),(xc,xr[1],yc,yr[1],"rgba(66,232,202,.07)")]: fig.add_shape(type="rect",x0=x0,x1=x1,y0=y0,y1=y1,fillcolor=color,line_width=0,layer="below")
    fig.add_vline(x=xc,line_dash="dot",line_color="#7087a7"); fig.add_hline(y=yc,line_dash="dot",line_color="#7087a7")
    for label,x,y in [("共識弱｜增持弱",.02,.04),("共識弱｜增持強",.98,.04),("共識強｜增持弱",.02,.96),("共識強｜增持強",.98,.96)]: fig.add_annotation(text=label,x=x,y=y,xref="paper",yref="paper",showarrow=False,xanchor="left" if x<.5 else "right",font=dict(color="#91a6c3"))
    fig.update_layout(height=640,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#091426",font_color="#dbe9f6",margin=dict(l=20,r=20,t=25,b=20),xaxis=dict(title="最新週大戶 400+－期間平均（ppts）",range=xr,gridcolor="#263954"),yaxis=dict(title="族群共識分數",range=yr,gridcolor="#263954"),coloraxis_colorbar=dict(title="散戶減少（ppts）",tickformat=",.2f"),clickmode="event+select")
    return fig

st.markdown('<div class="hero"><small>OWNERSHIP FLOW INTELLIGENCE</small><br><b>台股籌碼動能雷達</b><br>股權結構 × 產業共識 × 基本面動能｜追蹤最新一週相對歷史均值的籌碼變化</div>',unsafe_allow_html=True)
with st.sidebar:
    st.header("資料與條件"); mode=st.radio("資料來源",["使用專案內資料","自行上傳檔案"])
    if mode=="自行上傳檔案":
        tej_files=st.file_uploader("歷史持股資料（Excel，可多檔）",type="xlsx",accept_multiple_files=True); tdcc_files=st.file_uploader("每週股權分散資料（CSV，可多週）",type="csv",accept_multiple_files=True); xq_file=st.file_uploader("市場與基本面清單（CSV）",type="csv")
        if (not tej_files and not tdcc_files) or xq_file is None: st.info("請上傳持股資料與市場基本面清單。"); st.stop()
        try: chip=combine_chip_sources([parse_tej(f) for f in tej_files],[parse_tdcc(f) for f in tdcc_files]); xq=parse_xq(xq_file)
        except Exception as exc: st.error(f"讀取失敗：{exc}"); st.stop()
    else:
        try: chip,xq=local_data(data_signature())
        except Exception as exc: st.error(f"讀取失敗：{exc}"); st.stop()
    dates=sorted(pd.to_datetime(chip.date.unique()),reverse=True); current=st.selectbox("觀察日期",dates,format_func=lambda d:pd.Timestamp(d).strftime("%Y-%m-%d")); period=st.selectbox("比較週期（期間平均）",list(PERIOD_WEEKS),index=0)
    st.divider(); min_price=st.number_input("最低股價（元）",0.,value=30.,step=5.); min_volume=st.number_input("最低成交量（張）",0,value=300,step=100); min_revenue=st.number_input("最低月營收 YoY（%）",value=0.,step=5.); min_group=st.number_input("族群最少入選家數（家）",1,value=3); aligned=st.toggle("只看大戶增加且散戶減少",True)

stocks,start,end,weeks=build_stock_snapshot_average(chip,xq,pd.Timestamp(current),period)
if start is None: st.error(f"資料不足以計算{period}平均，請補入更早歷史。"); st.stop()
universe=xq[(xq.price.fillna(-np.inf)>=min_price)&(xq.volume.fillna(-np.inf)>=min_volume)]
stocks=stocks[(stocks.price.fillna(-np.inf)>=min_price)&(stocks.volume.fillna(-np.inf)>=min_volume)&(stocks.revenue_yoy.isna()|(stocks.revenue_yoy>=min_revenue))]
if aligned: stocks=stocks[(stocks.large_change>0)&(stocks.retail_decrease>0)]
groups=aggregate_industries(stocks,universe)
if groups.empty: st.warning("目前條件沒有符合族群，請降低門檻。"); st.stop()
groups=groups[groups.selected_count>=min_group]
if groups.empty: st.warning("目前沒有達到最少家數的族群。"); st.stop()
period_text=f"{pd.Timestamp(start):%Y-%m-%d}～{pd.Timestamp(end):%Y-%m-%d}（{weeks}週平均）"
for col,(label,value) in zip(st.columns(5),[("觀察日期",pd.Timestamp(current).strftime("%Y-%m-%d")),("平均比較期間",period_text),("入選股票",f"{stocks.code.nunique():,} 檔"),("入選族群",f"{len(groups):,} 個"),("大戶相對平均差（ppts）",f"{stocks.large_change.median():+,.2f}")]): col.metric(label,value)
st.subheader("產業族群互動泡泡圖"); st.markdown('<div class="note">X＝最新週大戶 400+－比較期間各週平均；Y＝覆蓋率 × ln(1＋入選家數)；泡泡大小＝入選家數（家）；顏色＝散戶 50 張以下相對期間平均的減少幅度（ppts）。持股比例與營收年增率使用 %；最新值減期間平均使用 ppts。點擊泡泡會切換個股明細。</div>',unsafe_allow_html=True)
event=st.plotly_chart(bubble_chart(groups),width="stretch",on_select="rerun",selection_mode="points",key="rotation")
industries=groups.industry.tolist()
if "selected_industry" not in st.session_state or st.session_state.selected_industry not in industries: st.session_state.selected_industry=industries[0]
try:
    if event.selection.points: st.session_state.selected_industry=event.selection.points[0]["customdata"][0]
except (AttributeError,KeyError,IndexError,TypeError): pass
ranking=pd.DataFrame({"排名（名）":groups["rank"].map(lambda v:f"{v:,.0f}"),"次產業":groups["industry"],"共識分數（分）":groups["consensus"].map(lambda v:f"{v:,.2f}"),"入選家數（家）":groups["selected_count"].map(lambda v:f"{v:,.0f}"),"母體家數（家）":groups["universe_count"].map(lambda v:f"{v:,.0f}"),"覆蓋率（%）":(groups["coverage"]*100).map(lambda v:f"{v:,.2f}%"),"大戶相對期間平均差（ppts）":groups["large_change"].map(lambda v:f"{v:+,.2f}"),"散戶相對期間平均減少（ppts）":groups["retail_decrease"].map(lambda v:f"{v:+,.2f}"),"平均營收 YoY（%）":groups["avg_revenue_yoy"].map(lambda v:"—" if pd.isna(v) else f"{v:+,.2f}%"),"總成交量（張）":groups["total_volume"].map(lambda v:"—" if pd.isna(v) else f"{v:,.0f}")})
st.subheader("族群排行榜"); st.dataframe(ranking,hide_index=True,width="stretch")
selected=st.selectbox("查看族群",industries,key="selected_industry"); detail=stocks[stocks.industry==selected].sort_values("large_change",ascending=False)
columns=["code","name","price","volume","revenue_yoy","large_400","avg_large_400","large_change","retail_50","avg_retail_50","retail_decrease","history_weeks","holders","industry_tags"]
detail_display=pd.DataFrame({"代碼":detail["code"],"名稱":detail["name"],"股價（元）":detail["price"].map(lambda v:f"{v:,.2f}"),"成交量（張）":detail["volume"].map(lambda v:f"{v:,.0f}"),"月營收 YoY（%）":detail["revenue_yoy"].map(lambda v:"—" if pd.isna(v) else f"{v:+,.2f}%"),"最新大戶持股比例（%）":detail["large_400"].map(lambda v:f"{v:,.2f}%"),"期間平均大戶持股比例（%）":detail["avg_large_400"].map(lambda v:f"{v:,.2f}%"),"大戶相對期間平均差（ppts）":detail["large_change"].map(lambda v:f"{v:+,.2f}"),"最新散戶持股比例（%）":detail["retail_50"].map(lambda v:f"{v:,.2f}%"),"期間平均散戶持股比例（%）":detail["avg_retail_50"].map(lambda v:f"{v:,.2f}%"),"散戶相對期間平均減少（ppts）":detail["retail_decrease"].map(lambda v:f"{v:+,.2f}"),"平均採樣週數（週）":detail["history_weeks"].map(lambda v:f"{v:,.0f}"),"股東人數（人）":detail["holders"].map(lambda v:f"{v:,.0f}"),"所有次產業":detail["industry_tags"]}); st.subheader(f"{selected}｜個股明細"); st.dataframe(detail_display,hide_index=True,width="stretch")
options=detail.apply(lambda row:f"{row.code} {row['name']}",axis=1).tolist()
if options:
    choice=st.selectbox("深入查看個股",options); code=choice.split(" ",1)[0]; row=detail[detail.code==code].iloc[0]; history=chip[chip.code==code].sort_values("date")
    st.subheader(f"{row['name']}（{code}）持股結構變化")
    for col,(label,value) in zip(st.columns(4),[("股價（元）",f"{row.price:,.2f}"),("成交量（張）",f"{row.volume:,.0f}"),("月營收 YoY（%）","尚未提供" if pd.isna(row.revenue_yoy) else f"{row.revenue_yoy:+,.2f}%"),("比較資料（週）",f"{int(row.history_weeks):,}")]): col.metric(label,value)
    structure=go.Figure()
    for field,name,color in [("retail_50","散戶 50張以下","#ff7c96"),("mid_50_400","中實戶 50–400張","#ffc857"),("large_400_1000","大戶 400–1000張","#42d9ff"),("super_1000","超級大戶 1000張以上","#42e8ca")]: structure.add_trace(go.Scatter(x=history.date,y=history[field],name=name,mode="lines+markers",line=dict(color=color,width=2.6),hovertemplate="%{y:,.2f}%<extra>%{fullData.name}</extra>"))
    structure.update_layout(height=460,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#091426",font_color="#dbe9f6",yaxis_title="持股比例（%）",xaxis_title="資料週",hovermode="x unified",legend=dict(orientation="h",y=1.12))
    st.plotly_chart(structure,width="stretch")
    latest=history.iloc[-1]
    st.caption(f"最新結構：散戶 {latest.retail_50:,.2f}%｜中實戶 {latest.mid_50_400:,.2f}%｜大戶 {latest.large_400_1000:,.2f}%｜超級大戶 {latest.super_1000:,.2f}%")
st.download_button("下載目前族群個股 CSV",detail_display.to_csv(index=False).encode("utf-8-sig"),f"{selected}_個股明細.csv","text/csv")
with st.expander("指標定義與品質說明"): st.markdown("- 散戶：50 張以下；中實戶：50–400 張；大戶：400–1000 張；超級大戶：1000 張以上。\n- 比較值＝最新週持股比例－比較期間內各週平均持股比例。散戶減少則反向計算。\n- 前 1 週／1 月／1 季／1 年分別採觀察日前最近 1／4／13／52 個資料週平均。\n- 缺少歷史資料不補 0；不同來源資料重疊時，優先採用最新匯入的官方週資料。")
