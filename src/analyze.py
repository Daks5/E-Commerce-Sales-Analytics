"""Execute named SQL analyses; reconcile integer paise and row lineage against Python."""
from pathlib import Path
import json,re
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sqlalchemy import text
from load_mysql import engine,ROOT

def main():
    eng=engine(); out=ROOT/'reports/sql_results';out.mkdir(exist_ok=True)
    results={}
    script=(ROOT/'sql/02_business_analysis.sql').read_text()
    with eng.connect() as con:
        for chunk in re.split(r'-- @question ',script)[1:]:
            name,query=chunk.split('\n',1)
            result=pd.read_sql(text(query.strip().rstrip(';')),con)
            result.to_csv(out/f'{name}.csv',index=False)
            results[name]=json.loads(result.to_json(orient='records',date_format='iso'))
        python=pd.read_csv(ROOT/'data/processed/analytical_order_lines.csv',dtype={'order_id':'string','amount_minor':'Int64'})
        sql=pd.read_sql(text('SELECT line_id,order_id,amount_minor,is_sales_eligible,quantity FROM v_order_lines ORDER BY line_id'),con)
        expected=python.sort_values('line_id')
        checks={
            'analytical_rows':len(sql)==len(python)==128969,
            'source_line_identity':sql.line_id.tolist()==expected.line_id.tolist(),
            'order_identity':sql.order_id.tolist()==expected.order_id.tolist(),
            'every_line_money':sql.amount_minor.astype('Int64').reset_index(drop=True).equals(expected.amount_minor.reset_index(drop=True)),
            'money_reconciles':int(sql.amount_minor.sum())==int(python.amount_minor.sum()),
            'eligible_money_reconciles':int(sql.loc[sql.is_sales_eligible.eq(1),'amount_minor'].sum())==int(python.loc[python.is_sales_eligible.eq(1),'amount_minor'].sum()),
            'shipped_units_reconcile':int(sql.loc[sql.is_sales_eligible.eq(1),'quantity'].sum())==int(python.loc[python.is_sales_eligible.eq(1),'quantity'].sum()),
            'no_join_fanout':sql.line_id.is_unique,
            'raw_fact_count':con.execute(text('SELECT COUNT(*) FROM fact_order_lines')).scalar()==128975,
        }
        for name,keys in [('category_performance',['category']),('state_performance',['ship_state']),('fulfillment_operations',['fulfillment']),('b2b_segment',['is_b2b'])]:
            sums=python.loc[python.is_sales_eligible.eq(1)].groupby(keys).amount_minor.sum()
            got=pd.DataFrame(results[name]).set_index(keys).shipped_value
            checks[name+'_money']=all(int(round(got[k]*100))==int(sums.get(k,0)) for k in got.index)
        raw_total=0
        for item in json.loads((ROOT/'reports/sql_load_inventory.json').read_text()):
            count=con.execute(text(f"SELECT COUNT(*) FROM {item['table']}")).scalar()
            checks[item['table']+'_count']=count==item['rows'];raw_total+=count
        checks['all_raw_sources']=raw_total==178405
        ddl=[]
        for table in ['dim_date','dim_product','dim_geography','dim_status','fact_order_lines']:
            ddl.append(con.execute(text(f'SHOW CREATE TABLE {table}')).first()[1]+';')
        (ROOT/'sql/00_schema.sql').write_text('-- Generated from the loaded MySQL 8 model.\n\n'+'\n\n'.join(ddl))
    report={'passed':all(checks.values()),'checks':checks,'sql_questions':len(results),'analytical_recorded_value_minor':int(python.amount_minor.sum())}
    (ROOT/'reports/validation.json').write_text(json.dumps(report,indent=2))
    (ROOT/'reports/business_results.json').write_text(json.dumps(results,indent=2))
    assert report['passed'],report
    charts(results)
    print(json.dumps({'validation':report,'overview':results['overview'],'comparison':results['comparable_may_june']},indent=2))

def charts(r):
    folder=ROOT/'reports/figures';folder.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','figure.facecolor':'#f6f8fc','axes.facecolor':'#f6f8fc','axes.labelcolor':'#334155','text.color':'#10243a'})
    for name,col,label,title in [('category_performance','category','Category','Shipped sales value by category'),('state_performance','ship_state','State','Top 10 states by shipped sales value')]:
        d=pd.DataFrame(r[name]).head(10).sort_values('shipped_value')
        fig,ax=plt.subplots(figsize=(11,6));ax.barh(d[col],d.shipped_value/1e6,color='#008f8c');ax.set_xlabel('INR millions');ax.set_title(title,loc='left',pad=20)
        fig.text(.01,.01,'Valued shipped lines • 31 Mar–29 Jun 2022 • six duplicate copies excluded',fontsize=9,color='#64748b');fig.tight_layout(rect=(0,.04,1,1));fig.savefig(folder/f'{name}.png',dpi=160);plt.close(fig)
    d=pd.DataFrame(r['daily_running_value']);d.order_date=pd.to_datetime(d.order_date)
    fig,ax=plt.subplots(figsize=(12,5));ax.plot(d.order_date,d.shipped_value/1e6,color='#90b7bb',linewidth=1);ax.plot(d.order_date,d.trailing_7_observed_day_average/1e6,color='#008f8c',linewidth=2.5,label='7 observed-day average');ax.set(title='Daily shipped sales value',ylabel='INR millions');ax.legend(frameon=False);fig.tight_layout();fig.savefig(folder/'daily_trend.png',dpi=160);plt.close(fig)
    d=pd.DataFrame(r['fulfillment_operations']);fig,ax=plt.subplots(figsize=(8,5));bars=ax.bar(d.fulfillment,d.cancelled_line_pct,color=['#008f8c','#e4a43a']);ax.bar_label(bars,fmt='%.1f%%',padding=3);ax.set(title='Cancelled-line rate by fulfillment',ylabel='Percent of observed lines');ax.set_ylim(0,d.cancelled_line_pct.max()*1.2);fig.tight_layout();fig.savefig(folder/'fulfillment_cancellations.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
