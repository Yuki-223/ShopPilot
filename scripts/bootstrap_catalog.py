"""Download and import a bounded six-category historical catalog; safe to repeat."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from .fetch_catalog import CATEGORIES,fetch_sample


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--per-category',type=int,default=100)
    p.add_argument('--directory',type=Path,default=Path('data/downloads'))
    args=p.parse_args()
    if not 1<=args.per_category<=500:p.error('--per-category must be 1..500')
    for category in CATEGORIES:
        output=args.directory/f'amazon-{category}-{args.per_category}.jsonl'
        if not output.exists():
            report=fetch_sample('amazon2023',category,args.per_category,output)
            print(f'{category}: downloaded {report["records"]} priced historical records',flush=True)
        subprocess.run([sys.executable,'-m','scripts.manage','import',str(output),'--format','amazon2023','--limit',str(args.per_category)],check=True)
    print('Catalog ready in admin view. Imported records remain inactive until RMB price review.')
if __name__=='__main__':main()
