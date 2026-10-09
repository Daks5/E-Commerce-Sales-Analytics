"""Reproducible cleaning and a star model, with preserved source-row lineage."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pandas as pd
from profile_data import read_csv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'processed'
SHIPPED = {'Shipped','Shipped - Delivered to Buyer','Shipped - Picked Up','Shipped - Out for Delivery'}
RETURNED = {'Shipped - Returned to Seller','Shipped - Returning to Seller'}
EXCEPTIONS = {'Shipped - Rejected by Buyer','Shipped - Lost in Transit','Shipped - Damaged'}
ALIASES = {
    'NEW DELHI':'DELHI','RAJSHTHAN':'RAJASTHAN','RAJSTHAN':'RAJASTHAN','RJ':'RAJASTHAN',
    'ORISSA':'ODISHA','PONDICHERRY':'PUDUCHERRY','PUNJAB/MOHALI/ZIRAKPUR':'PUNJAB',
    'NL':'NAGALAND','PB':'PUNJAB','AR':'ARUNACHAL PRADESH',
}

def normalize(s, upper=False):
    s=s.astype('string').str.strip().str.replace(r'\s+',' ',regex=True).replace('',pd.NA)
    return s.str.upper() if upper else s

def money_sum(s):
    return int(s.dropna().sum())

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    path=ROOT/'data/raw/source/Amazon Sale Report.csv'
    raw,_=read_csv(path,dtype='string')
    raw.columns=raw.columns.str.strip()
    business=[c for c in raw.columns if c not in ('index','Unnamed: 22')]
    duplicate=raw.duplicated(business,keep='first')
    d=pd.DataFrame(index=raw.index)
    d['line_id']=pd.to_numeric(raw['index'],errors='raise').astype('int64')+1
    d['source_index']=d.line_id-1
    d['order_id']=normalize(raw['Order ID'])
    dates=pd.to_datetime(raw.Date,format='%m-%d-%y',errors='raise')
    d['order_date']=dates.dt.strftime('%Y-%m-%d')
    d['date_key']=dates.dt.strftime('%Y%m%d').astype('int64')
    d['status']=normalize(raw.Status)
    groups={s:('Shipped' if s in SHIPPED else 'Cancelled' if s=='Cancelled' else 'Returned or returning' if s in RETURNED else 'Exception' if s in EXCEPTIONS else 'Pending' if s.startswith('Pending') else 'Shipping' if s=='Shipping' else 'Unmapped') for s in d.status.unique()}
    d['status_group']=d.status.map(groups)
    for original,target in [('Fulfilment','fulfillment'),('Sales Channel','sales_channel'),('ship-service-level','shipping_service'),('Style','style'),('SKU','sku'),('Category','category'),('Size','size'),('ASIN','asin')]:
        d[target]=normalize(raw[original])
    d['category']=d.category.replace({'kurta':'Kurta'})
    d['courier_status']=normalize(raw['Courier Status']).fillna('Unknown')
    d['quantity']=pd.to_numeric(raw.Qty,errors='raise').astype('int64')
    d['currency']=normalize(raw.currency,upper=True)
    amount=pd.to_numeric(raw.Amount,errors='raise')
    d['amount_minor']=(amount*100).round().astype('Int64')
    d['amount']=d.amount_minor.astype('Float64')/100
    d['ship_city_raw']=raw['ship-city']
    d['ship_state_raw']=raw['ship-state']
    d['ship_city']=normalize(raw['ship-city'],upper=True).fillna('Unknown')
    d['ship_state']=normalize(raw['ship-state'],upper=True).replace(ALIASES).fillna('Unknown').replace({'APO':'Unmapped (APO)'})
    d['postal_code']=normalize(raw['ship-postal-code']).str.replace(r'\.0$','',regex=True)
    d['country']=normalize(raw['ship-country'],upper=True).fillna('Unknown')
    d['is_b2b']=normalize(raw.B2B,upper=True).map({'TRUE':1,'FALSE':0}).astype('int64')
    d['has_promotion']=normalize(raw['promotion-ids']).notna().astype('int64')
    d['fulfilled_by']=normalize(raw['fulfilled-by'])
    d['is_duplicate_record']=duplicate.astype('int64')
    d['amount_missing']=d.amount_minor.isna().astype('int64')
    d['zero_quantity']=d.quantity.eq(0).astype('int64')
    d['is_cancelled']=d.status.eq('Cancelled').astype('int64')
    d['is_returned']=d.status.isin(RETURNED).astype('int64')
    d['is_shipped_status']=d.status.isin(SHIPPED).astype('int64')
    d['is_sales_eligible']=(d.is_shipped_status.eq(1)&d.quantity.gt(0)&d.amount_minor.notna()&d.amount_minor.ge(0)&d.currency.eq('INR')).astype('int64')
    d['is_unvalued_shipped']=(d.is_shipped_status.eq(1)&d.quantity.gt(0)&~d.is_sales_eligible.eq(1)).astype('int64')
    d['status_courier_conflict']=((d.is_cancelled.eq(1)&d.courier_status.eq('Shipped'))|(d.is_shipped_status.eq(1)&d.courier_status.eq('Cancelled'))).astype('int64')
    d['geography_missing']=d.ship_state.eq('Unknown').astype('int64')
    observed=d.loc[d.is_duplicate_record.eq(0)]
    unvalued=observed.groupby('order_id').is_unvalued_shipped.max()
    d['order_valuation_complete']=d.order_id.map(unvalued).eq(0).astype('int64')
    assert d.line_id.is_unique and d.order_id.notna().all()
    assert d.quantity.ge(0).all() and d.amount_minor.dropna().ge(0).all()
    assert d.postal_code.dropna().str.fullmatch(r'\d{6}').all()
    assert d.groupby('order_id').date_key.nunique().max()==1
    assert d.groupby('sku')[['style','category','size']].nunique().max().max()==1

    product=d[['sku','style','category','size']].drop_duplicates().sort_values('sku').reset_index(drop=True)
    product.insert(0,'product_key',range(1,len(product)+1))
    asin_counts=d.groupby('sku').asin.nunique()
    product['asin_count']=product.sku.map(asin_counts).astype('int64')
    d=d.merge(product[['sku','product_key']],on='sku',validate='many_to_one')
    geo_fields=['ship_city','ship_state','postal_code','country']
    geo=d[geo_fields].drop_duplicates().sort_values(geo_fields,na_position='last').reset_index(drop=True)
    geo.insert(0,'geography_key',range(1,len(geo)+1))
    d=d.merge(geo,on=geo_fields,validate='many_to_one')
    status=d[['status','status_group']].drop_duplicates().sort_values('status').reset_index(drop=True)
    status.insert(0,'status_key',range(1,len(status)+1))
    d=d.merge(status[['status','status_key']],on='status',validate='many_to_one')
    calendar=pd.DataFrame({'order_date':pd.date_range(f'{dates.min().year}-01-01',f'{dates.max().year}-12-31')})
    calendar['date_key']=calendar.order_date.dt.strftime('%Y%m%d').astype('int64')
    calendar['year']=calendar.order_date.dt.year
    calendar['month_number']=calendar.order_date.dt.month
    calendar['month_key']=calendar.order_date.dt.strftime('%Y-%m')
    calendar['month_start']=calendar.order_date.dt.to_period('M').dt.to_timestamp()
    calendar['month_label']=calendar.order_date.dt.strftime('%b %Y')
    calendar['day_of_month']=calendar.order_date.dt.day
    calendar['day_name']=calendar.order_date.dt.day_name()
    calendar['week_start']=calendar.order_date-pd.to_timedelta(calendar.order_date.dt.weekday,unit='D')
    calendar['is_observed_date']=calendar.order_date.between(dates.min(),dates.max()).astype('int64')
    coverage=observed.assign(month=observed.order_date.str[:7]).groupby('month').agg(first_date=('order_date','min'),last_date=('order_date','max'),days=('order_date','nunique'))
    complete={m:int(r['first_date'].endswith('-01') and pd.Timestamp(r['last_date']).day==pd.Timestamp(r['last_date']).days_in_month and r['days']==pd.Timestamp(r['last_date']).days_in_month) for m,r in coverage.iterrows()}
    calendar['is_complete_month']=calendar.month_key.map(complete).fillna(0).astype('int64')
    for col in ('order_date','month_start','week_start'):
        calendar[col]=calendar[col].dt.strftime('%Y-%m-%d')
    d=d.sort_values('line_id').reset_index(drop=True)
    fact_columns=['line_id','source_index','order_id','date_key','product_key','geography_key','status_key','fulfillment','sales_channel','shipping_service','courier_status','asin','quantity','currency','amount','amount_minor','is_b2b','has_promotion','fulfilled_by','is_duplicate_record','amount_missing','zero_quantity','is_sales_eligible','is_unvalued_shipped','order_valuation_complete','status_courier_conflict','geography_missing']
    fact=d[fact_columns]
    frames={'cleaned_order_lines':d,'analytical_order_lines':d.loc[d.is_duplicate_record.eq(0)],'fact_order_lines':fact,'dim_product':product,'dim_geography':geo,'dim_status':status,'dim_date':calendar}
    for name,frame in frames.items():
        frame.to_csv(OUT/f'{name}.csv',index=False,encoding='utf-8',float_format='%.2f')
    d.loc[d.is_duplicate_record.eq(1),['line_id','source_index','order_id','sku','order_date','status','quantity','amount']].to_csv(ROOT/'reports/flagged_duplicate_records.csv',index=False)
    pd.DataFrame([{'original':k,'canonical':v} for k,v in sorted(ALIASES.items())]).to_csv(ROOT/'docs/state_aliases.csv',index=False)
    report={
      'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'raw_rows':len(raw),'cleaned_rows':len(d),'analytical_rows':int(d.is_duplicate_record.eq(0).sum()),
      'distinct_orders':int(d.order_id.nunique()),'flagged_duplicate_rows':int(d.is_duplicate_record.sum()),'duplicate_recorded_amount_minor':money_sum(d.loc[d.is_duplicate_record.eq(1),'amount_minor']),
      'raw_recorded_amount_minor':money_sum(d.amount_minor),'analytical_recorded_amount_minor':money_sum(d.loc[d.is_duplicate_record.eq(0),'amount_minor']),
      'missing_amounts':int(d.amount_missing.sum()),'zero_amounts':int(d.amount_minor.eq(0).sum()),'zero_quantities':int(d.zero_quantity.sum()),
      'unvalued_positive_shipped_lines':int(d.loc[d.is_duplicate_record.eq(0)].is_unvalued_shipped.sum()),'orders_with_unvalued_shipped_lines':int(unvalued.sum()),
      'state_labels_before':int(raw['ship-state'].nunique()),'state_labels_after':int(d.ship_state.nunique()),'geography_missing':int(d.geography_missing.sum()),
      'status_courier_conflicts':int(d.status_courier_conflict.sum()),'sku_asin_conflicts':int(product.asin_count.gt(1).sum()),
      'date_min':str(dates.min().date()),'date_max':str(dates.max().date()),'month_coverage':coverage.reset_index().to_dict('records'),
      'dimension_rows':{k:len(v) for k,v in frames.items() if k.startswith('dim_')},
      'complete_months':[k for k,v in complete.items() if v],
    }
    (ROOT/'reports/cleaning_summary.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps(report,indent=2,default=str))

if __name__=='__main__':
    main()
