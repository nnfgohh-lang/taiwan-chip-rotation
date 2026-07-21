from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from modules.analysis_v3 import PERIOD_WEEKS, aggregate_industries, build_stock_snapshot_average, combine_chip_sources, parse_tdcc, parse_tej, parse_xq

DATA=Path(__file__).parent/"data"
st.set_page_config(page_title="台股籌碼輪動雷達",page_icon=":material/radar:",layout="wide")
st.markdown("""<style>[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 75% 0%,#183463,#081327 38%,#050b16);color:#edf7ff}[data-testid="stSidebar"]{background:#071225;border-right:1px solid #183554}.block-container{padding-top:1.3rem;max-width:1500px}.hero{padding:18px 22px;border:1px solid #1d5371;border-radius:18px;background:linear-gradient(135deg,#17365dcc,#0a1528cc)}.hero b{font-size:2rem}.hero small{color:#66dcf5;letter-spacing:.16em}[data-testid="stMetric"]{background:#0f1c34c7;border:1px solid #294363;padding:12px;border-radius:14px}.note{padding:12px 16px;border-left:3px solid #42d9ff;background:#162d4c88;border-radius:8px;color:#bdd4ec}[data-testid="stDataFrame"],[data-testid="stPlotlyChart"]{border:1px solid #27425e;border-radius:15px;overflow:hidden}</style>""",unsafe_allow_html=True)

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
    fig=px.scatter(p,x="large_change",y="consensus",size="selected_count",color="retail_decrease",text="industry",size_max=62,color_continuous_scale=[[0,"#246BFD"],[.5,"#E8EEF8"],[1,"#FF8A3D"]],custom_data=["industry","rank","selected_count","universe_count","coverage_text","retail_decrease","avg_revenue_yoy","leaders"])
    fig.update_traces(textposition="top center",marker=dict(line=dict(width=1.3,color="#d2f5ff"),opacity=.88),hovertemplate="<b>%{customdata[0]}</b>｜第 %{customdata[1]} 名<br>大戶 400+ 相對期間平均：%{x:.2f} pct<br>共識：%{y:.3f}<br>入選／母體：%{customdata[2]} / %{customdata[3]}<br>覆蓋率：%{customdata[4]}<br>散戶 50- 相對平均減少：%{customdata[5]:.2f} pct<br>平均營收 YoY：%{customdata[6]:.1f}%<br>增持前五：%{customdata[7]}<extra></extra>")
    xc,yc=0.,float(p.consensus.median()); xr,yr=equal_range(p.large_change,xc),equal_range(p.consensus,yc)
    for x0,x1,y0,y1,color in [(xr[0],xc,yr[0],yc,"rgba(255,107,129,.06)"),(xc,xr[1],yr[0],yc,"rgba(66,217,255,.06)"),(xr[0],xc,yc,yr[1],"rgba(130,139,160,.06)"),(xc,xr[1],yc,yr[1],"rgba(66,232,202,.07)")]: fig.add_shape(type="rect",x0=x0,x1=x1,y0=y0,y1=y1,fillcolor=color,line_width=0,layer="below")
    fig.add_vline(x=xc,line_dash="dot",line_color="#7087a7"); fig.add_hline(y=yc,line_dash="dot",line_color="#7087a7")
    for label,x,y in [("共識弱｜增持弱",.02,.04),("共識弱｜增持強",.98,.04),("共識強｜增持弱",.02,.96),("共識強｜增持強",.98,.96)]: fig.add_annotation(text=label,x=x,y=y,xref="paper",yref="paper",showarrow=False,xanchor="left" if x<.5 else "right",font=dict(color="#91a6c3"))
    fig.update_layout(height=640,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#091426",font_color="#dbe9f6",margin=dict(l=20,r=20,t=25,b=20),xaxis=dict(title="最新週大戶 400+－期間平均（百分點）",range=xr,gridcolor="#263954"),yaxis=dict(title="族群共識分數",range=yr,gridcolor="#263954"),coloraxis_colorbar=dict(title="散戶減少",ticksuffix=" pct"),clickmode="event+select")
    return fig

st.markdown('<div class="hero"><small>TAIWAN CHIP ROTATION INTELLIGENCE</small><br><b>台股籌碼輪動雷達</b><br>集保 × TEJ 歷史 × XQ 基本面｜最新週相對期間歷史平均</div>',unsafe_allow_html=True)
with st.sidebar:
    st.header("資料與條件"); mode=st.radio("資料來源",["使用專案內資料","自行上傳檔案"])
    if mode=="自行上傳檔案":
        tej_files=st.file_uploader("TEJ 歷史（可多檔）",type="xlsx",accept_multiple_files=True); tdcc_files=st.file_uploader("集保原始資料（可多週）",type="csv",accept_multiple_files=True); xq_file=st.file_uploader("XQ／Total Pool",type="csv")
        if (not tej_files and not tdcc_files) or xq_file is None: st.info("請上傳籌碼資料與 XQ 檔。"); st.stop()
        try: chip=combine_chip_sources([parse_tej(f) for f in tej_files],[parse_tdcc(f) for f in tdcc_files]); xq=parse_xq(xq_file)
        except Exception as exc: st.error(f"讀取失敗：{exc}"); st.stop()
    else:
        try: chip,xq=local_data(data_signature())
        except Exception as exc: st.error(f"讀取失敗：{exc}"); st.stop()
    dates=sorted(pd.to_datetime(chip.date.unique()),reverse=True); current=st.selectbox("觀察日期",dates,format_func=lambda d:pd.Timestamp(d).strftime("%Y-%m-%d")); period=st.selectbox("比較週期（期間平均）",list(PERIOD_WEEKS),index=0)
    st.divider(); min_price=st.number_input("最低股價",0.,value=30.,step=5.); min_volume=st.number_input("最低成交量（張）",0,value=300,step=100); min_revenue=st.number_input("最低月營收 YoY（%）",value=0.,step=5.); min_group=st.number_input("族群最少入選家數",1,value=3); aligned=st.toggle("只看大戶增加且散戶減少",True)

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
for col,(label,value) in zip(st.columns(5),[("觀察日期",pd.Timestamp(current).strftime("%Y-%m-%d")),("平均比較期間",period_text),("入選股票",f"{stocks.code.nunique():,}"),("入選族群",f"{len(groups):,}"),("大戶相對平均",f"{stocks.large_change.median():+.2f} pct")]): col.metric(label,value)
st.subheader("產業族群互動泡泡圖"); st.markdown('<div class="note">X＝最新週大戶 400+－比較期間各週平均；Y＝覆蓋率 × ln(1＋入選家數)；泡泡大小＝入選家數；顏色＝散戶 50 張以下相對期間平均的減少幅度。點擊泡泡會切換個股明細。</div>',unsafe_allow_html=True)
event=st.plotly_chart(bubble_chart(groups),width="stretch",on_select="rerun",selection_mode="points",key="rotation")
industries=groups.industry.tolist()
if "selected_industry" not in st.session_state or st.session_state.selected_industry not in industries: st.session_state.selected_industry=industries[0]
try:
    if event.selection.points: st.session_state.selected_industry=event.selection.points[0]["customdata"][0]
except (AttributeError,KeyError,IndexError,TypeError): pass
ranking=groups.assign(coverage_pct=groups.coverage*100)[["rank","industry","consensus","selected_count","universe_count","coverage_pct","large_change","retail_decrease","avg_revenue_yoy","total_volume"]]
st.subheader("族群排行榜"); st.dataframe(ranking,column_config={"rank":"排名","industry":"次產業","consensus":"共識分數","selected_count":"入選家數","universe_count":"母體家數","coverage_pct":st.column_config.NumberColumn("覆蓋率",format="%.2f%%"),"large_change":"大戶相對平均","retail_decrease":"散戶相對平均減少","avg_revenue_yoy":"平均營收 YoY","total_volume":"總成交量"},hide_index=True,width="stretch")
selected=st.selectbox("查看族群",industries,key="selected_industry"); detail=stocks[stocks.industry==selected].sort_values("large_change",ascending=False)
columns=["code","name","price","volume","revenue_yoy","large_400","avg_large_400","large_change","retail_50","avg_retail_50","retail_decrease","history_weeks","holders","industry_tags"]
st.subheader(f"{selected}｜個股明細"); st.dataframe(detail[columns],column_config={"code":"代碼","name":"名稱","price":"股價","volume":"成交量","revenue_yoy":"月營收 YoY","large_400":"最新大戶 400+","avg_large_400":"期間平均大戶 400+","large_change":"相對平均變化","retail_50":"最新散戶 50-","avg_retail_50":"期間平均散戶 50-","retail_decrease":"相對平均減少","history_weeks":"平均週數","holders":"股東人數","industry_tags":"所有次產業"},hide_index=True,width="stretch")
options=detail.apply(lambda row:f"{row.code} {row['name']}",axis=1).tolist()
if options:
    choice=st.selectbox("深入查看個股",options); code=choice.split(" ",1)[0]; row=detail[detail.code==code].iloc[0]; history=chip[chip.code==code].sort_values("date")
    st.subheader(f"{row['name']}（{code}）持股結構變化")
    for col,(label,value) in zip(st.columns(4),[("股價",f"{row.price:.2f}"),("成交量",f"{row.volume:,.0f} 張"),("月營收 YoY","尚未提供" if pd.isna(row.revenue_yoy) else f"{row.revenue_yoy:+.1f}%"),("比較資料",f"{int(row.history_weeks)} 週")]): col.metric(label,value)
    structure=go.Figure()
    for field,name,color in [("retail_50","散戶 50張以下","#ff7c96"),("mid_50_400","中實戶 50–400張","#ffc857"),("large_400_1000","大戶 400–1000張","#42d9ff"),("super_1000","超級大戶 1000張以上","#42e8ca")]: structure.add_trace(go.Scatter(x=history.date,y=history[field],name=name,mode="lines+markers",line=dict(color=color,width=2.6)))
    structure.update_layout(height=460,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#091426",font_color="#dbe9f6",yaxis_title="持股比例（%）",xaxis_title="資料週",hovermode="x unified",legend=dict(orientation="h",y=1.12))
    st.plotly_chart(structure,width="stretch")
    latest=history.iloc[-1]
    st.caption(f"最新結構：散戶 {latest.retail_50:.2f}%｜中實戶 {latest.mid_50_400:.2f}%｜大戶 {latest.large_400_1000:.2f}%｜超級大戶 {latest.super_1000:.2f}%")
st.download_button("下載目前族群個股 CSV",detail[columns].to_csv(index=False).encode("utf-8-sig"),f"{selected}_個股明細.csv","text/csv")
with st.expander("指標定義與品質說明"): st.markdown("- 散戶：50 張以下；中實戶：50–400 張；大戶：400–1000 張；超級大戶：1000 張以上。\n- 比較值＝最新週持股比例－比較期間內各週平均持股比例。散戶減少則反向計算。\n- 前 1 週／1 月／1 季／1 年分別採觀察日前最近 1／4／13／52 個資料週平均。\n- 缺少歷史資料不補 0；TEJ 與集保重疊時優先採集保。")
