function lodgingReport(parent, report, name) {
  const search = report.search || {}, rows = asList(report.observations);
  const basis = {night:'por noche · referencia',stay:'estancia · referencia',unknown:'unidad sin confirmar'};
  hero(parent, 'ALOJAMIENTO', search.city || search.destination || name,
    search.checkin ? `${search.checkin} → ${search.checkout} · ${search.nights} noches · ${search.adults} adulto(s) · ${search.rooms} habitación(es)` : 'CSV de observaciones. Abre el JSON para los parámetros completos.');
  stats(parent, [['Alojamientos y referencias',rows.length,'Puede haber tarifas distintas del mismo hotel'],
    ['Con precio publicado',rows.filter(row => row.amount != null && row.amount !== '').length,'No implica disponibilidad'],
    ['Estancias comparables',asList(report.comparable_stays).length,'Fechas, ocupación, EUR y precio por estancia explícitos']]);
  if (report.lowest_comparable_reference) parent.append(el('p', 'Menor referencia comparable: '+price(report.lowest_comparable_reference.amount,'EUR')+' · '+report.lowest_comparable_reference.property+'. Comprueba impuestos y disponibilidad en la web.','subtle'));
  parent.append(el('p', report.notice || 'Precios orientativos: verifica las fechas, ocupación, impuestos y disponibilidad en la web.','subtle'));
  const block=section(parent,'Alojamientos encontrados','No se multiplican precios por noche para inventar un total. Las estrellas del hotel y las reseñas son conceptos distintos.');
  const tools=el('div',null,'toolbar'), text=el('input'), score=el('select'), priced=el('input');
  text.placeholder='Filtrar nombre o proveedor';text.setAttribute('aria-label','Filtrar alojamientos');
  score.setAttribute('aria-label','Puntuación mínima de huéspedes');
  for (const [value,label] of [['0','Todas las puntuaciones'],['7','7/10 o más'],['8','8/10 o más'],['9','9/10 o más']]) {const option=el('option',label);option.value=value;score.append(option);}
  priced.type='checkbox';const pricedLabel=el('label');pricedLabel.append(priced,document.createTextNode(' Solo con precio'));
  tools.append(text,score,pricedLabel);block.append(tools);const grid=el('div');block.append(grid);
  function draw() {
    const filtered=rows.filter(row => (!priced.checked || row.amount != null && row.amount !== '') &&
      (Number(score.value) === 0 || row.rating_10 != null && row.rating_10 !== '' && Number(row.rating_10)>=Number(score.value)) &&
      `${row.property} ${row.provider}`.toLowerCase().includes(text.value.toLowerCase()));
    grid.replaceChildren(table(['Alojamiento','Web','Precio publicado','Unidad','Fechas de la tarifa','Reseñas /10','Enlace','Detalle'],filtered.map(row => [
      row.property,row.provider,price(row.amount,row.currency),basis[row.price_basis]||row.price_basis,
      row.scope==='dated_stay_reference' ? `${row.checkin} → ${row.checkout}` : 'Sin estancia confirmada',
      row.rating_10 == null || row.rating_10 === '' ? '—' : `${row.rating_10}${row.review_count ? ' ('+row.review_count+')' : ''}`,
      external(row.link),details('Datos y límites',row)])));
    if (!filtered.length) grid.append(el('p','Sin coincidencias para estos filtros. Revisa también los estados de las fuentes.','subtle'));
  }
  for (const control of [text,score,priced]) control.addEventListener('input',draw);draw();
  section(parent,'Estado de las webs').append(table(['Fuente','Estado','Alojamientos','Con precio','Detalle'],asList(report.sources).map(row => [
    row.name||row.provider,row.status,row.results||0,row.priced_results||0,details(row.error||'Diagnóstico',row)])));
  const links=asList(report.external_links);
  if (links.length) section(parent,'Continuar en las webs','HTML: URL con fechas enviadas, que la página puede ignorar. Manual: completa los datos en la web.').append(table(['Web','Método','Fechas en URL','Enlace'],links.map(row => [row.name,row.method,row.dates_in_url?'Enviadas; comprobar':'No',external(row.url)])));
  section(parent,'Informe completo').append(details('JSON original',report));
}

(() => {
  const form=$('lodging-form'),status=$('lodging-status');
  function copy() {
    $('lodging-destination').value=$('destination').value;
    $('lodging-checkin').value=$('departure').value;
    $('lodging-checkout').value=$('trip-type').value==='round-trip' ? $('return-date').value : '';
    $('lodging-checkout').min=$('lodging-checkin').value;
  }
  $('lodging-copy').addEventListener('click',copy);
  for (const id of ['destination','departure','return-date','trip-type']) $(id).addEventListener('change',()=>{if($('lodging-follow').checked) copy();});
  $('lodging-follow').addEventListener('change',()=>{if($('lodging-follow').checked) copy();});
  for (const id of ['lodging-destination','lodging-checkin','lodging-checkout']) $(id).addEventListener('change',()=>{$('lodging-follow').checked=false;});
  $('lodging-checkin').min=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Madrid'}).format(new Date());copy();
  fetch('/lodging/catalog').then(response=>{if(!response.ok) throw Error();return response.json();}).then(catalog=>{
    for (const row of catalog.filter(row=>row.method==='html')) {
      const label=el('label'),input=el('input');input.type='checkbox';input.value=row.id;input.checked=true;
      label.append(input,document.createTextNode(row.name));$('lodging-providers').append(label);
    }
    $('lodging-catalog').append(table(['Web','Enlace'],catalog.filter(row=>row.method==='manual').map(row=>[row.name,external(row.url)])));
    status.textContent=`${catalog.filter(row=>row.method==='html').length} lectores HTML y ${catalog.filter(row=>row.method==='manual').length} webs adicionales. Si no hay regreso de vuelo, indica una salida del alojamiento.`;
  }).catch(()=>{status.textContent='No se pudo cargar el catálogo. Reinicia el visor actualizado.';});
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    const providers=[...$('lodging-providers').querySelectorAll('input:checked')].map(input=>input.value);
    if(!providers.length){status.textContent='Selecciona al menos una fuente HTML.';return;}
    $('lodging-button').disabled=true;status.textContent='Consultando alojamiento… Puede tardar alrededor de un minuto. Mantén la página abierta.';
    try {
      const response=await fetch('/lodging/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        destination:$('lodging-destination').value,checkin:$('lodging-checkin').value,checkout:$('lodging-checkout').value,
        adults:Number($('lodging-adults').value),rooms:Number($('lodging-rooms').value),providers
      })});
      const data=await response.json();if(!response.ok) throw Error(data.error||'Error al buscar alojamiento.');
      $('lodging-results').replaceChildren();lodgingReport($('lodging-results'),data.report,data.name);
      status.textContent=`Guardado ${data.name} y su CSV. Revisa los estados y el alcance de las tarifas.`;refreshFiles();
    } catch(error){status.textContent=error.message;}
    finally{$('lodging-button').disabled=false;}
  });
})();
