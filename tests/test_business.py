import json
import pytest
from fastapi.testclient import TestClient
from backend import app as mod
from scripts.manage import seed

@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(mod,'DB',str(tmp_path/'test.sqlite3'))
    monkeypatch.delenv('LLM_API_KEY',raising=False)
    mod.init(); seed()
    client=TestClient(mod.app)
    return client

def login(c,name='alice',role='user'):
    creds={'username':name,'password':'Test-password-123'}
    assert c.post('/api/auth/register',json=creds).status_code==201
    if role=='admin':
        with mod.db() as db: db.execute("UPDATE users SET role='admin' WHERE username=?",(name,))
    assert c.post('/api/auth/login',json=creds).status_code==200
    return c.get('/api/auth/me').json()

def test_permissions_and_ownership(setup):
    c=setup
    assert c.get('/api/admin/products').status_code==401
    login(c)
    assert c.get('/api/admin/products').status_code==403
    assert c.post('/api/admin/import',json={'products':[]}).status_code==403
    profile=c.get('/api/profiles').json()[0]['id']
    c.post('/api/favorites/demo-001')
    c.put('/api/cart/demo-001',json={'quantity':1})
    chat=c.post('/api/chat',json={'query':'推荐VC','profile_id':profile}).json()
    c.post('/api/auth/logout')
    login(c,'bob')
    assert c.get('/api/favorites').json()==[]
    assert c.get('/api/cart').json()['items']==[]
    assert c.get('/api/chats').json()==[]
    assert c.put('/api/profiles/'+profile,json={'name':'偷改','preferences':{}}).status_code==404
    assert c.post('/api/chat',json={'query':'继续','conversation_id':chat['conversation_id']}).status_code==404
    assert c.post('/api/chat',json={'query':'搜索','profile_id':profile}).status_code==404

def test_admin_product_lifecycle(setup):
    c=setup; login(c,role='admin')
    p={'title':'测试商品','category':'测试分类','price_cents':1000,'stock':2}
    r=c.post('/api/admin/products',json=p); assert r.status_code==201,r.text
    pid=r.json()['id']; assert c.get('/api/products/'+pid).json()['title']=='测试商品'
    p['price_cents']=1500
    assert c.put('/api/admin/products/'+pid,json=p).status_code==200
    assert c.get('/api/products/'+pid).json()['price_cents']==1500
    assert c.delete('/api/admin/products/'+pid).status_code==200
    assert c.get('/api/products/'+pid).status_code==404
    assert len(c.get('/api/admin/overview').json()['audit'])==3

def test_order_snapshot_cancellation_and_isolation(setup):
    c=setup; login(c)
    assert c.put('/api/cart/demo-001',json={'quantity':2}).status_code==200
    r=c.post('/api/orders'); assert r.status_code==201
    oid=r.json()['id']
    assert c.get('/api/products/demo-001').json()['stock']==28
    assert c.get('/api/cart').json()['items']==[]
    with mod.db() as db: db.execute("UPDATE products SET price_cents=9999 WHERE id='demo-001'")
    o=c.get('/api/orders').json()[0]
    assert o['items'][0]['price_cents']==6800
    assert o['total_cents']==13600
    assert c.post('/api/orders/'+oid+'/cancel').status_code==200
    assert c.post('/api/orders/'+oid+'/cancel').status_code==409
    assert c.get('/api/products/demo-001').json()['stock']==30
    c.post('/api/auth/logout');login(c,'bob')
    assert c.get('/api/orders').json()==[]
    assert c.post('/api/orders/'+oid+'/cancel').status_code==404

def test_checkout_failure_rolls_back(setup):
    c=setup;login(c)
    c.put('/api/cart/demo-001',json={'quantity':2});c.put('/api/cart/demo-002',json={'quantity':2})
    with mod.db() as db: db.execute("UPDATE products SET stock=1 WHERE id='demo-002'")
    assert c.post('/api/orders').status_code==409
    assert c.get('/api/orders').json()==[]
    assert c.get('/api/products/demo-001').json()['stock']==30
    assert len(c.get('/api/cart').json()['items'])==2

