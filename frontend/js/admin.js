// frontend/js/admin.js

const API = '';
let ADMIN_KEY = null;
let RARITIES = {};
let ANIME_LIST = [];
let EDITING_CHAR = null;

function formatNum(n) {
    if (n === null || n === undefined) return '0';
    n = Number(n);
    if (isNaN(n)) return '0';
    const abs = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    if (abs >= 1e9) return sign + (abs / 1e9).toFixed(abs >= 1e10 ? 0 : 1).replace(/\.0$/, '') + 'B';
    if (abs >= 1e6) return sign + (abs / 1e6).toFixed(abs >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M';
    if (abs >= 1e3) return sign + (abs / 1e3).toFixed(abs >= 1e4 ? 0 : 1).replace(/\.0$/, '') + 'K';
    return sign + abs.toString();
}

// ============================================
// AUTH
// ============================================
async function checkAuth() {
    const params = new URLSearchParams(window.location.search);
    let key = params.get('key');
    const uid = params.get('uid');

    if (!key && uid) {
        // Получаем ключ по uid
        try {
            const r = await fetch(`${API}/api/admin/key/${uid}`);
            if (r.ok) {
                const d = await r.json();
                key = d.key;
            }
        } catch(e) {}
    }

    if (!key) {
        document.getElementById('login-status').textContent = '❌ Нет доступа. Открой через /admin в боте.';
        return false;
    }

    // Тестируем ключ
    try {
        const r = await fetch(`${API}/api/admin/characters`, {
            headers: {'X-Admin-Key': key}
        });
        if (r.status === 403) {
            document.getElementById('login-status').textContent = '❌ Неверный ключ';
            return false;
        }
        ADMIN_KEY = key;
        return true;
    } catch(e) {
        document.getElementById('login-status').textContent = '❌ Ошибка: ' + e.message;
        return false;
    }
}

function api(url, opts = {}) {
    opts.headers = opts.headers || {};
    opts.headers['X-Admin-Key'] = ADMIN_KEY;
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(opts.body);
    }
    return fetch(API + url, opts).then(r => r.json());
}

// ============================================
// INIT
// ============================================
async function init() {
    const ok = await checkAuth();
    if (!ok) return;

    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('admin-app').classList.remove('hidden');

    // Загружаем справочники
    RARITIES = await (await fetch('/api/rarities')).json();
    fillRaritySelects();

    // Табы
    document.querySelectorAll('.admin-tabs .tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.admin-tabs .tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('page-' + tab.dataset.tab).classList.add('active');
            loadTab(tab.dataset.tab);
        });
    });

    loadTab('characters');
    updateStats();
    updateSgBadge();

    setInterval(updateSgBadge, 30000);
}

async function updateStats() {
    const chars = await api('/api/admin/characters');
    const anime = await api('/api/admin/anime');
    const users = await api('/api/admin/users');
    document.getElementById('stat-chars').textContent = chars.length;
    document.getElementById('stat-anime').textContent = anime.length;
    document.getElementById('stat-users').textContent = users.length;
}

function loadTab(tab) {
    if (tab === 'characters') loadChars();
    if (tab === 'anime') loadAnime();
    if (tab === 'users') loadUsers();
    if (tab === 'logs') loadLogs();
    if (tab === 'suggestions') loadSuggestions();
    if (tab === 'import') loadImportStatus();

}

function fillRaritySelects() {
    const select = document.getElementById('filter-rarity');
    const modalSel = document.getElementById('char-rarity');
    for (const key in RARITIES) {
        const info = RARITIES[key];
        const opt = `<option value="${key}">${info.emoji} ${info.name}</option>`;
        select.innerHTML += opt;
        modalSel.innerHTML += opt;
    }
}

