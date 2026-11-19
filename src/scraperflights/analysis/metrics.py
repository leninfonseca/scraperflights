"""Price changes are computed within an explicit comparable series."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from statistics import median
from zoneinfo import ZoneInfo

FIELDS = ('amount', 'observed_at', 'origin', 'destination', 'departure', 'return_date',
          'currency', 'provider', 'seller', 'transport_mode', 'journey_leg', 'scope',
          'adults', 'cabin_bags', 'checked_bags', 'profile', 'comparison_group')
REQUIRED = ('amount', 'observed_at', 'origin', 'destination', 'departure', 'currency', 'transport_mode', 'scope')


def number(value):
    if isinstance(value, bool):
        raise ValueError('Precio inválido')
    text = str('' if value is None else value).strip().replace(' ', '').replace('\u00a0', '')
    if ',' in text:
        if '.' in text:
            text = text.replace('.', '').replace(',', '.') if text.rfind(',') > text.rfind('.') else text.replace(',', '')
        else:
            text = text.replace(',', '.')
    result = Decimal(text)
    if not result.is_finite() or result < 0:
        raise ValueError('Precio inválido')
    return result


def timestamp(value, epoch=None):
    text = str(value or '').strip()
    if epoch:
        try:
            return datetime.fromisoformat(epoch) + timedelta(days=float(text))
        except (ValueError, OverflowError):
            pass
    if not text:
        raise ValueError('Fecha vacía')
    text = text.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for pattern in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y'):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                pass
    raise ValueError('Fecha inválida')


def day(value, epoch=None):
    if not value:
        return ''
    parsed = timestamp(value, epoch)
    if isinstance(parsed, str):
        parsed = datetime.fromisoformat(parsed)
    return parsed.date().isoformat()


def normalize(rows, mapping=None, defaults=None, source='', epoch=None):
    mapping, defaults = mapping or {}, defaults or {}
    accepted, rejected = [], []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict):
            rejected.append({'row': i + 2, 'reason': 'Fila inválida'})
            continue
        values = {field: raw.get(mapping.get(field, field)) for field in FIELDS}
        for field, value in defaults.items():
            if field in FIELDS and values.get(field) in (None, ''):
                values[field] = value
        try:
            missing = [f for f in REQUIRED if values[f] in (None, '')]
            if missing:
                raise ValueError('Falta ' + ', '.join(missing))
            if raw.get('sandbox') is True or str(raw.get('sandbox')).lower() == 'true':
                raise ValueError('Datos sandbox')
            amount = number(values['amount'])
            observed = timestamp(values['observed_at'], epoch)
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=ZoneInfo('Europe/Madrid'))
            mode = str(values['transport_mode']).strip().lower()
            mode = {'avión': 'flight', 'avion': 'flight', 'tren': 'train', 'autobús': 'bus',
                    'autobus': 'bus', 'blablacar': 'carpool', 'coche compartido': 'carpool'}.get(mode, mode)
            if mode not in ('flight', 'train', 'bus', 'carpool'):
                raise ValueError('Medio de transporte no reconocido')
            origin, destination = str(values['origin']).strip().upper(), str(values['destination']).strip().upper()
            if origin == destination or len(origin) != 3 or len(destination) != 3:
                raise ValueError('Usa códigos de aeropuerto distintos de tres letras')
            currency = str(values['currency']).strip().upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError('Moneda ISO de tres letras')
            scope = str(values['scope']).strip()
            leg = str(values['journey_leg'] or 'unspecified')
            row = dict(values, amount=str(amount), observed_at=observed.astimezone(timezone.utc).isoformat(),
                       departure=day(values['departure'], epoch), return_date=day(values['return_date'], epoch),
                       origin=origin, destination=destination, currency=currency, scope=scope,
                       journey_leg=leg, transport_mode=mode, source=source)
            for count in ('adults', 'cabin_bags', 'checked_bags'):
                value = values[count]
                if value == 'unknown':
                    value = None
                if value not in (None, ''):
                    parsed = number(value)
                    if parsed != parsed.to_integral_value() or (count == 'adults' and parsed < 1):
                        raise ValueError('Viajeros y maletas requieren números enteros válidos')
                    row[count] = str(parsed.to_integral_value())
                else:
                    row[count] = 'unknown'
            for field in ('provider', 'seller', 'profile', 'comparison_group'):
                row[field] = str(values[field] or 'unknown')
            accepted.append(row)
        except (ValueError, TypeError, OverflowError, InvalidOperation) as exc:
            rejected.append({'row': i + 2, 'reason': str(exc)})
    return accepted, rejected


GROUP_FIELDS = ('origin', 'destination', 'departure', 'return_date', 'currency', 'provider',
                'seller', 'transport_mode', 'journey_leg', 'scope', 'adults', 'cabin_bags',
                'checked_bags', 'profile', 'comparison_group')


def percent(new, old):
    return str((new - old) / old * 100) if old else None


def analyze(rows):
    unique, duplicates = {}, 0
    for row in rows:
        key = tuple(row.get(k) for k in (*GROUP_FIELDS, 'observed_at', 'amount'))
        if key in unique:
            duplicates += 1
            unique[key]['sources'] = sorted(set(unique[key]['sources'] + [row['source']]))
        else:
            unique[key] = row | {'sources': [row['source']]}
    groups = {}
    for row in unique.values():
        key = tuple(row.get(k) for k in GROUP_FIELDS)
        groups.setdefault(key, []).append(row)
    result = []
    for key, observations in groups.items():
        observations.sort(key=lambda r: (r['observed_at'], Decimal(r['amount'])))
        prices = [Decimal(r['amount']) for r in observations]
        first, last = prices[0], prices[-1]
        previous = prices[-2] if len(prices) > 1 else None
        mid = median(prices)
        points = []
        for index, row in enumerate(observations):
            amount = Decimal(row['amount'])
            points.append(row | {'change_from_first_pct': percent(amount, first),
                                 'change_from_previous_pct': percent(amount, prices[index-1]) if index else None})
        ties = Counter(r['observed_at'] for r in observations)
        ambiguous = any(value > 1 for value in ties.values())
        result.append(dict(zip(GROUP_FIELDS, key)) | {
            'count': len(prices), 'first': str(first), 'latest': str(last), 'minimum': str(min(prices)),
            'maximum': str(max(prices)), 'mean': str(sum(prices)/len(prices)), 'median': str(mid),
            'change_pct': percent(last, first) if len(prices) > 1 and not ambiguous else None,
            'previous_change_pct': percent(last, previous) if previous is not None and not ambiguous else None,
            'range_pct': percent(max(prices), min(prices)), 'vs_median_pct': percent(last, mid) if not ambiguous else None,
            'ambiguous_timestamps': ambiguous, 'points': points,
        })
    return {'groups': result, 'observations': len(unique), 'duplicates': duplicates,
            'notice': 'Variación = (precio nuevo − base) / base × 100. Base cero sin porcentaje. Las series agrupan referencias con iguales condiciones declaradas, sin garantizar el mismo billete.'}
