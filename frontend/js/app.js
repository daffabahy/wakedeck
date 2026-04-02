// =============================================
// WAKEDECK — Main Application Logic
// =============================================

let statusPollingInterval = null;
let currentDevices = [];
let appTimezoneOffset = 0; // hours offset from UTC

// --- Toast ---
function showToast(msg, type = 'success') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    const icon = type === 'error' ? 'circle-exclamation' : 'check';
    t.innerHTML = `<i class="fa-solid fa-${icon}"></i> ${msg}`;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
}

// --- Timezone Helper ---
function formatTimestamp(isoStr) {
    if (!isoStr) return '—';
    // Backend stores UTC datetimes without 'Z' suffix (naive).
    // Ensure JS treats them as UTC by appending 'Z' if missing.
    let str = String(isoStr).trim();
    if (!str.endsWith('Z') && !str.includes('+') && !str.includes('T00:00:00')) {
        str += 'Z';
    }
    const d = new Date(str);
    if (isNaN(d.getTime())) return isoStr;
    // Convert UTC ms → target timezone ms
    const targetMs = d.getTime() + (appTimezoneOffset * 3600000);
    const target = new Date(targetMs);
    // Format using UTC methods so we don't get double-offset from browser locale
    const pad = n => String(n).padStart(2, '0');
    return `${pad(target.getUTCDate())}/${pad(target.getUTCMonth()+1)}/${target.getUTCFullYear()}, ${pad(target.getUTCHours())}:${pad(target.getUTCMinutes())}:${pad(target.getUTCSeconds())}`;
}

// --- Mobile Sidebar ---
function openSidebar() {
    document.getElementById('sidebar').classList.add('open');
    document.getElementById('sidebar-overlay').classList.add('active');
}

function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('active');
}

document.getElementById('mobile-menu-btn').addEventListener('click', openSidebar);
document.getElementById('sidebar-close').addEventListener('click', closeSidebar);
document.getElementById('sidebar-overlay').addEventListener('click', closeSidebar);

// --- App Init ---
async function initApp() {
    window.addEventListener('auth-expired', showAuthView);
    const token = API.getToken();
    if (token) {
        try {
            const user = await API.getMe();
            document.getElementById('current-username').textContent = user.username;
            // Load timezone
            try {
                const tz = await API.getTimezone();
                const tzStr = tz.timezone || 'UTC+0';
                appTimezoneOffset = parseInt(tzStr.replace('UTC', ''));
                document.getElementById('set-timezone').value = tzStr;
            } catch {}
            showDashboard();
        } catch { showAuthView(); }
    } else {
        showAuthView();
    }
}

async function showAuthView() {
    document.getElementById('dashboard-view').classList.add('hidden');
    document.getElementById('auth-view').classList.remove('hidden');
    try {
        const { needs_setup } = await API.checkSetupStatus();
        document.getElementById('setup-form').classList.toggle('hidden', !needs_setup);
        document.getElementById('login-form').classList.toggle('hidden', needs_setup);
    } catch { showToast("Cannot connect to server", "error"); }
}

function showDashboard() {
    document.getElementById('auth-view').classList.add('hidden');
    document.getElementById('dashboard-view').classList.remove('hidden');
    loadDevices();
    startStatusPolling();
}

// --- Navigation ---
document.querySelectorAll('.menu-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        closeSidebar();
        document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
        e.currentTarget.classList.add('active');
        
        const target = e.currentTarget.dataset.target;
        document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
        document.getElementById(`section-${target}`).classList.add('active');
        document.getElementById('page-title').textContent = e.currentTarget.textContent.trim();
        
        if (target === 'devices') loadDevices();
        if (target === 'schedules') loadSchedules();
        if (target === 'history') loadHistory();
        if (target === 'settings') loadSettings();
    });
});

// --- Auth ---
document.getElementById('setup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-setup'); btn.disabled = true;
    try {
        await API.setupInit({
            username: document.getElementById('setup-username').value,
            password: document.getElementById('setup-password').value
        });
        showToast("Setup complete. Please sign in.");
        setTimeout(showAuthView, 800);
    } catch (err) { showToast(err.message, "error"); }
    finally { btn.disabled = false; }
});

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-login'); btn.disabled = true;
    try {
        await API.login(
            document.getElementById('login-username').value,
            document.getElementById('login-password').value
        );
        initApp();
    } catch (err) { showToast(err.message, "error"); }
    finally { btn.disabled = false; }
});

