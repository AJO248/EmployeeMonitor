const loginPanel = document.querySelector("#login-panel");
const dashboard = document.querySelector("#dashboard");
const devices = document.querySelector("#devices");
const empty = document.querySelector("#empty");
const loginError = document.querySelector("#login-error");
const deviceFilter = document.querySelector("#device-filter");

const createAdminModal = document.querySelector("#create-admin-modal");
const showCreateAdminBtn = document.querySelector("#show-create-admin");
const closeCreateAdminBtn = document.querySelector("#close-create-admin");
const createAdminForm = document.querySelector("#create-admin-form");
const createAdminMessage = document.querySelector("#create-admin-message");

const timelineModal = document.querySelector("#timeline-modal");
const closeTimelineBtn = document.querySelector("#close-timeline");
const timelineEventsContainer = document.querySelector("#timeline-events");

let trendsChartInstance = null;

let activeCharts = {};
let allData = [];

// Intersection Observer for scroll animations
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1, rootMargin: "0px 0px -50px 0px" });

function duration(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function destroyCharts() {
  Object.keys(activeCharts).forEach((key) => {
    if (activeCharts[key]) {
      activeCharts[key].destroy();
    }
  });
  activeCharts = {};
  
  if (trendsChartInstance) {
    trendsChartInstance.destroy();
    trendsChartInstance = null;
  }
}

function getClassificationColor(cls) {
  // Vibrant theme colors for charts
  if (cls === "productive") return "#10b981"; // Emerald
  if (cls === "unproductive") return "#f43f5e"; // Rose
  return "#8b5cf6"; // Violet
}

function renderDeviceCard(device) {
  const safeId = escapeHtml(device.device_id);
  
  const appRows = device.top_apps.length
    ? device.top_apps.map((item) => `
        <li class="usage-row">
          <span class="usage-name">
            <span class="usage-dot ${item.classification}"></span>
            ${escapeHtml(item.name)}
          </span>
          <span class="usage-time">${duration(item.seconds)}</span>
        </li>
      `).join("")
    : `<li class="usage-row"><span class="usage-name">No measured intervals</span></li>`;

  const domainRows = device.top_domains.length
    ? device.top_domains.map((item) => `
        <li class="usage-row">
          <span class="usage-name">
            <span class="usage-dot ${item.classification}"></span>
            ${escapeHtml(item.name)}
          </span>
          <span class="usage-time">${duration(item.seconds)}</span>
        </li>
      `).join("")
    : `<li class="usage-row"><span class="usage-name">No measured intervals</span></li>`;

  return `
    <article class="panel device-card" id="card-${safeId}">
      <div class="device-card-header">
        <div class="device-title-area">
          <h2>${safeId}</h2>
          <span class="status-badge ${device.status.toLowerCase()}">${escapeHtml(device.status)}</span>
        </div>
        <button class="secondary-btn" onclick="openTimeline('${safeId}')">View Timeline</button>
      </div>

      <div class="metrics-row">
        <div class="metric-card productivity-score-card">
          <span>Productivity Score</span>
          <strong>${device.productivity_score}%</strong>
        </div>
        <div class="metric-card">
          <span>Active Duration</span>
          <strong>${duration(device.active_seconds)}</strong>
        </div>
        <div class="metric-card">
          <span>Idle Duration</span>
          <strong>${duration(device.idle_seconds)}</strong>
        </div>
      </div>

      <div class="charts-grid">
        <div class="chart-container">
          <h3>Application Time</h3>
          <div class="chart-wrapper">
            <canvas id="chart-apps-${safeId}"></canvas>
          </div>
        </div>
        <div class="chart-container">
          <h3>Domain Distribution</h3>
          <div class="chart-wrapper">
            <canvas id="chart-domains-${safeId}"></canvas>
          </div>
        </div>
      </div>

      <div class="lists-grid">
        <div class="list-container">
          <h3>Top Applications</h3>
          <ul class="usage-list">${appRows}</ul>
        </div>
        <div class="list-container">
          <h3>Top Domains</h3>
          <ul class="usage-list">${domainRows}</ul>
        </div>
      </div>
    </article>
  `;
}

function initChart(canvasId, items) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  if (items.length === 0) {
    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['No activity'],
        datasets: [{
          data: [1],
          backgroundColor: ['rgba(148, 163, 184, 0.1)'],
          borderColor: 'transparent',
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: false }
        },
        cutout: '80%'
      }
    });
  }

  const labels = items.map(item => item.name);
  const data = items.map(item => item.seconds);
  const colors = items.map(item => getClassificationColor(item.classification));

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors,
        hoverBackgroundColor: colors,
        borderColor: '#0f172a', // matches dark card background
        borderWidth: 3,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.9)',
          titleFont: { family: 'Inter', size: 14, weight: 'bold' },
          bodyFont: { family: 'Inter', size: 13 },
          padding: 12,
          cornerRadius: 8,
          boxPadding: 6,
          callbacks: {
            label: function(context) {
              const sec = context.raw;
              const hrs = Math.floor(sec / 3600);
              const mins = Math.floor((sec % 3600) / 60);
              return ` ${context.label}: ${hrs}h ${mins}m`;
            }
          }
        }
      },
      cutout: '75%',
      animation: {
        animateScale: true,
        animateRotate: true
      }
    }
  });
}