def test_constraints_unknown_not_safe_and_multiturn(setup):
    c=setup;login(c)
    p=c.get('/api/profiles').json()[0]['id']
    result=c.post('/api/chat',json={'query':'推荐100元以内的VC，不要滑石粉','profile_id':p}).json()
    assert result['mode']=='rules'
    assert [x['id'] for x in result['products']]==['demo-001']
    assert result['unknown_count']==1
    assert result['rejected_count']==1
    assert result['constraints']['max_price_cents']==10000
    r=c.post('/api/chat',json={'query':'再看看','profile_id':p,'conversation_id':result['conversation_id']}).json()
    assert [x['id'] for x in r['products']]==['demo-001']
    r=c.post('/api/chat',json={'query':'去掉预算','profile_id':p,'conversation_id':result['conversation_id']}).json()
    assert 'max_price_cents' not in r['constraints']
    assert c.get('/api/profiles').json()[0]['preferences']=={}

def test_profile_switch_requires_new_chat(setup):
    c=setup;login(c)
    p=c.get('/api/profiles').json()[0]['id']
    r=c.post('/api/chat',json={'query':'推荐VC','profile_id':p}).json()
    p2=c.post('/api/profiles',json={'name':'妈妈','preferences':{'max_price_cents':7000,'exclude':['滑石粉']}}).json()['id']
    assert c.post('/api/chat',json={'query':'继续','conversation_id':r['conversation_id'],'profile_id':p2}).status_code==409
    r=c.post('/api/chat',json={'query':'推荐VC','profile_id':p2}).json()
    assert [p['id'] for p in r['products']]==['demo-001']

def test_import_atomic_and_search(setup):
    c=setup;login(c,role='admin')
    before=c.get('/api/products').json()['total']
    good={'title':'商品','category':'类别','price_cents':1234}
    bad={**good,'price_cents':-1}
    assert c.post('/api/admin/import',json={'products':[good,bad]}).status_code==422
    assert c.get('/api/products').json()['total']==before
    assert c.post('/api/admin/import',json={'products':[good]}).json()['imported']==1
    result=c.get('/api/products',params={'category':'数码电子','sort':'price_asc','limit':2}).json()
    assert result['total']==4
    assert result['items'][0]['price_cents']<=result['items'][1]['price_cents']
    assert len(result['items'])==2

def test_csrf_password_storage_and_logout(setup):
    c=setup;login(c)
    with mod.db() as db:
        p=db.execute("SELECT password FROM users WHERE username='alice'").fetchone()[0]
        assert 'Test-password-123' not in p
    assert 'HttpOnly' in c.cookies.get('shop_session') or len(c.cookies.get('shop_session'))>30
    assert c.post('/api/orders',headers={'Origin':'https://attacker.example'}).status_code==403
    c.post('/api/auth/logout')
    assert c.get('/api/auth/me').status_code==401

def test_external_cannot_checkout(setup):
    c=setup;login(c,role='admin')
    pid=c.post('/api/admin/products',json={'title':'外部候选','category':'数码电子','price_cents':1000,'stock':20,'source':'external'}).json()['id']
    assert c.put('/api/cart/'+pid,json={'quantity':1}).status_code==400

def test_categories_rename_and_nonempty_delete(setup):
    c=setup; login(c,role='admin')
    assert c.post('/api/admin/categories',json={'name':'空分类'}).status_code==201
    assert c.post('/api/admin/categories',json={'name':'空分类'}).status_code==409
    assert c.delete('/api/admin/categories/空分类').status_code==200
    assert c.delete('/api/admin/categories/营养保健').status_code==409
    assert c.put('/api/admin/categories/营养保健',json={'name':'营养补充'}).status_code==200
    assert c.get('/api/products/demo-001').json()['category']=='营养补充'
    assert '营养保健' not in c.get('/api/categories').json()
    assert c.put('/api/admin/categories/营养补充',json={'name':'数码电子'}).status_code==409

