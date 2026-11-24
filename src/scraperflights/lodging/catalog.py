"""Dated public landing URLs and an honest directory of additional sources."""
from urllib.parse import urlencode

CITIES = {
    'BCN': {'name':'Barcelona', 'country':'es', 'trip':219, 'kayak':22567, 'expedia':179992,
            'hotels':453494, 'hotel_slug':'barcelona-espana'},
    'MAD': {'name':'Madrid', 'country':'es', 'trip':357, 'kayak':32213, 'expedia':178281,
            'hotels':457987, 'hotel_slug':'madrid-espana'},
    'MTY': {'name':'Monterrey', 'country':'mx', 'trip':3697, 'kayak':464, 'expedia':2448,
            'hotels':829675, 'hotel_slug':'monterrey-mexico'},
}
AUTOMATIC = {'booking':'Booking.com', 'expedia':'Expedia', 'hotels':'Hoteles.com',
             'tripcom':'Trip.com', 'kayak':'KAYAK'}
MANUAL = {
    'Agoda':'https://www.agoda.com/es-es/', 'Airbnb':'https://www.airbnb.es/',
    'Vrbo':'https://www.vrbo.com/es-es/', 'Hostelworld':'https://www.hostelworld.com/',
    'Trivago':'https://www.trivago.es/', 'momondo':'https://www.momondo.es/hoteles',
    'Google Hotels':'https://www.google.com/travel/hotels', 'Skyscanner Hoteles':'https://www.skyscanner.es/hoteles',
    'Despegar':'https://www.despegar.com.mx/hoteles/', 'Destinia':'https://destinia.com/',
    'Central de Reservas':'https://www.centraldereservas.com/', 'Atrápalo':'https://www.atrapalo.com/hoteles/',
    'Logitravel':'https://www.logitravel.com/hoteles/', 'Rumbo':'https://www.rumbo.es/hoteles',
    'lastminute.com':'https://www.lastminute.com/hotels/', 'eDreams':'https://www.edreams.es/hoteles/',
    'Priceline':'https://www.priceline.com/', 'Orbitz':'https://www.orbitz.com/Hotels',
    'Travelocity':'https://www.travelocity.com/Hotels', 'HotelsCombined':'https://www.hotelscombined.com/',
    'HRS':'https://www.hrs.com/', 'Traveloka':'https://www.traveloka.com/',
    'Marriott':'https://www.marriott.com/', 'Hilton':'https://www.hilton.com/es/',
    'IHG':'https://www.ihg.com/', 'Accor':'https://all.accor.com/',
    'NH Hotels':'https://www.nh-hotels.com/', 'Meliá':'https://www.melia.com/',
    'Barceló':'https://www.barcelo.com/', 'Fiesta Americana':'https://www.fiestamericana.com/',
    'Best Western':'https://www.bestwestern.com/', 'Wyndham':'https://www.wyndhamhotels.com/',
}


def search_url(provider, search):
    city = CITIES[search.destination]
    slug = city['name'].lower()
    dates = {'checkin':search.checkin, 'checkout':search.checkout}
    if provider == 'booking':
        return f'https://www.booking.com/city/{city["country"]}/{slug}.es.html?' + urlencode(dates | {
            'group_adults':search.adults,'no_rooms':search.rooms,'group_children':0,'selected_currency':'EUR'})
    if provider == 'tripcom':
        return f'https://es.trip.com/hotels/{slug}-hotels-list-{city["trip"]}/?' + urlencode(dates | {
            'adult':search.adults,'crn':search.rooms,'curr':'EUR'})
    if provider == 'kayak':
        return f'https://www.kayak.es/Hoteles-en-{city["name"]}.{city["kayak"]}.hotel.ksp?' + urlencode(dates | {
            'adults':search.adults,'rooms':search.rooms,'currency':'EUR'})
    params = {'startDate':search.checkin,'endDate':search.checkout,'adults':search.adults,'rooms':search.rooms,'currency':'EUR'}
    if provider == 'expedia':
        return f'https://www.expedia.es/{city["name"]}-Hoteles.d{city["expedia"]}.Guia-Viajes-Hoteles?' + urlencode(params)
    if provider == 'hotels':
        return f'https://es.hoteles.com/de{city["hotels"]}/hoteles-{city["hotel_slug"]}/?' + urlencode(params)
    raise ValueError('Fuente de alojamiento desconocida.')


def catalog(search=None):
    automatic = [{'id':key,'name':name,'method':'html','dates_in_url':True,
                  'url':search_url(key, search) if search else '',
                  'notice':'Puede devolver precios generales o ignorar las fechas; consulta el alcance de cada resultado.'}
                 for key,name in AUTOMATIC.items()]
    return automatic + [{'id':'manual-'+str(i),'name':name,'method':'manual','dates_in_url':False,'url':url,
                         'notice':'Enlace adicional. Completa ciudad, fechas y ocupación en la web; no es un scraper implementado.'}
                        for i,(name,url) in enumerate(MANUAL.items())]
