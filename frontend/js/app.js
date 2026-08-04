// frontend/js/app.js

// ============================================
// INIT
// ============================================
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();
tg.setHeaderColor('#0a0a1a');
tg.setBackgroundColor('#0a0a1a');

const API = '';  // Тот же домен
let USER_ID = tg.initDataUnsafe?.user?.id;

// Для тестирования без Telegram
if (!USER_ID) {
    USER_ID = 12345;
    console.warn('⚠️ Тестовый режим, USER_ID =', USER_ID);
}

let state = { coins: 0, cards: 0, pulls: 0, pity: 0 };

// ============================================
// LOAD USER
// ============================================
async function loadUser() {
    try {
        const r = await fetch(`${API}/api/user/${USER_ID}`);
        const d = await r.json();
        state.coins = d.coins;
        state.cards = d.total_cards;
        state.pulls = d.total_pulls;
        state.pity = d.pulls_since_pity;
        updateHeader();
    } catch(e) { console.error(e); }
}

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

function updateHeader() {
    const coinsEl = document.getElementById('coins');
    coinsEl.textContent = formatNum(state.coins);
    coinsEl.title = state.coins.toLocaleString('ru') + ' монет';  // тултип с полным числом

    document.getElementById('cards-count').textContent = formatNum(state.cards);
    document.getElementById('pity-count').textContent = state.pity;
}

// ============================================
// TABS
// ============================================
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('page-' + tab.dataset.tab).classList.add('active');

        if (tab.dataset.tab === 'collection') loadCollection();
        if (tab.dataset.tab === 'album') loadAlbum();
        if (tab.dataset.tab === 'profile') loadProfile();
        if (tab.dataset.tab === 'suggest') loadMySuggestions();

        haptic('selection');
    });
});

// ============================================
// CLAIM
// ============================================
document.getElementById('btn-claim').addEventListener('click', async () => {
    const btn = document.getElementById('btn-claim');
    btn.disabled = true;

    try {
        const r = await fetch(`${API}/api/claim/${USER_ID}`, {method:'POST'});
        const d = await r.json();
        if (d.success) {
            state.coins = d.coins;
            updateHeader();
            toast(d.message);
            haptic('success');
        } else {
            toast(d.message);
            haptic('warning');
        }
    } catch(e) { console.error(e); }

    setTimeout(() => btn.disabled = false, 1000);
});

// ============================================
// PULL x1
// ============================================
document.getElementById('btn-pull1').addEventListener('click', async () => {
    const btn = document.getElementById('btn-pull1');
    btn.disabled = true;

    // Анимация орба
    const orb = document.getElementById('gacha-orb');
    orb.classList.add('spinning');

    try {
        const r = await fetch(`${API}/api/pull/${USER_ID}`, {method:'POST'});
        const d = await r.json();

        if (!d.success) {
            toast(d.message);
            haptic('error');
            orb.classList.remove('spinning');
            btn.disabled = false;
            return;
        }

        state.coins = d.coins;
        if (d.card.is_new) state.cards++;
        state.pity = d.card.is_new ? state.pity : state.pity; // обновится при loadUser
        updateHeader();

        // Показываем карточку после анимации орба
        setTimeout(() => {
            orb.classList.remove('spinning');
            showCard(d.card);

            const stars = d.card.stars;
            if (stars >= 6) haptic('success');
            else if (stars >= 4) haptic('medium');
            else haptic('light');
        }, 600);

    } catch(e) { console.error(e); orb.classList.remove('spinning'); }

    setTimeout(() => btn.disabled = false, 1200);
});

// ============================================
// PULL x10
// ============================================
document.getElementById('btn-pull10').addEventListener('click', async () => {
    const btn = document.getElementById('btn-pull10');
    btn.disabled = true;

    const orb = document.getElementById('gacha-orb');
    orb.classList.add('spinning');

    try {
        const r = await fetch(`${API}/api/pull10/${USER_ID}`, {method:'POST'});
        const d = await r.json();

        if (!d.success) {
            toast(d.message);
            haptic('error');
            orb.classList.remove('spinning');
            btn.disabled = false;
            return;
        }

        state.coins = d.coins;
        state.cards += d.new_count;
        updateHeader();

        setTimeout(() => {
            orb.classList.remove('spinning');
            showMulti(d.cards);
            haptic('success');
        }, 600);

    } catch(e) { console.error(e); orb.classList.remove('spinning'); }

    setTimeout(() => btn.disabled = false, 1200);
});

