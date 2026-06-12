const STORAGE_KEY = 'kerajaan_auto_state_v3';
const PENDING_KEY = 'kerajaan_auto_pending_sync';
const ROUND_MS = 10000;
const RESULT_MS = 2000;
const URUTAN_RODA = [1, 2, 3, 6, 5, 4];
const PROJECTS = {
    1: 'Tambang',
    2: 'Kapal',
    3: 'Pasar',
    4: 'Benteng',
    5: 'Gua Kristal',
    6: 'Istana Emas',
};
const MULTIPLIER = {1: 2, 2: 4, 3: 6, 4: 8, 5: 10, 6: 12};
const SHOP_ITEMS = [
    ['🏠', 15000000], ['🌋', 20000000], ['🏬', 300000], ['🏢', 8000000],
    ['🏭', 1000000], ['🏪', 50000000], ['🚗', 80000000], ['🏎️', 900000],
    ['🚲', 20000000], ['🛵', 15000000], ['🏍️', 80000000], ['🚄', 3000000],
    ['🚅', 2500000], ['🚂', 50000000], ['✈️', 900000], ['🚁', 160000],
    ['🚀', 80000000], ['🚤', 8000000], ['🛳️', 13000000], ['👑', 1000000],
];

let state = null;
let pemainTerpilih = -1;
let firebaseApi = null;
let syncTimer = null;
let rotorIndex = 0;
let rotorLastMove = 0;
let rotorActiveProject = null;

const app = document.getElementById('app');
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('overlay');
const syncStatus = document.getElementById('syncStatus');

init();

async function init() {
    state = await loadInitialState();
    normalizeState(state);
    rotorIndex = Math.max(0, URUTAN_RODA.indexOf(state.posisiTerakhir || 1));
    bindChromeEvents();
    await initFirebase();
    await mergeRemoteIfNewer();
    startGameClock();
    startRotorAnimation();
    render();
    queueSync('Aplikasi siap');
}

async function loadInitialState() {
    const local = loadLocalState();
    if (local) return local;

    try {
        const response = await fetch('/seed-data.json', {cache: 'no-store'});
        if (response.ok) {
            const seeded = await response.json();
            return fromSeedData(seeded);
        }
    } catch (_) {
        // Tetap bisa mulai game baru saat offline total.
    }

    return newState();
}

function newState() {
    return {
        ronde: 1,
        bank: 1000000,
        history: [],
        petualang: [],
        hasilTerakhir: 0,
        hasilNext: randomHasil(),
        posisiTerakhir: 1,
        phase: 'running',
        phaseEndsAt: Date.now() + ROUND_MS,
        pemenangText: '',
        pesan: 'Tambah 6 pemain dulu',
        updatedAt: Date.now(),
    };
}

function fromSeedData(data) {
    return {
        ronde: data.ronde || 1,
        bank: data.bank || 1000000,
        history: data.history || [],
        petualang: (data.petualang || []).map(normalizePlayer),
        hasilTerakhir: (data.history || []).at(-1) || 0,
        hasilNext: randomHasil(),
        posisiTerakhir: (data.history || []).at(-1) || 1,
        phase: 'running',
        phaseEndsAt: Date.now() + ROUND_MS,
        pemenangText: '',
        pesan: `Data lama dimuat! Ronde ${data.ronde || 1}`,
        updatedAt: Date.now(),
    };
}

function normalizeState(value) {
    value.petualang = (value.petualang || []).map(normalizePlayer);
    value.history = value.history || [];
    value.hasilTerakhir = value.hasilTerakhir || value.history.at(-1) || 0;
    value.hasilNext = value.hasilNext || randomHasil();
    value.posisiTerakhir = value.posisiTerakhir || value.hasilTerakhir || 1;
    value.phase = value.phase || 'running';
    value.phaseEndsAt = value.phaseEndsAt || Date.now() + ROUND_MS;
    value.pemenangText = value.pemenangText || '';
    value.pesan = value.pesan || 'Game siap';
    value.updatedAt = value.updatedAt || Date.now();
}

