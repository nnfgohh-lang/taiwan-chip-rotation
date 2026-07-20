from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from modules.data_pipeline import PERIOD_DAYS, aggregate_industries, build_stock_snapshot, combine_chip_sources, parse_tdcc, parse_tej, parse_xq

DATA=Path(__file__).parent/"data"
st.set_page_config(page_title="台股籌碼輪動雷達",page_icon=":material/radar:",layout="wide")
st.markdown("""<style>[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 75% 0%,#183463,#081327 38%,#050b16);color:#edf7ff}[data-testid="stSidebar"]{background:#071225;border-right:1px solid #183554}.block-container{padding-top:1.3rem;max-width:1500px}.hero{padding:18px 22px;border:1px solid #1d5371;border-radius:18px;background:linear-gradient(135deg,#17365dcc,#0a1528cc)}.hero b{font-size:2rem}.hero small{color:#66dcf5;letter-spacing:.16em}[data-testid="stMetric"]{background:#0f1c34c7;border:1px solid #294363;padding:12px;border-radius:14px}.note{padding:12px 16px;border-left:3px solid #42d9ff;background:#162d4c88;border-radius:8px;color:#bdd4ec}[data-testid="stDataFrame"],[data-testid="stPlotlyChart"]{border:1px solid #27425e;border-radius:15px;overflow:hidden}</style>""",unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def local_data():
    tej=[parse_tej(p) for p in sorted((DATA/"tej").glob("*.xlsx"))]
    tdcc=[parse_tdcc(p) for p in sorted((DATA/"tdcc").glob("*.csv"))]
    xf=sorted((DATA/"xq").glob("*.csv"))
    return combine_chip_sources(tej,tdcc),parse_xq(xf[-1]) if xf else pd.DataFrame()

def eq_range(series,center):
    s=series.replace([np.inf,-np.inf],np.nan).dropna(); span=max(abs(s.min()-center),abs(s.max()-center),.05) if len(s) else 1
    return [center-span*1.12,center+span*1.12]

def bubble_chart(groups):
    p=groups.dropna(subset=["large_change","consensus"]).copy(); p["coverage_text"]=(p.coverage*100).round(1).astype(str)+"%"; p["compare_text"]=p.comparable_count.astype(str)+"/"+p.selected_count.astype(str)
    fig=px.scatter(p,x="large_change",y="consensus",size="selected_count",color="comparable_rate",text="industry",size_max=62,color_continuous_scale=[[0,"#53657c"],[.5,"#3977ff"],[1,"#42e8ca"]],custom_data=["industry","rank","selected_count","universe_count","coverage_text","compare_text","retail_decrease","avg_revenue_yoy","leaders"])
    fig.update_traces(textposition="top center",marker=dict(line=dict(width=1.3,color="#d2f5ff"),opacity=.88),hovertemplate="<b>%{customdata[0]}</b>｜第 %{customdata[1]} 名<br>大戶 400+ 變化：%{x:.2f} pct<br>共識：%{y:.3f}<br>入選／母體：%{customdata[2]} / %{customdata[3]}<br>覆蓋率：%{customdata[4]}<br>可比較：%{customdata[5]}<br>散戶 50- 減少：%{customdata[6]:.2f} pct<br>平均營收 YoY：%{customdata[7]:.1f}%<br>增持前五：%{customdata[8]}<extra></extra>")
    xc,yc=0.,float(p.consensus.median()); xr,yr=eq_range(p.large_change,xc),eq_range(p.consensus,yc)
    for x0,x1,y0,y1,color in [(xr[0],xc,yr[0],yc,"rgba(255,107,129,.06)"),(xc,xr[1],yr[0],yc,"rgba(66,217,255,.06)"),(xr[0],xc,yc,yr[1],"rgba(130,139,160,.06)"),(xc,xr[1],yc,yr[1],"rgba(66,232,202,.07)")]: fig.add_shape(type="rect",x0=x0,x1=x1,y0=y0,y1=y1,fillcolor=color,line_width=0,layer="below")
    fig.add_vline(x=xc,line_dash="dot",line_color="#7087a7"); fig.add_hline(y=yc,line_dash="dot",line_color="#7087a7")
    for label,x,y in [("共識弱｜增持弱",.02,.04),("共識弱｜增持強",.98,.04),("共識強｜增持弱",.02,.96),("共識強｜增持強",.98,.96)]: fig.add_annotation(text=label,x=x,y=y,xref="paper",yref="paper",showarrow=False,xanchor="left" if x<.5 else "right",font=dict(color="#91a6c3"))
    fig.update_layout(height=640,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#091426",font_color="#dbe9f6",margin=dict(l=20,r=20,t=25,b=20),xaxis=dict(title="大戶 400+ 持股變化中位數（百分點）",range=xr,gridcolor="#263954"),yaxis=dict(title="族群共識分數",range=yr,gridcolor="#263954"),coloraxis_colorbar=dict(title="可比較率",tickformat=".0%"),clickmode="event+select")
    return fig

st.markdown('<div class="hero"><small>TAIWAN CHIP ROTATION INTELLIGENCE</small><br><b>台股籌碼輪動雷達</b><br>集保 × TEJ 歷史 × XQ 基本面｜大戶 400 張以上、散戶 50 張以下</div>',unsafe_allow_html=True)
with st.sidebar:
    st.header("資料與條件"); mode=st.radio("資料來源",["使用專案內資料","自行上傳檔案"])
    if mode=="自行上傳檔案":
        tf=st.file_uploader("TEJ 歷史（可多檔）",type="xlsx",accept_multiple_files=True); df=st.file_uploader("集保原始資料（可多週）",type="csv",accept_multiple_files=True); xf=st.file_uploader("XQ／Total Pool",type="csv")
        if (not tf and not df) or xf is None: st.info("請上傳籌碼資料與 XQ 檔。"); st.stop()
        try: chip=combine_chip_sources([parse_tej(f) for f in tf],[parse_tdcc(f) for f in df]); xq=parse_xq(xf)
        except Exception as exc: st.error(f"讀取失敗：{exc}"); st.stop()
    else:
        try: chip,xq=local_data()
        except Exception as exc: st.error(f"讀取失敗：{exc}"); st.stop()
    dates=sorted(pd.to_datetime(chip.date.unique()),reverse=True); current=st.selectbox("觀察日期",dates,format_func=lambda d:pd.Timestamp(d).strftime("%Y-%m-%d")); period=st.selectbox("比較週期",list(PERIOD_DAYS),index=0)
    st.divider(); min_price=st.number_input("最低股價",0.,value=30.,step=5.); min_volume=st.number_input("最低成交量（張）",0,value=300,step=100); min_revenue=st.number_input("最低月營收 YoY（%）",value=0.,step=5.); min_group=st.number_input("族群最少入選家數",1,value=3); aligned=st.toggle("只看大戶增加且散戶減少",True)

stocks,base=build_stock_snapshot(chip,xq,pd.Timestamp(current),period)
if base is None: st.error(f"資料不足以比較{period}，請補入更早歷史。"); st.stop()
universe=xq[(xq.price.fillna(-np.inf)>=min_price)&(xq.volume.fillna(-np.inf)>=min_volume)]
stocks=stocks[(stocks.price.fillna(-np.inf)>=min_price)&(stocks.volume.fillna(-np.inf)>=min_volume)&(stocks.revenue_yoy.isna()|(stocks.revenue_yoy>=min_revenue))]
if aligned: stocks=stocks[(stocks.large_change>0)&(stocks.retail_decrease>0)]
groups=aggregate_industries(stocks,universe)
if groups.empty: st.warning("目前條件沒有符合族群，請降低門檻。"); st.stop()
groups=groups[groups.selected_count>=min_group]
if groups.empty: st.warning("目前沒有達到最少家數的族群。"); st.stop()
for col,(label,value) in zip(st.columns(5),[("觀察日期",pd.Timestamp(current).strftime("%Y-%m-%d")),("實際比較日",pd.Timestamp(base).strftime("%Y-%m-%d")),("入選股票",f"{stocks.code.nunique():,}"),("入選族群",f"{len(groups):,}"),("大戶增持中位數",f"{stocks.large_change.median():+.2f} pct")]): col.metric(label,value)
st.subheader("產業族群互動泡泡圖"); st.markdown('<div class="note">X＝大戶 400+ 變化中位數；Y＝覆蓋率 × ln(1＋入選家數)；泡泡大小＝入選家數；顏色＝可比較率。點擊泡泡會切換下方族群。</div>',unsafe_allow_html=True)
event=st.plotly_chart(bubble_chart(groups),use_container_width=True,on_select="rerun",selection_mode="points",key="rotation")
industries=groups.industry.tolist()
if "selected_industry" not in st.session_state or st.session_state.selected_industry not in industries: st.session_state.selected_industry=industries[0]
try:
    if event.selection.points: st.session_state.selected_industry=event.selection.points[0]["customdata"][0]
except (AttributeError,KeyError,IndexError,TypeError): pass
ranking=groups[["rank","industry","consensus","selected_count","universe_count","coverage","large_change","retail_decrease","comparable_rate","avg_revenue_yoy","total_volume"]]
st.subheader("族群排行榜"); st.dataframe(ranking,column_config={"rank":"排名","industry":"次產業","consensus":"共識分數","selected_count":"入選家數","universe_count":"母體家數","coverage":st.column_config.ProgressColumn("覆蓋率",min_value=0,max_value=1,format="%.1%%"),"large_change":"大戶 400+ 變化","retail_decrease":"散戶 50- 減少","comparable_rate":st.column_config.ProgressColumn("可比較率",min_value=0,max_value=1,format="%.0%%"),"avg_revenue_yoy":"平均營收 YoY","total_volume":"總成交量"},hide_index=True,use_container_width=True)
selected=st.selectbox("查看族群",industries,key="selected_industry"); detail=stocks[stocks.industry==selected].sort_values("large_change",ascending=False); columns=["code","name","price","volume","revenue_yoy","large_400","prev_large_400","large_change","retail_50","prev_retail_50","retail_decrease","holders","holders_decrease","industry_tags"]
st.subheader(f"{selected}｜個股明細"); st.dataframe(detail[columns],hide_index=True,use_container_width=True)
options=detail.apply(lambda row:f"{row.code} {row['name']}",axis=1).tolist()
if options:
    choice=st.selectbox("深入查看個股",options); code=choice.split(" ",1)[0]; row=detail[detail.code==code].iloc[0]; history=chip[chip.code==code].sort_values("date")
    st.subheader(f"{row['name']}（{code}）持股結構與基本面")
    for col,(label,value) in zip(st.columns(4),[("股價",f"{row.price:.2f}"),("成交量",f"{row.volume:,.0f} 張"),("月營收 YoY","尚未提供" if pd.isna(row.revenue_yoy) else f"{row.revenue_yoy:+.1f}%"),("股東人數",f"{row.holders:,.0f}")]): col.metric(label,value)
    fig=go.Figure()
    for y,name,color,dash in [("large_400","大戶 400+","#42e8ca","solid"),("retail_50","散戶 50-","#ff7c96","solid"),("super_1000","超級大戶 1000+","#6fa8ff","dot")]: fig.add_trace(go.Scatter(x=history.date,y=history[y],name=name,line=dict(color=color,width=3,dash=dash)))
    fig.update_layout(height=390,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#091426",font_color="#dbe9f6",yaxis_title="持股比例（%）",hovermode="x unified"); st.plotly_chart(fig,use_container_width=True)
st.download_button("下載目前族群個股 CSV",detail[columns].to_csv(index=False).encode("utf-8-sig"),f"{selected}_個股明細.csv","text/csv")
with st.expander("資料定義與品質說明"): st.markdown("- 大戶 400+＝集保第 12–15 級；散戶 50-＝第 1–8 級（包含零股）。\n- 1 月／1 季／1 年以 28／91／365 天前為目標，採最接近且早於觀察日的資料。\n- TEJ 與集保重疊時優先採集保。缺少基期不補 0，也不納入變化中位數。\n- 目前 XQ 檔若沒有月營收年增率欄位，網站會顯示尚未提供，且不會誤把全數股票排除。")