// ============================================
// CHARACTERS
// ============================================
async function loadChars() {
    const chars = await api('/api/admin/characters');
    const search = document.getElementById('search-char').value.toLowerCase();
    const rarity = document.getElementById('filter-rarity').value;

    const filtered = chars.filter(c => {
        if (rarity && c.rarity !== rarity) return false;
        if (search) {
            const s = (c.name_en + c.name_ru + c.anime_title).toLowerCase();
            if (!s.includes(search)) return false;
        }
        return true;
    });

    const tbody = document.getElementById('chars-tbody');
    tbody.innerHTML = filtered.map(c => `
        <tr>
            <td>${c.id}</td>
            <td>${c.image_url
                ? `<img src="${c.image_url}" class="table-img">`
                : `<div class="table-img" style="display:flex;align-items:center;justify-content:center">${c.rarity_info.emoji}</div>`
            }</td>
            <td>
                <b>${c.name_ru || c.name_en}</b><br>
                <small style="color:var(--text2)">${c.name_en}</small>
            </td>
            <td>${c.anime_title}</td>
            <td>
                <span class="rarity-badge" style="background:${c.rarity_info.color}22;color:${c.rarity_info.color}">
                    ${c.rarity_info.emoji} ${c.rarity_info.name}
                </span>
            </td>
            <td class="stats-inline">⚔${c.power} 🛡${c.defense} 💨${c.speed}</td>
            <td>${c.is_active ? '✅' : '🚫'}</td>
            <td>
                <button class="btn-icon" onclick='editChar(${c.id})'>✏️</button>
            </td>
        </tr>
    `).join('');
}

document.getElementById('search-char').addEventListener('input', loadChars);
document.getElementById('filter-rarity').addEventListener('change', loadChars);

async function openCharModal() {
    EDITING_CHAR = null;
    document.getElementById('char-modal-title').textContent = '➕ Новая карточка';
    document.getElementById('char-delete-btn').style.display = 'none';

    // Загружаем аниме
    const animeList = await api('/api/admin/anime');
    const sel = document.getElementById('char-anime');
    sel.innerHTML = '<option value="">— Не выбрано —</option>' +
        animeList.map(a => `<option value="${a.id}">${a.title_ru || a.title_en}</option>`).join('');

    // Очищаем поля
    document.getElementById('char-name-en').value = '';
    document.getElementById('char-name-ru').value = '';
    document.getElementById('char-name-jp').value = '';
    document.getElementById('char-rarity').value = 'common';
    document.getElementById('char-active').value = 'true';
    document.getElementById('char-power').value = 50;
    document.getElementById('char-defense').value = 50;
    document.getElementById('char-speed').value = 50;
    document.getElementById('char-description').value = '';
    document.getElementById('char-image-url').value = '';
    document.getElementById('char-preview').classList.add('hidden');

    document.getElementById('char-modal').classList.remove('hidden');
}

async function editChar(id) {
    const chars = await api('/api/admin/characters');
    const c = chars.find(x => x.id === id);
    if (!c) return;

    EDITING_CHAR = id;
    document.getElementById('char-modal-title').textContent = `✏️ Карточка #${id}`;
    document.getElementById('char-delete-btn').style.display = 'inline-block';

    const animeList = await api('/api/admin/anime');
    const sel = document.getElementById('char-anime');
    sel.innerHTML = '<option value="">— Не выбрано —</option>' +
        animeList.map(a => `<option value="${a.id}" ${a.id === c.anime_id ? 'selected' : ''}>${a.title_ru || a.title_en}</option>`).join('');

    document.getElementById('char-name-en').value = c.name_en || '';
    document.getElementById('char-name-ru').value = c.name_ru || '';
    document.getElementById('char-name-jp').value = c.name_jp || '';
    document.getElementById('char-rarity').value = c.rarity;
    document.getElementById('char-active').value = c.is_active ? 'true' : 'false';
    document.getElementById('char-power').value = c.power;
    document.getElementById('char-defense').value = c.defense;
    document.getElementById('char-speed').value = c.speed;
    document.getElementById('char-description').value = c.description || '';
    document.getElementById('char-image-url').value = c.image_url || '';

    const preview = document.getElementById('char-preview');
    if (c.image_url) {
        preview.src = c.image_url;
        preview.classList.remove('hidden');
    } else {
        preview.classList.add('hidden');
    }

    document.getElementById('char-modal').classList.remove('hidden');
}

function closeCharModal() {
    document.getElementById('char-modal').classList.add('hidden');
}

async function uploadCharImage() {
    const file = document.getElementById('char-image-file').files[0];
    if (!file) return;

    const fd = new FormData();
    fd.append('file', file);

    toast('⏳ Загрузка...');
    const r = await fetch('/api/admin/upload', {
        method: 'POST',
        headers: {'X-Admin-Key': ADMIN_KEY},
        body: fd,
    });
    const d = await r.json();

    if (d.url) {
        document.getElementById('char-image-url').value = d.url;
        const preview = document.getElementById('char-preview');
        preview.src = d.url;
        preview.classList.remove('hidden');
        toast('✅ Загружено', 'success');
    } else {
        toast('❌ Ошибка', 'error');
    }
}

