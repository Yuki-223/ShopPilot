"""Deterministic comparison: no model-invented ingredient or unit-cost facts."""
import math

def vc_cost(p):
    specs=p['specs']
    dose,count=specs.get('每片VC毫克'),specs.get('片数')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (dose,count)):
        return None
    # RMB yuan per gram of declared vitamin C, NOT dosage or efficacy advice.
    return round(p['price_cents']*10/(dose*count),4)

def build_comparison(products):
    rows=[{'attribute':'价格（人民币元）','values':[f"{p['price_cents']/100:.2f}" for p in products]},
          {'attribute':'品牌','values':[p['brand'] or '未知' for p in products]},
          {'attribute':'分类','values':[p['category'] for p in products]}]
    keys=list(dict.fromkeys(k for p in products for k in p['specs']))
    for key in keys:
        rows.append({'attribute':key,'values':[str(p['specs'].get(key,'未知')) for p in products]})
    rows.append({'attribute':'配料资料','values':['、'.join(p['ingredients']) if p['ingredients'] else '未知，不能认定不含指定成分' for p in products]})
    costs=[vc_cost(p) for p in products]
    if any(v is not None for v in costs):
        rows.append({'attribute':'每克标签VC成本（元）','values':['资料不足' if v is None else f'{v:.4f}' for v in costs]})
    rows.append({'attribute':'资料更新时间','values':[p['updated'] for p in products]})
    return {'products':[{'id':p['id'],'title':p['title']} for p in products],'rows':rows,'note':'单位成本只比较标签含量与记录价格，不代表吸收效果或服用建议。不同品类不计算通用性价比分数。'}