// ============================================
// SHOW SINGLE CARD
// ============================================
function showCard(card) {
    const container = document.getElementById('card-result');
    const reveal = document.getElementById('card-reveal');

    const stars = '⭐'.repeat(card.stars);
    const imgContent = card.image_url
        ? `<img src="${card.image_url}" onerror="this.parentElement.innerHTML='${card.emoji}'">`
        : card.emoji;

    reveal.className = `card-reveal rarity-border-${card.rarity}`;
    reveal.innerHTML = `
        <div class="card-img-area">
            ${typeof imgContent === 'string' && imgContent.startsWith('<') ? imgContent : `<span>${imgContent}</span>`}
            ${card.is_new
                ? '<span class="new-badge">NEW!</span>'
                : `<span class="dupe-badge">+${card.duplicate_coins}💰</span>`
            }
        </div>
        <div class="card-body">
            <div class="card-name">${card.name}</div>
            <div class="card-anime">📺 ${card.anime}</div>
            <div class="card-stars">${stars}</div>
            <div class="card-rarity-label" style="color:${card.color}">${card.rarity_name}</div>
            <div class="card-stats">
                <span>⚔️${card.power}</span>
                <span>🛡${card.defense}</span>
                <span>💨${card.speed}</span>
            </div>
        </div>
    `;

    container.classList.remove('hidden');
}

document.getElementById('close-result').addEventListener('click', () => {
    document.getElementById('card-result').classList.add('hidden');
    loadUser();  // Обновляем данные
});

// ============================================
// SHOW MULTI
// ============================================
function showMulti(cards) {
    const container = document.getElementById('multi-result');
    const grid = document.getElementById('multi-grid');

    grid.innerHTML = cards.map(card => `
        <div class="mini-card rarity-border-${card.rarity}" style="border-width:2px">
            <div class="mini-card-img">
                ${card.image_url
                    ? `<img src="${card.image_url}" onerror="this.parentElement.innerHTML='${card.emoji}'">`
                    : card.emoji}
            </div>
            <div class="mini-card-name">${card.name}</div>
            <div class="mini-card-rarity">${'⭐'.repeat(card.stars)}</div>
            ${card.is_new ? '<span class="mini-new">NEW</span>' : ''}
        </div>
    `).join('');

    container.classList.remove('hidden');
}

document.getElementById('close-multi').addEventListener('click', () => {
    document.getElementById('multi-result').classList.add('hidden');
    loadUser();
});

// ============================================
// COLLECTION
// ============================================
async function loadCollection(rarity = '') {
    try {
        let url = `${API}/api/collection/${USER_ID}?per_page=50`;
        if (rarity) url += `&rarity=${rarity}`;
        const r = await fetch(url);
        const d = await r.json();

        document.getElementById('progress-fill').style.width = d.completion + '%';
        document.getElementById('progress-text').textContent =
            `${d.total_collected}/${d.total_characters} (${d.completion}%)`;

        const grid = document.getElementById('collection-grid');
        if (d.cards.length === 0) {
            grid.innerHTML = '<p style="text-align:center;color:var(--text2);grid-column:1/-1;padding:40px">Пока пусто 😢</p>';
            return;
        }

        grid.innerHTML = d.cards.map(card => `
            <div class="grid-card r-${card.rarity}" onclick="toggleFav(${card.character_id})">
                <div class="grid-card-img">
                    ${card.image_url
                        ? `<img src="${card.image_url}" onerror="this.parentElement.innerHTML='${card.rarity_info.emoji}'">`
                        : card.rarity_info.emoji}
                </div>
                ${card.count > 1 ? `<span class="grid-card-count">x${card.count}</span>` : ''}
                ${card.is_favorite ? '<span class="grid-card-fav">⭐</span>' : ''}
                <div class="grid-card-info">
                    <div class="grid-card-name">${card.name}</div>
                    <div class="grid-card-sub">
                        <span>${card.rarity_info.emoji} ${'⭐'.repeat(card.rarity_info.stars)}</span>
                    </div>
                </div>
            </div>
        `).join('');
    } catch(e) { console.error(e); }
}

