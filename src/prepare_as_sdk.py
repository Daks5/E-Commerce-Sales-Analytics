"""Optional Windows validation SDK; caches official Microsoft NuGet packages locally."""
import io,zipfile,requests
from load_mysql import ROOT

def main():
 for package in ['microsoft.analysisservices','microsoft.analysisservices.adomdclient']:
  target=ROOT/'.setup/as_sdk'/package
  if target.exists():continue
  response=requests.get(f'https://api.nuget.org/v3-flatcontainer/{package}/19.117.0/{package}.19.117.0.nupkg',timeout=60)
  response.raise_for_status()
  with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
   for member in archive.infolist():
    if not (target/member.filename).resolve().is_relative_to(target.resolve()):raise ValueError('Unsafe archive path')
   archive.extractall(target)
 print('Official Microsoft TOM/ADOMD validation SDK cache ready.')

if __name__=='__main__':main()