def test_user_disable_revokes_session_and_protects_admin(setup):
    c=setup; alice=login(c)
    token=c.cookies.get('shop_session'); c.post('/api/auth/logout')
    # Make a second valid Alice session before switching to admin.
    c.post('/api/auth/login',json={'username':'alice','password':'Test-password-123'})
    token=c.cookies.get('shop_session');c.cookies.clear()
    boss=login(c,'boss',role='admin')
    assert c.put('/api/admin/users/'+alice['id']+'/status',json={'active':False}).status_code==200
    other=TestClient(mod.app);other.cookies.set('shop_session',token)
    assert other.get('/api/auth/me').status_code==401
    assert c.put('/api/admin/users/'+boss['id']+'/status',json={'active':False}).status_code==409
    assert c.put('/api/admin/users/'+alice['id']+'/status',json={'active':True}).status_code==200
    assert other.get('/api/auth/me').status_code==401  # old session stays revoked
    assert c.get('/api/admin/users?q=alice').json()['items'][0]['active']==1

def test_feedback_visibility_and_resolution(setup):
    c=setup;login(c)
    r=c.post('/api/feedback',json={'product_id':'demo-001','content':'请核实该商品标签配料信息'})
    assert r.status_code==201; fid=r.json()['id']
    assert c.get('/api/admin/feedback').status_code==403
    c.cookies.clear();login(c,'bob')
    assert c.get('/api/feedback').json()==[]
    c.cookies.clear();login(c,'boss',role='admin')
    assert c.get('/api/admin/feedback').json()['total']==1
    assert c.put('/api/admin/feedback/'+fid,json={'status':'resolved','reply':'已核查并补充资料来源'}).status_code==200
    c.cookies.clear();c.post('/api/auth/login',json={'username':'alice','password':'Test-password-123'})
    own=c.get('/api/feedback').json()[0]
    assert own['status']=='resolved' and own['reply']=='已核查并补充资料来源'

def test_comparison_dose_cost_and_unknown(setup):
    c=setup;login(c)
    r=c.post('/api/compare',json={'product_ids':['demo-001','demo-002','demo-003']})
    assert r.status_code==200
    row=next(x for x in r.json()['rows'] if x['attribute']=='每克标签VC成本（元）')
    assert row['values']==['1.1333','1.4833','2.6222']
    ingredients=next(x for x in r.json()['rows'] if x['attribute']=='配料资料')
    assert '未知' in ingredients['values'][2]
    assert c.post('/api/compare',json={'product_ids':['demo-001','demo-001']}).status_code==422

def test_remove_profile_conditions_and_preserve_selected_products(setup):
    c=setup;login(c)
    pid=c.get('/api/profiles').json()[0]['id']
    c.put('/api/profiles/'+pid,json={'name':'我','preferences':{'max_price_cents':6000,'exclude':['滑石粉']}})
    r=c.post('/api/chat',json={'query':'推荐VC','profile_id':pid}).json()
    assert r['products']==[]
    r=c.post('/api/chat',json={'query':'去掉预算','conversation_id':r['conversation_id'],'profile_id':pid,'drop_conditions':['budget']}).json()
    assert [x['id'] for x in r['products']]==['demo-001']
    r=c.post('/api/chat',json={'query':'移除这项排除条件','conversation_id':r['conversation_id'],'profile_id':pid,'drop_conditions':['exclude:滑石粉']}).json()
    assert {x['id'] for x in r['products']}=={'demo-001','demo-002','demo-003'}
    assert c.get('/api/profiles').json()[0]['preferences']['max_price_cents']==6000
    r=c.post('/api/chat',json={'query':'比较','product_ids':['demo-009','demo-011']}).json()
    assert len(r['products'])==2 and r['comparison'] is not None
    r=c.post('/api/chat',json={'query':'再说说','conversation_id':r['conversation_id']}).json()
    assert {x['id'] for x in r['products']}=={'demo-009','demo-011'}

def test_category_switch_and_chat_delete(setup):
    c=setup;login(c)
    r=c.post('/api/chat',json={'query':'推荐VC'}).json()
    r=c.post('/api/chat',json={'query':'换成耳机','conversation_id':r['conversation_id']}).json()
    assert [x['id'] for x in r['products']]==['demo-005']
    assert c.delete('/api/chats/'+r['conversation_id']).status_code==200
    assert c.get('/api/chats').json()==[]

