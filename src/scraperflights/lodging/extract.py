"""Property-level HTML extraction. Request parameters never prove price dates."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import re
from ..connectors.web.html import structured_nodes, has_type, object_value, amount
from ..core import now
from .catalog import CITIES


TYPES = ('Hotel','Hostel','LodgingBusiness','Apartment','VacationRental','BedAndBreakfast','Resort','Motel')


def safe_link(value, base):
    if not isinstance(value,str):
        return None
    try:
        url = urljoin(base,value)
        parts = urlsplit(url)
        if parts.scheme == 'https' and parts.hostname == urlsplit(base).hostname and not parts.username and not parts.password:
            return url
    except ValueError:
        pass
    return None


def euro(text):
    # Currency must be stated on this property, not inferred from the requested URL.
    for pattern in (r'€\s*(\d[\d.,\s\u00a0\u202f]*)', r'(\d[\d.,\s\u00a0\u202f]*)\s*(?:€|EUR)'):
        match = re.search(pattern,text)
        if match:
            value = amount(match[1].strip())
            if value is not None:
                return value
    return None


def rating(row):
    raw = object_value(row.get('aggregateRating'))
    value, best = amount(raw.get('ratingValue')), amount(raw.get('bestRating'))
    # Missing scale is unknown; hotel stars are not guest review scores.
    score = round(float(value / best * 10),2) if value is not None and best and 0 <= value <= best else None
    count = raw.get('reviewCount',raw.get('ratingCount'))
    return score, int(count) if str(count).isdigit() else None


def property_row(row, provider, search, base, offer=None):
    name = row.get('name')
    if not isinstance(name,str) or not name.strip():
        return None
    offer = object_value(offer)
    if str(offer.get('availability','')).rsplit('/',1)[-1] in ('OutOfStock','SoldOut','Discontinued'):
        return None
    currency = offer.get('priceCurrency')
    price = amount(offer.get('price')) if isinstance(currency,str) and re.fullmatch('[A-Z]{3}',currency) else None
    basis = 'unknown'
    spec = object_value(offer.get('priceSpecification'))
    unit = spec.get('unitCode',offer.get('unitCode'))
    if unit in ('DAY','NIGHT'):
        basis = 'night'
    elif offer.get('priceBasis') in ('stay','total_stay'):
        basis = 'stay'
    if price is None and row.get('priceRange'):
        price = euro(str(row['priceRange']))
        if price is not None:
            currency = 'EUR'
    checkin, checkout = offer.get('checkinDate'),offer.get('checkoutDate')
    date_match = (checkin,checkout) == (search.checkin,search.checkout)
    occupancy_match = type(offer.get('adults')) is int and type(offer.get('rooms')) is int and (offer['adults'],offer['rooms']) == (search.adults,search.rooms)
    score,count = rating(row)
    address = row.get('address')
    if isinstance(address,dict):
        address = ', '.join(str(address.get(k)) for k in ('streetAddress','addressLocality','addressCountry') if address.get(k))
    warnings = ['availability_and_checkout_unverified','taxes_and_fees_unconfirmed','location_requires_review']
    if not date_match: warnings.append('stay_dates_unconfirmed')
    if not occupancy_match: warnings.append('occupancy_unconfirmed')
    if basis == 'unknown' and price is not None: warnings.append('price_basis_unknown')
    return {'provider':provider,'property':name.strip()[:500],'address':str(address or '')[:1000],
            'link':safe_link(row.get('url') or offer.get('url'),base),'observed_at':now(),
            'amount':str(price) if price is not None else None,'currency':currency if price is not None else None,
            'price_basis':basis,'scope':'dated_stay_reference' if date_match and occupancy_match else 'undated_reference',
            'checkin':checkin if isinstance(checkin,str) else None,'checkout':checkout if isinstance(checkout,str) else None,
            'adults':offer.get('adults') if occupancy_match else None,'rooms':offer.get('rooms') if occupancy_match else None,
            'rating_10':score,'review_count':count,'price_text':str(offer.get('price',row.get('priceRange','')))[:300],
            'extraction_method':'structured_data','warnings':warnings}


class Node:
    def __init__(self,tag='',attrs=None,parent=None):
        self.tag,self.attrs,self.parent=tag,dict(attrs or []),parent
        self.children=[]
    def text(self):
        if self.attrs.get('aria-hidden') == 'true' or 'hidden' in self.attrs or self.tag in ('script','style','template','noscript'):
            return ''
        return ' '.join(child.text() if isinstance(child,Node) else child for child in self.children).strip()
    def descendants(self):
        stack=[self]
        while stack:
            item=stack.pop();yield item
            stack.extend(child for child in reversed(item.children) if isinstance(child,Node))
    def first(self,predicate):
        return next((node for node in self.descendants() if predicate(node)),None)


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root=Node();self.current=self.root;self.count=0;self.depth=0
    def handle_starttag(self,tag,attrs):
        self.count+=1
        if self.count>100000 or self.depth>128:raise ValueError('HTML de alojamiento demasiado complejo.')
        node=Node(tag,attrs,self.current);self.current.children.append(node)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.current=node;self.depth+=1
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs);self.handle_endtag(tag)
    def handle_endtag(self,tag):
        node=self.current
        while node.parent:
            if node.tag==tag:
                self.current=node.parent
                self.depth=0;parent=self.current
                while parent.parent:self.depth+=1;parent=parent.parent
                return
            node=node.parent
    def handle_data(self,data):
        self.current.children.append(data)


def html_properties(html, provider, search, base):
    result=[]
    for node in structured_nodes(html):
        if not any(has_type(node,t) for t in TYPES):continue
        offers=node.get('offers')
        for offer in offers if isinstance(offers,list) else [offers]:
            record=property_row(node,provider,search,base,offer)
            if record:result.append(record)
    tree=Tree();tree.feed(html)
    # Explicit property cards only; never take a FAQ's city-wide 'from' price.
    for node in tree.root.descendants():
        classes=(node.attrs.get('class') or '').split()
        trip_card='Template-Grid-Hotel-Cards-hotel-card' in classes
        booking_card=node.attrs.get('data-testid')=='property-card'
        expedia_card=node.attrs.get('data-stid')=='property-listing'
        if not (trip_card or booking_card or expedia_card):continue
        heading=node.first(lambda n:n.tag in ('h2','h3'))
        title=node.first(lambda n:n.attrs.get('data-testid')=='title') or heading
        if not title:continue
        anchor=node if node.tag=='a' else node.first(lambda n:n.tag=='a' and n.attrs.get('href'))
        data={'name':title.text().strip(' ★'),'url':anchor.attrs.get('href') if anchor else None}
        score_node=node.first(lambda n:'Template-Grid-Hotel-Cards-rating-score' in (n.attrs.get('class') or '').split())
        if score_node:data['aggregateRating']={'ratingValue':score_node.text(),'bestRating':10}
        price_node=node.first(lambda n:n.attrs.get('data-testid')=='price-and-discounted-price' or 'Template-Grid-Hotel-Cards-hotel-price' in (n.attrs.get('class') or '').split())
        price=euro(price_node.text()) if price_node else None
        record=property_row(data,provider,search,base)
        if not record:continue
        record['extraction_method']='html_property_card'
        if price is not None:
            record['price_text']=price_node.text()[:300]
            record.update(amount=str(price),currency='EUR',price_basis='night' if trip_card else 'unknown')
            if not trip_card:record['warnings'].append('price_basis_unknown')
        result.append(record)
    # Booking city pages use titleLink even when no priced search cards are returned.
    if provider=='booking':
        for anchor in tree.root.descendants():
            if anchor.attrs.get('data-testid')!='titleLink':continue
            heading=anchor.first(lambda n:n.tag in ('h2','h3'))
            record=property_row({'name':heading.text() if heading else anchor.text(),'url':anchor.attrs.get('href')},provider,search,base)
            if record:result.append(record)
    if provider in ('expedia','hotels'):
        for anchor in tree.root.descendants():
            href=anchor.attrs.get('href') or ''
            if anchor.tag=='a' and ('.Informacion-Hotel' in href or re.search(r'/ho\d+/',href)):
                name=anchor.text().replace('Se abre en una ventana nueva','').strip(' :')
                if CITIES[search.destination]['name'].casefold() not in (name+' '+href).casefold():continue
                record=property_row({'name':name,'url':href},provider,search,base)
                if record:result.append(record)
    # Merge duplicate schema/HTML representations, retaining richer property records.
    unique={}
    for row in result:
        if not row['link']:continue
        key=(urlsplit(row['link']).path.rstrip('/'),row['checkin'],row['checkout'],row['price_basis'])
        previous=unique.get(key)
        if previous is None or row['amount'] is not None and previous['amount'] is None:
            unique[key]=row
        elif previous['rating_10'] is None and row['rating_10'] is not None:
            previous['rating_10'],previous['review_count']=row['rating_10'],row['review_count']
    metadata={}
    for row in unique.values():
        path=urlsplit(row['link']).path.rstrip('/')
        if row['rating_10'] is not None:metadata[path]=(row['rating_10'],row['review_count'])
    priced_paths={urlsplit(row['link']).path.rstrip('/') for row in unique.values() if row['amount'] is not None}
    final=[]
    for row in unique.values():
        path=urlsplit(row['link']).path.rstrip('/')
        if row['amount'] is None and path in priced_paths:continue
        if row['rating_10'] is None and path in metadata:row['rating_10'],row['review_count']=metadata[path]
        final.append(row)
    return final[:200]
