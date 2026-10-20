"""Traditional administration and feedback, all authorization enforced server-side."""
import json
import secrets
import sqlite3
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .app import Product,admin,audit,db,user,serialize,write_product,product

router=APIRouter(prefix='/api')

class PriceReview(BaseModel):
    price_cents: int=Field(ge=0,le=100000000)
    stock: int=Field(ge=0,le=1000000)
    source_url: str=Field(min_length=10,max_length=1500,pattern=r'^https://[^\s]+$')
    note: str=Field(min_length=5,max_length=2000)

@router.post('/admin/products/{pid}/review')
def review_product(pid: str,req: PriceReview,u=Depends(admin)):
    checked=time.time()
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
        if not row: raise HTTPException(404,'商品不存在')
        p=serialize(row);p.pop('quality',None);p.pop('id');p.pop('updated')
        specs=p['specs'];meta=specs.get('_provenance',{})
        specs['_provenance']={**meta,'review_status':'reviewed','price_checked_at':checked,'review_note':req.note}
        specs['currency']='CNY'
        p.update(price_cents=req.price_cents,stock=req.stock,source_url=req.source_url,status='active',specs=specs)
        write_product(c,Product(**p),pid)
        c.execute('INSERT INTO price_checks(product_id,price_cents,checked_at,note,source_url,actor) VALUES(?,?,?,?,?,?)',(pid,req.price_cents,checked,req.note,req.source_url,u['id']))
        audit(c,u,'review_product',pid)
    return {'ok':True,'price_checked_at':checked}

@router.get('/products/{pid}/price-history')
def price_history(pid: str):
    product(pid)
    with db() as c:
        rows=c.execute('SELECT price_cents,checked_at,note,source_url FROM price_checks WHERE product_id=? ORDER BY checked_at DESC,id DESC LIMIT 30',(pid,))
        return {'items':[dict(r) for r in rows],'note':'仅记录管理员手动核验的人民币报价，不代表平台完整历史价格。'}

class Category(BaseModel):
    name: str=Field(min_length=1,max_length=50,pattern=r'^\S(?:.*\S)?$')

@router.get('/admin/categories')
def categories(u=Depends(admin)):
    with db() as c:
        return [dict(r) for r in c.execute('SELECT c.name,COUNT(p.id) AS product_count FROM categories c LEFT JOIN products p ON p.category=c.name GROUP BY c.name ORDER BY c.name')]

@router.post('/admin/categories',status_code=201)
def create_category(req: Category,u=Depends(admin)):
    with db() as c:
        if c.execute('SELECT 1 FROM categories WHERE name=?',(req.name,)).fetchone(): raise HTTPException(409,'分类已存在')
        c.execute('INSERT INTO categories VALUES(?)',(req.name,)); audit(c,u,'create_category',req.name)
    return {'ok':True}

@router.put('/admin/categories/{name}')
def rename_category(name: str,req: Category,u=Depends(admin)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM categories WHERE name=?',(name,)).fetchone(): raise HTTPException(404,'分类不存在')
        if name==req.name: return {'ok':True}
        if c.execute('SELECT 1 FROM categories WHERE name=?',(req.name,)).fetchone(): raise HTTPException(409,'目标分类已存在')
        c.execute('INSERT INTO categories VALUES(?)',(req.name,))
        c.execute('UPDATE products SET category=?,updated=? WHERE category=?',(req.name,time.time(),name))
        c.execute('DELETE FROM categories WHERE name=?',(name,))
        audit(c,u,'rename_category',name+' → '+req.name)
    return {'ok':True}

@router.delete('/admin/categories/{name}')
def delete_category(name: str,u=Depends(admin)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM products WHERE category=?',(name,)).fetchone(): raise HTTPException(409,'分类下有商品，请先调整商品分类')
        if not c.execute('DELETE FROM categories WHERE name=?',(name,)).rowcount: raise HTTPException(404,'分类不存在')
        audit(c,u,'delete_category',name)
    return {'ok':True}

@router.get('/admin/users')
def users(q: str='',page: int=1,u=Depends(admin)):
    with db() as c:
        args=('%'+q+'%',)
        total=c.execute('SELECT COUNT(*) FROM users WHERE username LIKE ?',args).fetchone()[0]
        rows=c.execute('SELECT id,username,role,active FROM users WHERE username LIKE ? ORDER BY username LIMIT 20 OFFSET ?',(*args,(max(1,page)-1)*20))
        return {'items':[dict(r) for r in rows],'total':total,'page':max(1,page),'limit':20}

class UserStatus(BaseModel):
    active: bool

@router.put('/admin/users/{uid}/status')
def user_status(uid: str,req: UserStatus,u=Depends(admin)):
    with db() as c:
        row=c.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
        if not row: raise HTTPException(404,'用户不存在')
        if row['role']=='admin': raise HTTPException(409,'管理员账号不能在此停用或更改')
        c.execute('UPDATE users SET active=? WHERE id=?',(int(req.active),uid))
        if not req.active: c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        audit(c,u,'enable_user' if req.active else 'disable_user',uid)
    return {'ok':True}

class Feedback(BaseModel):
    product_id: str | None=None
    content: str=Field(min_length=5,max_length=2000)

@router.post('/feedback',status_code=201)
def feedback(req: Feedback,u=Depends(user)):
    fid=secrets.token_hex(12)
    with db() as c:
        if req.product_id and not c.execute('SELECT 1 FROM products WHERE id=?',(req.product_id,)).fetchone(): raise HTTPException(404,'商品不存在')
        c.execute('INSERT INTO feedback VALUES(?,?,?,?,?,?,?,?)',(fid,u['id'],req.product_id,req.content,'open','',time.time(),time.time()))
    return {'id':fid}

@router.get('/feedback')
def own_feedback(u=Depends(user)):
    with db() as c:
        return [dict(r) for r in c.execute('SELECT f.*,p.title AS product_title FROM feedback f LEFT JOIN products p ON p.id=f.product_id WHERE f.user_id=? ORDER BY f.created DESC',(u['id'],))]

@router.get('/admin/feedback')
def all_feedback(status: str='',page: int=1,u=Depends(admin)):
    with db() as c:
        where='WHERE f.status=?' if status else ''
        args=(status,) if status else ()
        total=c.execute('SELECT COUNT(*) FROM feedback f '+where,args).fetchone()[0]
        rows=c.execute('SELECT f.*,u.username,p.title AS product_title FROM feedback f JOIN users u ON f.user_id=u.id LEFT JOIN products p ON f.product_id=p.id '+where+' ORDER BY f.created DESC LIMIT 20 OFFSET ?',(*args,(max(1,page)-1)*20))
        return {'items':[dict(r) for r in rows],'total':total,'page':max(1,page),'limit':20}

class Resolution(BaseModel):
    status: str=Field(pattern='^(open|resolved|dismissed)$')
    reply: str=Field(min_length=1,max_length=2000)

@router.put('/admin/feedback/{fid}')
def resolve_feedback(fid: str,req: Resolution,u=Depends(admin)):
    with db() as c:
        if not c.execute('UPDATE feedback SET status=?,reply=?,updated=? WHERE id=?',(req.status,req.reply,time.time(),fid)).rowcount: raise HTTPException(404,'反馈不存在')
        audit(c,u,'resolve_feedback',fid)
    return {'ok':True}

@router.delete('/chats/{cid}')
def delete_chat(cid: str,u=Depends(user)):
    with db() as c:
        if not c.execute('DELETE FROM chats WHERE id=? AND user_id=?',(cid,u['id'])).rowcount: raise HTTPException(404,'对话不存在')
    return {'ok':True}