function render() {
  destroyCharts();
  
  const filterVal = deviceFilter.value;
  const filtered = filterVal === "all"
    ? allData
    : allData.filter(d => d.device_id === filterVal);

  empty.hidden = filtered.length > 0;
  devices.innerHTML = filtered.map(renderDeviceCard).join("");

  // Initialize charts and observers
  filtered.forEach((device) => {
    const safeId = device.device_id;
    activeCharts[`apps-${safeId}`] = initChart(`chart-apps-${safeId}`, device.top_apps);
    activeCharts[`domains-${safeId}`] = initChart(`chart-domains-${safeId}`, device.top_domains);
    
    // Observe the new card for entry animation
    const card = document.getElementById(`card-${safeId}`);
    if (card) observer.observe(card);
  });
}

function updateDeviceFilterOptions() {
  const currentVal = deviceFilter.value;
  deviceFilter.innerHTML = '<option value="all">All Devices</option>';
  
  const deviceIds = [...new Set(allData.map(d => d.device_id))].sort();
  deviceIds.forEach((id) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    if (id === currentVal) opt.selected = true;
    deviceFilter.appendChild(opt);
  });
}

async function loadTrends() {
  const hours = document.querySelector("#hours").value;
  const filterVal = deviceFilter.value;
  let url = `/api/v1/analytics/trends?hours=${hours}`;
  if (filterVal !== "all") {
    url += `&device_id=${encodeURIComponent(filterVal)}`;
  }
  
  const response = await fetch(url);
  if (!response.ok) return;
  
  const trends = await response.json();
  
  const ctx = document.getElementById("trendsChart");
  if (!ctx) return;
  
  if (trendsChartInstance) {
    trendsChartInstance.destroy();
  }
  
  const labels = trends.map(t => {
    const d = new Date(t.hour_timestamp);
    return d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  });
  
  const toMinutes = (seconds) => (seconds / 60).toFixed(1);
  
  trendsChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Productive (min)',
          data: trends.map(t => toMinutes(t.productive_seconds)),
          borderColor: getClassificationColor('productive'),
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'Unproductive (min)',
          data: trends.map(t => toMinutes(t.unproductive_seconds)),
          borderColor: getClassificationColor('unproductive'),
          backgroundColor: 'rgba(244, 63, 94, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'Idle (min)',
          data: trends.map(t => toMinutes(t.idle_seconds)),
          borderColor: getClassificationColor('idle'),
          backgroundColor: 'rgba(245, 158, 11, 0.1)',
          fill: true,
          tension: 0.4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#f8fafc', font: { family: 'Inter' } } },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: 'rgba(15, 23, 42, 0.9)'
        }
      },
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
        y: { beginAtZero: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
      }
    }
  });
}

