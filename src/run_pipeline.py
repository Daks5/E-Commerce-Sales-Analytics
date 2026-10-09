"""Run Phase 1 in dependency order; credentials stay in the ignored .env."""
import subprocess,sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
for script in ['download_dataset.py','profile_data.py','clean_data.py','load_mysql.py','analyze.py','build_powerbi.py','build_dark_powerbi.py','prepare_dark_validation.py']:
 print(f'Running {script}',flush=True)
 subprocess.run([sys.executable,str(root/'src'/script)],cwd=root,check=True)
print('Pipeline complete. Refresh Power BI Desktop to update its cached report.')
