/**
 * charts.js — Helpers para Chart.js
 */

const CHART_COLORS = {
  blue:   'rgba(37,  99,  235, 0.8)',
  green:  'rgba(22,  163, 74,  0.8)',
  red:    'rgba(220, 38,  38,  0.8)',
  yellow: 'rgba(217, 119, 6,   0.8)',
  purple: 'rgba(124, 58,  237, 0.8)',
  cyan:   'rgba(8,   145, 178, 0.8)',
  palette: [
    'rgba(37,99,235,0.75)', 'rgba(22,163,74,0.75)', 'rgba(217,119,6,0.75)',
    'rgba(220,38,38,0.75)', 'rgba(124,58,237,0.75)', 'rgba(8,145,178,0.75)',
  ],
};

/**
 * Cria um gráfico de barras a partir de dados da API.
 * @param {string} canvasId  - ID do elemento <canvas>
 * @param {string} apiUrl    - URL do endpoint JSON
 * @param {string} labelKey  - chave do label nos dados (ex: 'subject')
 * @param {string} valueKey  - chave do valor nos dados (ex: 'avg')
 * @param {string} title     - Título do eixo Y
 */
async function createBarChart(canvasId, apiUrl, labelKey = 'subject', valueKey = 'avg', title = 'Média') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  try {
    const res = await fetch(apiUrl);
    const data = await res.json();
    if (!data.length) return;
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.map(d => d[labelKey]),
        datasets: [{
          label: title,
          data: data.map(d => d[valueKey]),
          backgroundColor: CHART_COLORS.palette,
          borderRadius: 6,
          borderSkipped: false,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, max: 10, grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
          x: { grid: { display: false }, ticks: { color: '#64748b' } },
        }
      }
    });
  } catch (e) {
    console.warn('Erro ao carregar gráfico:', e);
  }
}

/**
 * Cria um gráfico radar para desempenho por disciplina.
 */
async function createRadarChart(canvasId, apiUrl) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  try {
    const res = await fetch(apiUrl);
    const data = await res.json();
    if (!data.length) return;
    new Chart(canvas, {
      type: 'radar',
      data: {
        labels: data.map(d => d.subject),
        datasets: [{
          label: 'Média',
          data: data.map(d => d.avg),
          backgroundColor: 'rgba(37,99,235,0.15)',
          borderColor: 'rgba(37,99,235,0.8)',
          borderWidth: 2,
          pointBackgroundColor: 'rgba(37,99,235,0.9)',
        }]
      },
      options: {
        responsive: true,
        scales: { r: { min: 0, max: 10, ticks: { stepSize: 2 } } },
        plugins: { legend: { display: false } }
      }
    });
  } catch (e) {
    console.warn('Erro ao carregar radar:', e);
  }
}

/**
 * Cria um gráfico de rosca para frequência.
 */
async function createAttendanceDonut(canvasId, apiUrl) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  try {
    const res = await fetch(apiUrl);
    const data = await res.json();
    if (!data.length) return;
    const total_p = data.reduce((acc, d) => acc + d.presences, 0);
    const total_a = data.reduce((acc, d) => acc + d.absences, 0);
    new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: ['Presenças', 'Faltas'],
        datasets: [{
          data: [total_p, total_a],
          backgroundColor: [CHART_COLORS.green, CHART_COLORS.red],
          borderWidth: 0,
        }]
      },
      options: {
        responsive: true,
        cutout: '70%',
        plugins: { legend: { position: 'bottom' } }
      }
    });
  } catch (e) {
    console.warn('Erro ao carregar donut:', e);
  }
}

/**
 * Cria um gráfico de linha multi-série para evolução de notas por bimestre.
 * Espera: { periods: [...], series: [{label, data: [...]}, ...] }
 */
async function createEvolutionChart(canvasId, apiUrl) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  try {
    const res = await fetch(apiUrl);
    const data = await res.json();
    if (!data.series || !data.series.length) return;

    const colors = [
      '#2563eb', '#16a34a', '#d97706', '#dc2626',
      '#7c3aed', '#0891b2', '#db2777', '#65a30d',
    ];

    const datasets = data.series.map((s, i) => ({
      label: s.label,
      data: s.data,
      borderColor: colors[i % colors.length],
      backgroundColor: 'transparent',
      borderWidth: 2.5,
      pointRadius: 5,
      pointHoverRadius: 7,
      tension: 0.3,
      spanGaps: true,
    }));

    // Linha de referência do mínimo
    datasets.push({
      label: 'Mínimo (5,0)',
      data: data.periods.map(() => 5),
      borderColor: 'rgba(251,191,36,0.7)',
      borderDash: [5, 5],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
    });

    new Chart(canvas, {
      type: 'line',
      data: { labels: data.periods, datasets },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 },
          },
          tooltip: {
            callbacks: {
              label: ctx =>
                `${ctx.dataset.label}: ${ctx.parsed.y != null ? ctx.parsed.y.toFixed(1) : '—'}`,
            },
          },
        },
        scales: {
          y: {
            min: 0,
            max: 10,
            grid: { color: '#f1f5f9' },
            ticks: { color: '#64748b' },
          },
          x: { grid: { display: false }, ticks: { color: '#64748b' } },
        },
      },
    });
  } catch (e) {
    console.warn('Erro ao carregar gráfico de evolução:', e);
  }
}