document.getElementById('btn-logout').addEventListener('click', () => {
    API.clearToken();
    stopStatusPolling();
    showAuthView();
});

// =============================================
// DEVICES
// =============================================

async function loadDevices() {
    try {
        currentDevices = await API.getDevices();
        renderDevices(currentDevices);
    } catch { showToast("Failed to load devices", "error"); }
}

async function refreshDevices() {
    showToast("Refreshing...");
    await loadDevices();
}

function renderDevices(devices) {
    const c = document.getElementById('devices-container');
    if (!devices.length) {
        c.innerHTML = `<div class="empty-state"><i class="fa-solid fa-desktop"></i><p>No devices yet. Add your first device to get started.</p></div>`;
        return;
    }
    c.innerHTML = devices.map(d => {
        const osIcon = d.os_type === 'linux' ? 'fa-linux' : 'fa-windows';
        return `
        <div class="device-card" id="device-${d.id}">
            <div class="device-header">
                <div class="device-header-left">
                    <div class="dev-icon"><i class="fa-brands ${osIcon}"></i></div>
                    <div class="dev-info">
                        <h3>${escapeHtml(d.name)}</h3>
                        <p>${escapeHtml(d.ip_address)} · ${escapeHtml(d.mac_address)}</p>
                    </div>
                </div>
                <span class="dev-status status-checking" id="status-${d.id}"><div class="status-dot"></div> ...</span>
            </div>
            <div class="device-ports" id="ports-${d.id}">
                <span class="port-badge">SSH: --</span>
                <span class="port-badge">RDP: --</span>
                <span class="port-badge">VNC: --</span>
            </div>
            <div class="device-actions">
                <button class="btn-primary" onclick="controlDevice(${d.id},'wake')"><i class="fa-solid fa-bolt"></i> Wake</button>
                <button class="btn-icon" onclick="controlDevice(${d.id},'shutdown')" title="Shutdown"><i class="fa-solid fa-power-off"></i></button>
                <button class="btn-icon" onclick="controlDevice(${d.id},'restart')" title="Restart"><i class="fa-solid fa-rotate-right"></i></button>
                <button class="btn-icon" onclick="editDevice(${d.id})" title="Edit"><i class="fa-solid fa-pen"></i></button>
                <button class="btn-icon" onclick="deleteLocalDevice(${d.id})" title="Delete" style="color:var(--red);"><i class="fa-solid fa-trash"></i></button>
            </div>
        </div>
    `}).join('');
    devices.forEach(d => checkDeviceStatus(d.id));
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

async function checkDeviceStatus(id) {
    try {
        const st = await API.statusDevice(id);
        const badge = document.getElementById(`status-${id}`);
        const ports = document.getElementById(`ports-${id}`);
        if (!badge) return;
        
        badge.className = `dev-status ${st.online ? 'status-online' : 'status-offline'}`;
        badge.innerHTML = `<div class="status-dot"></div> ${st.online ? 'Online' : 'Offline'}`;
        
        if (ports) {
            const pb = (label, open) => `<span class="port-badge${open ? ' open' : ''}">${label}: ${open ? 'Open' : 'Closed'}</span>`;
            ports.innerHTML = pb('SSH', st.ssh_open) + pb('RDP', st.rdp_open) + pb('VNC', st.vnc_open);
        }
    } catch {}
}

function startStatusPolling() {
    if (statusPollingInterval) clearInterval(statusPollingInterval);
    statusPollingInterval = setInterval(() => {
        if (document.getElementById('section-devices').classList.contains('active')) {
            currentDevices.forEach(d => checkDeviceStatus(d.id));
        }
    }, 10000);
}

function stopStatusPolling() { if (statusPollingInterval) clearInterval(statusPollingInterval); }

async function controlDevice(id, action) {
    try {
        if (action === 'wake') {
            await API.wakeDevice(id);
            showToast("Magic packet sent!");
        } else if (action === 'shutdown') {
            if (!confirm("Shutdown this PC?")) return;
            await API.shutdownDevice(id);
            showToast("Shutdown command sent!");
        } else if (action === 'restart') {
            if (!confirm("Restart this PC?")) return;
            await API.restartDevice(id);
            showToast("Restart command sent!");
        }
        setTimeout(() => checkDeviceStatus(id), 3000);
    } catch (err) { showToast(err.message, "error"); }
}

// --- Device Modal ---
function openDeviceModal() {
    document.getElementById('device-form').reset();
    document.getElementById('dev-id').value = '';
    document.getElementById('device-modal-title').textContent = 'Add Device';
    document.getElementById('modal-device').classList.remove('hidden');
}

function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

function editDevice(id) {
    const d = currentDevices.find(x => x.id === id);
    if (!d) return;
    document.getElementById('dev-id').value = d.id;
    document.getElementById('dev-name').value = d.name;
    document.getElementById('dev-ip').value = d.ip_address;
    document.getElementById('dev-mac').value = d.mac_address;
    document.getElementById('dev-os').value = d.os_type || 'windows';
    document.getElementById('dev-ssh-user').value = d.ssh_user || '';
    document.getElementById('dev-ssh-pass').value = '';
    document.getElementById('device-modal-title').textContent = 'Edit Device';
    document.getElementById('modal-device').classList.remove('hidden');
}

async function deleteLocalDevice(id) {
    if (!confirm("Delete this device?")) return;
    try { await API.deleteDevice(id); showToast("Deleted"); loadDevices(); }
    catch (e) { showToast(e.message, "error"); }
}

document.getElementById('device-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('dev-id').value;
    const data = {
        name: document.getElementById('dev-name').value,
        ip_address: document.getElementById('dev-ip').value,
        mac_address: document.getElementById('dev-mac').value,
        os_type: document.getElementById('dev-os').value,
        ssh_user: document.getElementById('dev-ssh-user').value || null
    };
    const pw = document.getElementById('dev-ssh-pass').value;
    if (pw) data.ssh_password = pw;
    try {
        if (id) await API.updateDevice(id, data);
        else await API.createDevice(data);
        showToast("Device saved!");
        closeModal('modal-device');
        loadDevices();
    } catch (err) { showToast(err.message, "error"); }
});

