'use strict';

(() => {
  function profileName(value) {
    if (!value || value === 'unknown') return '';
    try { const data = JSON.parse(value); return data.label || data.device || value; }
    catch { return value; }
  }

  let records = [];
  let pending = [];
  let revision = 0;
  const fields = ['amount', 'observed_at', 'origin', 'destination', 'departure', 'return_date', 'currency',
    'provider', 'seller', 'transport_mode', 'journey_leg', 'scope', 'adults', 'cabin_bags', 'checked_bags',
    'profile', 'comparison_group'];
  const names = {amount:'Precio', observed_at:'Fecha de observación', origin:'Origen IATA', destination:'Destino IATA',
    departure:'Fecha de salida', return_date:'Fecha de regreso', currency:'Moneda ISO', provider:'Fuente',
    seller:'Vendedor', transport_mode:'Transporte', journey_leg:'Tramo', scope:'Tipo de referencia',
    adults:'Viajeros', cabin_bags:'Maletas de cabina', checked_bags:'Maletas facturadas', profile:'Perfil',
    comparison_group:'Tarifa o grupo propio'};
  const aliases = {amount:['precio','importe','price'], observed_at:['fecha_observacion','fecha_consulta','timestamp'],
    origin:['origen'],destination:['destino'],departure:['salida','fecha_salida'],return_date:['regreso','fecha_regreso'],
    currency:['moneda'],provider:['fuente'],seller:['vendedor'],transport_mode:['transporte','medio'],scope:['tipo_referencia']};
  const required = new Set(['amount','observed_at','origin','destination','departure','currency','transport_mode','scope']);
  const status = $('analysis-status');
  const imports = $('analysis-import');
  const output = $('analysis-results');
  const pct = value => value == null ? '—' : new Intl.NumberFormat('es-ES', {
    maximumFractionDigits:2, minimumFractionDigits:1, signDisplay:'exceptZero'}).format(Number(value)) + ' %';

  async function post(path, body) {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación.');
    return result;
  }
  async function calculate() {
    const current = ++revision;
    if (!records.length) { output.replaceChildren(); return; }
    try {
      const result = await post('/analysis/calculate', {records});
      if (current !== revision) return;
      render(result);
    } catch(error) { if (current === revision) status.textContent = error.message; }
  }
  function issues(result) {
    const invalid = asList(result.rejected);
    const box = el('div');
    if (invalid.length) box.append(details(invalid.length + ' filas excluidas · ver motivos', invalid));
    if (asList(result.issues).length) box.append(details('Avisos de lectura', result.issues));
    return box;
  }
  $('analysis-history').addEventListener('click', async event => {
    event.target.disabled = true;
    status.textContent = 'Leyendo SQLite y los JSON de output…';
    try {
      const result = await post('/analysis/history', {});
      if (records.length + result.records.length > 20000) throw new Error('El conjunto supera 20.000 filas. Vacía el análisis y selecciona menos datos.');
      records.push(...result.records);
      imports.replaceChildren(issues(result));
      status.textContent = result.records.length + ' filas leídas del histórico. Las duplicadas se eliminan al calcular.';
      await calculate();
    } catch(error) { status.textContent = error.message; }
    finally { event.target.disabled = false; }
  });
  $('analysis-clear').addEventListener('click', () => {
    revision++;
    records = [];
    pending = [];
    imports.replaceChildren();
    output.replaceChildren();
    status.textContent = 'Análisis vacío. Los archivos originales se conservan.';
  });
  $('analysis-upload').addEventListener('change', async event => {
    const files = Array.from(event.target.files);
    event.target.value = '';
    for (const file of files) {
      try {
        if (file.size > 8 * 1024 * 1024) throw new Error('El archivo supera 8 MB.');
        const bytes = new Uint8Array(await file.arrayBuffer());
        let binary = '';
        for (let i=0; i<bytes.length; i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
        const result = await post('/analysis/import', {name:file.name, content:btoa(binary)});
        for (const tab of result.tables) pending.push({...tab, source:file.name + ' · ' + tab.name});
        status.textContent = 'Revisa las columnas antes de añadir los datos.';
      } catch(error) { status.textContent = file.name + ' · ' + error.message; }
    }
    importNext();
  });
  function importNext() {
    if (!pending.length) return;
    const tab = pending[0];
    const columns = Array.from(new Set(tab.rows.flatMap(row => Object.keys(row))));
    imports.replaceChildren();
    const box = section(imports, 'Importar · ' + tab.source, tab.rows.length + ' filas. Los valores por defecto solo completan celdas vacías.');
    if (!tab.rows.length) {
      const skip = el('button','Saltar hoja vacía');
      skip.type='button'; skip.onclick=()=>{pending.shift();imports.replaceChildren();importNext();};
      box.append(skip); return;
    }
    const form = el('form');
    const grid = el('div',null,'mapping-grid');
    const optional = details('Columnas y condiciones opcionales', {});
    optional.lastChild.remove();
    const optionalGrid = el('div',null,'mapping-grid');
    const controls = {};
    for (const field of fields) {
      const entry = el('label', names[field]);
      const select = el('select');
      select.setAttribute('aria-label','Columna de ' + names[field]);
      select.append(new Option('Sin columna',''));
      for (const column of columns) select.append(new Option(column,column));
      const equivalent = [field,...(aliases[field]||[])];
      const matched = columns.find(column => equivalent.includes(column.trim().toLowerCase()));
      if (matched) select.value=matched;
      const fallback = el('input');
      fallback.placeholder='Valor por defecto';
      fallback.setAttribute('aria-label','Valor por defecto de '+names[field]);
      entry.append(select,fallback);
      (required.has(field) ? grid : optionalGrid).append(entry);
      controls[field]={select,fallback};
    }
    optional.append(optionalGrid);
    const preview = details('Vista previa de las primeras filas',tab.rows.slice(0,5));
    const add=el('button','Validar y añadir', 'primary');add.type='submit';
    const skip=el('button','Saltar tabla');skip.type='button';
    skip.onclick=()=>{pending.shift();imports.replaceChildren();importNext();};
    const note=el('p','Usa flight, train, bus o carpool para transporte. Para datos propios puedes declarar user_reference como tipo. Completa viajeros y equipaje cuando los conozcas. Las filas sin hora se registran a medianoche.','subtle');
    form.append(grid,optional,preview,note,add,skip);
    form.addEventListener('submit',async event=>{
      event.preventDefault();add.disabled=true;
      const mapping={},defaults={};
      for(const [field,control] of Object.entries(controls)) {
        mapping[field]=control.select.value || '__unmapped__';
        if(control.fallback.value.trim())defaults[field]=control.fallback.value.trim();
      }
      try {
        const result=await post('/analysis/normalize',{rows:tab.rows,mapping,defaults,source:tab.source,epoch:tab.excel_epoch});
        if(records.length+result.records.length>20000)throw new Error('El conjunto supera 20.000 filas.');
        records.push(...result.records);
        pending.shift();
        imports.replaceChildren(issues(result));
        status.textContent=result.records.length+' filas añadidas. '+result.rejected.length+' filas excluidas.';
        await calculate();
        if(pending.length)importNext();
      } catch(error){status.textContent=error.message;}
      finally{add.disabled=false;}
    });
    box.append(form);
  }
  function trendChart(parent, group) {
    if(group.points.length<2)return;
    const width=780,height=190,pad=35;
    const values=group.points.map(point=>Number(point.amount));
    const minimum=Math.min(...values), maximum=Math.max(...values);
    const times=group.points.map(point=>new Date(point.observed_at).getTime());
    const first=Math.min(...times),last=Math.max(...times);
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
    svg.setAttribute('role','img');
    svg.setAttribute('aria-label','Evolución de precios observados para la serie seleccionada.');
    const title=document.createElementNS(svg.namespaceURI,'title');
    title.textContent='Evolución de precios observados';svg.append(title);
    const path=document.createElementNS(svg.namespaceURI,'polyline');
    path.setAttribute('points',values.map((value,index)=>{
      const x=pad+(times[index]-first)/(last-first||1)*(width-pad*2);
      const y=height-pad-(value-minimum)/(maximum-minimum||1)*(height-pad*2);
      return x+','+y;
    }).join(' '));
    path.setAttribute('fill','none');path.setAttribute('stroke','#126c61');path.setAttribute('stroke-width','3');
    svg.append(path);parent.append(svg);
  }
  function render(result) {
    output.replaceChildren();
    stats(output,[['Observaciones únicas',result.observations,'Conservan su procedencia'],
      ['Series comparables',result.groups.length,'Separadas por fechas y condiciones'],
      ['Duplicados retirados',result.duplicates,'Incluye exportaciones repetidas']]);
    if(!result.groups.length)return;
    const box=section(output,'Evolución porcentual',result.notice);
    const download = el('button', 'Exportar resumen porcentual CSV');
    download.type = 'button';
    download.addEventListener('click', () => {
      const columns = ['origin','destination','departure','return_date','currency','provider','seller',
        'transport_mode','journey_leg','scope','count','first','latest','minimum','maximum','mean','median',
        'change_pct','previous_change_pct','range_pct','vs_median_pct','ambiguous_timestamps'];
      const cell = value => {
        const text = value == null ? '' : String(value);
        const safe = /^[=+@-]/.test(text) && !Number.isFinite(Number(text)) ? "'" + text : text;
        return '"' + safe.replaceAll('"', '""') + '"';
      };
      const csv = [columns.join(','), ...result.groups.map(group =>
        columns.map(column => cell(group[column])).join(','))].join('\r\n');
      const url = URL.createObjectURL(new Blob(['\uFEFF', csv], {type:'text/csv;charset=utf-8'}));
      const link = el('a'); link.href=url; link.download='analisis-precios.csv'; link.click();
      URL.revokeObjectURL(url);
    });
    box.append(download);
    const filter=el('input');filter.placeholder='Filtrar ruta, vendedor o transporte';filter.setAttribute('aria-label','Filtrar series');
    const select=el('select');select.setAttribute('aria-label','Serie a analizar');
    const toolbar=el('div',null,'toolbar');toolbar.append(filter,select);box.append(toolbar);
    const selected=el('div');box.append(selected);
    function show(){
      const group=result.groups[Number(select.value)];
      selected.replaceChildren();
      if(!group){selected.append(el('p','Sin series para este filtro.'));return;}
      stats(selected,[['Primer precio',price(group.first,group.currency),'Base de comparación'],
        ['Último precio',price(group.latest,group.currency),pct(group.change_pct)+' frente al primero'],
        ['Mediana',price(group.median,group.currency),pct(group.vs_median_pct)+' último vs. mediana'],
        ['Variación anterior',pct(group.previous_change_pct),'Última observación vs. anterior']]);
      selected.append(el('p','Mínimo '+price(group.minimum,group.currency)+' · Máximo '+price(group.maximum,group.currency)+
        ' · Media '+price(group.mean,group.currency)+' · Rango sobre el mínimo '+pct(group.range_pct),'subtle'));
      if(group.ambiguous_timestamps)selected.append(el('p','Hay precios diferentes con la misma hora. Se muestran el rango y los datos, y se omiten las variaciones temporales.','subtle'));
      trendChart(selected,group);
      selected.append(table(['Observado','Precio','% desde primero','% anterior','Procedencia'],
        group.points.map(point=>[formatDate(point.observed_at),price(point.amount,group.currency),
          group.ambiguous_timestamps?'—':pct(point.change_from_first_pct),
          group.ambiguous_timestamps?'—':pct(point.change_from_previous_pct),point.sources.join(', ')])));
      selected.append(details('Condiciones y datos completos de la serie',group));
    }
    function options(){
      select.replaceChildren();
      const query=filter.value.toLowerCase();
      result.groups.forEach((group,index)=>{
        const text=[group.origin+' → '+group.destination, group.departure,group.return_date,
          label(group.transport_mode),group.seller,label(group.scope),label(group.journey_leg),profileName(group.profile),group.count+' observaciones'].filter(Boolean).join(' · ');
        if(text.toLowerCase().includes(query))select.append(new Option(text,index));
      });
      show();
    }
    filter.addEventListener('input',options);select.addEventListener('change',show);options();
  }
})();
