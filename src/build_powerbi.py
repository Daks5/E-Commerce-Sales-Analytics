"""Generate an editable native Power BI project using Microsoft's documented PBIR format."""
from pathlib import Path
import json,csv,uuid
from load_mysql import ROOT

OUT=ROOT/'powerbi'; REPORT=OUT/'SalesAnalytics.Report'; MODEL=OUT/'SalesAnalytics.SemanticModel'
SCHEMA='https://developer.microsoft.com/json-schemas/fabric/item/report/definition/'
MEASURES={
 'Observed Lines':('COUNTROWS(Sales)','#,0'),
 'Observed Orders':('DISTINCTCOUNT(Sales[order_id])','#,0'),
 'Shipped Sales Value':('CALCULATE(SUM(Sales[amount_minor]), Sales[is_sales_eligible] = 1) / 100','₹#,0.00'),
 'Valued Shipped Orders':('CALCULATE(DISTINCTCOUNT(Sales[order_id]), Sales[is_sales_eligible] = 1)','#,0'),
 'Valued Shipped Units':('CALCULATE(SUM(Sales[quantity]), Sales[is_sales_eligible] = 1)','#,0'),
 'Complete Valued Orders':('CALCULATE([Valued Shipped Orders], Sales[order_valuation_complete] = 1)','#,0'),
 'Complete Order Value':('CALCULATE([Shipped Sales Value], Sales[order_valuation_complete] = 1)','₹#,0.00'),
 'Complete Order AOV':('DIVIDE([Complete Order Value], [Complete Valued Orders])','₹#,0.00'),
 'Cancelled Lines':('CALCULATE(COUNTROWS(Sales), \'Status\'[status] = "Cancelled")','#,0'),
 'Cancelled Line Rate':('DIVIDE([Cancelled Lines], [Observed Lines])','0.0%'),
 'Returned Lines':('CALCULATE(COUNTROWS(Sales), \'Status\'[status_group] = "Returned or returning")','#,0'),
 'Returned Line Rate':('DIVIDE([Returned Lines], [Observed Lines])','0.0%'),
 'Missing Amount Lines':('SUM(Sales[amount_missing])','#,0'),
 'Missing Amount Rate':('DIVIDE([Missing Amount Lines], [Observed Lines])','0.0%'),
 'Unvalued Shipped Lines':('SUM(Sales[is_unvalued_shipped])','#,0'),
 'Courier Conflict Lines':('SUM(Sales[status_courier_conflict])','#,0'),
 'Recorded Amount':('SUM(Sales[amount_minor]) / 100','₹#,0.00'),
 'May 1-29 Value':('CALCULATE([Shipped Sales Value], REMOVEFILTERS(\'Date\'), \'Date\'[order_date] >= DATE(2022,5,1), \'Date\'[order_date] <= DATE(2022,5,29))','₹#,0.00'),
 'June 1-29 Value':('CALCULATE([Shipped Sales Value], REMOVEFILTERS(\'Date\'), \'Date\'[order_date] >= DATE(2022,6,1), \'Date\'[order_date] <= DATE(2022,6,29))','₹#,0.00'),
 'Comparable Value Change':('[June 1-29 Value] - [May 1-29 Value]','₹#,0.00'),
 'Comparable Value Change Rate':('DIVIDE([Comparable Value Change], [May 1-29 Value])','0.0%'),
 'Product Value Share':('DIVIDE([Shipped Sales Value], CALCULATE([Shipped Sales Value], REMOVEFILTERS(Product)))','0.0%'),
 'Cumulative Shipped Value':('VAR LastObservedDate = MAX(\'Date\'[order_date]) RETURN CALCULATE([Shipped Sales Value], FILTER(ALLSELECTED(\'Date\'[order_date]), \'Date\'[order_date] <= LastObservedDate))','₹#,0.00'),
}

def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')

