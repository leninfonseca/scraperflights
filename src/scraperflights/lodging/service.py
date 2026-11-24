"""Accommodation orchestration and exports, without inventory APIs or bookings."""
import csv
from dataclasses import asdict
import json
from uuid import uuid4

from ..connectors.web.vueling import VuelingWeb
from ..core import now, money
from ..http import Client, ProviderError
from .catalog import AUTOMATIC, catalog, search_url
from .extract import html_properties
from .models import LodgingSearch


def run_lodging(search, providers=None, budget=5, fetch=None):
    providers=list(dict.fromkeys(providers if providers is not None else AUTOMATIC))
    if not providers or any(name not in AUTOMATIC for name in providers):
        raise ValueError('Elige fuentes HTML de alojamiento válidas.')
    if type(budget) is not int or not 1 <= budget <= 10:
        raise ValueError('Presupuesto HTTP: 1–10 consultas.')
    client=Client(budget=budget,timeout=12)
    started=now();sources=[];observations=[]
    for provider in providers:
        reader=VuelingWeb(client)
        url=search_url(provider,search)
        source={'provider':provider,'name':AUTOMATIC[provider],'url':url,'started_at':now()}
        sources.append(source)
        try:
            html=fetch(provider,url) if fetch else reader.fetch(url)
            rows=html_properties(html,provider,search,url)
            observations.extend(rows)
            source.update(status='references_found' if any(row['amount'] is not None for row in rows) else 'listings_only' if rows else 'no_recognized_properties',results=len(rows),
                          priced_results=sum(row['amount'] is not None for row in rows))
        except (ProviderError,ValueError,TypeError,KeyError,RecursionError) as exc:
            source.update(status='error',error=str(exc) if isinstance(exc,ProviderError) else 'lodging_schema_validation_failed')
        finally:
            if hasattr(reader,'fetch_diagnostics'):source['http']=reader.fetch_diagnostics
            source['finished_at']=now()
    comparable=[row for row in observations if row['amount'] is not None and row['currency']=='EUR'
                and row['scope']=='dated_stay_reference' and row['price_basis']=='stay']
    comparable.sort(key=lambda row:money(row['amount']))
    return {'kind':'lodging','id':str(uuid4()),'search':asdict(search)|{'nights':search.nights,'city':catalog_city(search)},
            'started_at':started,'finished_at':now(),'sources':sources,'observations':observations,
            'comparable_stays':comparable,'lowest_comparable_reference':comparable[0] if comparable else None,
            'external_links':catalog(search),
            'notice':'Precios publicados sin disponibilidad ni total de compra confirmados. Las fechas enviadas en la URL no prueban que una tarifa corresponda a tu estancia. No se multiplican precios orientativos por noches ni se mezclan monedas. Ajusta la entrada a la llegada real del vuelo.'}


def catalog_city(search):
    from .catalog import CITIES
    return CITIES[search.destination]['name']


def export_lodging(report,directory):
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/('lodging-'+report['id']+'.json')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    fields=['provider','property','amount','currency','price_basis','scope','checkin','checkout','adults','rooms',
            'requested_destination','requested_checkin','requested_checkout','requested_adults','requested_rooms',
            'rating_10','review_count','address','observed_at','link','warnings']
    with target.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for item in report['observations']:
            row=item|{'requested_'+key:report['search'][key] for key in ('destination','checkin','checkout','adults','rooms')}
            row['warnings']=';'.join(item['warnings'])
            writer.writerow({key:"'"+str(value) if isinstance(value,str) and value.startswith(('=','+','-','@','\t','\r')) else value for key,value in row.items()})
    return target


def search_from_payload(data):
    if not isinstance(data,dict):raise ValueError('Petición de alojamiento inválida.')
    search=LodgingSearch(data.get('destination'),data.get('checkin'),data.get('checkout'),data.get('adults',1),data.get('rooms',1))
    providers=data.get('providers',list(AUTOMATIC))
    if not isinstance(providers,list) or not providers or any(not isinstance(key,str) or key not in AUTOMATIC for key in providers):
        raise ValueError('Selecciona al menos una fuente de alojamiento válida.')
    return search,providers
