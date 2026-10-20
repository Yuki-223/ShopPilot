"""Source-keyed imports: never overwrite an administrator's curated product."""
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .app import Product, write_product


def convert_record(record,source):
    if source=='normalized':
        return Product(**record), None
    raw_price=record.get('price')
    try:
        amount=Decimal(str(raw_price))
        if not amount.is_finite() or amount<0: return None,None
        cents=int((amount*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError,TypeError,OverflowError): return None,None
    images=record.get('images') or []
    image=record.get('thumbnail','')
    if not image and images:
        first=images[0]
        image=first if isinstance(first,str) else first.get('hi_res') or first.get('large') or ''
    description=record.get('description') or ''
    if isinstance(description,list): description='\n'.join(str(x) for x in description)
    details=dict(record.get('details') or {})
    details.update(currency='USD',original_price=raw_price)
    key=str(record.get('parent_asin') or record.get('asin') or record.get('id') or hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    details['source_id']=key
    product=Product(title=str(record.get('title',''))[:200],category=str(record.get('main_category') or record.get('category') or '未分类')[:50],brand=str(record.get('brand') or record.get('store') or '')[:100],price_cents=cents,stock=0,description=str(description)[:12000],image=image,specs=details,source=source,status='inactive')
    return product,key


def import_record(c,p,key=None):
    # Normalized imports use explicit source ID or source URL when available.
    key=key or p.specs.get('source_id') or p.source_url or hashlib.sha256(json.dumps(p.model_dump(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    key=str(key)
    if c.execute('SELECT 1 FROM imports WHERE source=? AND source_key=?',(p.source,key)).fetchone():
        return False
    pid=hashlib.sha256((p.source+'\0'+key).encode()).hexdigest()[:24]
    # Hash collisions/older records are not silently replaced.
    if c.execute('SELECT 1 FROM products WHERE id=?',(pid,)).fetchone():
        raise ValueError('导入记录标识冲突，请核查来源')
    write_product(c,p,pid)
    c.execute('INSERT INTO imports VALUES(?,?,?)',(p.source,key,pid))
    return True