def test_import_dedup_does_not_overwrite_curated_product(setup):
    c=setup;login(c,role='admin')
    p={'title':'导入商品','category':'测试','price_cents':1000,'source':'external','source_url':'https://example.com/product/1'}
    assert c.post('/api/admin/import',json={'products':[p,p]}).json()=={'imported':1,'duplicates':1}
    items=c.get('/api/admin/products?q=导入商品').json()['items']
    assert len(items)==1
    pid=items[0]['id'];c.put('/api/admin/products/'+pid,json={**p,'title':'管理员核实名称'})
    assert c.post('/api/admin/import',json={'products':[p]}).json()=={'imported':0,'duplicates':1}
    assert c.get('/api/products/'+pid).json()['title']=='管理员核实名称'

def test_admin_product_pagination_and_foreign_currency(setup):
    c=setup;login(c,role='admin')
    d=c.get('/api/admin/products?limit=5&page=2').json()
    assert d['total']==24 and len(d['items'])==5
    p={'title':'美元商品','category':'测试','price_cents':1000,'specs':{'currency':'USD'},'status':'active'}
    assert c.post('/api/admin/products',json=p).status_code==422
    p['status']='inactive'
    assert c.post('/api/admin/products',json=p).status_code==201


def test_dataset_conversion_and_cli_dedup(setup,tmp_path,monkeypatch,capsys):
    from backend.importing import convert_record
    from scripts.manage import main
    p,key=convert_record({'id':123,'title':'Sample phone','price':12.345,'category':'smartphones','images':['https://example.com/p.jpg']},'dummyjson')
    assert p.price_cents==1235 and p.specs['currency']=='USD' and p.status=='inactive' and key=='123'
    assert convert_record({'price':'NaN'},'amazon2023')==(None,None)
    path=tmp_path/'data.json';path.write_text(json.dumps({'products':[{'id':123,'title':'Phone','price':10,'category':'smartphones'}]}))
    monkeypatch.setattr('sys.argv',['manage','import',str(path),'--format','dummyjson']);main();main()
    with mod.db() as db:
        assert db.execute("SELECT COUNT(*) FROM products WHERE source='dummyjson'").fetchone()[0]==1


def test_model_malformed_response_falls_back(setup,monkeypatch):
    c=setup;login(c)
    monkeypatch.setenv('LLM_API_KEY','test-not-real');monkeypatch.setenv('LLM_MODEL','fake')
    class FakeClient:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs):
            import httpx
            return httpx.Response(200,content=b'not json',request=httpx.Request('POST','https://example.test'))
    monkeypatch.setattr(mod.httpx,'AsyncClient',FakeClient)
    r=c.post('/api/chat',json={'query':'推荐VC'})
    assert r.status_code==200 and r.json()['mode']=='rules'
    assert '回退' in r.json()['warning']

def test_historical_product_review_preserves_original_and_records_snapshot(setup):
    from backend.importing import convert_record,import_record
    c=setup;login(c,role='admin')
    p,key=convert_record({'parent_asin':'B0TEST0001','title':'Historical Headphones','price':12.34,'main_category':'数码电子','_shoppilot_meta':{'dataset_version':'2023','fetched_at':mod.time.time(),'dataset_url':'https://example.test/dataset'}},'amazon2023')
    with mod.db() as db: import_record(db,p,key)
    item=c.get('/api/admin/products?source=amazon2023').json()['items'][0];pid=item['id']
    assert item['status']=='inactive' and item['quality']['price_state']=='unverified'
    assert item['specs']['original_price']==12.34 and item['quality']['price_checked_at'] is None
    assert item['quality']['source_updated_at'] is None
    assert c.get('/api/products/'+pid).status_code==404
    publish={'price_cents':8000,'stock':5,'source_url':'https://example.test/headphones','note':'核对同规格人民币售价，仅为测试'}
    assert c.post('/api/admin/products/'+pid+'/review',json=publish).status_code==200
    item=c.get('/api/products/'+pid).json()
    assert item['specs']['currency']=='CNY' and item['specs']['original_currency']=='USD'
    assert item['price_cents']==8000 and item['quality']['price_state']=='checked'
    assert item['specs']['original_price']==12.34
    h=c.get('/api/products/'+pid+'/price-history').json()
    assert h['items'][0]['price_cents']==8000
    # Changing the reviewed price requires review again and must not overwrite snapshots.
    req={k:item[k] for k in mod.Product.model_fields};req['price_cents']=9000
    assert c.put('/api/admin/products/'+pid,json=req).status_code==200
    assert c.get('/api/products/'+pid).status_code==404
    admin_item=c.get('/api/admin/products?q=Historical').json()['items'][0]
    assert admin_item['quality']['price_state']=='unverified'
    assert c.post('/api/admin/products/'+pid+'/review',json={**publish,'price_cents':9000}).status_code==200
    assert [x['price_cents'] for x in c.get('/api/products/'+pid+'/price-history').json()['items']]==[9000,8000]


