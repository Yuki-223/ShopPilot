"""Run from project root: python -m scripts.manage seed | admin USERNAME"""
import argparse
import getpass
import json
import secrets
from pathlib import Path
from backend.app import Product, ROOT, db, hash_password, write_product

CATALOG=[
('营养保健','维生素 C 500mg 120片','每日营养',6800,{'每片VC毫克':500,'片数':120},['抗坏血酸','微晶纤维素']),
('营养保健','维生素 C 1000mg 60片','营养时光',8900,{'每片VC毫克':1000,'片数':60},['抗坏血酸','滑石粉']),
('营养保健','维生素 C 咀嚼片 90片','轻养',5900,{'每片VC毫克':250,'片数':90},None),
('营养保健','鱼油软胶囊 60粒','海洋日记',9600,{'粒数':60},['鱼油','明胶','甘油']),
('数码电子','无线降噪耳机','听见',25900,{'续航':'30小时','接口':'USB-C'},None),
('数码电子','便携蓝牙音箱','声旅',15900,{'防水':'IPX5','重量':'380g'},None),
('数码电子','65W 氮化镓充电器','电力站',9900,{'接口':'2C1A','功率':'65W'},None),
('数码电子','轻薄无线鼠标','桌面伙伴',6900,{'连接':'蓝牙','重量':'65g'},None),
('服饰运动','纯棉圆领短袖','日常衣橱',7900,{'面料':'100%棉','尺码':'M'},None),
('服饰运动','轻量透气跑鞋','向前',22900,{'尺码':'42','鞋面':'织物'},None),
('服饰运动','直筒休闲长裤','日常衣橱',13900,{'面料':'棉98% 氨纶2%','尺码':'L'},None),
('服饰运动','防滑瑜伽垫','舒展',8900,{'材质':'TPE','厚度':'6mm'},None),
('家居生活','不锈钢保温杯','温度',6900,{'容量':'500ml','材质':'304不锈钢'},None),
('家居生活','护眼桌面台灯','光合',12900,{'功率':'12W','色温':'可调'},None),
('家居生活','纯棉毛巾两条装','柔软日记',3900,{'面料':'纯棉','数量':2},None),
('家居生活','收纳箱 35L','有序',4900,{'容量':'35L','材质':'PP'},None),
('食品饮料','原味燕麦片 1kg','谷物日记',3500,{'净含量':'1kg'},['燕麦']),
('食品饮料','无糖豆奶 250ml 6盒','植物餐桌',2900,{'数量':6},['水','大豆']),
('食品饮料','混合坚果 300g','果园',5900,{'净含量':'300g'},['杏仁','腰果','核桃']),
('食品饮料','黑巧克力 100g','可可时光',2500,{'可可含量':'85%'},['可可液块','可可脂','糖']),
('美妆个护','温和洁面乳 150ml','素研',4900,{'容量':'150ml'},['水','甘油','椰油酰甘氨酸钠']),
('美妆个护','保湿面霜 50g','素研',7900,{'净含量':'50g'},None),
('美妆个护','清爽洗发水 400ml','日常护理',3900,{'容量':'400ml'},None),
('美妆个护','润肤身体乳 250ml','日常护理',5900,{'容量':'250ml'},None),
]
def seed():
    with db() as c:
        for i,(category,title,brand,price,specs,ingredients) in enumerate(CATALOG):
            pid=f'demo-{i+1:03}'
            if c.execute('SELECT 1 FROM products WHERE id=?',(pid,)).fetchone(): continue
            p=Product(title=title,category=category,brand=brand,price_cents=price,stock=30,description='虚构教学商品，仅用于功能测试。规格、成分和价格均为演示数据，不代表真实品牌或购买建议。',specs=specs,ingredients=ingredients,source='demo')
            write_product(c,p,pid)
    print('Seeded 24 clearly labeled fictional teaching products (idempotent).')

def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('seed'); a=sub.add_parser('admin'); a.add_argument('username')
    a=sub.add_parser('import'); a.add_argument('file'); a.add_argument('--format',choices=['normalized','dummyjson','amazon2023'],default='normalized'); a.add_argument('--limit',type=int,default=500)
    args=parser.parse_args()
    if args.command=='seed': seed()
    elif args.command=='admin':
        name=args.username.lower()
        import re
        if not re.fullmatch(r'[a-z0-9_\-]{3,40}',name): parser.error('Invalid username')
        password=getpass.getpass('New admin password (10+ chars): ')
        if len(password)<10: parser.error('Password too short')
        with db() as c:
            if c.execute('SELECT 1 FROM users WHERE username=?',(name,)).fetchone(): parser.error('Account already exists; refusing implicit role change')
            uid=secrets.token_hex(12)
            c.execute('INSERT INTO users(id,username,password,role) VALUES(?,?,?,?)',(uid,name,hash_password(password),'admin'))
            c.execute('INSERT INTO profiles VALUES(?,?,?,?)',(secrets.token_hex(12),uid,'我','{}'))
        print('Admin created.')
    else:
        import gzip
        from decimal import Decimal, InvalidOperation
        path=Path(args.file)
        opener=gzip.open if path.suffix=='.gz' else open
        with opener(path,'rt',encoding='utf-8') as f:
            if path.name.endswith(('.jsonl','.jsonl.gz')): records=(json.loads(line) for line in f if line.strip())
            else:
                data=json.load(f); records=data['products'] if isinstance(data,dict) else data
            validated=[]; skipped=0
            for index,r in enumerate(records):
                if len(validated)>=max(1,min(args.limit,5000)): break
                if args.format=='normalized': p=Product(**r)
                else:
                    value=r.get('price')
                    try: cents=int((Decimal(str(value))*100).quantize(Decimal('1')))
                    except (InvalidOperation,ValueError,TypeError): skipped+=1; continue
                    images=r.get('images') or []
                    image=r.get('thumbnail','')
                    if not image and images:
                        first=images[0]; image=first if isinstance(first,str) else first.get('large') or first.get('hi_res') or ''
                    description=r.get('description','')
                    if isinstance(description,list): description='\n'.join(str(x) for x in description)
                    # Source currency is preserved; no silent USD -> CNY conversion.
                    details=dict(r.get('details') or {}); details['currency']='USD'; details['original_price']=value
                    p=Product(title=str(r.get('title',''))[:200],category=str(r.get('main_category') or r.get('category') or '未分类')[:50],brand=str(r.get('brand') or r.get('store') or '')[:100],price_cents=cents,stock=0,description=description[:12000],image=image,specs=details,source=args.format,status='inactive')
                validated.append(p)
            with db() as c:
                for p in validated: write_product(c,p,secrets.token_hex(12))
        print(f'Imported {len(validated)} products; skipped {skipped} missing prices. External datasets start inactive; verify currency/stock before publication.')
if __name__=='__main__': main()