async function saveChar() {
    const data = {
        name_en: document.getElementById('char-name-en').value.trim(),
        name_ru: document.getElementById('char-name-ru').value.trim() || null,
        name_jp: document.getElementById('char-name-jp').value.trim(),
        anime_id: parseInt(document.getElementById('char-anime').value) || null,
        rarity: document.getElementById('char-rarity').value,
        is_active: document.getElementById('char-active').value === 'true',
        power: parseInt(document.getElementById('char-power').value),
        defense: parseInt(document.getElementById('char-defense').value),
        speed: parseInt(document.getElementById('char-speed').value),
        description: document.getElementById('char-description').value.trim() || null,
        image_url: document.getElementById('char-image-url').value || null,
    };

    if (!data.name_en) {
        toast('❌ Укажи английское имя', 'error');
        return;
    }

    let result;
    if (EDITING_CHAR) {
        result = await api(`/api/admin/characters/${EDITING_CHAR}`, {method: 'PUT', body: data});
    } else {
        result = await api('/api/admin/characters', {method: 'POST', body: data});
    }

    if (result.success) {
        toast('✅ Сохранено', 'success');
        closeCharModal();
        loadChars();
        updateStats();
    } else {
        toast('❌ Ошибка', 'error');
    }
}

async function deleteChar() {
    if (!EDITING_CHAR) return;
    if (!confirm('Точно удалить? Также удалится из коллекций игроков!')) return;

    const r = await api(`/api/admin/characters/${EDITING_CHAR}`, {method: 'DELETE'});
    if (r.success) {
        toast('🗑 Удалено', 'success');
        closeCharModal();
        loadChars();
        updateStats();
    }
}

// ============================================
// ANIME
// ============================================
async function loadAnime() {
    const list = await api('/api/admin/anime');
    document.getElementById('anime-tbody').innerHTML = list.map(a => `
        <tr>
            <td>${a.id}</td>
            <td>${a.title_en}</td>
            <td>${a.title_ru || '—'}</td>
            <td>${a.genre || '—'}</td>
            <td>${a.chars_count}</td>
        </tr>
    `).join('');
}

function openAnimeModal() {
    document.getElementById('anime-title-en').value = '';
    document.getElementById('anime-title-ru').value = '';
    document.getElementById('anime-genre').value = '';
    document.getElementById('anime-modal').classList.remove('hidden');
}

function closeAnimeModal() {
    document.getElementById('anime-modal').classList.add('hidden');
}

async function saveAnime() {
    const data = {
        title_en: document.getElementById('anime-title-en').value.trim(),
        title_ru: document.getElementById('anime-title-ru').value.trim() || null,
        genre: document.getElementById('anime-genre').value.trim() || null,
    };

    if (!data.title_en) {
        toast('❌ Укажи EN название', 'error');
        return;
    }

    const r = await api('/api/admin/anime', {method: 'POST', body: data});
    if (r.success) {
        toast('✅ Аниме создано', 'success');
        closeAnimeModal();
        loadAnime();
        updateStats();
    }
}

// ============================================
// USERS
// ============================================
async function loadUsers() {
    const users = await api('/api/admin/users');

    if (users.length === 0) {
        document.getElementById('users-tbody').innerHTML =
            '<tr><td colspan="7" style="text-align:center;color:var(--text2);padding:40px">Игроков пока нет</td></tr>';
        return;
    }

    document.getElementById('users-tbody').innerHTML = users.map(u => {
        const name = u.first_name || '<span style="color:var(--text2)">—</span>';
        const uname = u.username
            ? `<a href="https://t.me/${u.username}" target="_blank" style="color:var(--accent)">@${u.username}</a>`
            : '<span style="color:var(--text2)">—</span>';

        return `
            <tr>
                <td><code style="font-size:11px">${u.telegram_id}</code></td>
                <td><b>${name}</b></td>
                <td>${uname}</td>
                <td title="${u.coins.toLocaleString('ru')} монет">💰 <b>${formatNum(u.coins)}</b></td>
                <td>🎴 ${u.total_cards}</td>
                <td>🎰 ${u.total_pulls}</td>
                <td>
                    <button class="btn-icon" onclick="quickGiveCoins(${u.telegram_id})" title="Выдать монеты">💰</button>
                </td>
            </tr>
        `;
    }).join('');
}

