'use strict';

const $ = id => document.getElementById(id);
const asList = value => Array.isArray(value) ? value : [];
const formatDate = value => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return String(value);
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' }).format(date);
};
const labels = {
  indicative_dated_reference: 'Coincide con tus fechas', indicative_monthly_minimum: 'Mínimo del mes',
  indicative_route_minimum: 'Mínimo de la ruta', imported_snapshot: 'Precio importado',
  availability_and_checkout_unverified: 'Disponibilidad y total por confirmar',
  exact_flight_not_confirmed: 'Vuelo concreto sin confirmar', stops_unconfirmed: 'Escalas sin confirmar',
  revalidation_failed: 'No se pudo revalidar', indicative: 'Orientativo', imported: 'Importado',
  complete: 'Completo', partial: 'Parcial', unsupported_profile: 'Perfil sin cobertura',
  credentials_missing: 'Faltan credenciales', error: 'Error', paired: 'Comparable',
  no_comparable_observations: 'Sin pares comparables', same_minimum: 'Mismo mínimo',
  different_minimum: 'Mínimo diferente', unpaired: 'Falta un perfil', device: 'Dispositivo',
  locale: 'Idioma y región', session: 'Sesión', desktop: 'Escritorio', mobile: 'Móvil',
  fresh: 'Primera visita', warm: 'Segunda visita', total_incomplete: 'Total incompleto',
  not_freshly_revalidated: 'Sin verificación reciente', seller_reputation_unapproved: 'Vendedor pendiente de revisión',
  required_baggage_total_unconfirmed: 'Equipaje sin precio confirmado',
};
const label = value => labels[value] || value || '—';
const offerReasons = row => [...new Set([
  ...asList(row.warnings),
  ...(Array.isArray(row.exclusion_reasons) ? row.exclusion_reasons :
    (row.exclusion_reasons?.match(/['"]([^'"]+)['"]/g) || []).map(x => x.slice(1, -1)))
])];
const scopeOf = row => offerReasons(row).find(x => x.startsWith('indicative_') || x === 'imported_snapshot') ||
  (row.total ? 'Precio con total informado' : 'Alcance sin identificar');

