"""Product provenance is separate from local edit time and current-price verification."""
import math
import time

SOURCE_NAMES={'demo':'虚构教学商品','dummyjson':'DummyJSON 测试数据','amazon2023':'Amazon 2023 历史商品','manual':'管理员录入','external':'外部候选'}


def valid_time(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0 or value>time.time()+300:
        return None
    return value


def quality(product,now=None):
    now=now or time.time()
    raw=product.get('specs',{}).get('_provenance',{})
    meta=raw if isinstance(raw,dict) else {}
    checked=valid_time(meta.get('price_checked_at'))
    source=product.get('source','manual')
    if source in ('demo','dummyjson'):
        label='演示数据，非真实报价'; state='demo'
    elif checked is None:
        state='unverified'; label='历史价格，未核实当前报价' if source=='amazon2023' else '价格尚未核验'
    elif now-checked>7*86400:
        state='stale'; label='价格核验已超过7天，请复核'
    else:
        state='checked'; label='管理员近期核验，仍以购买页为准'
    warnings=[]
    if state!='checked': warnings.append(label)
    if product.get('ingredients') is None: warnings.append('配料资料不足，不能确认不含指定成分')
    if not product.get('source_url'): warnings.append('未提供商品来源链接')
    if source=='amazon2023': warnings.append('来自2023数据集，不代表当前在售、库存或配方')
    return {'source_label':SOURCE_NAMES.get(source,source),'price_state':state,'price_label':label,
            'fetched_at':valid_time(meta.get('fetched_at')),'source_updated_at':valid_time(meta.get('source_updated_at')),
            'price_checked_at':checked,'review_status':meta.get('review_status','unreviewed'),
            'review_note':str(meta.get('review_note',''))[:2000],'dataset_version':str(meta.get('dataset_version',''))[:100],
            'source_record_id':str(product.get('specs',{}).get('source_id',''))[:100],
            'dataset_url':meta.get('dataset_url',''),'ingredients_complete':product.get('ingredients') is not None,'warnings':warnings}
