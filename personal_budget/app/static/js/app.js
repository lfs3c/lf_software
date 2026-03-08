let monthChart;
let categoryChart;
let annualChart;
let investmentsChart;
let investmentsCache;
let currentCategoryItems = [];

const CATEGORY_PALETTE = ['#264653', '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51', '#8ab17d', '#1d3557', '#7f5539'];

function formatUsd(value) {
  const number = Number(value || 0);
  return `USD ${number.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

async function loadDashboard() {
  const res = await fetch('/api/dashboard');
  if (!res.ok) return;
  const data = await res.json();
  drawCharts(data);
}

async function loadAnnual() {
  const res = await fetch('/api/annual-current');
  if (!res.ok) return;
  const data = await res.json();
  drawAnnualChart(data);
}

async function loadInvestments() {
  const res = await fetch('/api/investments/current');
  if (!res.ok) return;
  investmentsCache = await res.json();
  syncInvestmentManualInput();
  drawInvestmentsChart();
}

function drawCharts(data) {
  const monthLabel = data.month || '';
  const income = data.totals?.income || 0;
  const expenses = data.totals?.expenses || 0;
  const categories = data.categories || [];
  const userInitials = data.user_initials || 'USR';

  const monthLabelEl = document.getElementById('chart-month-label');
  if (monthLabelEl) monthLabelEl.innerText = monthLabel;

  if (monthChart) monthChart.destroy();
  if (categoryChart) categoryChart.destroy();

  const monthCanvas = document.getElementById('monthChart');
  if (monthCanvas) {
    const ctx1 = monthCanvas.getContext('2d');
    monthChart = new Chart(ctx1, {
      type: 'bar',
      data: {
        labels: ['Income', 'Expenses'],
        datasets: [{
          label: `Month ${monthLabel}`,
          data: [income, expenses],
          backgroundColor: ['#2a9d8f', '#e76f51'],
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: {
            ticks: {
              callback: (value) => formatUsd(value),
            },
          },
        },
        plugins: {
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label} [${userInitials}]: ${formatUsd(ctx.parsed.y)}`,
            },
          },
        },
      }
    });
  }

  const categoryCanvas = document.getElementById('categoryChart');
  if (!categoryCanvas) return;
  const ctx2 = categoryCanvas.getContext('2d');
  const categoriesSorted = [...categories].sort((a, b) => {
    const amountA = Number(a?.amount || 0);
    const amountB = Number(b?.amount || 0);
    if (amountB !== amountA) return amountB - amountA;
    return String(a?.category || '').localeCompare(String(b?.category || ''));
  });
  const resolvedCategories = categoriesSorted.map((item, index) => ({
    ...item,
    color: item.color || CATEGORY_PALETTE[index % CATEGORY_PALETTE.length],
  }));
  currentCategoryItems = resolvedCategories;
  categoryChart = new Chart(ctx2, {
    type: 'doughnut',
    data: {
      labels: resolvedCategories.map(c => `${c.category} (${c.percent}%)`),
      datasets: [{
        data: resolvedCategories.map(c => c.amount),
        backgroundColor: resolvedCategories.map(c => c.color),
      }]
    },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${formatUsd(ctx.parsed)}`,
          },
        },
      },
    }
  });
  renderCategoryColorEditor();
}

function drawAnnualChart(data) {
  const labels = data.labels || [];
  const income = data.income || [];
  const expenses = data.expenses || [];
  const balance = data.balance || [];
  const year = data.year || '';
  const userInitials = data.user_initials || 'USR';
  const annualYearLabel = document.getElementById('annual-year-label');
  if (annualYearLabel) annualYearLabel.innerText = `Year ${year}`;

  if (annualChart) annualChart.destroy();
  const annualCanvas = document.getElementById('annualChart');
  if (!annualCanvas) return;
  const ctx = annualCanvas.getContext('2d');
  annualChart = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: 'bar',
          label: 'Income',
          data: income,
          backgroundColor: '#2a9d8f',
        },
        {
          type: 'bar',
          label: 'Expenses',
          data: expenses,
          backgroundColor: '#e76f51',
        },
        {
          type: 'line',
          label: 'Balance',
          data: balance,
          borderColor: '#1d3557',
          backgroundColor: '#1d3557',
          borderWidth: 3,
          tension: 0.25,
          fill: false,
          pointRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: {
          ticks: {
            callback: (value) => formatUsd(value),
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label} [${userInitials}]: ${formatUsd(ctx.parsed.y)}`,
          },
        },
      },
    },
  });
}

