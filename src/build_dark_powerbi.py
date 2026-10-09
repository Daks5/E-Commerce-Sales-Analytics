"""Build Commerce Pulse: a dark, decision-oriented native Power BI report."""
import csv
import json
import uuid
import build_powerbi as base
from load_mysql import ROOT

OUT = ROOT / 'powerbi'
REPORT = OUT / 'CommercePulse.Report'
MODEL = OUT / 'CommercePulse.SemanticModel'
BG, RAIL, PANEL = '#0B1322', '#0F1D30', '#14243A'
TEXT, MUTED, GRID = '#F3F7FC', '#9CADC5', '#253750'
MINT, AMBER, CORAL = '#3DE2C4', '#F6BD60', '#FF708B'
SCHEMA = base.SCHEMA
write, lit, color, obj = base.write, base.lit, base.color, base.obj

EXTRA = {
 'Sales Value (crore)':('[Shipped Sales Value] / 10000000', '₹0.00" Cr"'),
 'Shipped Orders Display':('FORMAT([Valued Shipped Orders], "#,0")', ''),
 'Shipped Units Display':('FORMAT([Valued Shipped Units], "#,0")', ''),
 'Top 5 Category Share':('VAR Position = RANKX(ALLSELECTED(Product[category]), [Shipped Sales Value], , DESC, DENSE) RETURN IF(Position <= 5, [Product Value Share])', '0.0%'),
 'May Value (crore)':('[May 1-29 Value] / 10000000', '₹0.00" Cr"'),
 'June Value (crore)':('[June 1-29 Value] / 10000000', '₹0.00" Cr"'),
 'Value Change (lakh)':('[Comparable Value Change] / 100000', '+₹0.00" L";-₹0.00" L";₹0.00" L"'),
 'May daily value':('VAR SelectedDays = VALUES(\'Date\'[day_of_month]) RETURN CALCULATE([Shipped Sales Value], REMOVEFILTERS(\'Date\'), \'Date\'[year] = 2022, \'Date\'[month_number] = 5, \'Date\'[day_of_month] <= 29, TREATAS(SelectedDays, \'Date\'[day_of_month]))', '₹#,0'),
 'June daily value':('VAR SelectedDays = VALUES(\'Date\'[day_of_month]) RETURN CALCULATE([Shipped Sales Value], REMOVEFILTERS(\'Date\'), \'Date\'[year] = 2022, \'Date\'[month_number] = 6, \'Date\'[day_of_month] <= 29, TREATAS(SelectedDays, \'Date\'[day_of_month]))', '₹#,0'),
 'Category decline (lakh)':('VAR Change = [Comparable Value Change] RETURN IF(ISINSCOPE(Product[category]), IF(Change < 0, Change / 100000), MIN(Change, 0) / 100000)', '₹0.00" L"'),
 'Category growth (lakh)':('VAR Change = [Comparable Value Change] RETURN IF(ISINSCOPE(Product[category]), IF(Change > 0, Change / 100000), MAX(Change, 0) / 100000)', '₹0.00" L"'),
 'Net Decline Contribution':('DIVIDE([Comparable Value Change], CALCULATE([Comparable Value Change], REMOVEFILTERS(Product)))', '0.0%'),
 'Leading Category':('VAR Leaders = TOPN(1, ADDCOLUMNS(VALUES(Product[category]), "Value", [Shipped Sales Value]), [Value], DESC, Product[category], ASC) RETURN CONCATENATEX(Leaders, Product[category], ", ")', ''),
 'Leading Category Share':('VAR Leaders = TOPN(1, ADDCOLUMNS(VALUES(Product[category]), "Value", [Shipped Sales Value]), [Value], DESC, Product[category], ASC) RETURN DIVIDE(SUMX(Leaders, [Value]), [Shipped Sales Value])', '0.0%'),
 'Leading State':('VAR Leaders = TOPN(1, ADDCOLUMNS(VALUES(Geography[ship_state]), "Value", [Shipped Sales Value]), [Value], DESC, Geography[ship_state], ASC) RETURN CONCATENATEX(Leaders, Geography[ship_state], ", ")', ''),
 'Top Two Markets Share':('VAR Leaders = TOPN(2, ADDCOLUMNS(VALUES(Geography[ship_state]), "Value", [Shipped Sales Value]), [Value], DESC, Geography[ship_state], ASC) RETURN DIVIDE(SUMX(Leaders, [Value]), [Shipped Sales Value])', '0.0%'),
 'Active Regions':('COUNTROWS(FILTER(VALUES(Geography[ship_state]), [Observed Lines] > 0))', '#,0'),
 'Top 10 Market Value (crore)':('VAR Position = RANKX(ALLSELECTED(Geography[ship_state]), [Shipped Sales Value], , DESC, DENSE) RETURN IF(Position <= 10, [Sales Value (crore)])', '₹0.00" Cr"'),
 'Merchant Cancel Rate':('CALCULATE([Cancelled Line Rate], REMOVEFILTERS(Sales[fulfillment]), Sales[fulfillment] = "Merchant")', '0.00%'),
 'Amazon Cancel Rate':('CALCULATE([Cancelled Line Rate], REMOVEFILTERS(Sales[fulfillment]), Sales[fulfillment] = "Amazon")', '0.00%'),
 'Fulfillment Gap (pp)':('([Merchant Cancel Rate] - [Amazon Cancel Rate]) * 100', '0.00" pp"'),
 'Amount Coverage':('1 - [Missing Amount Rate]', '0.0%'),
}

