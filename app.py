import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import io

st.set_page_config(page_title='ProcessIQ Analytics', page_icon='📊', layout='wide')
st.markdown('''<style>
.stApp {background:#f4f7fb;color:#17243a;}
[data-testid="stSidebar"] {background:#e5edf7;}
[data-testid="stMetric"] {background:#ffffff;border:1px solid #dbe5f1;border-radius:14px;padding:16px;border-top:4px solid #2563eb;}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"] {color:#17243a;}
.block-container {padding-top:2rem;}
.hero {background:linear-gradient(110deg,#102343,#2056a5);color:white;padding:26px;border-radius:16px;margin-bottom:22px;}
.hero h1 {color:white;margin:0;font-size:32px;}
</style>''', unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>ProcessIQ Analytics</h1><p>BUSINESS PROCESS INTELLIGENCE / ORDER-TO-DELIVERY</p>Discover bottlenecks, monitor performance and simulate improvements.</div>',unsafe_allow_html=True)
STANDARD=['Order Created','Payment Approved','Inventory Checked','Order Packed','Order Shipped','Order Delivered']
COLS=['case_id','activity','timestamp','region','channel']
st.sidebar.title('ProcessIQ | Controls')
upload=st.sidebar.file_uploader('Upload event log (CSV)',type='csv')
try:
    raw=pd.read_csv(upload if upload is not None else Path(__file__).parent/'data'/'order_event_log.csv',dtype=str)
except Exception as e:
    st.error(f'Cannot read dataset: {e}'); st.stop()
missing=set(COLS)-set(raw.columns)
if missing:
    st.error('Missing columns: '+', '.join(sorted(missing))); st.stop()
raw=raw[COLS].copy()
raw['timestamp']=pd.to_datetime(raw['timestamp'],errors='coerce',utc=True).dt.tz_convert(None)
invalid=int(raw.isna().any(axis=1).sum())
clean=raw.dropna().copy()
for c in ['case_id','activity','region','channel']:
    clean[c]=clean[c].str.strip()
blank=clean[['case_id','activity','region','channel']].eq('').any(axis=1)
invalid+=int(blank.sum()); clean=clean[~blank]
duplicates=int(clean.duplicated().sum()); clean=clean.drop_duplicates().sort_values(['case_id','timestamp'],kind='stable')
if clean.empty: st.error('No valid events.'); st.stop()
ambiguous=int(clean.duplicated(['case_id','timestamp'],keep=False).sum())
orders=clean.groupby('case_id').agg(start=('timestamp','min'),end=('timestamp','max'),region=('region','first'),channel=('channel','first'),event_count=('activity','size')).reset_index()
paths=clean.groupby('case_id')['activity'].agg(list)
orders['variant']=orders.case_id.map(paths.map(lambda x:' → '.join(x)))
orders['complete']=orders.case_id.map(paths.map(lambda x:x[0]=='Order Created' and x[-1]=='Order Delivered'))
orders['standard']=orders.case_id.map(paths.map(lambda x:x==STANDARD))
orders['rework']=orders.case_id.map(paths.map(lambda x:len(x)!=len(set(x)) or any(a in x for a in ['Inventory Recheck','Payment Retry'])))
orders['days']=(orders.end-orders.start).dt.total_seconds()/86400
sla=st.sidebar.slider('Delivery SLA (days)',1,100,40)
orders['status']='Incomplete'; orders.loc[orders.complete,'status']='On Time'; orders.loc[orders.complete & (orders.days>sla),'status']='Delayed'
region=st.sidebar.multiselect('Regions',sorted(orders.region.unique()),default=sorted(orders.region.unique()))
channel=st.sidebar.multiselect('Channels',sorted(orders.channel.unique()),default=sorted(orders.channel.unique()))
dates=st.sidebar.date_input('Order start dates',(orders.start.min().date(),orders.start.max().date()))
status=st.sidebar.multiselect('Status',['On Time','Delayed','Incomplete'],default=['On Time','Delayed','Incomplete'])
if len(dates)!=2: st.stop()
o=orders[orders.region.isin(region)&orders.channel.isin(channel)&orders.status.isin(status)&(orders.start.dt.date>=dates[0])&(orders.start.dt.date<=dates[1])].copy()
if o.empty: st.warning('No matching orders. Change filters.'); st.stop()
e=clean[clean.case_id.isin(o.case_id)].copy(); e['next_activity']=e.groupby('case_id').activity.shift(-1); e['next_time']=e.groupby('case_id').timestamp.shift(-1); e['hours']=(e.next_time-e.timestamp).dt.total_seconds()/3600
tr=e.dropna(subset=['next_activity','hours']).copy(); tr['transition']=tr.activity+' → '+tr.next_activity
b=tr.groupby('transition').hours.agg(['mean','median','sum','count']).reset_index().sort_values('mean',ascending=False)
completed=o[o.complete]; n=len(o); nc=len(completed); avg=completed.days.mean() if nc else 0; late=int((completed.status=='Delayed').sum()); rate=100*(nc-late)/nc if nc else 0
st.caption(('Uploaded dataset' if upload else 'Synthetic demonstration dataset')+' | '+str(len(e))+' filtered events | Delivery KPIs use completed orders only')
for col,(label,value) in zip(st.columns(5),[('Orders',n),('Completed',nc),('Avg cycle',f'{avg:.1f} days' if nc else 'N/A'),('On-time rate',f'{rate:.1f}%' if nc else 'N/A'),('Standard path',f'{100*o.standard.mean():.1f}%')]): col.metric(label,value)
page=st.sidebar.radio('Navigation',['Executive Overview','Process Discovery','Bottleneck Intelligence','Compliance & Variants','Delay Drivers','Risk Monitoring','What-if & Value','Order Explorer','Data Quality','Report Center'])
def chart(fig):
    fig.update_layout(template='plotly_white',paper_bgcolor='white',plot_bgcolor='white',font_color='#17243a',margin=dict(l=25,r=25,t=55,b=25))
    st.plotly_chart(fig, config={"displaylogo": False})
def table(data): st.dataframe(data,width='stretch',hide_index=True)
if page=='Executive Overview':
    st.header('Executive performance overview')
    a,c=st.columns(2)
    with a: chart(px.pie(o,names='status',hole=.6,title='Order status',color='status',color_discrete_map={'On Time':'#10b981','Delayed':'#ef4444','Incomplete':'#94a3b8'}))
    with c: chart(px.histogram(completed,x='days',nbins=20,title='Completed order cycle time',color_discrete_sequence=['#2563eb']))
    monthly=completed.assign(month=completed.start.dt.strftime('%Y-%m')).groupby('month').days.mean().reset_index()
    chart(px.line(monthly,x='month',y='days',markers=True,title='Monthly average cycle time (days)'))
    st.subheader('Automated insights'); st.write(f'{late} completed orders exceed the selected {sla}-day SLA. {int(o.rework.sum())} orders contain rework indicators.')
    if not b.empty: st.info(f"Review {b.iloc[0].transition}: highest average observed transition time ({b.iloc[0]['mean']:.1f} hours).")
elif page=='Process Discovery':
    st.header('Discover actual process paths')
    flow=tr.groupby(['activity','next_activity']).size().reset_index(name='frequency')
    if flow.empty: st.info('No transitions in selection.')
    else:
        nodes=list(dict.fromkeys(flow.activity.tolist()+flow.next_activity.tolist())); idx={v:i for i,v in enumerate(nodes)}
        fig=go.Figure(go.Sankey(node=dict(label=nodes,pad=25,thickness=22,color='#2563eb'),link=dict(source=flow.activity.map(idx),target=flow.next_activity.map(idx),value=flow.frequency,color='rgba(37,99,235,0.25)'))); fig.update_layout(height=550,title='Directly-follows process map'); chart(fig); table(flow)
    st.caption('Link thickness represents transition frequency; loops may occur in uploaded data.')
elif page=='Bottleneck Intelligence':
    st.header('Transition waiting-time analysis'); chart(px.bar(b,x='mean',y='transition',orientation='h',color='mean',title='Average elapsed hours between events')); table(b.round(2)); st.caption('Elapsed time includes work and waiting; event logs alone cannot separate them.')
elif page=='Compliance & Variants':
    st.header('Process conformance'); st.write('Reference path: '+' → '.join(STANDARD)); v=o.groupby('variant').agg(orders=('case_id','size'),average_days=('days','mean'),standard=('standard','first')).reset_index().sort_values('orders',ascending=False); st.metric('Unique variants',len(v)); chart(px.bar(v.head(10),x='orders',y='variant',orientation='h',title='Top process variants')); table(v.round(2)); st.caption('Standard means exact sequence match, not legal compliance. Incomplete cases are included in variant counts.')
elif page=='Delay Drivers':
    st.header('Delay driver exploration'); dimension=st.selectbox('Compare by',['region','channel','rework','standard']); g=completed.assign(late=completed.status.eq('Delayed')).groupby(dimension).agg(orders=('case_id','size'),average_days=('days','mean'),delay_rate=('late','mean')).reset_index(); g['delay_rate']*=100; g[dimension]=g[dimension].astype(str); chart(px.bar(g,x=dimension,y='delay_rate',color=dimension,title='Delay rate (%) by segment')); table(g.round(2)); st.caption('Associations are descriptive, not proof of root cause.')
elif page=='Risk Monitoring':
    st.header('SLA exceptions and near misses'); threshold=st.slider('Near-miss threshold (% of SLA)',50,100,80); risk=completed[completed.days>=sla*threshold/100].sort_values('days',ascending=False); st.metric('Completed orders flagged',len(risk)); table(risk[['case_id','region','channel','days','status','rework']].round(2)); st.caption('Retrospective rule-based flags, not predictions of future delays.')
elif page=='What-if & Value':
    st.header('Business value simulation'); cb=tr[tr.case_id.isin(completed.case_id)].groupby('transition').hours.sum()
    if cb.empty: st.info('No completed order transitions to simulate.')
    else:
        selected=st.selectbox('Transition to improve',cb.index.tolist()); reduction=st.slider('Reduction in elapsed time (%)',0,80,20); cost=st.number_input('Assumed value per saved hour (INR)',min_value=0,value=100); saved=cb[selected]*reduction/100; projected=max(0,avg-saved/nc/24); a,c,d=st.columns(3); a.metric('Potential hours saved',f'{saved:,.1f}'); c.metric('Illustrative value',f'₹{saved*cost:,.0f}'); d.metric('Projected average days',f'{projected:.1f}'); chart(px.bar(pd.DataFrame({'Scenario':['Current','Projected'],'Days':[avg,projected]}),x='Scenario',y='Days',color='Scenario',title='Scenario comparison')); st.warning('Hypothetical estimate for selected completed orders. Assumes reductions translate directly to shorter cycle times; not actual financial savings.')
elif page=='Order Explorer':
    st.header('Individual order investigation'); query=st.text_input('Search order ID'); ids=o[o.case_id.str.contains(query,case=False,regex=False)].case_id.tolist()
    if ids:
        case=st.selectbox('Select order',ids); table(o[o.case_id==case]); history=e[e.case_id==case].copy(); table(history[['activity','timestamp','hours']]); timeline=history.dropna(subset=['next_time']); chart(px.timeline(timeline,x_start='timestamp',x_end='next_time',y='activity',color='activity',title='Elapsed time between order events'))
    else: st.info('No matching order IDs.')
elif page=='Data Quality':
    st.header('Event-log quality audit'); a,c,d=st.columns(3); a.metric('Raw rows',len(raw)); c.metric('Invalid rows removed',invalid); d.metric('Duplicates removed',duplicates); st.metric('Events with tied case timestamps',ambiguous); st.write('Required CSV columns: '+', '.join(COLS)); st.write('Tied timestamps can make event ordering ambiguous. Missing or blank required fields are excluded.'); st.download_button('Download cleaned dataset',clean.to_csv(index=False),'cleaned_event_log.csv','text/csv')
else:
    st.header('Report center'); st.write('Export the current filtered analysis.'); st.download_button('Download order KPI report',o.to_csv(index=False),'order_kpis.csv','text/csv'); st.download_button('Download event log',e.to_csv(index=False),'event_log.csv','text/csv'); st.download_button('Download bottleneck report',b.to_csv(index=False),'bottlenecks.csv','text/csv'); report=f'ProcessIQ Analytics\nOrders: {n}\nCompleted: {nc}\nDelayed: {late}\nSLA: {sla} days\nOn-time rate: {rate:.1f}% (N/A if no completed orders)\nSource: {"uploaded" if upload else "synthetic"}\n'; st.download_button('Download executive summary',report,'executive_summary.txt','text/plain')
st.divider(); st.caption('ProcessIQ Analytics | Academic portfolio | Inspired by Celonis process mining concepts; not an official Celonis implementation.')