// --- Network Scan ---
async function scanNetwork() {
    document.getElementById('modal-scan').classList.remove('hidden');
    document.getElementById('scan-loading').classList.remove('hidden');
    document.getElementById('scan-results-container').classList.add('hidden');
    try {
        const results = await API.scanNetwork();
        document.getElementById('scan-loading').classList.add('hidden');
        document.getElementById('scan-results-container').classList.remove('hidden');
        document.getElementById('scan-tbody').innerHTML = results.length
            ? results.map(r => `<tr><td>${escapeHtml(r.ip)}</td><td><code>${escapeHtml(r.mac)}</code></td><td><button class="btn-primary" style="padding:0.25rem 0.5rem;font-size:0.8rem;" onclick="addFromScan('${escapeHtml(r.ip)}','${escapeHtml(r.mac)}')"><i class="fa-solid fa-plus"></i></button></td></tr>`).join('')
            : '<tr><td colspan="3" style="text-align:center;color:var(--text-tertiary);padding:2rem;">No devices found.</td></tr>';
    } catch (e) { showToast("Scan failed: " + e.message, "error"); closeModal('modal-scan'); }
}

function addFromScan(ip, mac) {
    closeModal('modal-scan');
    openDeviceModal();
    document.getElementById('dev-ip').value = ip;
    document.getElementById('dev-mac').value = mac;
    document.getElementById('dev-name').value = `PC (${ip})`;
}

// =============================================
// SCHEDULES
// =============================================

async function loadSchedules() {
    try {
        const schedules = await API.getSchedules();
        const tbody = document.getElementById('schedules-tbody');
        if (!schedules.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-tertiary);padding:2rem;">No schedules configured.</td></tr>';
            return;
        }
        const dm = {};
        currentDevices.forEach(d => { dm[d.id] = d.name; });
        tbody.innerHTML = schedules.map(s => `
            <tr>
                <td>${escapeHtml(dm[s.device_id] || '#' + s.device_id)}</td>
                <td><span class="log-action-badge" style="color:${s.action==='wake'?'var(--green)':'var(--red)'};">${escapeHtml(s.action)}</span></td>
                <td><code>${escapeHtml(s.cron_expression)}</code></td>
                <td style="color:${s.enabled?'var(--green)':'var(--text-tertiary)'};">${s.enabled?'Active':'Off'}</td>
                <td><button class="btn-icon" onclick="deleteSchedule(${s.id})" style="color:var(--red);"><i class="fa-solid fa-trash"></i></button></td>
            </tr>
        `).join('');
    } catch { showToast("Failed to load schedules", "error"); }
}