def save_visual(page, name, data):
 write(REPORT / f'definition/pages/{page}/visuals/{name}/visual.json', data)

def visual(page, name, kind, x, y, w, h, roles=None, title='', objects=None, bg=PANEL, z=10, aliases=None, sort=None):
 v = {'visualType':kind, 'drillFilterOtherVisuals':True,
      'visualContainerObjects':{
       'title':obj(show=lit(bool(title)), text=lit(title), fontSize=lit(12), fontColor=color(TEXT), fontFamily=lit('Segoe UI Semibold'), alignment=lit('left')),
       'background':obj(show=lit(True), color=color(bg), transparency=lit(0)),
       'border':obj(show=lit(False)),
       'visualHeader':obj(show=lit(False))}}
 if roles:
  v['query']={'queryState':{role:{'projections':[base.projection(*p) for p in ps]} for role,ps in roles.items()}}
  if aliases:
   for role in v['query']['queryState'].values():
    for projection in role['projections']:
     if projection['queryRef'] in aliases: projection['displayName']=aliases[projection['queryRef']]
  if sort: v['query']['sortDefinition']={'sort':[{'field':base.field(*sort[:3]), 'direction':sort[3]}], 'isDefaultSort':False}
 if objects: v['objects']=objects
 data={'$schema':SCHEMA+'visualContainer/2.1.0/schema.json', 'name':name,
       'position':{'x':x,'y':y,'width':w,'height':h,'z':z,'tabOrder':y*10+x}, 'visual':v}
 save_visual(page,name,data)
 return data

def text(page,name,value,x,y,w,h,size=12,fg=MUTED,bg=BG,weight=False,z=20):
 data=visual(page,name,'textbox',x,y,w,h,objects={'general':obj(paragraphs=[{'textRuns':[{'value':value,'textStyle':{'fontSize':str(size)+'pt','fontFamily':'Segoe UI Semibold' if weight else 'Segoe UI','color':fg}}]}])},bg=bg,z=z)
 data['visual']['visualContainerObjects']['padding']=obj(left=lit(0),right=lit(0),top=lit(0),bottom=lit(0))
 save_visual(page,name,data)
 return data