function normalizePlayer(player) {
    return {
        nama: player.nama || '',
        poin: Number(player.poin || 0),
        hutang: Number(player.hutang || 0),
        rupiah: Number(player.rupiah || 0),
        investasi: normalizeNumberMap(player.investasi || {}),
        investasiNext: normalizeNumberMap(player.investasiNext || player.investasi_next || {}),
        aset: player.aset || {},
        gelar: player.gelar || '',
    };
}

function normalizeNumberMap(value) {
    const output = {};
    for (const [key, item] of Object.entries(value)) {
        output[Number(key)] = Number(item || 0);
    }
    return output;
}

function bindChromeEvents() {
    document.getElementById('menuBtn').addEventListener('click', toggleMenu);
    document.getElementById('saveBtn').addEventListener('click', () => {
        saveLocal('Game disimpan');
        queueSync('Menunggu sinkron Firebase');
        closeMenu();
    });
    overlay.addEventListener('click', closeMenu);
    sidebar.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenu));
    window.addEventListener('popstate', render);
    window.addEventListener('online', () => queueSync('Online, sinkronisasi...'));
    window.addEventListener('offline', () => setSyncStatus('Offline, data aman di perangkat'));
}

function toggleMenu() {
    sidebar.classList.toggle('show');
    overlay.classList.toggle('show');
}

function closeMenu() {
    sidebar.classList.remove('show');
    overlay.classList.remove('show');
}

function startGameClock() {
    setInterval(() => {
        const before = state.phase;
        tickGame();
        updateTimerOnly();
        if (before !== state.phase) render();
    }, 100);
}

function tickGame() {
    const now = Date.now();
    while (now >= state.phaseEndsAt) {
        if (state.phase === 'running') {
            finishRound();
        } else {
            state.phase = 'running';
            state.phaseEndsAt += ROUND_MS;
            state.pesan = `Ronde ${state.ronde} berjalan`;
            markDirty();
        }
    }
}

function finishRound() {
    const hasil = state.hasilNext;
    state.hasilTerakhir = hasil;
    state.posisiTerakhir = hasil;
    rotorIndex = Math.max(0, URUTAN_RODA.indexOf(hasil));
    updateRunningProject(hasil);
    state.hasilNext = randomHasil();
    const pemenang = [];

    state.petualang.forEach((player) => {
        const inv = Number(player.investasi[hasil] || 0);
        if (inv > 0) {
            const profit = inv * MULTIPLIER[hasil];
            player.poin += profit;
            pemenang.push(`${player.nama} +${formatNumber(profit)} poin`);
        }
        player.investasi = {...player.investasiNext};
        player.investasiNext = {};
    });

    state.ronde += 1;
    state.history.push(hasil);
    state.bank += 1000 * hasil;
    state.pemenangText = pemenang.length ? pemenang.join(' | ') : 'Ga ada yg menang';
    state.phase = 'result';
    state.phaseEndsAt += RESULT_MS;
    state.pesan = `Hasil keluar: ${PROJECTS[hasil]}`;
    markDirty();
}