function openScheduleModal() {
    document.getElementById('schedule-form').reset();
    document.getElementById('sch-id').value = '';
    document.getElementById('sch-enabled').checked = true;
    const sel = document.getElementById('sch-device');
    sel.innerHTML = currentDevices.length
        ? currentDevices.map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('')
        : '<option disabled>No devices</option>';
    document.getElementById('modal-schedule').classList.remove('hidden');
}

document.getElementById('schedule-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        await API.createSchedule({
            device_id: parseInt(document.getElementById('sch-device').value),
            action: document.getElementById('sch-action').value,
            cron_expression: document.getElementById('sch-cron').value,
            enabled: document.getElementById('sch-enabled').checked,
            label: document.getElementById('sch-cron').value
        });
        showToast("Schedule created!");
        closeModal('modal-schedule');
        loadSchedules();
    } catch (err) { showToast(err.message, "error"); }
});

async function deleteSchedule(id) {
    if (!confirm("Delete this schedule?")) return;
    try { await API.deleteSchedule(id); showToast("Deleted"); loadSchedules(); }
    catch (e) { showToast(e.message, "error"); }
}

// =============================================
// HISTORY — with timezone
// =============================================

async function loadHistory() {
    try {
        const logs = await API.getHistory();
        const c = document.getElementById('history-container');
        if (!logs.length) {
            c.innerHTML = '<div class="empty-state"><i class="fa-solid fa-list"></i><p>No activity yet.</p></div>';
            return;
        }
        const dm = {};
        currentDevices.forEach(d => { dm[d.id] = d.name; });
        c.innerHTML = logs.map(h => `
            <div class="log-item">
                <div class="log-time">${formatTimestamp(h.timestamp)}</div>
                <div class="log-action"><span class="log-action-badge">${escapeHtml(h.action)}</span></div>
                <div class="log-msg">
                    <strong>${escapeHtml(dm[h.device_id] || '#' + h.device_id)}</strong>
                    ${h.status === 'success' ? '<span class="badge-success">✓</span>' : `<span class="badge-fail">✗</span> ${escapeHtml(h.message || '')}`}
                    <span style="color:var(--text-tertiary);margin-left:0.3rem;">(${escapeHtml(h.triggered_by)})</span>
                </div>
            </div>
        `).join('');
    } catch {}
}

async function clearHistory() {
    if (!confirm("Clear all logs?")) return;
    try { await API.clearHistory(); showToast("Cleared"); loadHistory(); }
    catch (e) { showToast(e.message, "error"); }
}

// =============================================
// SETTINGS
// =============================================

async function loadSettings() {
    // SSH key
    try {
        const keyData = await API.getSSHPublicKey();
        document.getElementById('set-ssh-pubkey').value = keyData.public_key || 'Key not available';
    } catch {}
    
    // Timezone
    try {
        const tz = await API.getTimezone();
        document.getElementById('set-timezone').value = tz.timezone || 'UTC+0';
    } catch {}
    
    // Webhook status (masked)
    try {
        const s = await API.getWebhookSettings();
        
        // Discord
        const dStatus = document.getElementById('discord-status');
        const dForm = document.getElementById('discord-form-area');
        if (s.discord_configured) {
            dStatus.innerHTML = `<p style="color:var(--green);font-size:0.85rem;margin-bottom:0.75rem;">
                <i class="fa-solid fa-check-circle"></i> Configured (${escapeHtml(s.discord_hint)})
                <button class="btn-danger" style="margin-left:0.5rem;font-size:0.75rem;" onclick="clearDiscord()"><i class="fa-solid fa-trash"></i> Remove</button>
            </p>`;
            dForm.classList.add('hidden');
        } else {
            dStatus.innerHTML = '';
            dForm.classList.remove('hidden');
        }
        
        // Telegram
        const tStatus = document.getElementById('telegram-status');
        const tForm = document.getElementById('telegram-form-area');
        if (s.telegram_configured) {
            tStatus.innerHTML = `<p style="color:var(--green);font-size:0.85rem;margin-bottom:0.75rem;">
                <i class="fa-solid fa-check-circle"></i> Configured (Chat: ${escapeHtml(s.telegram_hint)})
                <button class="btn-danger" style="margin-left:0.5rem;font-size:0.75rem;" onclick="clearTelegram()"><i class="fa-solid fa-trash"></i> Remove</button>
            </p>`;
            tForm.classList.add('hidden');
        } else {
            tStatus.innerHTML = '';
            tForm.classList.remove('hidden');
        }
        
        // Triggers
        document.getElementById('set-notify-wake').checked = s.notify_on_wake !== false;
        document.getElementById('set-notify-shutdown').checked = s.notify_on_shutdown !== false;
        document.getElementById('set-notify-offline').checked = s.notify_on_offline !== false;
    } catch {}
}