def card(page,name,measure,label,x,y,w=286,h=112,accent=TEXT,size=32,bg=PANEL,note=None):
 text(page,name+'Label',label.upper(),x+16,y+12,w-32,23,10,MUTED,bg)
 visual(page,name,'card',x+12,y+35,w-24,h-43,{'Values':[('Sales',measure,True)]},objects={'labels':obj(fontSize=lit(size),color=color(accent),labelDisplayUnits=lit(0),displayUnits=lit(0)),'categoryLabels':obj(show=lit(False))},bg=bg)
 if note: text(page,name+'Note',note,x+16,y+h-22,w-32,22,9,MUTED,bg)
 # The panel itself sits below the label and number.
 text(page,name+'Panel','',x,y,w,h,1,fg=bg,bg=bg,z=1)

def chart(page,name,kind,title,x,y,w,h,roles,sort=None,colors=None,percent=False):
 objects={
  'categoryAxis':obj(show=lit(True),showAxisTitle=lit(False),fontSize=lit(10),fontColor=color(MUTED),labelColor=color(MUTED)),
  'valueAxis':obj(show=lit(True),showAxisTitle=lit(False),fontSize=lit(10),fontColor=color(MUTED),labelColor=color(MUTED),gridlineShow=lit(True),gridlineColor=color(GRID)),
  'legend':obj(show=lit(len(roles.get('Y',[]))>1),position=lit('Top'),fontSize=lit(10),fontColor=color(MUTED),titleShow=lit(False)),
  'labels':obj(show=lit(kind!='lineChart'),color=color(TEXT),fontSize=lit(10),labelDisplayUnits=lit(0),labelPrecision=lit(1)),
  'lineStyles':obj(strokeWidth=lit(3)),
  'plotArea':obj(transparency=lit(100)),
 }
 if colors:
  objects['dataPoint']=[{'properties':{'fill':color(c)},'selector':{'metadata':f'{t}.{m}'}} for (t,m,_),c in zip(roles['Y'],colors)]
 return visual(page,name,kind,x,y,w,h,roles,title=title,objects=objects,sort=sort)

def table(page,name,title,x,y,w,h,fields,aliases,sort):
 return visual(page,name,'tableEx',x,y,w,h,{'Values':fields},title=title,aliases=aliases,sort=sort,objects={
  'grid':obj(gridVertical=lit(False),gridHorizontal=lit(False),rowPadding=lit(2),outlineColor=color(GRID)),
  'columnHeaders':obj(fontColor=color(MUTED),backColor=color(PANEL),fontSize=lit(10),outline=lit('None'),wordWrap=lit(False)),
  'values':obj(fontColor=color(TEXT),backColor=color(PANEL),backColorSecondary=color('#192C45'),fontSize=lit(10),wordWrap=lit(False)),
  'total':obj(totals=lit(True),fontColor=color(TEXT),backColor=color('#203650'),fontSize=lit(10))})

def observed_month_filter(data):
 data['filterConfig']={'filters':[{'name':'ObservedMonths','field':base.field('Date','is_observed_date'), 'type':'Categorical',
  'filter':{'Version':2,'From':[{'Name':'d','Entity':'Date','Type':0}], 'Where':[{'Condition':{'In':{'Expressions':[{'Column':{'Expression':{'SourceRef':{'Source':'d'}},'Property':'is_observed_date'}}], 'Values':[[{'Literal':{'Value':'1L'}}]]}}}]}}]}
 return data

