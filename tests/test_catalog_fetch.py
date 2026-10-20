import gzip
import hashlib
import json
import httpx
import pytest
from scripts.fetch_catalog import fetch_sample


def test_bounded_amazon_sample_manifest_and_overwrite_protection(tmp_path):
    records=[{'parent_asin':'B0TEST0001','title':'No price','price':None},{'parent_asin':'B0TEST0002','title':'Priced sample','price':10,'main_category':'All Beauty'},{'parent_asin':'B0TEST0003','title':'Extra sample','price':15}]
    payload=gzip.compress(''.join(json.dumps(x)+'\n' for x in records).encode())
    def handler(request):
        assert request.url.host=='mcauleylab.ucsd.edu'
        return httpx.Response(200,content=payload)
    client=httpx.Client(transport=httpx.MockTransport(handler))
    out=tmp_path/'sample.jsonl'
    m=fetch_sample('amazon2023','All_Beauty',1,out,client)
    assert m['records']==1 and m['scanned']==2 and m['skipped_missing_price']==1
    assert hashlib.sha256(out.read_bytes()).hexdigest()==m['sha256']
    row=json.loads(out.read_text())
    assert row['parent_asin']=='B0TEST0002' and row['_shoppilot_meta']['category']=='美妆个护'
    assert out.with_suffix('.jsonl.manifest.json').exists()
    with pytest.raises(ValueError,match='已存在'):fetch_sample('amazon2023','All_Beauty',1,out,client)
    with pytest.raises(ValueError):fetch_sample('amazon2023','untrusted',1,tmp_path/'evil',client)


def test_fetch_failure_leaves_no_partial_artifact(tmp_path):
    out=tmp_path/'broken.jsonl'
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'bad gzip')))
    import zlib
    with pytest.raises(zlib.error):fetch_sample('amazon2023','All_Beauty',1,out,client)
    assert not out.exists() and not out.with_suffix('.jsonl.manifest.json').exists()