def test_cannot_bypass_import_review_by_editing_metadata(setup):
    from backend.importing import convert_record,import_record
    c=setup;login(c,role='admin')
    p,key=convert_record({'id':1,'title':'Sample','price':10,'category':'test'},'dummyjson')
    with mod.db() as db: import_record(db,p,key)
    item=c.get('/api/admin/products?source=dummyjson').json()['items'][0];pid=item['id']
    req=p.model_dump();req['specs']={**req['specs'],'currency':'CNY'};req['status']='active'
    assert c.put('/api/admin/products/'+pid,json=req).status_code==409
    req['status']='inactive';req['specs']['source_id']='forged-id'
    assert c.put('/api/admin/products/'+pid,json=req).status_code==409
    req['specs']['source_id']=p.specs['source_id']
    req['status']='inactive';req['specs']['_provenance']={'review_status':'reviewed','price_checked_at':mod.time.time()}
    assert c.put('/api/admin/products/'+pid,json=req).status_code==409
    c.cookies.clear();login(c,'bob')
    assert c.post('/api/admin/products/'+pid+'/review',json={'price_cents':100,'stock':1,'source_url':'https://example.test/p','note':'尝试核验，权限不足'}).status_code==403


def test_provenance_staleness_and_unknown_timestamp():
    from backend.provenance import quality
    now=mod.time.time()
    p={'source':'amazon2023','specs':{'_provenance':{'fetched_at':now,'price_checked_at':now-8*86400}},'ingredients':None,'source_url':'https://example.test'}
    q=quality(p,now)
    assert q['price_state']=='stale' and q['source_updated_at'] is None
    p['specs']['_provenance']['price_checked_at']=None
    assert quality(p,now)['price_state']=='unverified'
    p['source']='demo'
    assert quality(p,now)['price_state']=='demo'


def test_bilingual_keyword_matches_reviewed_english_products(setup):
    c=setup;login(c,role='admin')
    pid=c.post('/api/admin/products',json={'title':'Wireless Bluetooth Headphones','category':'数码电子','price_cents':5000,'stock':1}).json()['id']
    r=c.post('/api/chat',json={'query':'推荐100元以内的耳机'}).json()
    assert [x['id'] for x in r['products']]==[pid]
    assert r['products'][0]['quality']['price_state']=='unverified'
    assert '价格' in r['answer']

def test_manifest_checksum_mismatch_rejects_import(setup,tmp_path,monkeypatch):
    from scripts.manage import main
    p=tmp_path/'sample.jsonl';p.write_text(json.dumps({'title':'Changed','price':10})+'\n')
    p.with_suffix('.jsonl.manifest.json').write_text(json.dumps({'source':'amazon2023','sha256':'0'*64}))
    monkeypatch.setattr('sys.argv',['manage','import',str(p),'--format','amazon2023'])
    with pytest.raises(SystemExit): main()
    with mod.db() as db: assert db.execute("SELECT COUNT(*) FROM products WHERE source='amazon2023'").fetchone()[0]==0