async function openTimeline(deviceId) {
  timelineEventsContainer.innerHTML = '<p style="color:var(--text-muted); text-align:center;">Loading timeline...</p>';
  timelineModal.hidden = false;
  
  const hours = document.querySelector("#hours").value;
  try {
    const response = await fetch(`/api/v1/analytics/timeline/${encodeURIComponent(deviceId)}?hours=${hours}`);
    if (!response.ok) throw new Error("Failed to load timeline");
    
    const events = await response.json();
    
    if (events.length === 0) {
      timelineEventsContainer.innerHTML = '<p style="color:var(--text-muted); text-align:center;">No activity recorded.</p>';
      return;
    }
    
    timelineEventsContainer.innerHTML = events.map(ev => {
      const timeStr = new Date(ev.timestamp).toLocaleTimeString();
      let content = ev.classification === 'idle' ? 'Idle' : escapeHtml(ev.app_name || 'Unknown App');
      if (ev.domain) {
        content += ` - <em>${escapeHtml(ev.domain)}</em>`;
      }
      return `
        <div class="timeline-item ${ev.classification}">
          <div class="timeline-time">${timeStr} (${duration(ev.duration_seconds)})</div>
          <div class="timeline-content">${content}</div>
        </div>
      `;
    }).join('');
    
  } catch (err) {
    timelineEventsContainer.innerHTML = '<p class="error">Error loading timeline data.</p>';
  }
}

closeTimelineBtn.addEventListener("click", () => {
  timelineModal.hidden = true;
});

async function loadSummary() {
  const hours = document.querySelector("#hours").value;
  const response = await fetch(`/api/v1/analytics/summary?hours=${hours}`);
  if (response.status === 401) {
    loginPanel.hidden = false;
    dashboard.hidden = true;
    destroyCharts();
    return;
  }
  if (!response.ok) throw new Error("Could not load analytics");
  
  allData = await response.json();
  
  updateDeviceFilterOptions();
  render();
  loadTrends();
  
  loginPanel.hidden = true;
  dashboard.hidden = false;
}

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      username: document.querySelector("#username").value,
      password: document.querySelector("#password").value,
    }),
  });
  if (!response.ok) {
    loginError.textContent = "Invalid username or password.";
    return;
  }
  await loadSummary();
});

document.querySelector("#refresh").addEventListener("click", loadSummary);
document.querySelector("#hours").addEventListener("change", () => {
  loadSummary();
  if (!timelineModal.hidden) timelineModal.hidden = true;
});
deviceFilter.addEventListener("change", () => {
  render();
  loadTrends();
});

document.querySelector("#logout").addEventListener("click", async () => {
  await fetch("/api/v1/auth/logout", {method: "POST"});
  dashboard.hidden = true;
  loginPanel.hidden = false;
  destroyCharts();
});

showCreateAdminBtn.addEventListener("click", () => {
  createAdminModal.hidden = false;
  createAdminMessage.textContent = "";
  createAdminMessage.className = "error";
  createAdminForm.reset();
});

closeCreateAdminBtn.addEventListener("click", () => {
  createAdminModal.hidden = true;
});

createAdminForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  createAdminMessage.textContent = "";
  createAdminMessage.className = "error";

  const username = document.querySelector("#new-admin-username").value;
  const password = document.querySelector("#new-admin-password").value;

  try {
    const response = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (response.ok) {
      createAdminMessage.textContent = "Admin created successfully!";
      createAdminMessage.className = "success";
      createAdminForm.reset();
      setTimeout(() => {
        createAdminModal.hidden = true;
      }, 1500);
    } else {
      createAdminMessage.textContent = data.detail || "Failed to create admin.";
    }
  } catch (error) {
    createAdminMessage.textContent = "An error occurred.";
  }
});

loadSummary().catch(console.error);
