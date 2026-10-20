/** Original category illustrations for fictional/unpictured products, never real pack shots. */
export function productArt(p){
 const cat=p.category;let art;
 if(cat==='数码电子')art='<path d="M28 76V60a32 32 0 0 1 64 0v16" fill="none" stroke="#426753" stroke-width="9"/><rect x="20" y="65" width="20" height="39" rx="8" fill="#547a63"/><rect x="80" y="65" width="20" height="39" rx="8" fill="#547a63"/>';
 else if(cat==='服饰运动')art='<path d="m40 28-24 17 14 24 10-6v50h40V63l10 6 14-24-24-17c-10 13-30 13-40 0Z" fill="#b5c7ac" stroke="#759071" stroke-width="2"/>';
 else if(cat==='家居生活')art='<path d="M30 48h57v52a15 15 0 0 1-15 15H45a15 15 0 0 1-15-15Z" fill="#d9c8a6"/><path d="M87 58h8a14 14 0 0 1 0 28h-8" fill="none" stroke="#a88e65" stroke-width="7"/><path d="M45 20c-10 12 9 13 0 24m20-24c-10 12 9 13 0 24" stroke="#adad97" stroke-width="3" fill="none"/>';
 else if(cat==='食品饮料')art='<path d="m30 30 62 0-5 85H35Z" fill="#e1c99a" stroke="#b59d6d" stroke-width="2"/><path d="M30 30h62v13H30" fill="#809d69"/><rect x="36" y="58" width="50" height="35" rx="4" fill="#f7f7ed"/><path d="m60 64-10 14 10 12 10-12Z" fill="#a2b77d"/>';
 else art='<rect x="39" y="20" width="43" height="18" rx="4" fill="#587249"/><rect x="30" y="36" width="62" height="85" rx="13" fill="'+(cat==='美妆个护'?'#d8dfcc':'#bc9460')+'"/><rect x="31" y="61" width="60" height="42" fill="#fafaf2"/><text x="61" y="78" text-anchor="middle" font-family="Arial" font-size="9" fill="#547145">DEMO</text><text x="61" y="94" text-anchor="middle" font-family="Arial" font-size="14" fill="#547145">'+(p.title?.includes('维生素')?'C':'DAILY')+'</text>';
 return '<svg viewBox="0 0 120 145" role="img" aria-label="商品分类示意图" class="product-art">'+art+'</svg>';
}