function el(tag, text, cls) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = text;
  if (cls) element.className = cls;
  return element;
}
function details(title, value) {
  const node = el('details');
  node.append(el('summary', title), el('pre', JSON.stringify(value, null, 2)));
  return node;
}
function price(value, currency = 'EUR') {
  if (value == null || value === '' || !Number.isFinite(Number(value))) return '—';
  try {
    return new Intl.NumberFormat('es-ES', { style: 'currency', currency: currency || 'EUR' }).format(Number(value));
  } catch {
    return value + ' ' + currency;
  }
}
function external(value) {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol)) return '—';
    const a = el('a', 'Abrir web ↗');
    a.href = url.href;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    return a;
  } catch {
    return '—';
  }
}
function table(headers, rows) {
  const wrap = el('div', null, 'table-wrap');
  const element = el('table');
  const head = element.createTHead().insertRow();
  for (const name of headers) {
    const th = el('th', name);
    th.scope = 'col';
    head.append(th);
  }
  const body = element.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    for (const value of row) {
      const cell = tr.insertCell();
      cell.append(value instanceof Node ? value : String(value ?? '—'));
    }
  }
  wrap.append(element);
  return wrap;
}
function section(parent, title, subtitle) {
  const node = el('section', null, 'panel section');
  node.append(el('div', null, 'section-head'));
  node.firstChild.append(el('h2', title));
  if (subtitle) node.append(el('p', subtitle, 'subtle'));
  parent.append(node);
  return node;
}
function hero(parent, kind, title, text) {
  const node = el('div', null, 'hero');
  node.append(el('div', kind, 'eyebrow'), el('h2', title), el('p', text));
  parent.append(node);
}
function stats(parent, values) {
  const grid = el('div', null, 'stats');
  for (const [name, value, note] of values) {
    const card = el('div', null, 'panel stat');
    card.append(el('span', name, 'hint'), el('strong', value), el('p', note, 'hint'));
    grid.append(card);
  }
  parent.append(grid);
}
function offers(parent, rows, title = 'Precios y ofertas', subtitle) {
  const node = section(parent, title, subtitle);
  if (!rows.length) {
    node.append(el('p', 'El informe no contiene filas en esta sección.', 'subtle'));
    return;
  }
  const toolbar = el('div', null, 'toolbar');
  const filter = el('input');
  filter.type = 'search';
  filter.placeholder = 'Filtrar proveedor o vendedor';
  filter.setAttribute('aria-label', 'Filtrar proveedor o vendedor');
  const scope = el('select');
  scope.setAttribute('aria-label', 'Filtrar tipo de precio');
  scope.append(new Option('Todos los tipos', ''));
  for (const value of new Set(rows.map(scopeOf))) scope.append(new Option(label(value), value));
  const sort = el('select');
  sort.setAttribute('aria-label', 'Orden de precios');
  sort.append(new Option('Orden del informe', ''), new Option('Menor precio primero', 'asc'),
    new Option('Mayor precio primero', 'desc'));
  const count = el('span', '', 'hint');
  count.setAttribute('aria-live', 'polite');
  toolbar.append(filter, scope, sort, count);
  const results = el('div');
  node.append(toolbar, results);
  function render() {
    const query = filter.value.trim().toLocaleLowerCase('es');
    const visible = rows.filter(row => (!scope.value || scopeOf(row) === scope.value) &&
      [row.seller, row.provider].some(v => String(v || '').toLocaleLowerCase('es').includes(query)));
    if (sort.value) visible.sort((a, b) => {
      const left = a.amount == null || a.amount === '' ? NaN : Number(a.amount);
      const right = b.amount == null || b.amount === '' ? NaN : Number(b.amount);
      if (!Number.isFinite(left)) return Number.isFinite(right) ? 1 : 0;
      if (!Number.isFinite(right)) return -1;
      return sort.value === 'asc' ? left - right : right - left;
    });
    count.textContent = visible.length + ' de ' + rows.length;
    results.replaceChildren(visible.length ? table(
      ['Vendedor / fuente', 'Referencia', 'Total de compra', 'Tipo', 'Observado', 'Enlace', 'Detalle'],
      visible.map(row => {
        const seller = el('div', row.seller || row.provider || '—');
        if (row.provider && row.provider !== row.seller) seller.append(el('div', row.provider, 'hint'));
        const info = details('Ver datos', row);
        for (const reason of offerReasons(row)) info.insertBefore(el('p', label(reason), 'hint'), info.lastChild);
        if (asList(row.segments).length) {
          info.insertBefore(el('p', row.segments.map(segment =>
            [segment.origin, segment.destination, segment.departure].filter(Boolean).join(' · ')).join(' / ')), info.lastChild);
        }
        return [seller, el('span', price(row.amount, row.currency), 'price'),
          row.total ? price(row.total, row.currency) : 'Sin confirmar', el('span', label(scopeOf(row)), 'tag'),
          formatDate(row.observed_at), external(row.link), info];
      })
    ) : el('p', 'Ninguna fila coincide con los filtros.', 'subtle'));
  }
  filter.addEventListener('input', render);
  scope.addEventListener('change', render);
  sort.addEventListener('change', render);
  render();
}
function sources(parent, rows) {
  const node = section(parent, 'Fuentes consultadas', 'Una fuente sin coincidencias puede seguir teniendo vuelos disponibles en su web.');
  if (!rows.length) {
    node.append(el('p', 'Este informe no incluye estados de fuentes.', 'subtle'));
    return;
  }
  node.append(table(['Proveedor', 'Estado', 'Resultados', 'Hora de fin', 'Detalle'],
    rows.map(row => [row.provider, el('span', label(row.status), 'tag'), row.results,
      formatDate(row.finished_at), details(row.error || 'Ver datos', row)])));
}
function routeTitle(search, name) {
  return search?.origin && search?.destination ? search.origin + ' → ' + search.destination : name;
}
function profileLine(search) {
  if (!search) return '';
  return [search.departure, search.return_date ? 'Vuelta ' + search.return_date : 'Solo ida',
    search.adults + ' adulto(s)', search.direct ? 'Solo directos solicitados' : 'Escalas permitidas',
    'Cabina ' + search.cabin_bags, 'Facturadas ' + search.checked_bags].join('  ·  ');
}
function searchReport(parent, report, name) {
  hero(parent, 'INFORME DE BÚSQUEDA', routeTitle(report.search, name), profileLine(report.search));
  const classified = [...asList(report.ranked), ...asList(report.pending)];
  const rows = classified.length ? classified : asList(report.supplemental_prices);
  // Older exports stored the dated reference only among the price rows.
  const dated = report.lowest_dated_reference ?? rows.filter(row =>
    scopeOf(row) === 'indicative_dated_reference' && row.amount != null &&
    row.amount !== '' && Number.isFinite(Number(row.amount)))
    .sort((a, b) => Number(a.amount) - Number(b.amount))[0];
  const winner = report.winner;
  stats(parent, [
    ['Menor referencia para tus fechas', price(dated?.amount, dated?.currency), dated?.seller || 'Sin referencia para esas fechas'],
    ['Total de compra verificado', price(winner?.total, winner?.currency), winner?.seller || 'Sin total confirmado'],
    ['Fuentes consultadas', asList(report.sources).length, formatDate(report.finished_at)],
    ['Observaciones registradas', asList(report.observations).length, 'Incluye datos orientativos'],
  ]);
  offers(parent, rows,
    'Precios y ofertas', 'Filtra por tipo para separar las coincidencias de los mínimos orientativos.');
  sources(parent, asList(report.sources));
  const audit = section(parent, 'Historial de la ejecución', 'Las referencias pueden cambiar y el total de compra depende de la disponibilidad y las condiciones del vendedor.');
  audit.append(details('Parámetros de búsqueda', report.search || {}),
    details('Observaciones originales (' + asList(report.observations).length + ')', asList(report.observations)),
    details('Cambios de precio (' + asList(report.price_changes).length + ')', asList(report.price_changes)),
    details('Precios complementarios (' + asList(report.supplemental_prices).length + ')', asList(report.supplemental_prices)),
    details('Informe JSON completo', report));
}
function comparisonReport(parent, report, name) {
  const pairs = asList(report.pairs);
  const paired = pairs.filter(pair => pair.status === 'paired').length;
  const changes = pairs.flatMap(pair => asList(pair.comparisons)).filter(c => c.status === 'different_minimum').length;
  hero(parent, 'COMPARACIÓN DE PERFILES', routeTitle(report.search, name),
    label(report.factor) + '  ·  ' + profileLine(report.search));
  stats(parent, [['Pares comparables', paired + ' / ' + pairs.length, 'Por proveedor y ronda'],
    ['Diferencias observadas', changes, 'Mínimos publicados'], ['Fin de la prueba', formatDate(report.finished_at), 'Hora de España peninsular']]);
  const profiles = section(parent, 'Perfiles de la prueba', 'La diferencia se calcula como B menos A.');
  profiles.append(table(['Perfil', 'Dispositivo', 'Idioma', 'Sesión'],
    Object.entries(report.profiles || {}).map(([key, row]) =>
      [key.toUpperCase(), label(row.device), row.locale, label(row.session)])));
  const rounds = section(parent, 'Resultados por ronda',
    'Un cambio de mínimo puede corresponder a una oferta distinta. La comparación no prueba qué causó el cambio.');
  for (const pair of pairs) {
    const block = el('article', null, 'pair');
    block.append(el('h3', 'Ronda ' + pair.round + ' · ' + pair.provider),
      el('p', 'Orden ' + asList(pair.order).join(' → ').toUpperCase() + ' · ' + label(pair.status), 'subtle'));
    const comparisons = asList(pair.comparisons);
    if (comparisons.length) block.append(table(['Alcance', 'Mínimo A', 'Mínimo B', 'Diferencia', 'Resultado', 'Intervalo', 'Detalle'],
      comparisons.map(c => [label(c.scope), price(c.a_minimum?.amount, c.currency),
        price(c.b_minimum?.amount, c.currency), price(c.delta_b_minus_a, c.currency), label(c.status),
        c.observation_gap_seconds == null ? '—' : Number(c.observation_gap_seconds).toFixed(1) + ' s',
        details('Ver observaciones', c)])));
    const pairSources = Object.entries(pair.runs || {}).flatMap(([key, run]) =>
      asList(run.sources).map(row => key.toUpperCase() + ' · ' + label(row.status) + (row.error ? ' · ' + row.error : '')));
    if (pairSources.length) block.append(el('p', pairSources.join(' / '), 'subtle'));
    block.append(details('Consultas originales', pair.runs || {}));
    rounds.append(block);
  }
  section(parent, 'Datos del experimento').append(details('Informe JSON completo', report));
}

