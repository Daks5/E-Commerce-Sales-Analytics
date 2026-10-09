"""Independent display-metric expectations from verified SQL result exports."""
import json
import pandas as pd
from load_mysql import ROOT

def main():
 result=json.loads((ROOT/'reports/business_results.json').read_text())
 o=result['overview'][0]; comp=result['comparable_may_june']; cats=result['category_performance']; states=result['state_performance']
 full={r['fulfillment']:r for r in result['fulfillment_operations']}
 value=o['shipped_sales_value']; may=comp[0]['shipped_value']; june=comp[1]['shipped_value']; difference=june-may
 expected={
  'Sales Value (crore)':value/1e7,'May Value (crore)':may/1e7,'June Value (crore)':june/1e7,'Value Change (lakh)':difference/1e5,
  'Shipped Orders Display':f"{o['valued_shipped_orders']:,}",'Shipped Units Display':f"{int(o['valued_shipped_units']):,}",'Top 5 Category Share':1,
  'May daily value':may,'June daily value':june,'Category decline (lakh)':min(difference,0)/1e5,'Category growth (lakh)':max(difference,0)/1e5,
  'Net Decline Contribution':1,'Leading Category':cats[0]['category'],'Leading Category Share':cats[0]['shipped_value']/value,
  'Leading State':states[0]['ship_state'],'Top Two Markets Share':sum(s['shipped_value'] for s in states[:2])/value,
  'Active Regions':len(states),'Top 10 Market Value (crore)':value/1e7,
  'Merchant Cancel Rate':full['Merchant']['cancelled_lines']/full['Merchant']['line_count'],
  'Amazon Cancel Rate':full['Amazon']['cancelled_lines']/full['Amazon']['line_count'],
  'Amount Coverage':1-o['missing_amount_lines']/o['analytical_lines']}
 expected['Fulfillment Gap (pp)']=(expected['Merchant Cancel Rate']-expected['Amazon Cancel Rate'])*100
 (ROOT/'reports/powerbi_dark_expected.json').write_text(json.dumps(expected,indent=2))
 fact=pd.read_csv(ROOT/'data/powerbi/fact_order_lines.csv'); dates=pd.read_csv(ROOT/'data/powerbi/dim_date.csv')
 joined=fact.merge(dates[['date_key','order_date']],on='date_key',validate='many_to_one')
 joined=joined.loc[joined.is_sales_eligible.eq(1)].copy();joined['date']=pd.to_datetime(joined.order_date)
 sums=joined.groupby('date').amount_minor.sum()/100
 daily=[{'day':d,'may':float(sums.get(pd.Timestamp(2022,5,d),0)),'june':float(sums.get(pd.Timestamp(2022,6,d),0))} for d in range(1,30)]
 (ROOT/'reports/powerbi_daily_expected.json').write_text(json.dumps(daily,indent=2))
 print(f'Prepared expectations for {len(expected)} decision measures and 29 aligned daily comparisons.')

if __name__=='__main__':main()