function startRotorAnimation() {
    const animate = (now) => {
        if (!rotorLastMove) rotorLastMove = now;

        if (state.phase === 'result') {
            rotorIndex = Math.max(0, URUTAN_RODA.indexOf(state.hasilTerakhir || state.posisiTerakhir || 1));
            updateRunningProject(URUTAN_RODA[rotorIndex]);
            rotorLastMove = now;
            requestAnimationFrame(animate);
            return;
        }

        const remaining = getRemainingMs();
        const delay = remaining > 3000 ? 110 : Math.max(150, 220 + (3000 - remaining) / 3000 * 380);

        if (now - rotorLastMove >= delay) {
            rotorLastMove = now;
            rotorIndex = (rotorIndex + 1) % URUTAN_RODA.length;
            updateRunningProject(URUTAN_RODA[rotorIndex]);
        }

        requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
}

function updateRunningProject(no) {
    if (rotorActiveProject === no) {
        document.getElementById(`p${no}`)?.classList.add('running');
        return;
    }
    if (rotorActiveProject) {
        document.getElementById(`p${rotorActiveProject}`)?.classList.remove('running');
    }
    rotorActiveProject = no;
    document.getElementById(`p${no}`)?.classList.add('running');
}

function render() {
    tickGame();
    const menu = new URLSearchParams(location.search).get('menu') || '';
    if (!menu) renderHome();
    else if (menu === 'history') renderHistory();
    else renderForm(menu);
    updateTimerOnly();
    updateRunningProject(rotorActiveProject || URUTAN_RODA[rotorIndex]);
}

function renderHome() {
    app.className = 'box';
    app.innerHTML = `
        <h1>🏰 KERAJAAN AUTO</h1>
        <div class="info">Ronde: <b>${state.ronde}</b> | Bank: <b>Rp${formatNumber(state.bank)}</b></div>
        <div class="pesan" id="pesanBox">${escapeHtml(state.pesan)}</div>
        <div class="offline-note">Mode offline aktif: game tetap jalan tanpa internet. Saat online, data akan disinkronkan ke Firebase Firestore.</div>
        <div class="timer" id="timerBox"></div>
        <h3 class="section-title">Pilih Pemain → Isi Investasi → Klik Kotak Proyek</h3>
        <table>
            <thead><tr><th>No</th><th>Nama</th><th>Poin</th><th>Hutang</th><th>Rp</th><th>Aset</th></tr></thead>
            <tbody>${renderRows()}</tbody>
        </table>
        <h3 class="section-title">Proyek</h3>
        <div class="grid3x2">${renderProjects()}</div>
    `;

    app.querySelectorAll('[data-player]').forEach((row) => {
        row.addEventListener('click', () => pilihPemain(Number(row.dataset.player)));
    });
    app.querySelectorAll('[data-project]').forEach((card) => {
        card.addEventListener('click', () => submitInvest(Number(card.dataset.project)));
    });
    if (pemainTerpilih >= state.petualang.length) pemainTerpilih = -1;
    refreshInvestmentInputs();
}

function renderRows() {
    if (!state.petualang.length) {
        return '<tr><td colspan="6">Belum ada pemain. Tambah pemain dulu dari menu.</td></tr>';
    }
    return state.petualang.map((p, idx) => {
        const aset = Object.entries(p.aset).map(([k, v]) => `${escapeHtml(k)}x${v}`).join(' ') || '-';
        const hutang = p.hutang > 0 ? `Rp${formatNumber(p.hutang)}` : '-';
        const selected = idx === pemainTerpilih ? ' class="selected"' : '';
        return `<tr data-player="${idx}"${selected}><td>${idx + 1}</td><td>${escapeHtml(`${p.gelar ? `${p.gelar} ` : ''}${p.nama}`)}</td><td>${formatNumber(p.poin)}</td><td>${hutang}</td><td>Rp${formatNumber(p.rupiah)}</td><td>${aset}</td></tr>`;
    }).join('');
}

function renderProjects() {
    return [1, 2, 3, 4, 5, 6].map((no) => {
        const inputs = state.petualang.map((p, idx) => {
            const current = p.investasi[no] || 0;
            return `<input data-invest-player="${idx}" data-invest-project="${no}" type="number" value="${current}" min="0" style="display:none">`;
        }).join('');
        const active = state.phase === 'result' && state.hasilTerakhir === no ? ' active' : '';
        return `<div class="proj${active}" id="p${no}" data-project="${no}"><div class="no">${no}</div><div class="nama">${PROJECTS[no]}</div>${inputs}</div>`;
    }).join('');
}

function pilihPemain(idx) {
    pemainTerpilih = idx;
    renderHome();
}

function refreshInvestmentInputs() {
    app.querySelectorAll('[data-invest-player]').forEach((input) => {
        input.style.display = Number(input.dataset.investPlayer) === pemainTerpilih ? 'inline-block' : 'none';
    });
}

function submitInvest(no) {
    if (pemainTerpilih < 0) {
        alert('Pilih pemain dulu!');
        return;
    }
    const player = state.petualang[pemainTerpilih];
    const input = app.querySelector(`[data-invest-player="${pemainTerpilih}"][data-invest-project="${no}"]`);
    const inv = Math.max(0, Number(input?.value || 0));
    const target = getRemainingMs() <= 500 ? player.investasiNext : player.investasi;
    const rondeTarget = getRemainingMs() <= 500 ? state.ronde + 1 : state.ronde;
    const saldo = player.poin + Number(target[no] || 0);

    if (inv <= saldo) {
        player.poin += Number(target[no] || 0);
        player.poin -= inv;
        target[no] = inv;
        state.pesan = `${player.nama} invest ${formatNumber(inv)} ke ${PROJECTS[no]} [Ronde ${rondeTarget}]`;
        markDirty();
        renderHome();
    } else {
        state.pesan = 'Poin ga cukup';
        renderHome();
    }
}

function renderForm(menu) {
    const titles = {
        pinjam: '2. PINJAM BANK',
        donatur: '3. DONATUR / KAS',
        topup: '4. TOPUP JUAL BELI',
        shop: '5. SHOP',
        tambah: '8. TAMBAH PEMAIN',
        edit: '9. EDIT/HAPUS PEMAIN',
    };
    app.className = 'box';
    app.innerHTML = `<div class="form-box"><h2>${titles[menu] || 'MENU'}</h2><div class="pesan">${escapeHtml(state.pesan)}</div>${formBody(menu)}<a href="/"><button class="back">← KEMBALI</button></a></div>`;
    const form = app.querySelector('form');
    if (form) form.addEventListener('submit', (event) => handleFormSubmit(event, menu));
}

function formBody(menu) {
    const options = state.petualang.map((p, idx) => `<option value="${idx}">${escapeHtml(p.nama)}</option>`).join('');
    if (menu === 'pinjam') return `<form><select name="idx">${options}</select><input type="number" name="jumlah" placeholder="Jumlah pinjam"><button>Pinjam</button></form>`;
    if (menu === 'donatur') return `<form><select name="idx">${options}</select><select name="pilih"><option value="1">Donasi ke pemain</option><option value="2">Tambah kas bank</option></select><input type="number" name="jumlah" placeholder="Jumlah"><button>Proses</button></form>`;
    if (menu === 'topup') return `<form><select name="idx">${options}</select><select name="pilih"><option value="1">Beli Poin 1:1500</option><option value="2">Jual Poin 1000:1</option></select><input type="number" name="jumlah" value="1500"><button>Proses</button></form>`;
    if (menu === 'shop') return `<form><select name="idx">${options}</select><select name="noBarang">${SHOP_ITEMS.map((item, idx) => `<option value="${idx}">${item[0]} Rp${formatRupiah(item[1])}</option>`).join('')}</select><button>Beli</button></form>`;
    if (menu === 'tambah') return `<form><input name="nama" placeholder="Nama baru max 15 huruf" maxlength="15"><button>Tambah</button></form>`;
    if (menu === 'edit') return `<form><select name="idx">${options}</select><select name="pilih"><option value="1">Edit Nama</option><option value="2">Hapus</option></select><input name="namaBaru" placeholder="Nama baru"><button>Proses</button></form>`;
    return '<p>Menu tidak ditemukan.</p>';
}

function handleFormSubmit(event, menu) {
    event.preventDefault();
    const form = new FormData(event.target);
    const idx = Number(form.get('idx'));
    const jumlah = Number(form.get('jumlah') || 0);
    const player = state.petualang[idx];

    if (menu === 'pinjam' && player) {
        if (jumlah > 0 && jumlah <= state.bank) {
            player.poin += jumlah;
            player.hutang += jumlah;
            state.bank -= jumlah;
            state.pesan = `Pinjaman ${formatNumber(jumlah)} ke ${player.nama}`;
            markDirty();
        } else state.pesan = 'Kas bank ga cukup';
    } else if (menu === 'donatur') {
        const pilih = form.get('pilih');
        if (pilih === '1' && player && jumlah > 0 && jumlah <= state.bank) {
            player.poin += jumlah;
            state.bank -= jumlah;
            state.pesan = `Donasi ${formatNumber(jumlah)} ke ${player.nama}`;
            markDirty();
        } else if (pilih === '2' && jumlah > 0) {
            state.bank += jumlah;
            state.pesan = `Kas +${formatNumber(jumlah)}`;
            markDirty();
        }
    } else if (menu === 'topup' && player) {
        const pilih = form.get('pilih');
        if (pilih === '1' && jumlah >= 1500 && player.rupiah >= jumlah) {
            const poinDapat = Math.floor(jumlah / 1500);
            player.rupiah -= jumlah;
            player.poin += poinDapat;
            state.bank += jumlah - poinDapat * 1000;
            state.pesan = `Beli ${formatNumber(poinDapat)} poin`;
            markDirty();
        } else if (pilih === '2' && jumlah >= 1 && player.poin >= jumlah) {
            const rpDapat = jumlah * 1000;
            player.poin -= jumlah;
            player.rupiah += rpDapat;
            state.bank -= rpDapat;
            state.pesan = `Jual ${formatNumber(jumlah)} poin`;
            markDirty();
        }
    } else if (menu === 'shop' && player) {
        const [item, harga] = SHOP_ITEMS[Number(form.get('noBarang'))];
        if (player.rupiah >= harga) {
            player.rupiah -= harga;
            player.aset[item] = (player.aset[item] || 0) + 1;
            if (item === '👑') player.gelar = '👑';
            state.pesan = `${player.nama} beli ${item}`;
            markDirty();
        } else state.pesan = 'Rupiah ga cukup';
    } else if (menu === 'tambah') {
        const nama = String(form.get('nama') || '').trim();
        if (nama && state.petualang.length < 6) {
            state.petualang.push(normalizePlayer({nama, poin: 1000}));
            state.pesan = `${nama} masuk!`;
            markDirty();
        }
    } else if (menu === 'edit' && player) {
        const pilih = form.get('pilih');
        const namaBaru = String(form.get('namaBaru') || '').trim();
        if (pilih === '1' && namaBaru) {
            player.nama = namaBaru;
            state.pesan = `Ganti nama jadi ${namaBaru}`;
            markDirty();
        } else if (pilih === '2') {
            const namaHapus = player.nama;
            state.petualang.splice(idx, 1);
            state.pesan = `${namaHapus} dihapus`;
            markDirty();
        }
    }

    renderForm(menu);
}

function renderHistory() {
    app.className = 'box';
    const history = state.history.length
        ? state.history.slice(-50).map((no, idx) => `${idx + 1}. ${PROJECTS[no]}<br>`).join('')
        : 'Belum ada ronde';
    app.innerHTML = `<div class="form-box"><h2>6. HISTORY</h2><div class="history-box">${history}</div><a href="/"><button class="back">← KEMBALI</button></a></div>`;
}

function updateTimerOnly() {
    const timer = document.getElementById('timerBox');
    if (!timer) return;
    const seconds = Math.max(0, getRemainingMs() / 1000);
    if (state.phase === 'result') {
        timer.innerHTML = `<div class="result-name">Hasil: ${PROJECTS[state.hasilTerakhir]}</div><div class="winner-text">${escapeHtml(state.pemenangText)}</div><div class="status-text">Hasil keluar!</div>`;
    } else {
        timer.innerHTML = `<div class="countdown">${seconds.toFixed(1)}s</div><div class="status-text">Investasi jalan - ${seconds.toFixed(1)}s</div>`;
    }
}

function getRemainingMs() {
    return Math.max(0, state.phaseEndsAt - Date.now());
}

function markDirty() {
    state.updatedAt = Date.now();
    saveLocal();
    localStorage.setItem(PENDING_KEY, '1');
    queueSync('Perubahan tersimpan offline');
}

function saveLocal(message) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    if (message) setSyncStatus(message);
}