function quickGiveCoins(uid) {
    document.querySelectorAll('.admin-tabs .tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelector('[data-tab="give"]').classList.add('active');
    document.getElementById('page-give').classList.add('active');
    document.getElementById('give-user-id').value = uid;
    document.getElementById('give-coins-amount').focus();
}

// ============================================
// GIVE
// ============================================
async function giveCoins() {
    const uid = parseInt(document.getElementById('give-user-id').value);
    const amount = parseInt(document.getElementById('give-coins-amount').value);

    if (!uid || !amount) {
        toast('❌ Заполни поля', 'error');
        return;
    }

    const r = await api('/api/admin/give_coins', {
        method: 'POST',
        body: {user_id: uid, amount},
    });

    if (r.success) {
        toast(`✅ Баланс: ${r.new_balance}💰`, 'success');
        document.getElementById('give-coins-amount').value = '';
    } else {
        toast('❌ Ошибка', 'error');
    }
}

async function giveCard() {
    const uid = parseInt(document.getElementById('give-card-user').value);
    const cid = parseInt(document.getElementById('give-card-id').value);

    if (!uid || !cid) {
        toast('❌ Заполни поля', 'error');
        return;
    }

    const r = await api('/api/admin/give_card', {
        method: 'POST',
        body: {user_id: uid, character_id: cid},
    });

    if (r.success) {
        toast('✅ Карточка выдана', 'success');
        document.getElementById('give-card-id').value = '';
    }
}

// ============================================
// LOGS
// ============================================
async function loadLogs() {
    const logs = await api('/api/admin/logs?limit=100');
    document.getElementById('logs-tbody').innerHTML = logs.map(l => `
        <tr>
            <td style="font-size:11px">${new Date(l.created_at).toLocaleString('ru')}</td>
            <td><b>${l.action}</b></td>
            <td>${l.details || '—'}</td>
            <td>${l.target_user_id || '—'}</td>
        </tr>
    `).join('');
}

// ============================================
// SUGGESTIONS
// ============================================
let CURRENT_SG = null;

async function loadSuggestions() {
    const status = document.getElementById('sg-filter').value;
    const items = await api(`/api/admin/suggestions?status=${status}`);

    const list = document.getElementById('sg-admin-list');
    if (items.length === 0) {
        list.innerHTML = '<p style="color:var(--text2);text-align:center;padding:40px">Пусто</p>';
        return;
    }

    list.innerHTML = items.map(s => `
        <div class="sg-admin-item ${s.status}" onclick='openSgModal(${JSON.stringify(s).replace(/'/g, "&#39;")})'>
            <div style="display:flex;gap:12px;align-items:flex-start">
                ${s.image_url
                    ? `<img src="${s.image_url}" style="width:60px;height:80px;object-fit:cover;border-radius:8px;flex-shrink:0">`
                    : `<div style="width:60px;height:80px;background:var(--bg3);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:24px;flex-shrink:0">${s.rarity_info.emoji}</div>`
                }
                <div style="flex:1;min-width:0">
                    <div class="sg-admin-header">
                        <div>
                            <div class="sg-admin-title">${s.rarity_info.emoji} ${s.name_ru || s.name_en}</div>
                            <div class="sg-admin-user">👤 ${s.user_name || 'ID:' + s.user_id}</div>
                        </div>
                        <span class="sg-status ${s.status}" style="padding:4px 10px;border-radius:6px;font-size:11px">
                            ${s.status === 'pending' ? '⏳' : s.status === 'approved' ? '✅' : '❌'}
                        </span>
                    </div>
                    <div class="sg-admin-meta">
                        📺 ${s.anime_title} | ⚔${s.power} 🛡${s.defense} 💨${s.speed}
                        ${s.image_url ? ' | 🖼 <b style="color:var(--green)">Есть картинка</b>' : ''}
                    </div>
                    ${s.description ? `<div class="sg-admin-desc">${s.description}</div>` : ''}
                    ${s.admin_comment ? `<div class="sg-admin-desc">💬 ${s.admin_comment}</div>` : ''}
                </div>
            </div>
        </div>
    `).join('');
}


function openSgModal(s) {
    CURRENT_SG = s;

    document.getElementById('sg-modal-info').innerHTML = `
        <p><b>👤 Автор:</b> ${s.user_name || 'ID:' + s.user_id} (<code>${s.user_id}</code>)</p>
        <p><b>📅 Дата:</b> ${new Date(s.created_at).toLocaleString('ru')}</p>
        ${s.image_url
            ? `<p style="margin-top:8px"><b>🖼 Предложенная картинка:</b></p>
               <img src="${s.image_url}" style="max-width:200px;border-radius:8px;margin-top:4px">`
            : `<p style="color:var(--text2);margin-top:8px"><i>Без картинки</i></p>`
        }
    `;

    document.getElementById('sg-e-name-en').value = s.name_en;
    document.getElementById('sg-e-name-ru').value = s.name_ru || '';
    document.getElementById('sg-e-name-jp').value = s.name_jp || '';
    document.getElementById('sg-e-power').value = s.power;
    document.getElementById('sg-e-defense').value = s.defense;
    document.getElementById('sg-e-speed').value = s.speed;
    document.getElementById('sg-e-description').value = s.description || '';
    document.getElementById('sg-e-comment').value = '';

    // Если юзер приложил картинку — используем её по умолчанию
    if (s.image_url) {
        document.getElementById('sg-image-url').value = s.image_url;
        const preview = document.getElementById('sg-preview');
        preview.src = s.image_url;
        preview.classList.remove('hidden');
    } else {
        document.getElementById('sg-image-url').value = '';
        document.getElementById('sg-preview').classList.add('hidden');
    }

    const raritySel = document.getElementById('sg-e-rarity');
    raritySel.innerHTML = '';
    for (const key in RARITIES) {
        const info = RARITIES[key];
        raritySel.innerHTML += `<option value="${key}" ${key === s.rarity_suggested ? 'selected' : ''}>${info.emoji} ${info.name}</option>`;
    }

    document.getElementById('sg-modal').classList.remove('hidden');
}

function closeSgModal() {
    document.getElementById('sg-modal').classList.add('hidden');
    CURRENT_SG = null;
}


async function uploadSgImage() {
    const file = document.getElementById('sg-image-file').files[0];
    if (!file) return;

    const fd = new FormData();
    fd.append('file', file);

    toast('⏳ Загрузка...');
    const r = await fetch('/api/admin/upload', {
        method: 'POST',
        headers: {'X-Admin-Key': ADMIN_KEY},
        body: fd,
    });
    const d = await r.json();

    if (d.url) {
        document.getElementById('sg-image-url').value = d.url;
        const preview = document.getElementById('sg-preview');
        preview.src = d.url;
        preview.classList.remove('hidden');
        toast('✅ Загружено', 'success');
    }
}


async function approveSg() {
    if (!CURRENT_SG) return;
    if (!confirm('Одобрить и создать карточку?')) return;

    const data = {
        name_en: document.getElementById('sg-e-name-en').value.trim(),
        name_ru: document.getElementById('sg-e-name-ru').value.trim() || null,
        name_jp: document.getElementById('sg-e-name-jp').value.trim(),
        rarity: document.getElementById('sg-e-rarity').value,
        power: parseInt(document.getElementById('sg-e-power').value),
        defense: parseInt(document.getElementById('sg-e-defense').value),
        speed: parseInt(document.getElementById('sg-e-speed').value),
        description: document.getElementById('sg-e-description').value.trim() || null,
        comment: document.getElementById('sg-e-comment').value.trim() || null,
        image_url: document.getElementById('sg-image-url').value || null,
    };

    const r = await api(`/api/admin/suggestions/${CURRENT_SG.id}/approve`, {
        method: 'POST',
        body: data,
    });

    if (r.success) {
        toast(`✅ Одобрено! Карточка #${r.character_id}`, 'success');
        closeSgModal();
        loadSuggestions();
        updateSgBadge();
    } else {
        toast('❌ Ошибка', 'error');
    }
}


async function rejectSg() {
    if (!CURRENT_SG) return;
    const comment = document.getElementById('sg-e-comment').value.trim();
    if (!comment) {
        toast('❌ Укажи причину отказа', 'error');
        return;
    }
    if (!confirm('Отклонить это предложение?')) return;

    const r = await api(`/api/admin/suggestions/${CURRENT_SG.id}/reject`, {
        method: 'POST',
        body: {comment},
    });

    if (r.success) {
        toast('❌ Отклонено', 'success');
        closeSgModal();
        loadSuggestions();
        updateSgBadge();
    }
}


async function updateSgBadge() {
    try {
        const r = await api('/api/admin/suggestions/count');
        const badge = document.getElementById('badge-suggestions');
        if (r.pending > 0) {
            badge.textContent = r.pending;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    } catch(e) {}
}

// ============================================
// TOAST
// ============================================
function toast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast ' + type;
    setTimeout(() => el.classList.add('hidden'), 3000);
    el.classList.remove('hidden');
}

// ============================================
// IMPORT
// ============================================
let SELECTED_ANIME = new Map(); // id → {title, cover}
let IMPORT_POLL_INTERVAL = null;


async function importSearch() {
    const query = document.getElementById('import-search-input').value.trim();
    if (!query) return;

    toast('🔍 Поиск...');
    try {
        const results = await api('/api/admin/import/search', {
            method: 'POST',
            body: { query },
        });
        renderImportResults(results);
    } catch(e) {
        toast('❌ Ошибка поиска', 'error');
    }
}


async function importLoadTop() {
    toast('🏆 Загрузка топа...');
    try {
        const results = await fetch('/api/admin/import/top?count=20', {
            headers: { 'X-Admin-Key': ADMIN_KEY }
        }).then(r => r.json());
        renderImportResults(results);
    } catch(e) {
        toast('❌ Ошибка', 'error');
    }
}


function renderImportResults(results) {
    const container = document.getElementById('import-results');
    if (!results || results.length === 0) {
        container.innerHTML = '<p style="color:var(--text2);text-align:center;padding:20px;grid-column:1/-1">Ничего не найдено</p>';
        return;
    }

    container.innerHTML = results.map(anime => {
        const isSelected = SELECTED_ANIME.has(anime.id);
        const isImported = anime.already_imported;

        // Форматы для отображения
        const formatIcon = {
            'TV': '📺',
            'MOVIE': '🎬',
            'OVA': '📀',
            'ONA': '💻',
            'SPECIAL': '⭐',
            'MUSIC': '🎵',
        }[anime.format] || '🎭';

        // Цвет метки популярности
        const charBadge = anime.char_count > 30 ? '🔥' :
                          anime.char_count > 15 ? '👥' :
                          anime.char_count > 5 ? '👤' : '';

        // Данные для click (безопасное кодирование)
        const dataAttr = encodeURIComponent(JSON.stringify({
            id: anime.id,
            title: anime.title_en,
            cover: anime.cover,
        }));

        return `
            <div class="import-anime-card ${isSelected ? 'selected' : ''} ${isImported ? 'imported' : ''}"
                 onclick="toggleAnimeFromData('${dataAttr}')">
                <div style="position:relative">
                    <img src="${anime.cover || ''}" class="import-anime-cover"
                         onerror="this.style.background='var(--bg3)';this.src=''">
                    ${isImported ? '<div class="imported-badge">✓ В БД</div>' : ''}
                    ${charBadge ? `<div class="char-count-badge">${charBadge} ${anime.char_count}</div>` : ''}
                </div>
                <div class="import-anime-info">
                    <div class="import-anime-title" title="${anime.title_en}">
                        ${anime.title_en}
                    </div>
                    <div class="import-anime-meta">
                        <span>${formatIcon} ${anime.year || '?'}</span>
                        <span>⭐ ${anime.score || '?'}</span>
                    </div>
                    ${anime.episodes ? `<div style="font-size:10px;color:var(--text2);margin-top:2px">🎬 ${anime.episodes} эп.</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}


function toggleAnimeFromData(dataAttr) {
    try {
        const data = JSON.parse(decodeURIComponent(dataAttr));
        toggleAnimeSelect(data.id, data.title, data.cover);
    } catch(e) {
        console.error('Parse error:', e);
    }
}


function toggleAnimeSelect(id, title, cover) {
    if (SELECTED_ANIME.has(id)) {
        SELECTED_ANIME.delete(id);
    } else {
        SELECTED_ANIME.set(id, { title, cover });
    }
    updateSelectedList();
    // Перерисуем результаты чтобы обновить .selected
    document.querySelectorAll('.import-anime-card').forEach(card => {
        card.classList.toggle('selected', card.querySelector('.import-anime-title').textContent === title);
    });
}


function updateSelectedList() {
    const container = document.getElementById('import-selected-list');
    const countEl = document.getElementById('import-count');
    const startBtn = document.getElementById('import-start-btn');

    countEl.textContent = `(${SELECTED_ANIME.size})`;
    startBtn.disabled = SELECTED_ANIME.size === 0;

    if (SELECTED_ANIME.size === 0) {
        container.innerHTML = '<p style="color:var(--text2);font-size:13px">Выбери аниме из результатов выше</p>';
        return;
    }

    container.innerHTML = Array.from(SELECTED_ANIME.entries()).map(([id, data]) => `
        <span class="selected-item" onclick="removeSelected(${id})">${data.title}</span>
    `).join('');
}


function removeSelected(id) {
    SELECTED_ANIME.delete(id);
    updateSelectedList();
    // Убираем выделение
    document.querySelectorAll('.import-anime-card.selected').forEach(card => {
        // Не самое элегантное но работает
        card.classList.remove('selected');
    });
    // Перерисовываем текущие результаты
    document.querySelectorAll('.import-anime-card').forEach(card => {
        const title = card.querySelector('.import-anime-title').textContent;
        let isSelected = false;
        SELECTED_ANIME.forEach(v => {
            if (v.title === title) isSelected = true;
        });
        card.classList.toggle('selected', isSelected);
    });
}


async function importStart() {
    if (SELECTED_ANIME.size === 0) return;

    if (!confirm(`Импортировать ${SELECTED_ANIME.size} аниме?`)) return;

    const data = {
        anime_ids: Array.from(SELECTED_ANIME.keys()),
        chars_limit: parseInt(document.getElementById('import-chars-limit').value),
        filter_gender: document.getElementById('import-gender').value || null,
        download_images: document.getElementById('import-images').value === 'true',
    };

    try {
        const r = await api('/api/admin/import/start', {
            method: 'POST',
            body: data,
        });

        if (r.success) {
            toast('🚀 Импорт запущен!', 'success');
            document.getElementById('import-progress').classList.remove('hidden');
            startPollingStatus();
        } else {
            toast('❌ Ошибка запуска', 'error');
        }
    } catch(e) {
        toast('❌ Ошибка: ' + e.message, 'error');
    }
}


function startPollingStatus() {
    // Пингуем каждые 2 секунды
    if (IMPORT_POLL_INTERVAL) clearInterval(IMPORT_POLL_INTERVAL);

    IMPORT_POLL_INTERVAL = setInterval(async () => {
        try {
            const status = await api('/api/admin/import/status');
            updateImportStatus(status);

            if (status.finished || !status.running) {
                clearInterval(IMPORT_POLL_INTERVAL);
                IMPORT_POLL_INTERVAL = null;

                if (status.finished) {
                    toast(`✅ Готово! Добавлено ${status.added}`, 'success');
                    // Обновляем статистику
                    setTimeout(updateStats, 1000);
                    setTimeout(loadChars, 1000);
                    // Очищаем выбор
                    SELECTED_ANIME.clear();
                    updateSelectedList();
                }
            }
        } catch(e) {
            console.error(e);
        }
    }, 2000);
}


function updateImportStatus(status) {
    const progress = status.total > 0 ? (status.progress / status.total * 100) : 0;

    document.getElementById('import-progress-fill').style.width = progress + '%';
    document.getElementById('import-progress-text').textContent =
        `${status.progress}/${status.total} • +${status.added} персонажей`;
    document.getElementById('import-current').textContent = status.current || '—';

    // Логи
    const logEl = document.getElementById('import-log');
    logEl.textContent = (status.log || []).join('\n');
    logEl.scrollTop = logEl.scrollHeight;
}


async function importStop() {
    await api('/api/admin/import/stop', { method: 'POST' });
    toast('⏹ Остановка...', 'warning');
}


async function loadImportStatus() {
    updateSelectedList();
    try {
        const status = await api('/api/admin/import/status');
        if (status.running || status.finished) {
            document.getElementById('import-progress').classList.remove('hidden');
            updateImportStatus(status);
            if (status.running) {
                startPollingStatus();
            }
        }
    } catch(e) {}
}

// ============================================
// START
// ============================================
init();