function parseCSV(input) {
  const text = input.replace(/^\uFEFF/, '');
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (char === '"') quoted = false;
      else field += char;
    } else if (char === '"' && !field.length) quoted = true;
    else if (char === ',') { row.push(field); field = ''; }
    else if (char === '\n' || char === '\r') {
      row.push(field);
      if (row.some(Boolean)) rows.push(row);
      row = [];
      field = '';
      if (char === '\r' && text[i + 1] === '\n') i++;
    } else field += char;
  }
  if (quoted) throw new Error('El CSV contiene un campo entre comillas sin cerrar.');
  row.push(field);
  if (row.some(Boolean)) rows.push(row);
  const headers = rows.shift();
  if (!headers || !headers.includes('provider') || !headers.includes('amount'))
    throw new Error('Este CSV no tiene las columnas de un informe de scraperflights.');
  if (rows.some(row => row.length !== headers.length)) throw new Error('El CSV contiene filas incompletas.');
  return rows.map(row => Object.fromEntries(headers.map((header, i) => [header, row[i]])));
}
function showReport(text, name) {
  const fragment = document.createDocumentFragment();
  if (name.toLowerCase().endsWith('.csv')) {
    const rows = parseCSV(text);
    hero(fragment, 'TABLA DE PRECIOS · CSV', name, 'Abre el JSON del mismo nombre para ver fechas, fuentes y parámetros.');
    offers(fragment, rows, 'Precios del archivo', 'El CSV contiene los precios exportados y los motivos de exclusión.');
  } else if (name.toLowerCase().endsWith('.json')) {
    const report = JSON.parse(text.replace(/^\uFEFF/, ''));
    if (!report || typeof report !== 'object') throw new Error('El JSON no es un informe.');
    if (Array.isArray(report.pairs)) comparisonReport(fragment, report, name);
    else if (report.search && Array.isArray(report.sources)) searchReport(fragment, report, name);
    else throw new Error('El JSON no tiene el formato de un informe de scraperflights.');
  } else throw new Error('Selecciona un archivo JSON o CSV.');
  $('report').replaceChildren(fragment);
}
let requestNumber = 0;
let currentName = null;
async function openReport(name, load) {
  const request = ++requestNumber;
  $('message').textContent = 'Abriendo ' + name + '…';
  try {
    const text = await load();
    if (request !== requestNumber) return;
    showReport(text, name);
    currentName = name;
    for (const button of $('files').querySelectorAll('button'))
      button.setAttribute('aria-current', String(button.dataset.name === name));
    $('message').textContent = 'Abierto · ' + name;
  } catch (error) {
    if (request === requestNumber) $('message').textContent = 'No se pudo abrir el archivo. ' + error.message;
  }
}
async function refreshFiles(autoOpen = false) {
  const files = $('files');
  try {
    const response = await fetch('/reports');
    if (!response.ok) throw new Error('Error al cargar la lista');
    const reports = await response.json();
    const buttons = reports.map(report => {
      const button = el('button', null, 'file');
      button.type = 'button';
      button.dataset.name = report.name;
      button.setAttribute('aria-current', String(currentName === report.name));
      const type = report.name.toLowerCase().endsWith('.csv') ? 'CSV' :
        report.name.startsWith('comparison-') ? 'COMPARACIÓN · JSON' : 'BÚSQUEDA · JSON';
      button.append(el('span', type + ' · ' + formatDate(report.modified * 1000)),
        document.createTextNode(report.name));
      button.addEventListener('click', () => openReport(report.name, async () => {
        const response = await fetch('/report?name=' + encodeURIComponent(report.name));
        if (!response.ok) throw new Error('El archivo no está disponible (' + response.status + ').');
        return response.text();
      }));
      return button;
    });
    files.replaceChildren(...(buttons.length ? buttons : [el('p', 'Todavía no hay informes en esta carpeta.', 'hint')]));
    if (autoOpen && requestNumber === 0) (buttons.find(b => b.dataset.name.toLowerCase().endsWith('.json')) || buttons[0])?.click();
  } catch {
    files.replaceChildren(el('p', 'La lista no está disponible. Puedes abrir un archivo manualmente.', 'hint'));
  }
}
$('refresh').addEventListener('click', () => refreshFiles());
$('upload').addEventListener('change', event => {
  const file = event.target.files[0];
  if (file) openReport(file.name, () => file.size > 32 * 1024 * 1024 ?
    Promise.reject(new Error('El informe supera 32 MB.')) : file.text());
  event.target.value = '';
});
refreshFiles(true);

