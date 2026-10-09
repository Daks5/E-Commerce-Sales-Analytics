"""Load preserved raw sources and cleaned star tables into the project-only database."""
from pathlib import Path
import json, re, hashlib
import pandas as pd
from sqlalchemy import create_engine, text, URL, types, inspect
from profile_data import read_csv

ROOT = Path(__file__).resolve().parents[1]

def engine():
    values = dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if line and not line.startswith('#'))
    return create_engine(URL.create('mysql+pymysql', username=values['MYSQL_USER'], password=values['MYSQL_PASSWORD'], host=values['MYSQL_HOST'], port=int(values['MYSQL_PORT']), database=values['MYSQL_DATABASE']), hide_parameters=True, pool_pre_ping=True)

def sql_name(value):
    return re.sub(r'[^a-z0-9]+','_',value.strip().lower()).strip('_')

def main():
    eng=engine()
    raw_files=sorted((ROOT/'data/raw/source').glob('*.csv'))
    fingerprint=hashlib.sha256(''.join(hashlib.sha256(p.read_bytes()).hexdigest() for p in raw_files).encode()).hexdigest()
    with eng.begin() as con:
        existing=inspect(con).get_table_names()
        if existing and '_project_metadata' not in existing:
            raise RuntimeError('Database contains unmanaged tables; refusing to modify it.')
        con.execute(text('CREATE TABLE IF NOT EXISTS _project_metadata (name VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL)'))
        old=con.execute(text("SELECT value FROM _project_metadata WHERE name='source_fingerprint'")).scalar()
        if old and old != fingerprint: raise RuntimeError('Source changed; review before replacing managed data.')
        con.execute(text("INSERT INTO _project_metadata VALUES ('source_fingerprint',:v) ON DUPLICATE KEY UPDATE value=:v"),{'v':fingerprint})
    inventory=[]
    for path in raw_files:
        frame,_=read_csv(path,dtype='string')
        original=list(frame.columns)
        frame.columns=[sql_name(c) for c in original]
        assert frame.columns.is_unique
        frame.insert(0,'source_row',range(1,len(frame)+1))
        table='stg_'+sql_name(path.stem)
        load_table(eng,table,frame,'source_row',raw=True)
        inventory.append({'file':path.name,'table':table,'rows':len(frame),'column_mapping':dict(zip(original,list(frame.columns)[1:]))})
        print(f'{table}: {len(frame):,} rows verified',flush=True)
    for table,key in [('dim_date','date_key'),('dim_product','product_key'),('dim_geography','geography_key'),('dim_status','status_key'),('fact_order_lines','line_id')]:
        frame=pd.read_csv(ROOT/f'data/processed/{table}.csv',dtype={'order_id':'string','sku':'string','asin':'string','postal_code':'string','currency':'string'})
        for col in ['order_date','month_start','week_start']:
            if col in frame: frame[col]=pd.to_datetime(frame[col]).dt.date
        load_table(eng,table,frame,key)
        print(f'{table}: {len(frame):,} rows verified',flush=True)
    views='\n'.join(line for line in (ROOT/'sql/01_views.sql').read_text().splitlines() if not line.lstrip().startswith('--'))
    with eng.begin() as con:
        for statement in views.split(';'):
            if statement.strip(): con.execute(text(statement))
        for col,dim in [('date_key','dim_date'),('product_key','dim_product'),('geography_key','dim_geography'),('status_key','dim_status')]:
            constraint=f'fk_fact_{col}'
            names={f['name'] for f in inspect(con).get_foreign_keys('fact_order_lines')}
            if constraint not in names:
                con.execute(text(f'ALTER TABLE fact_order_lines ADD CONSTRAINT {constraint} FOREIGN KEY ({col}) REFERENCES {dim} ({col})'))
        con.execute(text("INSERT INTO _project_metadata VALUES ('load_status','complete') ON DUPLICATE KEY UPDATE value='complete'"))
    (ROOT/'reports/sql_load_inventory.json').write_text(json.dumps(inventory,indent=2))
    # Actual SQL exports are the portable Power BI import source.
    export=ROOT/'data/powerbi'; export.mkdir(exist_ok=True)
    with eng.connect() as con:
        for table in ['dim_date','dim_product','dim_geography','dim_status','fact_order_lines']:
            query=f'SELECT * FROM {table}'+(' WHERE is_duplicate_record=0' if table=='fact_order_lines' else '')
            pd.read_sql(text(query),con).to_csv(export/f'{table}.csv',index=False)
    print('SQL exports ready for Power BI.',flush=True)

def load_table(eng,table,frame,key,raw=False):
    with eng.connect() as con:
        exists=inspect(con).has_table(table)
        if exists:
            count=con.execute(text(f'SELECT COUNT(*) FROM `{table}`')).scalar()
            if count==len(frame): return
            if count: raise RuntimeError(f'{table} incomplete ({count} rows); review before retry.')
    dtype={}
    for col in frame:
        if col==key or col in ['date_key','product_key','geography_key','status_key','amount_minor','source_index']: dtype[col]=types.BigInteger()
        elif raw: dtype[col]=types.Text(collation='utf8mb4_0900_as_cs')
        elif col=='amount': dtype[col]=types.Numeric(12,2)
        elif col in ['order_date','month_start','week_start']: dtype[col]=types.Date()
        elif pd.api.types.is_integer_dtype(frame[col]): dtype[col]=types.Integer()
        elif col=='postal_code': dtype[col]=types.String(6,collation='utf8mb4_0900_as_cs')
        else: dtype[col]=types.String(max(32,int(frame[col].astype('string').str.len().max() or 0)),collation='utf8mb4_0900_as_cs')
    with eng.begin() as con:
        frame.head(0).to_sql(table,con,if_exists='append' if exists else 'fail',index=False,dtype=dtype)
        if not exists: con.execute(text(f'ALTER TABLE `{table}` ADD PRIMARY KEY (`{key}`)'))
        frame.to_sql(table,con,if_exists='append',index=False,dtype=dtype,chunksize=1000,method='multi')
        assert con.execute(text(f'SELECT COUNT(*) FROM `{table}`')).scalar()==len(frame)

if __name__=='__main__': main()