async function toggleFav(charId) {
    try {
        await fetch(`${API}/api/favorite/${USER_ID}/${charId}`, {method: 'POST'});
        haptic('success');
        toast('⭐ Карточка выбрана для профиля!');
        loadCollection();
    } catch(e) { console.error(e); }
}

document.getElementById('filter-rarity').addEventListener('change', e => {
    loadCollection(e.target.value);
});

// ============================================
// ALBUM
// ============================================
async function loadAlbum() {
    try {
        const [allR, collR] = await Promise.all([
            fetch(`${API}/api/characters?per_page=200`),
            fetch(`${API}/api/collection/${USER_ID}?per_page=999`),
        ]);
        const allD = await allR.json();
        const collD = await collR.json();

        const owned = new Set(collD.cards.map(c => c.character_id));

        document.getElementById('album-grid').innerHTML = allD.characters.map(char => `
            <div class="grid-card r-${char.rarity} ${owned.has(char.id) ? '' : 'not-owned'}">
                <div class="grid-card-img" style="font-size:20px">
                    ${char.rarity_info.emoji}
                </div>
                <div class="grid-card-info">
                    <div class="grid-card-name" style="font-size:9px">
                        ${owned.has(char.id) ? char.name : '???'}
                    </div>
                </div>
            </div>
        `).join('');

    } catch(e) { console.error(e); }
}

// ============================================
// PROFILE
// ============================================
async function loadProfile() {
    await loadUser();
    const name = tg.initDataUnsafe?.user?.first_name || 'Игрок';
    document.getElementById('profile-name').textContent = name;
    document.getElementById('p-coins').textContent = formatNum(state.coins);
    document.getElementById('p-cards').textContent = state.cards;
    document.getElementById('p-pulls').textContent = state.pulls;
    document.getElementById('p-pity').textContent = `${state.pity}/90`;

    // Загружаем фон профиля
    try {
        const r = await fetch(`${API}/api/user/${USER_ID}`);
        const d = await r.json();

        const bg = document.getElementById('profile-bg');
        const fav = document.getElementById('profile-fav');

        if (d.profile_card && d.profile_card.image_url) {
            bg.style.backgroundImage = `url('${d.profile_card.image_url}')`;
            fav.textContent = `⭐ ${d.profile_card.name} • ${d.profile_card.anime}`;
        } else {
            bg.style.backgroundImage = '';
            fav.textContent = '💡 Выбери избранную карточку в коллекции';
        }
    } catch(e) { console.error(e); }
}

// ============================================
// TOAST
// ============================================
function toast(msg) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 2500);
}

// ============================================
// HAPTIC
// ============================================
function haptic(type) {
    try {
        if (type === 'selection') tg.HapticFeedback.selectionChanged();
        else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
        else if (type === 'warning') tg.HapticFeedback.notificationOccurred('warning');
        else if (type === 'error') tg.HapticFeedback.notificationOccurred('error');
        else if (type === 'light') tg.HapticFeedback.impactOccurred('light');
        else if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
    } catch(e) {}
}

