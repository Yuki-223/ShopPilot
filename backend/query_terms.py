"""Small transparent bilingual lexicon; explicitly not a semantic retrieval model."""
TERMS={
 '维生素 C':('营养保健',('维生素c','vitaminc','ascorbicacid')),
 '鱼油':('营养保健',('鱼油','fishoil','omega3')),
 '耳机':('数码电子',('耳机','headphone','earbud','headset')),
 '音箱':('数码电子',('音箱','speaker')),
 '鼠标':('数码电子',('鼠标','mouse')),
 '充电器':('数码电子',('充电器','charger')),
 '跑鞋':('服饰运动',('跑鞋','runningshoe','sneaker')),
 '长裤':('服饰运动',('长裤','pants','trousers')),
 '短袖':('服饰运动',('短袖','t-shirt','tshirt')),
 '台灯':('家居生活',('台灯','desklamp','tablelamp')),
 '燕麦':('食品饮料',('燕麦','oat')),
 '面霜':('美妆个护',('面霜','facecream','moisturiz')),
 '洁面':('美妆个护',('洁面','cleanser','facewash')),
}

def normalize(text): return ''.join(str(text).casefold().split())

def match_keyword(title,keyword):
    aliases=TERMS.get(keyword,('',(keyword,)))[1]
    normalized=normalize(title)
    return any(normalize(alias) in normalized for alias in aliases)