function loadLocalState() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

async function initFirebase() {
    const config = window.KERAJAAN_FIREBASE_CONFIG || {};
    if (!config.projectId || !config.apiKey) {
        setSyncStatus('Firebase belum dikonfigurasi, pakai offline lokal');
        return;
    }

    try {
        const [{initializeApp}, firestore] = await Promise.all([
            import('https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js'),
            import('https://www.gstatic.com/firebasejs/10.12.5/firebase-firestore.js'),
        ]);
        const firebaseApp = initializeApp(config);
        const db = firestore.getFirestore(firebaseApp);
        firebaseApi = {
            db,
            doc: firestore.doc,
            getDoc: firestore.getDoc,
            setDoc: firestore.setDoc,
            enableIndexedDbPersistence: firestore.enableIndexedDbPersistence,
        };
        try {
            await firebaseApi.enableIndexedDbPersistence(db);
        } catch (_) {
            // LocalStorage tetap menjadi mode offline utama jika persistence Firestore tidak aktif.
        }
        setSyncStatus('Firebase aktif');
    } catch (_) {
        setSyncStatus('Firebase belum bisa dimuat, mode offline aktif');
    }
}

async function mergeRemoteIfNewer() {
    if (!firebaseApi || !navigator.onLine) return;
    try {
        const ref = firebaseApi.doc(firebaseApi.db, 'kerajaanGames', window.KERAJAAN_FIREBASE_DOC_ID || 'default');
        const snap = await firebaseApi.getDoc(ref);
        if (snap.exists()) {
            const remote = snap.data();
            if (remote?.state?.updatedAt && remote.state.updatedAt > state.updatedAt) {
                state = remote.state;
                normalizeState(state);
                saveLocal('Data Firebase dimuat');
            }
        }
    } catch (_) {
        setSyncStatus('Gagal baca Firebase, lanjut offline');
    }
}