function drawInvestmentsChart() {
  if (!investmentsCache) return;
  const userInitials = investmentsCache.user_initials || 'USR';
  const modeEl = document.getElementById('investments-view-mode');
  const mode = modeEl?.value === 'year' ? 'year' : 'month';
  const labels = mode === 'year' ? investmentsCache.labels : (investmentsCache.month_day_labels || []);
  const acornsValues = mode === 'year'
    ? (investmentsCache.acorns_month_values || [])
    : (investmentsCache.acorns_day_values || []);
  const webullValues = mode === 'year'
    ? (investmentsCache.webull_month_values || [])
    : (investmentsCache.webull_day_values || []);
  const rangeLabel = document.getElementById('investments-range-label');
  if (rangeLabel) {
    rangeLabel.innerText = mode === 'year'
      ? `Year ${investmentsCache.year}`
      : `${investmentsCache.current_month} (daily trend)`;
  }

  if (investmentsChart) investmentsChart.destroy();
  const canvas = document.getElementById('investmentsChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  investmentsChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: `Acorns (${mode === 'year' ? investmentsCache.year : investmentsCache.current_month})`,
        data: acornsValues,
        borderColor: '#2a9d8f',
        backgroundColor: '#2a9d8f',
        borderWidth: 3,
        tension: 0.25,
        fill: false,
        pointRadius: mode === 'year' ? 4 : 3,
      },
      {
        label: `Webull (${mode === 'year' ? investmentsCache.year : investmentsCache.current_month})`,
        data: webullValues,
        borderColor: '#1d3557',
        backgroundColor: '#1d3557',
        borderWidth: 3,
        tension: 0.25,
        fill: false,
        pointRadius: mode === 'year' ? 4 : 3,
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          ticks: {
            callback: (value) => formatUsd(value),
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label} [${userInitials}]: ${formatUsd(ctx.parsed.y)}`,
          },
        },
      },
    }
  });
}

function parseMaskedCurrencyToNumber(raw) {
  const value = String(raw ?? '').trim();
  if (!value) return null;
  const hasDot = value.includes('.');
  const hasComma = value.includes(',');
  let normalized = value;
  if (hasDot && hasComma) {
    normalized = value.lastIndexOf(',') > value.lastIndexOf('.')
      ? value.replace(/\./g, '').replace(',', '.')
      : value.replace(/,/g, '');
  } else if (hasComma) {
    normalized = value.replace(',', '.');
  }
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function renderCategoryColorEditor() {
  const list = document.getElementById('category-colors-list');
  if (!list) return;
  if (!currentCategoryItems.length) {
    list.innerHTML = '<span>No categories in the current chart.</span>';
    return;
  }
  list.innerHTML = currentCategoryItems
    .map((item) => `
      <label class="category-color-row">
        <span>${item.category}</span>
        <input type="color" data-category-name="${item.category}" value="${item.color}" />
      </label>
    `)
    .join('');
}

function syncInvestmentManualInput() {
  const acornsInput = document.getElementById('investment-manual-acorns');
  const webullInput = document.getElementById('investment-manual-webull');
  if (!(acornsInput && webullInput && investmentsCache)) return;
  const acorns = Number(investmentsCache.current_manual_acorns || 0);
  const webull = Number(investmentsCache.current_manual_webull || 0);
  acornsInput.value = acorns.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  webullInput.value = webull.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

window.addEventListener('DOMContentLoaded', () => {
  const startCharts = () => {
    loadAnnual();
    loadDashboard();
    loadInvestments();
  };

  if (window.__appSplashRunning || document.body.classList.contains('app-splash-running')) {
    document.addEventListener('app-splash:end', startCharts, { once: true });
  } else {
    startCharts();
  }

  document.getElementById('investments-view-mode')?.addEventListener('change', drawInvestmentsChart);
  document.getElementById('toggle-investment-manual')?.addEventListener('click', () => {
    const panel = document.getElementById('investment-manual-panel');
    panel?.classList.toggle('hidden');
  });
  document.getElementById('investment-manual-save')?.addEventListener('click', async () => {
    const acornsInput = document.getElementById('investment-manual-acorns');
    const webullInput = document.getElementById('investment-manual-webull');
    const feedback = document.getElementById('investment-manual-feedback');
    if (!(acornsInput && webullInput && feedback && investmentsCache)) return;

    const parsedAcorns = parseMaskedCurrencyToNumber(acornsInput.value);
    const parsedWebull = parseMaskedCurrencyToNumber(webullInput.value);
    if (parsedAcorns === null || parsedAcorns < 0 || parsedWebull === null || parsedWebull < 0) {
      feedback.innerText = 'Enter valid manual values for Acorns and Webull.';
      return;
    }

    const payload = new URLSearchParams();
    payload.append('month_label', investmentsCache.current_month);
    payload.append('acorns_value', String(parsedAcorns));
    payload.append('webull_value', String(parsedWebull));

    const res = await fetch('/api/investments/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: payload.toString(),
    });
    if (!res.ok) {
      feedback.innerText = 'Could not save manual value.';
      return;
    }
    feedback.innerText = 'Manual values saved.';
    await loadInvestments();
  });

  document.getElementById('edit-category-colors-btn')?.addEventListener('click', () => {
    const panel = document.getElementById('category-colors-panel');
    panel?.classList.toggle('hidden');
    renderCategoryColorEditor();
  });

  document.getElementById('save-category-colors-btn')?.addEventListener('click', async () => {
    const feedback = document.getElementById('category-colors-feedback');
    const inputs = Array.from(document.querySelectorAll('#category-colors-list input[type="color"]'));
    const colors = {};
    inputs.forEach((input) => {
      const categoryName = input.dataset.categoryName || '';
      if (categoryName) {
        colors[categoryName] = input.value;
      }
    });
    if (Object.keys(colors).length === 0) {
      if (feedback) feedback.innerText = 'No categories to save.';
      return;
    }

    const res = await fetch('/api/category-colors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ colors }),
    });
    if (!res.ok) {
      if (feedback) feedback.innerText = 'Could not save colors.';
      return;
    }
    if (feedback) feedback.innerText = 'Colors saved.';
    await loadDashboard();
  });
});
