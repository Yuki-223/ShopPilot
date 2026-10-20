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