def frame(page,title,subtitle,number):
 write(REPORT/f'definition/pages/{page}/page.json',{'$schema':SCHEMA+'page/2.0.0/schema.json','name':page,'displayName':title,'displayOption':'FitToPage','width':1440,'height':900,'objects':{'background':obj(color=color(BG),transparency=lit(0))}})
 text(page,'Rail','',0,0,192,900,1,RAIL,RAIL,z=0)
 text(page,'Brand','COMMERCE\nPULSE',18,26,158,86,21,MINT,RAIL,True)
 text(page,'BrandSub','SALES INTELLIGENCE',20,114,152,28,9,MUTED,RAIL)
 text(page,'ScopeHeading','EXPLORE THE DATA',20,228,152,28,10,TEXT,RAIL,True)
 filters=[('Date','month_label','Reporting month'),('Product','category','Product category'),('Sales','fulfillment','Fulfillment'),('Sales','Customer Segment','Customer type')]
 for i,(table_name,column,label) in enumerate(filters):
  data=visual(page,'Filter'+str(i),'slicer',16,268+i*104,160,88,{'Values':[(table_name,column,False)]},title=label,bg=RAIL,
    aliases={table_name+'.'+column:label},objects={'data':obj(mode=lit('Dropdown')),'selection':obj(selectAllCheckboxEnabled=lit(True)),'header':obj(show=lit(False)),'items':obj(fontColor=color(TEXT),background=color(PANEL),textSize=lit(11))})
  data['visual']['syncGroup']={'groupName':'CommercePulseFilter'+str(i),'fieldChanges':True,'filterChanges':True}
  save_visual(page,'Filter'+str(i),data)
  if i==0: save_visual(page,'Filter0',observed_month_filter(data))
 text(page,'RailNote','SOURCE SNAPSHOT\n31 Mar – 29 Jun 2022\n\nCurrency: INR\nValued shipped lines\n\nSix duplicate copies\nexcluded from analysis.',20,718,152,150,10,MUTED,RAIL)
 text(page,'Title',title,216,24,760,54,30,TEXT,BG,True)
 text(page,'Subtitle',subtitle,216,80,960,26,11,MUTED)
 text(page,'PageNumber',f'0{number} / 04',1310,34,104,34,12,MINT,BG,True)
 visual(page,'Navigator','pageNavigator',212,112,1208,40,objects={
  'gridLayout':obj(orientation=lit('Horizontal'),padding=lit(8)),
  'text':[{'properties':{'fontSize':lit(11),'fontColor':color(MUTED)}},{'properties':{'fontSize':lit(11),'fontColor':color(MUTED)},'selector':{'id':'default'}},{'properties':{'fontColor':color(BG)},'selector':{'id':'selected'}}],
  'fill':[{'properties':{'show':lit(True),'fillColor':color(PANEL)}},{'properties':{'show':lit(True),'fillColor':color(PANEL)},'selector':{'id':'default'}},{'properties':{'show':lit(True),'fillColor':color(MINT)},'selector':{'id':'selected'}}],
  'outline':obj(show=lit(False))},bg=BG)
 text(page,'Footer','PUBLIC AMAZON SALES EXPORT  /  Snapshot analysis • Shipped value is not profit or collected revenue.',216,867,1198,26,9,MUTED)

