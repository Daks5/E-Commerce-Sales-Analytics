"""Cache official Microsoft report schemas and their referenced dependencies."""
import json
from urllib.parse import urljoin,urldefrag
import requests
from load_mysql import ROOT

def fetch():
 base='https://developer.microsoft.com/json-schemas/fabric/item/report/definition/'
 queue=[base+n+'/'+v+'/schema.json' for n,v in [('visualContainer','2.1.0'),('report','3.0.0'),('page','2.0.0'),('pagesMetadata','1.0.0'),('versionMetadata','1.0.0')]]
 seen={}
 while queue:
  url=queue.pop()
  if url in seen:continue
  response=requests.get(url.replace('https://developer.microsoft.com/json-schemas/','https://raw.githubusercontent.com/microsoft/json-schemas/main/'),timeout=30)
  response.raise_for_status();document=response.json();seen[url]=document
  def walk(value):
   if isinstance(value,dict):
    for k,v in value.items():
     if k=='$ref' and not v.startswith('#'):queue.append(urldefrag(urljoin(url,v))[0])
     else:walk(v)
   elif isinstance(value,list):
    for v in value:walk(v)
  walk(document)
 path=ROOT/'.setup/schemas/schema_store.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(seen))
 return seen

if __name__=='__main__':print(f'Cached {len(fetch())} schemas.')