function queueSync(message) {
    if (message) setSyncStatus(message);
    clearTimeout(syncTimer);
    syncTimer = setTimeout(syncNow, 500);
}

async function syncNow() {
    if (!firebaseApi) return;
    if (!navigator.onLine) {
        setSyncStatus('Offline, sinkron ditunda');
        return;
    }
    try {
        const ref = firebaseApi.doc(firebaseApi.db, 'kerajaanGames', window.KERAJAAN_FIREBASE_DOC_ID || 'default');
        await firebaseApi.setDoc(ref, {state, updatedAt: Date.now()}, {merge: true});
        localStorage.removeItem(PENDING_KEY);
        setSyncStatus('Tersimpan ke Firebase');
    } catch (_) {
        localStorage.setItem(PENDING_KEY, '1');
        setSyncStatus('Gagal sync, data tetap aman offline');
    }
}

function setSyncStatus(text) {
    if (syncStatus) syncStatus.textContent = text;
}

function randomHasil() {
    const choices = [1, 2, 3, 4, 5, 6];
    const weights = [23, 23, 18, 18, 10, 10];
    const total = weights.reduce((a, b) => a + b, 0);
    let pick = Math.random() * total;
    for (let i = 0; i < choices.length; i++) {
        pick -= weights[i];
        if (pick <= 0) return choices[i];
    }
    return choices.at(-1);
}

function formatNumber(n) {
    return Number(n || 0).toLocaleString('id-ID');
}

function formatRupiah(n) {
    if (n >= 1000000000) return `${(n / 1000000000).toFixed(1)}M`;
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}jt`;
    if (n >= 1000) return `${(n / 1000).toFixed(0)}rb`;
    return formatNumber(n);
}

function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;',
    }[char]));
}

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js').catch(() => {});
    });
}
