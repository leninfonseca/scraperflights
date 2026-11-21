"""Bounded, non-executing HTML/JSON readers shared by public-page adapters."""
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import json
import re

MAX_NODES = 50000
DECODER = json.JSONDecoder()


def amount(value):
    """Accept explicit decimal amounts, including Spanish and English separators."""
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    if not isinstance(value, str):
        try:
            parsed = Decimal(str(value))
            return parsed if parsed.is_finite() and 0 <= parsed <= Decimal('10000000') else None
        except InvalidOperation:
            return None
    text = str(value).strip().replace('\u00a0', '').replace('\u202f', '').replace(' ', '')
    if not re.fullmatch(r'\d+(?:[.,]\d+)*', text):
        return None
    if ',' in text and '.' in text:
        decimal, grouping = (',', '.') if text.rfind(',') > text.rfind('.') else ('.', ',')
        integer, fraction = text.rsplit(decimal, 1)
        if not re.fullmatch(r'\d{1,3}(?:' + re.escape(grouping) + r'\d{3})+', integer) or not 1 <= len(fraction) <= 2:
            return None
        text = integer.replace(grouping, '') + '.' + fraction
    elif ',' in text or '.' in text:
        separator = ',' if ',' in text else '.'
        if re.fullmatch(r'\d{1,3}(?:' + re.escape(separator) + r'\d{3})+', text):
            text = text.replace(separator, '')
        elif text.count(separator) == 1 and len(text.rsplit(separator, 1)[1]) <= 2:
            text = text.replace(separator, '.')
        else:
            return None
    try:
        result = Decimal(text)
        return result if result.is_finite() and 0 <= result <= Decimal('10000000') else None
    except InvalidOperation:
        return None


def has_type(node, name):
    value = node.get('@type') if isinstance(node, dict) else None
    return value == name or isinstance(value, list) and name in value


def walk(value):
    stack = [(value, 0)]
    for _ in range(MAX_NODES):
        if not stack:
            return
        item, depth = stack.pop()
        if depth > 64:
            continue
        if isinstance(item, dict):
            yield item
            stack.extend((v, depth + 1) for v in reversed(list(item.values())))
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in reversed(item))


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts, self.articles, self.parts = [], [], []
        self.stack = []
        self.script = None
        self.article = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.script = [attrs, []]
        hidden = (tag in ('script', 'style', 'template', 'noscript') or 'hidden' in attrs
                  or (attrs.get('aria-hidden') or '').lower() == 'true'
                  or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', attrs.get('style') or '', re.I)))
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.stack.append((tag, hidden or bool(self.stack and self.stack[-1][1])))
        if tag == 'article' and self.article is None:
            self.article = []
        if self.article is not None:
            self.article.append(self.get_starttag_text())
        if tag in ('br', 'hr') and not (self.stack and self.stack[-1][1]):
            self.parts.append(' ')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.scripts.append((self.script[0], ''.join(self.script[1])))
            self.script = None
        if self.article is not None:
            self.article.append(f'</{tag}>')
            if tag == 'article':
                self.articles.append(''.join(self.article))
                self.article = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in ('p', 'div', 'span', 'li', 'td', 'article'):
            self.parts.append(' ')

    def handle_data(self, data):
        if self.script is not None:
            self.script[1].append(data)
        if self.article is not None:
            self.article.append(data)
        if not (self.stack and self.stack[-1][1]):
            self.parts.append(data)


def document(html):
    parser = Document()
    parser.feed(html)
    parser.close()
    return parser


def visible_text(html):
    return ' '.join(' '.join(document(html).parts).split())


def structured_nodes(html):
    """JSON-LD arrays, graphs and local @id references; never fetch remote contexts."""
    nodes = []
    for attrs, text in document(html).scripts:
        if (attrs.get('type') or '').split(';')[0].strip().lower() != 'application/ld+json':
            continue
        try:
            nodes.extend(walk(json.loads(text)))
        except (ValueError, RecursionError):
            continue
        if len(nodes) > MAX_NODES:
            break
    indexed = {row['@id']: row for row in nodes if isinstance(row.get('@id'), str) and len(row) > 1}
    for node in nodes[:MAX_NODES]:
        # Shallow expansion is sufficient for offers/brand/airports without cycles.
        yield {key: indexed.get(value['@id'], value) if isinstance(value, dict) and set(value) == {'@id'} and isinstance(value['@id'], str) else value
               for key, value in node.items()}


def embedded_nodes(html):
    """Read JSON object literals without relying on key order or executing scripts."""
    scripts = [text for _, text in document(html).scripts] or [html]
    candidates = 0
    count = 0
    opening = re.compile(r'[\[{]')
    for text in scripts:
        offset = 0
        while candidates < 10000:
            match = opening.search(text, offset)
            if not match:
                break
            start = match.start()
            candidates += 1
            try:
                value, end = DECODER.raw_decode(text, start)
            except (ValueError, RecursionError):
                offset = start + 1
                continue
            for node in walk(value):
                yield node
                count += 1
                if count >= MAX_NODES:
                    return
            offset = end


def object_value(value):
    return value if isinstance(value, dict) else {}


def route_name_matches(name, origin, destination):
    if not isinstance(name, str):
        return False
    text = name.casefold()
    a, b = text.find(origin.casefold()), text.find(destination.casefold())
    return 0 <= a < b