def main():
 base.REPORT,base.MODEL=REPORT,MODEL
 base.model()
 data=json.loads((MODEL/'model.bim').read_text(encoding='utf-8'))
 sales=next(t for t in data['model']['tables'] if t['name']=='Sales')
 sales['measures'] += [{'name':n,'expression':e,'formatString':f,'displayFolder':'Dashboard • Decision Metrics','description':'Filter-aware display or decision measure. See docs/metric_contract.md and docs/dashboard_redesign.md.'} for n,(e,f) in EXTRA.items()]
 sales['columns'].append({'name':'Customer Segment','dataType':'string','type':'calculated','expression':'IF(Sales[is_b2b] = 1, "Business (B2B)", "Retail")','summarizeBy':'none'})
 write(MODEL/'model.bim',data)
 write(OUT/'CommercePulse.pbip',{'version':'1.0','artifacts':[{'report':{'path':'CommercePulse.Report'}}],'settings':{'enableAutoRecovery':True}})
 write(REPORT/'definition.pbir',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':'../CommercePulse.SemanticModel'}}})
 write(REPORT/'definition/version.json',{'$schema':SCHEMA+'versionMetadata/1.0.0/schema.json','version':'2.0.0'})
 for folder,kind in [(REPORT,'Report'),(MODEL,'SemanticModel')]:
  write(folder/'.platform',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json','metadata':{'type':kind,'displayName':'Commerce Pulse'},'config':{'version':'2.0','logicalId':str(uuid.uuid5(uuid.NAMESPACE_URL,'commerce-pulse/'+kind))}})
 import shutil
 base_theme=REPORT/'StaticResources/SharedResources/BaseThemes/CY24SU02.json'
 base_theme.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(OUT/'SalesAnalytics.Report/StaticResources/SharedResources/BaseThemes/CY24SU02.json',base_theme)
 theme={'name':'Commerce Pulse • Midnight','dataColors':[MINT,AMBER,CORAL,'#7F9CFF','#59B8DF','#B29CE8'],'background':PANEL,'foreground':TEXT,'tableAccent':MINT,
  'textClasses':{'title':{'fontFace':'Segoe UI Semibold','fontSize':12,'color':TEXT},'label':{'fontFace':'Segoe UI','fontSize':10,'color':MUTED},'callout':{'fontFace':'Segoe UI Semibold','fontSize':32,'color':TEXT}},
  'visualStyles':{'*':{'*':{'background':[{'show':True,'color':{'solid':{'color':PANEL}},'transparency':0}], 'border':[{'show':False}], 'visualHeader':[{'show':False}]}}}}
 write(REPORT/'StaticResources/RegisteredResources/CommercePulseTheme.json',theme)
 write(OUT/'CommercePulseTheme.json',theme)
 versions={'visual':'1.8.89','report':'2.0.89','page':'1.3.89'}
 write(REPORT/'definition/report.json',{'$schema':SCHEMA+'report/3.0.0/schema.json','themeCollection':{'baseTheme':{'name':'CY24SU02','reportVersionAtImport':versions,'type':'SharedResources'},'customTheme':{'name':'CommercePulseTheme.json','reportVersionAtImport':versions,'type':'RegisteredResources'}},'resourcePackages':[{'name':'SharedResources','type':'SharedResources','items':[{'name':'CY24SU02','path':'BaseThemes/CY24SU02.json','type':'BaseTheme'}]},{'name':'RegisteredResources','type':'RegisteredResources','items':[{'name':'CommercePulseTheme.json','path':'CommercePulseTheme.json','type':'CustomTheme'}]}],'settings':{'useStylableVisualContainerHeader':True,'exportDataMode':'AllowSummarized','defaultDrillFilterOtherVisuals':True}})
 pages=[('Executive','Sales pulse'),('Products','Product drivers'),('Geography','Market demand'),('Operations','Operations')]
 write(REPORT/'definition/pages/pages.json',{'$schema':SCHEMA+'pagesMetadata/1.0.0/schema.json','pageOrder':[p for p,_ in pages],'activePageName':'Executive'})
 frame('Executive','Sales pulse','Track the scale of demand, the comparable-period shift, and the categories behind it.',1)
 for i,(measure,label,accent) in enumerate([('Sales Value (crore)','Valued shipped sales',MINT),('Shipped Orders Display','Valued shipped orders',TEXT),('Complete Order AOV','Complete-order AOV',TEXT),('Cancelled Line Rate','Cancelled lines',AMBER)]):card('Executive','KPI'+str(i),measure,label,216+i*302,174,286,110,accent)
 chart('Executive','Comparison','lineChart','May vs June • aligned days 1–29',216,310,754,296,{'Category':[('Date','day_of_month',False)],'Y':[('Sales','May daily value',True),('Sales','June daily value',True)]},sort=('Date','day_of_month',False,'Ascending'),colors=[AMBER,MINT])
 text('Executive','ShiftPanel','',988,310,424,296,1,PANEL,PANEL,z=1)
 card('Executive','ComparableRate','Comparable Value Change Rate','Comparable shipped-value change',1000,320,400,112,CORAL,46)
 card('Executive','May','May Value (crore)','May 1–29',1000,434,196,90,AMBER,25)
 card('Executive','June','June Value (crore)','June 1–29',1202,434,196,90,MINT,25)
 text('Executive','ComparisonNote','Same 29-day window. Month filters leave this comparison fixed; product and fulfillment filters apply.',1008,536,384,62,11,MUTED,PANEL)
 chart('Executive','Category','clusteredBarChart','Top 5 categories • share of all shipped value',216,626,754,222,{'Category':[('Product','category',False)],'Y':[('Sales','Top 5 Category Share',True)]},sort=('Sales','Top 5 Category Share',True,'Descending'))
 text('Executive','LeaderPanel','',988,626,424,222,1,PANEL,PANEL,z=1)
 card('Executive','Leader','Leading Category','Leading category',1000,637,220,92,MINT,28)
 card('Executive','LeaderShare','Leading Category Share','Selection share',1218,637,182,92,TEXT,31)
 text('Executive','LeaderNote','Explore Product drivers to separate category declines from the categories offsetting them.',1008,745,384,74,12,MUTED,PANEL)

 frame('Products','Product drivers','Explain the May–June shift, then examine the categories contributing to it.',2)
 for i,(measure,label,accent) in enumerate([('Leading Category','Leading category',MINT),('Leading Category Share','Leading category share',TEXT),('Value Change (lakh)','May–June value change',CORAL),('Shipped Units Display','Valued shipped units',TEXT)]):card('Products','KPI'+str(i),measure,label,216+i*302,174,286,110,accent)
 chart('Products','Decline','clusteredBarChart','What changed? • June minus May, INR lakh',216,310,754,298,{'Category':[('Product','category',False)],'Y':[('Sales','Category decline (lakh)',True),('Sales','Category growth (lakh)',True)]},sort=('Sales','Category decline (lakh)',True,'Ascending'),colors=[CORAL,MINT])
 chart('Products','Category','clusteredBarChart','Category demand • shipped value, INR crore',988,310,424,298,{'Category':[('Product','category',False)],'Y':[('Sales','Sales Value (crore)',True)]},sort=('Sales','Sales Value (crore)',True,'Descending'))
 table('Products','CategoryDetail','Category detail • equal 29-day windows',216,626,1196,222,[('Product','category',False),('Sales','May Value (crore)',True),('Sales','June Value (crore)',True),('Sales','Value Change (lakh)',True),('Sales','Net Decline Contribution',True),('Sales','Cancelled Line Rate',True)],{'Product.category':'Category','Sales.May Value (crore)':'May · Cr','Sales.June Value (crore)':'June · Cr','Sales.Value Change (lakh)':'Change · L','Sales.Net Decline Contribution':'Net change share','Sales.Cancelled Line Rate':'Cancelled lines'},('Sales','Value Change (lakh)',True,'Ascending'))

 frame('Geography','Market demand','Understand shipping-destination demand and investigate regional cancellation differences.',3)
 for i,(measure,label,accent) in enumerate([('Leading State','Leading market',MINT),('Top Two Markets Share','Top two market share',TEXT),('Active Regions','Shipping regions observed',TEXT),('Sales Value (crore)','Valued shipped sales',MINT)]):card('Geography','KPI'+str(i),measure,label,216+i*302,174,286,110,accent,24 if i==0 else 32)
 chart('Geography','State','clusteredBarChart','Market leaderboard • top 10 in this selection',216,310,754,538,{'Category':[('Geography','ship_state',False)],'Y':[('Sales','Top 10 Market Value (crore)',True)]},sort=('Sales','Top 10 Market Value (crore)',True,'Descending'))
 table('Geography','StateDetail','Market detail • all observed regions',988,310,424,420,[('Geography','ship_state',False),('Sales','Sales Value (crore)',True),('Sales','Cancelled Line Rate',True)],{'Geography.ship_state':'Shipping region','Sales.Sales Value (crore)':'Value · Cr','Sales.Cancelled Line Rate':'Cancel %'},('Sales','Sales Value (crore)',True,'Descending'))
 text('Geography','MarketNote','READ THE SIGNAL\nDemand measures destination concentration. It does not establish regional profitability. Unknown and unmapped locations remain in the data.',1004,748,392,98,11,MUTED,PANEL)

 frame('Operations','Operations','Compare fulfillment outcomes and make missing-value exposure visible.',4)
 for i,(measure,label,accent) in enumerate([('Cancelled Line Rate','Cancelled lines',CORAL),('Returned Line Rate','Returned / returning lines',AMBER),('Missing Amount Lines','Lines without amounts',AMBER),('Unvalued Shipped Lines','Unvalued shipped lines',CORAL)]):card('Operations','KPI'+str(i),measure,label,216+i*302,174,286,110,accent)
 chart('Operations','Fulfillment','clusteredBarChart','Fulfillment cancellation • share of observed lines',216,310,754,264,{'Category':[('Sales','fulfillment',False)],'Y':[('Sales','Cancelled Line Rate',True)]},sort=('Sales','Cancelled Line Rate',True,'Descending'))
 text('Operations','GapPanel','',988,310,424,264,1,PANEL,PANEL,z=1)
 card('Operations','Gap','Fulfillment Gap (pp)','Merchant minus Amazon',1000,320,400,112,CORAL,42)
 card('Operations','Amazon','Amazon Cancel Rate','Amazon',1000,437,196,90,MINT,25)
 card('Operations','Merchant','Merchant Cancel Rate','Merchant',1202,437,196,90,AMBER,25)
 text('Operations','GapNote','Descriptive gap. Product mix and process differences require investigation.',1008,530,384,40,10,MUTED,PANEL)
 table('Operations','StatusDetail','Status exposure • recorded amount includes every status',216,594,754,254,[('Status','status_group',False),('Sales','Observed Lines',True),('Sales','Recorded Amount',True),('Sales','Missing Amount Lines',True)],{'Status.status_group':'Status group','Sales.Observed Lines':'Lines','Sales.Recorded Amount':'Recorded amount','Sales.Missing Amount Lines':'Missing amounts'},('Sales','Observed Lines',True,'Descending'))
 text('Operations','QualityPanel','',988,594,424,254,1,PANEL,PANEL,z=1)
 card('Operations','Coverage','Amount Coverage','Amount coverage',1000,606,214,112,MINT,34)
 card('Operations','Conflicts','Courier Conflict Lines','Courier conflicts',1218,606,182,112,AMBER,34)
 text('Operations','QualityNote','DATA CONFIDENCE\nMissing amounts stay missing. Returned statuses are a snapshot, not a refund ledger. No profit or causal improvement is claimed.',1008,726,384,100,11,MUTED,PANEL)
 write(OUT/'CommercePulse_measures.json',{**base.MEASURES,**EXTRA})
 (OUT/'CommercePulse_measures.dax').write_text('\n\n'.join(n+' =\n'+e for n,(e,_) in {**base.MEASURES,**EXTRA}.items()),encoding='utf-8')
 validate()
 print(f'Commerce Pulse generated: 4 pages, {len(base.MEASURES)+len(EXTRA)} measures.')

def validate():
 import jsonschema
 store=json.loads((ROOT/'.setup/schemas/schema_store.json').read_text())
 checked=0
 for path in (REPORT/'definition').rglob('*.json'):
  data=json.loads(path.read_text(encoding='utf-8')); url=data['$schema'];schema=store[url]
  resolver=jsonschema.RefResolver(base_uri=url,referrer=schema,store=store)
  jsonschema.Draft7Validator(schema,resolver=resolver).validate(data);checked+=1
 write(ROOT/'reports/powerbi_dark_schema_validation.json',{'passed':True,'files_validated':checked,'pages':4,'measures':len(base.MEASURES)+len(EXTRA),'native_desktop_validation':'pending'})

if __name__=='__main__':main()