const searchForm = $('search-form');
const departure = $('departure');
const returnDate = $('return-date');
const tripType = $('trip-type');
const searchButton = $('search-button');
departure.min = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Europe/Madrid'}).format(new Date());

function updateReturnDate() {
  const roundTrip = tripType.value === 'round-trip';
  $('return-field').hidden = !roundTrip;
  returnDate.disabled = !roundTrip;
  returnDate.required = roundTrip;
  returnDate.min = departure.value || departure.min;
}
departure.addEventListener('change', updateReturnDate);
tripType.addEventListener('change', updateReturnDate);
updateReturnDate();

searchForm.addEventListener('submit', async event => {
  event.preventDefault();
  const values = new FormData(searchForm);
  const status = $('search-status');
  searchButton.disabled = true;
  status.textContent = 'Consultando las webs… Puede tardar unos segundos.';
  try {
    const response = await fetch('/search', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({origin: values.get('origin'), departure: values.get('departure'),
                            return_date: values.get('return_date') || null}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Error al buscar.');
    await openReport(result.name, async () => {
      const file = await fetch('/report?name=' + encodeURIComponent(result.name));
      if (!file.ok) throw new Error('No se pudo abrir el informe.');
      return file.text();
    });
    await refreshFiles();
    status.textContent = 'Búsqueda terminada. Consulta el informe y el estado de cada web.';
  } catch (error) {
    status.textContent = 'No se pudo completar la búsqueda. ' + error.message;
  } finally {
    searchButton.disabled = false;
  }
});

function catalogLinks(row) {
  if (!row.route_links) return external(row.url);
  const links = el('div');
  for (const [route, url] of Object.entries(row.route_links)) {
    const link = external(url);
    if (typeof link !== 'string') {
      link.textContent = route.replace('-', ' → ');
      links.append(link, el('br'));
    }
  }
  return links;
}

const catalog = document.querySelector('.catalog');
catalog.addEventListener('toggle', async () => {
  const container = $('catalog-results');
  if (!catalog.open || container.dataset.loaded) return;
  container.dataset.loaded = 'true';
  container.replaceChildren(el('p', 'Cargando fuentes…', 'subtle'));
  try {
    const response = await fetch('/catalog');
    if (!response.ok) throw new Error('Error al cargar el catálogo');
    const rows = await response.json();
    const categories = {agency: 'Agencia', airline: 'Aerolínea', metasearch: 'Comparador', distribution: 'Distribuidor'};
    container.replaceChildren(el('p', rows.length + ' fuentes. Las candidatas están disponibles como enlaces para consulta manual.', 'subtle'),
      table(['Empresa', 'Tipo', 'Consulta en el visor', 'Enlace'], rows.map(row => [
        row.name, categories[row.category], asList(row.implemented_methods).includes('web') ? 'Integrada' : row.status === 'candidate' ? 'Candidata' : 'Adaptador histórico',
        catalogLinks(row),
      ])));
  } catch {
    delete container.dataset.loaded;
    container.replaceChildren(el('p', 'No se pudo cargar el catálogo.', 'subtle'));
  }
});
