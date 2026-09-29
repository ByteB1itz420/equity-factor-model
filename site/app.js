const $ = s => document.querySelector(s);
let charts = {};
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function chartDefaults() {
  Chart.defaults.color = css('--muted');
  Chart.defaults.borderColor = css('--line');
  Chart.defaults.font.size = 11.5;
}
$('#theme-toggle').onclick = () => {
  const h = document.documentElement;
  h.dataset.theme = h.dataset.theme === 'dark' ? 'light' : 'dark';
  chartDefaults();
  Object.values(charts).forEach(c => c.update());
};

const pct = (x, d=1) => (x*100).toFixed(d) + '%';
const f2 = x => (+x).toFixed(2);
const f3 = x => (+x).toFixed(3);

async function load() {
  chartDefaults();
  const [meta, loadings, aapl, oos, bt] = await Promise.all(
    ['meta','loadings','aapl_timeseries','oos','backtest'].map(n => fetch(`data/${n}.json`).then(r => r.json())));
  $('#retrieved').textContent = meta.retrieved_at_utc.slice(0,10);

  // stat cards
  const ff3 = oos.summary.find(s => s.model === 'FF3');
  const cards = [
    [meta.universe.length, 'stocks in universe'],
    ['108', 'months, 2015-2023'],
    ['4', 'factor models'],
    [pct(ff3.oos_r2), 'FF3 out-of-sample R²'],
    ['36', 'backtest months (OOS)'],
  ];
  $('#stat-cards').innerHTML = cards.map(([v,k]) => `<div class="card"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('');

  // model tabs + loadings table
  const models = Object.keys(meta.models);
  let curModel = 'FF3', sortKey = 'beta_MKT', sortDir = -1;
  $('#model-tabs').innerHTML = models.map(m =>
    `<button data-m="${m}" class="${m===curModel?'active':''}">${m} (${meta.models[m].join('+')})</button>`).join('');
  document.querySelectorAll('#model-tabs button').forEach(b => b.onclick = () => {
    curModel = b.dataset.m;
    document.querySelectorAll('#model-tabs button').forEach(x => x.classList.toggle('active', x===b));
    renderTable();
  });
  function cols(m) {
    const base = [['alpha', 'beta_const', 'alpha_p','p_const','q','alpha_bh_q']];
    const fs = meta.models[m].map(f => 'beta_' + f.replace('Mkt-RF','MKT'));
    return ['ticker','alpha','q',...fs,'r2'];
  }
  function renderTable() {
    const rows = loadings.filter(r => r.model === curModel);
    const keys = cols(curModel);
    rows.sort((a,b) => (a[sortKey]-b[sortKey])*sortDir || a.ticker.localeCompare(b.ticker));
    const head = {ticker:'Ticker', alpha:'α /mo', q:'α BH q', r2:'R²'};
    meta.models[curModel].forEach(f => head['beta_'+f.replace('Mkt-RF','MKT')] = 'β ' + f.replace('Mkt-RF','MKT'));
    $('#loadings-table').innerHTML =
      '<tr>' + keys.map(k => `<th data-k="${k}">${head[k]||k}${k===sortKey?(sortDir<0?' ▾':' ▴'):''}</th>`).join('') + '</tr>' +
      rows.map(r => '<tr>' + keys.map(k => {
        if (k==='ticker') return `<td><b>${r.ticker}</b>${r.alpha_bh_q<0.05?' <span class="sig yes">α sig</span>':''}</td>`;
        if (k==='q') return `<td class="${r.alpha_bh_q<0.05?'pos':''}">${f3(r.alpha_bh_q)}</td>`;
        if (k==='alpha') return `<td class="${r.beta_const>=0?'pos':'neg'}">${pct(r.beta_const,2)}</td>`;
        if (k==='r2') return `<td>${pct(r.r2,1)}</td>`;
        const v = r[k]; return `<td class="${v>=0?'pos':'neg'}">${f2(v)}</td>`;
      }).join('') + '</tr>').join('');
    document.querySelectorAll('#loadings-table th').forEach(th => th.onclick = () => {
      const k = th.dataset.k;
      if (sortKey===k) sortDir*=-1; else { sortKey=k; sortDir=-1; }
      renderTable();
    });
  }
  renderTable();

  // diagnostics chips
  const d = aapl.diagnostics.AAPL_FF3;
  $('#diag-chips').innerHTML = [
    `Jarque-Bera <b>p=${d.jarque_bera.pvalue.toExponential(1)}</b> (fat tails, non-normal)`,
    `Ljung-Box(12) <b>p=${d.ljung_box.pvalue.toFixed(2)}</b> (no residual autocorrelation)`,
    `skew <b>${d.jarque_bera.skew.toFixed(2)}</b>`, `excess kurtosis <b>${d.jarque_bera.excess_kurtosis.toFixed(2)}</b>`,
  ].map(c => `<span class="chip">${c}</span>`).join('');

  // fitted vs actual
  charts.fitted = new Chart($('#chart-fitted'), {type:'line', data:{labels:aapl.months, datasets:[
    {label:'Actual excess return', data:aapl.actual, borderColor:css('--accent'), borderWidth:1.4, pointRadius:0},
    {label:'FF3 fitted', data:aapl.fitted, borderColor:css('--accent2'), borderWidth:1.4, pointRadius:0}]},
    options:{interaction:{mode:'index',intersect:false}, scales:{y:{ticks:{callback:v=>pct(v,0)}}}, plugins:{legend:{labels:{boxWidth:12}}}}});

  // rolling beta
  charts.beta = new Chart($('#chart-beta'), {type:'line', data:{labels:aapl.rolling_beta_months, datasets:[
    {label:'β MKT (36m rolling)', data:aapl.rolling_beta, borderColor:css('--warn'), borderWidth:1.8, pointRadius:0, fill:{target:{value:1}, above:'rgba(91,140,255,0.06)'}}]},
    options:{scales:{y:{suggestedMin:0.8,suggestedMax:1.6}}, plugins:{legend:{labels:{boxWidth:12}}}}});

  // OOS
  charts.oos = new Chart($('#chart-oos'), {type:'bar', data:{labels:oos.summary.map(s=>s.model), datasets:[
    {label:'Train R² (2015-20)', data:oos.summary.map(s=>s.train_r2), backgroundColor:css('--line')},
    {label:'OOS R² (2021-23)', data:oos.summary.map(s=>s.oos_r2), backgroundColor:css('--accent')}]},
    options:{scales:{y:{ticks:{callback:v=>pct(v,0)},max:0.7}}, plugins:{legend:{labels:{boxWidth:12}}}}});

  // equity curves
  const series = [['strategy_net','Momentum tilt (net 10bps)','--accent'],['strategy_gross','Momentum tilt (gross)','--accent2'],
                  ['equal_weight_16','Equal-weight 16','--warn'],['spy','SPY','--muted']];
  charts.eq = new Chart($('#chart-equity'), {type:'line', data:{labels:bt.months, datasets:series.map(([k,l,c],i)=>({
    label:l, data:bt.curves[k], borderColor:css(c), borderWidth:i===0?2.4:1.4, pointRadius:0,
    borderDash:k==='spy'?[5,4]:[]}))},
    options:{interaction:{mode:'index',intersect:false}, plugins:{legend:{labels:{boxWidth:12}}}}});

  // backtest stats table
  const show = ['strategy_gross','strategy_net','equal_weight_16','spy','net_cost_25bps','net_cost_50bps'];
  const names = {strategy_gross:'Momentum tilt · gross', strategy_net:'Momentum tilt · net 10bps',
    equal_weight_16:'Equal-weight universe', spy:'SPY (benchmark)',
    net_cost_25bps:'Momentum tilt · net 25bps', net_cost_50bps:'Momentum tilt · net 50bps'};
  const rows = bt.stats.filter(s => show.includes(s.series));
  $('#bt-table').innerHTML = '<tr><th>Series</th><th>Total return</th><th>CAGR</th><th>Ann. vol</th><th>Sharpe</th><th>Max DD</th><th>Hit rate</th></tr>' +
    rows.map(s => `<tr><td><b>${names[s.series]}</b></td><td class="${s.total_return>=0?'pos':'neg'}">${pct(s.total_return)}</td>
    <td>${pct(s.cagr)}</td><td>${pct(s.ann_vol)}</td><td>${f2(s.sharpe)}</td>
    <td class="neg">${pct(s.max_drawdown)}</td><td>${pct(s.hit_rate,0)}</td></tr>`).join('');
}
load().catch(e => { document.body.insertAdjacentHTML('beforeend', `<pre style="padding:20px;color:red">load error: ${e}</pre>`); });
