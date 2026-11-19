(() => {
  const form = $('devices-form'), status = $('device-status'), result = $('device-results');
  let catalog = {};
  function checked(id) { return [...$(id).querySelectorAll('input:checked')].map(input => input.value); }
  function estimate() {
    const count = checked('device-options').filter(key => key !== $('device-baseline').value).length;
    const sources = checked('device-providers').length;
    $('device-estimate').textContent = `${count} perfiles frente al control · ${sources} fuentes · ${(count + 2) * sources * Number($('device-rounds').value)} consultas previstas, incluyendo la repetición de control. Puede tardar varios minutos.`;
  }
  async function init() {
    try {
      const response = await fetch('/devices'); if (!response.ok) throw Error();
      catalog = await response.json();
      for (const [key, row] of Object.entries(catalog.devices)) {
        const text = `${row.label} · ${row.brand} · ${row.tier}`;
        const option = el('option', text); option.value = key; $('device-baseline').append(option);
        const label = el('label'), input = el('input'); input.type = 'checkbox'; input.value = key;
        input.checked = ['redmi', 'iphone'].includes(key); label.append(input, document.createTextNode(text)); $('device-options').append(label);
      }
      for (const key of catalog.providers) {
        const label = el('label'), input = el('input'); input.type = 'checkbox'; input.value = key;
        input.checked = key === 'iberia-web'; label.append(input, document.createTextNode(key)); $('device-providers').append(label);
      }
      status.textContent = 'Selecciona perfiles y fuentes. Los resultados se guardan como JSON en output y quedan disponibles en el análisis histórico.';
      estimate();
    } catch { status.textContent = 'No se pudieron cargar los perfiles. Reinicia el visor actualizado.'; }
  }
  form.addEventListener('change', estimate);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const values = new FormData($('search-form'));
    const devices = checked('device-options'), providers = checked('device-providers');
    if (!values.get('departure') || values.get('origin') === values.get('destination') ||
        ($('trip-type').value === 'round-trip' && !values.get('return_date'))) {
      status.textContent = 'Completa la ruta y las fechas de Nueva búsqueda.'; return;
    }
    if (!providers.length || providers.length > 4 || !devices.some(key => key !== $('device-baseline').value)) {
      status.textContent = 'Elige 1–4 fuentes y al menos un dispositivo distinto del control.'; return;
    }
    $('device-run').disabled = true; status.textContent = 'Comparando perfiles… Mantén abierta esta página.';
    try {
      const response = await fetch('/compare-devices', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
        origin:values.get('origin'), destination:values.get('destination'), departure:values.get('departure'),
        return_date:values.get('return_date') || null, direct_only:values.has('direct_only'), devices, providers,
        baseline:$('device-baseline').value, rounds:Number($('device-rounds').value)
      })});
      const data = await response.json(); if (!response.ok) throw Error(data.error || 'Error al comparar.');
      result.replaceChildren(); comparisonReport(result, data.report, data.name);
      status.textContent = `Guardado: ${data.name}. En Análisis histórico pulsa Cargar histórico local para incorporar las observaciones por perfil.`;
      refreshFiles();
    } catch (error) { status.textContent = error.message; }
    finally { $('device-run').disabled = false; }
  });
  init();
})();