def lit(v):
 return {'expr':{'Literal':{'Value':('true' if v is True else 'false' if v is False else str(v)+'D' if isinstance(v,(float,int)) else "'"+str(v).replace("'","''")+"'")}}}
def color(v):return {'solid':{'color':lit(v)}}
def obj(**kwargs):return [{'properties':kwargs}]

def model():
 tables=[]
 for name,file,key in [('Sales','fact_order_lines','line_id'),('Date','dim_date','date_key'),('Product','dim_product','product_key'),('Geography','dim_geography','geography_key'),('Status','dim_status','status_key')]:
  rows=list(csv.DictReader((ROOT/f'data/powerbi/{file}.csv').open(encoding='utf-8')))
  cols=[];mtypes=[]
  for col in rows[0]:
   values=[r[col] for r in rows if r[col]]
   typ='dateTime' if col in ['order_date','month_start','week_start'] else 'int64' if col in ['line_id','source_index','date_key','product_key','geography_key','status_key','amount_minor','quantity','year','month_number','day_of_month','asin_count'] or col.startswith('is_') or col in ['has_promotion','amount_missing','zero_quantity','order_valuation_complete','status_courier_conflict','geography_missing'] else 'decimal' if col=='amount' else 'string'
   definition={'name':col,'dataType':typ,'sourceColumn':col,'summarizeBy':'none','isHidden':col.endswith('_key') or (name=='Sales' and col not in ['fulfillment','sales_channel','shipping_service','is_b2b','has_promotion','order_id'])}
   if col==key:definition['isKey']=True
   if typ=='dateTime':definition['formatString']='dd MMM yyyy'
   if col=='month_label':definition['sortByColumn']='month_key'
   cols.append(definition)
   mtypes.append('{"'+col+'", '+('type date' if typ=='dateTime' else 'Int64.Type' if typ=='int64' else 'Currency.Type' if typ=='decimal' else 'type text')+'}')
  expression=['let',f'    Source = Csv.Document(File.Contents(ProjectRoot & "/data/powerbi/{file}.csv"), [Delimiter=",", Columns={len(cols)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),','    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),','    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),','    Typed = Table.TransformColumnTypes(EmptyAsNull, {'+', '.join(mtypes)+'}, "en-US")','in','    Typed']
  t={'name':name,'columns':cols,'partitions':[{'name':name,'mode':'import','source':{'type':'m','expression':expression}}]}
  if name=='Sales':t['measures']=[{'name':n,'expression':e,'formatString':f,'displayFolder':'Sales' if 'Value' in n or 'AOV' in n or 'Units' in n else 'Operations & Quality','description':'See docs/metric_contract.md for inclusion rules and limitations.'} for n,(e,f) in MEASURES.items()]
  if name=='Date':t['annotations']=[{'name':'PBI_Id','value':str(uuid.uuid4())}]
  tables.append(t)
 relationships=[{'name':str(uuid.uuid5(uuid.NAMESPACE_URL,'ecommerce/'+dim)),'fromTable':'Sales','fromColumn':key,'toTable':dim,'toColumn':key,'crossFilteringBehavior':'oneDirection','fromCardinality':'many','toCardinality':'one'} for dim,key in [('Date','date_key'),('Product','product_key'),('Geography','geography_key'),('Status','status_key')]]
 data={'name':'ECommerce','compatibilityLevel':1601,'model':{'culture':'en-US','defaultPowerBIDataSourceVersion':'powerBI_V3','sourceQueryCulture':'en-US','expressions':[{'name':'ProjectRoot','kind':'m','expression':'"'+ROOT.as_posix()+'" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}],'tables':tables,'relationships':relationships,'annotations':[{'name':'PBI_QueryOrder','value':json.dumps(['ProjectRoot','Sales','Date','Product','Geography','Status'])}]}}
 write(MODEL/'model.bim',data)
 write(MODEL/'definition.pbism',{'version':'4.0','settings':{}})
 (OUT/'measures.dax').write_text('\n\n'.join(n+' =\n'+e for n,(e,f) in MEASURES.items()),encoding='utf-8')

def field(table,name,measure=False):return {('Measure' if measure else 'Column'):{'Expression':{'SourceRef':{'Entity':table}},'Property':name}}
def projection(table,name,measure=False):return {'field':field(table,name,measure),'queryRef':table+'.'+name,'nativeQueryRef':name}

def visual(page,name,kind,title,x,y,w,h,roles=None,sort=None,objects=None):
 v={'visualType':kind,'drillFilterOtherVisuals':True,'visualContainerObjects':{
 'title':obj(show=lit(bool(title)),text=lit(title),fontSize=lit(12),fontColor=color('#10243a'),bold=lit(True)),
 'background':obj(show=lit(True),color=color('#ffffff'),transparency=lit(0)),
 'border':obj(show=lit(True),color=color('#e2e8f0'),radius=lit(8)),
 'visualHeader':obj(show=lit(True))}}
 if roles:
  v['query']={'queryState':{role:{'projections':[projection(*p) for p in ps]} for role,ps in roles.items()}}
  if sort:v['query']['sortDefinition']={'sort':[{'field':field(*sort[:3]),'direction':sort[3]}],'isDefaultSort':False}
 if objects:v['objects']=objects
 d={'$schema':SCHEMA+'visualContainer/2.1.0/schema.json','name':name,'position':{'x':x,'y':y,'width':w,'height':h,'z':y,'tabOrder':y},'visual':v}
 write(REPORT/f'definition/pages/{page}/visuals/{name}/visual.json',d)
 return d

def textbox(page,name,text,x,y,w,h,size=14,fg='#64748b',bg='#f6f8fc'):
 d=visual(page,name,'textbox','',x,y,w,h,objects={'general':obj(paragraphs=[{'textRuns':[{'value':text,'textStyle':{'fontSize':str(size)+'pt','fontFamily':'Segoe UI','color':fg}}]}])})
 d['visual']['visualContainerObjects']['background']=obj(show=lit(True),color=color(bg),transparency=lit(0))
 d['visual']['visualContainerObjects']['border']=obj(show=lit(False))
 write(REPORT/f'definition/pages/{page}/visuals/{name}/visual.json',d)

def main():
 model()
 write(OUT/'SalesAnalytics.pbip',{'version':'1.0','artifacts':[{'report':{'path':'SalesAnalytics.Report'}}],'settings':{'enableAutoRecovery':True}})
 write(REPORT/'definition.pbir',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':'../SalesAnalytics.SemanticModel'}}})
 write(REPORT/'definition/version.json',{'$schema':SCHEMA+'versionMetadata/1.0.0/schema.json','version':'2.0.0'})
 for folder,kind in [(REPORT,'Report'),(MODEL,'SemanticModel')]:
  write(folder/'.platform',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json','metadata':{'type':kind,'displayName':'E-Commerce Sales Analytics'},'config':{'version':'2.0','logicalId':str(uuid.uuid5(uuid.NAMESPACE_URL,'local-ecommerce/'+kind))}})
 import requests
 base=REPORT/'StaticResources/SharedResources/BaseThemes/CY24SU02.json'
 if not base.exists():
  response=requests.get('https://raw.githubusercontent.com/microsoft/BCApps/main/src/Apps/W1/PowerBIReports/Power%20BI%20Files/Projects%20app/Projects%20app.Report/StaticResources/SharedResources/BaseThemes/CY24SU02.json',timeout=30);response.raise_for_status();write(base,response.json())
 custom=REPORT/'StaticResources/RegisteredResources/EcommerceTheme.json'
 write(custom,{'name':'Ecommerce Navy Teal','dataColors':['#008f8c','#10243a','#e4a43a','#7aa7b1','#59718c'],'background':'#f6f8fc','foreground':'#10243a','tableAccent':'#008f8c'})
 versions={'visual':'1.8.89','report':'2.0.89','page':'1.3.89'}
 write(REPORT/'definition/report.json',{'$schema':SCHEMA+'report/3.0.0/schema.json','themeCollection':{'baseTheme':{'name':'CY24SU02','reportVersionAtImport':versions,'type':'SharedResources'},'customTheme':{'name':'EcommerceTheme.json','reportVersionAtImport':versions,'type':'RegisteredResources'}},'resourcePackages':[{'name':'SharedResources','type':'SharedResources','items':[{'name':'CY24SU02','path':'BaseThemes/CY24SU02.json','type':'BaseTheme'}]},{'name':'RegisteredResources','type':'RegisteredResources','items':[{'name':'EcommerceTheme.json','path':'EcommerceTheme.json','type':'CustomTheme'}]}],'settings':{'useStylableVisualContainerHeader':True,'exportDataMode':'AllowSummarized','defaultDrillFilterOtherVisuals':True}})
 pages=[('Executive','Sales overview','What sold, where demand is concentrated, and how the comparable period changed.'),('Products','Product performance','Compare categories and sizes. Use the SQL SKU ranking for products with at least 30 observed lines.'),('Geography','Geographic demand','State and city demand. City and state labels are normalized; postal codes remain text.'),('Operations','Operations & data quality','Cancellation and return rates use observed lines. Associations do not establish fulfillment causality.')]
 write(REPORT/'definition/pages/pages.json',{'$schema':SCHEMA+'pagesMetadata/1.0.0/schema.json','pageOrder':[p[0] for p in pages],'activePageName':'Executive'})
 for page,title,subtitle in pages:
  write(REPORT/f'definition/pages/{page}/page.json',{'$schema':SCHEMA+'page/2.0.0/schema.json','name':page,'displayName':title,'displayOption':'FitToPage','width':1280,'height':800,'objects':{'background':obj(color=color('#f6f8fc'),transparency=lit(0))}})
  textbox(page,'Header','E-COMMERCE  /  '+title.upper(),24,16,1232,60,24,'#ffffff','#10243a')
  textbox(page,'Subtitle',subtitle,24,82,1232,40,12)
  for i,(t,c,label) in enumerate([('Date','month_key','Month'),('Product','category','Category'),('Sales','fulfillment','Fulfillment'),('Sales','is_b2b','B2B: 0 retail / 1 business')]):
   visual(page,'Filter'+str(i),'slicer',label,24+i*312,128,296,80,{'Values':[(t,c,False)]},objects={'data':obj(mode=lit('Dropdown')),'selection':obj(selectAllCheckboxEnabled=lit(True))})
  metrics=['Shipped Sales Value','Valued Shipped Orders','Complete Order AOV','Comparable Value Change Rate' if page=='Executive' else 'Cancelled Line Rate'] if page!='Operations' else ['Observed Lines','Cancelled Line Rate','Returned Line Rate','Unvalued Shipped Lines']
  for i,m in enumerate(metrics):visual(page,'KPI'+str(i),'card',m,24+i*312,224,296,112,{'Values':[('Sales',m,True)]},objects={'labels':obj(fontSize=lit(26),color=color('#008f8c')),'categoryLabels':obj(show=lit(False))})
  if page=='Executive':
   visual(page,'Trend','lineChart','Daily shipped sales value · INR',24,352,752,350,{'Category':[('Date','order_date',False)],'Y':[('Sales','Shipped Sales Value',True)]},sort=('Date','order_date',False,'Ascending'))
   visual(page,'Category','clusteredBarChart','Value by category · INR',792,352,464,350,{'Category':[('Product','category',False)],'Y':[('Sales','Shipped Sales Value',True)]},sort=('Sales','Shipped Sales Value',True,'Descending'))
   textbox(page,'PeriodNote','COMPARABLE PERIOD: SQL compares May 1–29 with June 1–29. March and June are partial calendar months.',24,710,1232,32,11)
  elif page=='Products':
   visual(page,'Category','clusteredBarChart','Value by category · INR',24,352,600,350,{'Category':[('Product','category',False)],'Y':[('Sales','Shipped Sales Value',True)]},sort=('Sales','Shipped Sales Value',True,'Descending'))
   visual(page,'Size','clusteredBarChart','Value by size · INR',640,352,616,350,{'Category':[('Product','size',False)],'Y':[('Sales','Shipped Sales Value',True)]},sort=('Sales','Shipped Sales Value',True,'Descending'))
   textbox(page,'PeriodNote','Open sql/02_business_analysis.sql for category decline contributions and ranked SKUs with a minimum volume threshold.',24,710,1232,32,11)
  elif page=='Geography':
   visual(page,'State','clusteredBarChart','State value · INR (scroll for all states)',24,352,600,350,{'Category':[('Geography','ship_state',False)],'Y':[('Sales','Shipped Sales Value',True)]},sort=('Sales','Shipped Sales Value',True,'Descending'))
   visual(page,'StateTable','tableEx','State demand and cancellation',640,352,616,350,{'Values':[('Geography','ship_state',False),('Sales','Shipped Sales Value',True),('Sales','Observed Orders',True),('Sales','Cancelled Line Rate',True)]},sort=('Sales','Shipped Sales Value',True,'Descending'))
   textbox(page,'PeriodNote','Geography reflects shipping destination. Demand alone does not establish regional profitability.',24,710,1232,32,11)
  else:
   visual(page,'Fulfillment','clusteredBarChart','Cancelled-line rate by fulfillment',24,352,600,350,{'Category':[('Sales','fulfillment',False)],'Y':[('Sales','Cancelled Line Rate',True)]},sort=('Sales','Cancelled Line Rate',True,'Descending'))
   visual(page,'Status','tableEx','Status distribution and recorded amount',640,352,616,350,{'Values':[('Status','status',False),('Sales','Observed Lines',True),('Sales','Recorded Amount',True),('Sales','Missing Amount Lines',True)]},sort=('Sales','Observed Lines',True,'Descending'))
   textbox(page,'PeriodNote','Recorded amount includes non-shipped statuses. It is a source-data total, not realized revenue or cancellation loss.',24,710,1232,32,11)
  textbox(page,'Footer','31 MAR–29 JUN 2022  •  INR  •  Valued shipped lines  •  Six duplicate copies excluded  •  Profit and refunds unavailable',24,752,1232,28,10)
 write(OUT/'theme.json',{'name':'Ecommerce Navy Teal','dataColors':['#008f8c','#10243a','#e4a43a','#7aa7b1','#59718c'],'background':'#f6f8fc','foreground':'#10243a','tableAccent':'#008f8c'})
 validate()
 print('Created native Power BI project: four pages, 23 explicit DAX measures, five tables, four relationships.')

def validate():
 import jsonschema
 cache=ROOT/'.setup/schemas/schema_store.json'
 if not cache.exists() or SCHEMA+'report/3.0.0/schema.json' not in json.loads(cache.read_text()):
  from fetch_powerbi_schemas import fetch
  fetch()
 store=json.loads(cache.read_text())
 checked=0
 for path in (REPORT/'definition').rglob('*.json'):
  d=json.loads(path.read_text(encoding='utf-8'));u=d['$schema'];schema=store[u]
  resolver=jsonschema.RefResolver(base_uri=u,referrer=schema,store=store)
  jsonschema.Draft7Validator(schema,resolver=resolver).validate(d);checked+=1
 write(ROOT/'reports/powerbi_schema_validation.json',{'passed':True,'files_validated':checked,'pages':4,'measures':len(MEASURES),'native_desktop_validation':'pending'})

if __name__=='__main__':main()
