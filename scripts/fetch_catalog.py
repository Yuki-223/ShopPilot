"""Bounded samples from official sources. No browser scraping or claims of live comparison."""
import argparse
import hashlib
import json
import time
import zlib
from pathlib import Path

import httpx
from backend.importing import convert_record

AMAZON_BASE='https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/'
CATEGORIES={'All_Beauty':'美妆个护','Electronics':'数码电子','Clothing_Shoes_and_Jewelry':'服饰运动','Home_and_Kitchen':'家居生活','Grocery_and_Gourmet_Food':'食品饮料','Health_and_Household':'健康日用'}
MAX_BYTES=32*1024*1024
MAX_SCAN=5000


def read_amazon(client,url):
    decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
    buffer=b''; total=0; decoded=0
    with client.stream('GET',url,follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=32768):
            total+=len(chunk)
            if total>MAX_BYTES: raise ValueError('下载超过32MB，已停止采样')
            # Decode with a bound even if the server returns malformed compressed input.
            out=decoder.decompress(chunk,MAX_BYTES+1-decoded)
            decoded+=len(out)
            if decoded>=MAX_BYTES or decoder.unconsumed_tail: raise ValueError('解压内容超过32MB，已停止采样')
            buffer+=out
            if len(buffer)>2*1024*1024 and b'\n' not in buffer: raise ValueError('单条商品记录过大')
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1)
                if line.strip(): yield json.loads(line)
        if buffer.strip(): yield json.loads(buffer)


def fetch_sample(source,category,limit,output,client=None):
    if not 1<=limit<=500: raise ValueError('单次采样数量需为1至500')
    if source=='amazon2023' and category not in CATEGORIES: raise ValueError('不支持的Amazon分类')
    output=Path(output)
    manifest_path=output.with_suffix(output.suffix+'.manifest.json')
    if output.exists() or manifest_path.exists(): raise ValueError('输出文件已存在，请指定新路径；避免覆盖已有数据')
    owned=client is None
    client=client or httpx.Client(timeout=httpx.Timeout(30,connect=15),headers={'User-Agent':'ShopPilot-academic-catalog/0.2'})
    started=time.time();selected=[];scanned=0;missing_price=0
    url=AMAZON_BASE+'meta_'+category+'.jsonl.gz' if source=='amazon2023' else 'https://dummyjson.com/products?limit='+str(limit)
    iterator=None
    try:
        if source=='amazon2023': iterator=read_amazon(client,url)
        elif source=='dummyjson':
            response=client.get(url);response.raise_for_status();iterator=iter(response.json()['products'])
        else: raise ValueError('不支持的数据来源')
        for record in iterator:
            scanned+=1
            product,_=convert_record(record,source)
            if product is None: missing_price+=1
            else:
                record['_shoppilot_meta']={'fetched_at':started,'dataset_version':'2023' if source=='amazon2023' else 'test-api','dataset_url':url,'category':CATEGORIES.get(category),'source_category':category,'sample_method':'first_valid_priced_records'}
                selected.append(record)
            if len(selected)>=limit or scanned>=MAX_SCAN: break
        if not selected: raise ValueError('没有获取到可用的带价格商品记录')
        payload=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected).encode()
        digest=hashlib.sha256(payload).hexdigest()
        manifest={'source':source,'category':category,'url':url,'fetched_at':started,'records':len(selected),'scanned':scanned,'skipped_missing_price':missing_price,'sha256':digest,'sample_method':'first_valid_priced_records','note':'历史/测试数据；下载时间不是报价核验时间。导入后下架，需管理员核实币种、价格与资料。'}
        output.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation prevents accidental overwrites. Failure removes only this run's files.
        created=[]
        try:
            with output.open('xb') as f: created.append(output); f.write(payload)
            with manifest_path.open('x',encoding='utf-8') as f: created.append(manifest_path);json.dump(manifest,f,ensure_ascii=False,indent=2)
        except Exception:
            for path in created: path.unlink(missing_ok=True)
            raise
        return manifest
    finally:
        if iterator is not None and hasattr(iterator,'close'): iterator.close()
        if owned: client.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=['amazon2023','dummyjson'],default='amazon2023')
    parser.add_argument('--category',choices=list(CATEGORIES),default='All_Beauty')
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        manifest=fetch_sample(args.source,args.category,args.limit,args.output)
    except (httpx.HTTPError,ValueError,OSError,KeyError,zlib.error) as exc:
        parser.exit(1,f'采样失败：{type(exc).__name__}: {exc}\n')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