function copySSHKey() {
    const el = document.getElementById('set-ssh-pubkey');
    el.select();
    navigator.clipboard.writeText(el.value).then(
        () => showToast("Public key copied!"),
        () => showToast("Copy failed — select and copy manually", "error")
    );
}

async function saveTimezone() {
    const tz = document.getElementById('set-timezone').value;
    try {
        await API.setTimezone(tz);
        appTimezoneOffset = parseInt(tz.replace('UTC', ''));
        showToast(`Timezone set to ${tz}`);
    } catch (e) { showToast(e.message, "error"); }
}

// --- Discord ---
async function saveDiscordWebhook() {
    const url = document.getElementById('set-discord-url').value;
    if (!url) { showToast("Enter a webhook URL", "error"); return; }
    try {
        await API.saveWebhookSettings({
            discord_url: url,
            notify_on_wake: document.getElementById('set-notify-wake').checked,
            notify_on_shutdown: document.getElementById('set-notify-shutdown').checked,
            notify_on_offline: document.getElementById('set-notify-offline').checked
        });
        showToast("Discord webhook saved!");
        document.getElementById('set-discord-url').value = '';
        loadSettings();
    } catch (e) { showToast(e.message, "error"); }
}

async function testDiscordWebhook() {
    const url = document.getElementById('set-discord-url').value;
    if (!url) { showToast("Enter a webhook URL to test", "error"); return; }
    try {
        await API.testNotification({ type: 'discord', url });
        showToast("Discord test sent!");
    } catch (e) { showToast(e.message, "error"); }
}

async function clearDiscord() {
    if (!confirm("Remove Discord webhook?")) return;
    try {
        await API.clearDiscordWebhook();
        showToast("Discord webhook removed");
        loadSettings();
    } catch (e) { showToast(e.message, "error"); }
}

// --- Telegram ---
async function saveTelegramBot() {
    const token = document.getElementById('set-telegram-token').value;
    const chat = document.getElementById('set-telegram-chat').value;
    if (!token || !chat) { showToast("Enter bot token and chat ID", "error"); return; }
    try {
        await API.saveWebhookSettings({
            telegram_bot_token: token,
            telegram_chat_id: chat,
            notify_on_wake: document.getElementById('set-notify-wake').checked,
            notify_on_shutdown: document.getElementById('set-notify-shutdown').checked,
            notify_on_offline: document.getElementById('set-notify-offline').checked
        });
        showToast("Telegram bot saved!");
        document.getElementById('set-telegram-token').value = '';
        document.getElementById('set-telegram-chat').value = '';
        loadSettings();
    } catch (e) { showToast(e.message, "error"); }
}

async function testTelegramBot() {
    const token = document.getElementById('set-telegram-token').value;
    const chat = document.getElementById('set-telegram-chat').value;
    if (!token || !chat) { showToast("Enter bot token and chat ID first", "error"); return; }
    try {
        await API.testNotification({ type: 'telegram', bot_token: token, chat_id: chat });
        showToast("Telegram test sent!");
    } catch (e) { showToast(e.message, "error"); }
}

async function clearTelegram() {
    if (!confirm("Remove Telegram bot?")) return;
    try {
        await API.clearTelegramBot();
        showToast("Telegram bot removed");
        loadSettings();
    } catch (e) { showToast(e.message, "error"); }
}

// --- Trigger Settings ---
async function saveTriggerSettings() {
    try {
        // Get current webhook config and just update triggers
        const current = await API.getWebhookSettings();
        await API.saveWebhookSettings({
            notify_on_wake: document.getElementById('set-notify-wake').checked,
            notify_on_shutdown: document.getElementById('set-notify-shutdown').checked,
            notify_on_offline: document.getElementById('set-notify-offline').checked
        });
        showToast("Trigger settings saved!");
    } catch (e) { showToast(e.message, "error"); }
}

// --- Init ---
document.addEventListener('DOMContentLoaded', initApp);