// ============================================
// SUGGEST
// ============================================
document.getElementById('sg-submit').addEventListener('click', async () => {
    const btn = document.getElementById('sg-submit');
    btn.disabled = true;

    const data = {
        name_en: document.getElementById('sg-name-en').value.trim(),
        name_ru: document.getElementById('sg-name-ru').value.trim(),
        name_jp: document.getElementById('sg-name-jp').value.trim(),
        anime_title: document.getElementById('sg-anime').value.trim(),
        rarity_suggested: document.getElementById('sg-rarity').value,
        description: document.getElementById('sg-desc').value.trim(),
        power: parseInt(document.getElementById('sg-power').value) || 50,
        defense: parseInt(document.getElementById('sg-defense').value) || 50,
        speed: parseInt(document.getElementById('sg-speed').value) || 50,
        image_url: document.getElementById('sg-image-url-hidden').value || null,  // ← НОВОЕ
    };

    if (!data.name_en || !data.anime_title) {
        toast('❌ Заполни имя и аниме');
        haptic('error');
        btn.disabled = false;
        return;
    }

    try {
        const r = await fetch(`${API}/api/suggest/${USER_ID}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data),
        });
        const d = await r.json();

        if (d.success) {
            toast('✅ Предложение отправлено!');
            haptic('success');
            ['sg-name-en','sg-name-ru','sg-name-jp','sg-anime','sg-desc'].forEach(id => {
                document.getElementById(id).value = '';
            });
            document.getElementById('sg-power').value = 50;
            document.getElementById('sg-defense').value = 50;
            document.getElementById('sg-speed').value = 50;
            clearSgImage();  // ← сбрасываем картинку
            loadMySuggestions();
        } else {
            toast('❌ ' + (d.detail || 'Ошибка'));
            haptic('error');
        }
    } catch(e) {
        toast('❌ Ошибка сети');
        console.error(e);
    }

    btn.disabled = false;
});


async function loadMySuggestions() {
    try {
        const r = await fetch(`${API}/api/suggestions/${USER_ID}`);
        const items = await r.json();

        const list = document.getElementById('sg-list');
        if (items.length === 0) {
            list.innerHTML = '<p style="color:var(--text2);text-align:center;padding:16px">Пусто</p>';
            return;
        }

        const statusText = {
            pending: '⏳ На проверке',
            approved: '✅ Одобрено',
            rejected: '❌ Отклонено',
        };

        list.innerHTML = items.map(s => `
            <div class="sg-item ${s.status}">
                <div class="sg-item-with-img">
                    ${s.image_url
                        ? `<img src="${s.image_url}" class="sg-item-thumb">`
                        : '<div class="sg-item-thumb" style="display:flex;align-items:center;justify-content:center">🎴</div>'
                    }
                    <div class="sg-item-body">
                        <div class="sg-item-header">
                            <span class="sg-item-name">${s.name_ru || s.name_en}</span>
                            <span class="sg-status ${s.status}">${statusText[s.status]}</span>
                        </div>
                        <div class="sg-item-anime">📺 ${s.anime_title}</div>
                        ${s.admin_comment
                            ? `<div class="sg-item-comment">💬 ${s.admin_comment}</div>`
                            : ''}
                    </div>
                </div>
            </div>
        `).join('');
    } catch(e) { console.error(e); }
}

// Загрузка картинки для предложения
document.getElementById('sg-image-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Проверка размера
    if (file.size > 5 * 1024 * 1024) {
        toast('❌ Файл больше 5 МБ');
        haptic('error');
        e.target.value = '';
        return;
    }

    const hint = document.getElementById('sg-image-hint');
    hint.textContent = '⏳ Загрузка...';

    const fd = new FormData();
    fd.append('file', file);

    try {
        const r = await fetch(`${API}/api/suggest/upload/${USER_ID}`, {
            method: 'POST',
            body: fd,
        });
        const d = await r.json();

        if (d.url) {
            document.getElementById('sg-image-url-hidden').value = d.url;
            const preview = document.getElementById('sg-preview-img');
            preview.src = d.url;
            preview.classList.remove('hidden');
            document.querySelector('.sg-clear-btn').classList.remove('hidden');
            hint.textContent = '✅ Загружено';
            haptic('success');
        } else {
            hint.textContent = '❌ ' + (d.detail || 'Ошибка');
            haptic('error');
        }
    } catch(err) {
        hint.textContent = '❌ Ошибка сети';
        console.error(err);
    }
});


function clearSgImage() {
    document.getElementById('sg-image-input').value = '';
    document.getElementById('sg-image-url-hidden').value = '';
    document.getElementById('sg-preview-img').classList.add('hidden');
    document.querySelector('.sg-clear-btn').classList.add('hidden');
    document.getElementById('sg-image-hint').textContent = 'Формат: JPG, PNG, WEBP';
}

// ============================================
// START
// ============================================
loadUser();