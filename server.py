import http.server
import socketserver
import random
import base64
import hashlib
import os
import json
import shutil
import time
from threading import Thread
from urllib.parse import parse_qs, urlparse

PORT = 9000
FILE_SAVE = 'data_kerajaan.json'
FILE_BACKUP = 'data_kerajaan.bak'
SECRET_KEY = "kerajaan_v96_chache"
URUTAN_RODA = [1,2,3,6,5,4]

class Petualang:
    def __init__(self, nama, poin=1000, hutang=0, rupiah=0):
        self.nama = nama; self.poin = poin; self.hutang = hutang; self.rupiah = rupiah
        self.investasi = {}; self.investasi_next = {}; self.aset = {}; self.gelar = ""
    def to_dict(self):
        return {'nama': self.nama, 'poin': self.poin, 'hutang': self.hutang,
                'rupiah': self.rupiah, 'investasi': self.investasi, 'aset': self.aset, 'gelar': self.gelar}
    @classmethod
    def from_dict(cls, data):
        p = cls(data['nama'], data['poin'], data['hutang'], data.get('rupiah', 0))
        p.investasi = data.get('investasi', {}); p.aset = data.get('aset', {}); p.gelar = data.get('gelar', "")
        return p

def nama_proyek(no):
    return {1:"Tambang", 2:"Kapal", 3:"Pasar", 4:"Benteng", 5:"Gua Kristal", 6:"Istana Emas"}[no]

MULTIPLIER = {1:2,2:4,3:6,4:8,5:10,6:12}

def simpan_data(petualang_list, bank, ronde, history):
    data = {'ronde': ronde, 'bank': bank, 'history': history, 'petualang': [p.to_dict() for p in petualang_list]}
    json_str = json.dumps(data, separators=(',', ':'))
    checksum = hashlib.md5((json_str + SECRET_KEY).encode()).hexdigest()
    data_enkripsi = {'data': base64.b64encode(json_str.encode()).decode(), 'cek': checksum}
    with open(FILE_SAVE, 'w') as f: json.dump(data_enkripsi, f)
    shutil.copy2(FILE_SAVE, FILE_BACKUP)

def muat_data():
    def baca_file(nama_file):
        with open(nama_file, 'r') as f: d=json.load(f)
        js=base64.b64decode(d['data']).decode()
        if hashlib.md5((js + SECRET_KEY).encode()).hexdigest()!=d['cek']: return None
        return json.loads(js)
    data=None
    if os.path.exists(FILE_SAVE):
        try: data=baca_file(FILE_SAVE)
        except:
            try:
                with open(FILE_SAVE,'r') as f: data_lama=json.load(f)
                p=[Petualang.from_dict(x) for x in data_lama['petualang']]
                simpan_data(p,data_lama['bank'],data_lama['ronde'],data_lama.get('history',[]))
                data=data_lama
            except: pass
    if data is None and os.path.exists(FILE_BACKUP):
        try: data=baca_file(FILE_BACKUP); shutil.copy2(FILE_BACKUP,FILE_SAVE)
        except: pass
    if data is None: return None
    return [Petualang.from_dict(x) for x in data['petualang']], data['bank'], data['ronde'], data.get('history',[])

def format_rupiah(n):
    if n >= 1000000: return f"{n/1000000:.1f}T"
    elif n >= 1000000: return f"{n/1000000:.1f}M"
    elif n >= 1000: return f"{n/1000:.0f}rb"
    else: return f"{n:,}"

data = muat_data()
if data:
    petualang_list, bank, ronde, history = data
    hasil_terakhir = history[-1] if history else 0
    pesan = f"Data lama ketemu! Ronde {ronde}"
else:
    petualang_list, bank, ronde, history, hasil_terakhir = [], 1000000, 1, [], 0
    pesan = "Tambah 6 pemain dulu"

waktu_stop = time.time() + 10
status = "running"
pemenang_text = ""
hasil_next = random.choices([1,2,3,4,5,6], weights=[23,23,18,18,10,10], k=1)[0]
posisi_terakhir = hasil_terakhir if hasil_terakhir > 0 else 1

def roda_loop():
    global petualang_list, bank, ronde, history, hasil_terakhir, waktu_stop, status, pemenang_text, hasil_next, pesan, posisi_terakhir
    while True:
        now = time.time()
        sisa = waktu_stop - now
        if sisa <= 0:
            hasil = hasil_next
            hasil_terakhir = hasil
            posisi_terakhir = hasil
            hasil_next = random.choices([1,2,3,4,5,6], weights=[23,23,18,18,10,10], k=1)[0]
            pemenang = []
            for p in petualang_list:
                inv = p.investasi.get(hasil, 0)
                if inv > 0:
                    profit = inv * MULTIPLIER[hasil]
                    p.poin += profit
                    pemenang.append(f"{p.nama} +{profit:,} poin")
                p.investasi = p.investasi_next.copy()
                p.investasi_next = {}
            ronde += 1
            history.append(hasil)
            bank += 1000 * hasil
            pemenang_text = " | ".join(pemenang) if pemenang else "Ga ada yg menang"
            status = "result"
            waktu_stop = now + 2
            simpan_data(petualang_list, bank, ronde, history)
            time.sleep(2)
            status = "running"
            waktu_stop = time.time() + 10
        time.sleep(0.05)

Thread(target=roda_loop, daemon=True).start()

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        global petualang_list,bank,ronde,history,pesan,hasil_terakhir
        length=int(self.headers['Content-Length'])
        post=parse_qs(self.rfile.read(length).decode())
        aksi=post.get('aksi',[''])[0]; idx=int(post.get('idx',['-1'])[0])
        jumlah=int(post.get('jumlah',['0'])[0]); nama=post.get('nama',[''])[0].strip()
        nama_baru=post.get('nama_baru',[''])[0].strip(); no_proyek=int(post.get('no_proyek',['0'])[0])
        no_barang=int(post.get('no_barang',['0'])[0]); pilih=post.get('pilih',[''])[0]; menu=post.get('menu',[''])[0]

        sisa = waktu_stop - time.time()

        if aksi=='invest' and 0<=idx<len(petualang_list) and 1<=no_proyek<=6:
            p = petualang_list[idx]
            inv = int(post.get(f'inv{idx}_{no_proyek}',['0'])[0])
            if sisa <= 0.5:
                if inv <= p.poin + p.investasi_next.get(no_proyek, 0):
                    p.poin += p.investasi_next.get(no_proyek, 0)
                    p.poin -= inv
                    p.investasi_next[no_proyek] = inv
                    pesan = f"{p.nama} invest {inv:,} ke {nama_proyek(no_proyek)} [Ronde {ronde+1}]"
                else: pesan = "Poin ga cukup"
            else:
                if inv <= p.poin + p.investasi.get(no_proyek, 0):
                    p.poin += p.investasi.get(no_proyek, 0)
                    p.poin -= inv
                    p.investasi[no_proyek] = inv
                    pesan = f"{p.nama} invest {inv:,} ke {nama_proyek(no_proyek)} [Ronde {ronde}]"
                else: pesan = "Poin ga cukup"

        elif aksi=='pinjam' and 0<=idx<len(petualang_list):
            if jumlah<=bank and jumlah>0:
                petualang_list[idx].poin+=jumlah; petualang_list[idx].hutang+=jumlah; bank-=jumlah
                pesan=f"Pinjaman {jumlah:,} ke {petualang_list[idx].nama}"; simpan_data(petualang_list,bank,ronde,history)
            else: pesan="Kas bank ga cukup"

        elif aksi=='donatur':
            if pilih=='1' and 0<=idx<len(petualang_list) and jumlah<=bank and jumlah>0:
                petualang_list[idx].poin+=jumlah; bank-=jumlah; pesan=f"Donasi {jumlah:,} ke {petualang_list[idx].nama}"; simpan_data(petualang_list,bank,ronde,history)
            elif pilih=='2' and jumlah>0: bank+=jumlah; pesan=f"Kas +{jumlah:,}"; simpan_data(petualang_list,bank,ronde,history)

        elif aksi=='topup' and 0<=idx<len(petualang_list):
            p=petualang_list[idx]
            if pilih=='1' and jumlah>=1500 and p.rupiah>=jumlah:
                poin_dapat=jumlah//1500; p.rupiah-=jumlah; p.poin+=poin_dapat; bank+=jumlah-poin_dapat*1000
                pesan=f"Beli {poin_dapat:,} poin"; simpan_data(petualang_list,bank,ronde,history)
            elif pilih=='2' and jumlah>=1 and p.poin>=jumlah:
                rp_dapat=jumlah*1000; p.poin-=jumlah; p.rupiah+=rp_dapat; bank-=rp_dapat
                pesan=f"Jual {jumlah:,} poin"; simpan_data(petualang_list,bank,ronde,history)

        elif aksi=='shop' and 0<=idx<len(petualang_list):
            shop=[["🏠",15000000],["🌋",20000000],["🏬",300000],["🏢",8000000],["🏭",1000000],["🏪",50000000],
                  ["🚗",80000000],["🏎️",900000],["🚲",20000000],["🛵",15000000],["🏍️",80000000],["🚄",3000000],
                  ["🚅",2500000],["🚂",50000000],["✈️",900000],["🚁",160000],["🚀",80000000],["🚤",8000000],["🛳️",13000000],["👑",1000000]]
            if 0<=no_barang<len(shop):
                p=petualang_list[idx]; harga=shop[no_barang][1]
                if p.rupiah>=harga:
                    p.rupiah-=harga; p.aset[shop[no_barang][0]]=p.aset.get(shop[no_barang][0],0)+1
                    if shop[no_barang][0]=="👑": p.gelar="👑"
                    pesan=f"{p.nama} beli {shop[no_barang][0]}"; simpan_data(petualang_list,bank,ronde,history)
                else: pesan="Rupiah ga cukup"

        elif aksi=='tambah' and nama and len(petualang_list)<6:
            petualang_list.append(Petualang(nama)); pesan=f"{nama} masuk!"; simpan_data(petualang_list,bank,ronde,history)

        elif aksi=='edit' and 0<=idx<len(petualang_list):
            if pilih=='1' and nama_baru: petualang_list[idx].nama=nama_baru; pesan=f"Ganti nama jadi {nama_baru}"; simpan_data(petualang_list,bank,ronde,history)
            elif pilih=='2': nama_hapus=petualang_list[idx].nama; petualang_list.pop(idx); pesan=f"{nama_hapus} dihapus"; simpan_data(petualang_list,bank,ronde,history)

        elif aksi=='keluar': simpan_data(petualang_list,bank,ronde,history); pesan="Game disimpan"

        self.send_response(303); self.send_header('Location',f'/?menu={menu}' if menu else '/'); self.end_headers()

    def do_GET(self):
        global pesan
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        menu = params.get('menu',[''])[0]

        if parsed.path=='/':
            self.send_response(200); self.send_header('Content-type','text/html; charset=utf-8'); self.end_headers()
            sisa = max(0, waktu_stop - time.time())

            options="".join([f"<option value='{i}'>{p.nama}</option>" for i,p in enumerate(petualang_list)])
            shop=[["🏠",15000000],["🌋",20000000],["🏬",300000],["🏢",8000000],["🏭",1000000],["🏪",50000000],
                  ["🚗",80000000],["🏎️",900000],["🚲",20000000],["🛵",15000000],["🏍️",80000000],["🚄",3000000],
                  ["🚅",2500000],["🚂",50000000],["✈️",900000],["🚁",160000],["🚀",80000000],["🚤",8000000],["🛳️",13000000],["👑",1000000]]

            tabel=""; poin_list = []
            for i,p in enumerate(petualang_list):
                gelar = f"{p.gelar} " if p.gelar else ""
                hutang = f"Rp{p.hutang:,}" if p.hutang>0 else "-"
                tabel+=f"<tr><td>{i+1}</td><td>{gelar}{p.nama}</td><td>{p.poin:,}</td><td>Rp{format_rupiah(p.rupiah)}</td><td>{hutang}</td></tr>"
                poin_list.append(p.poin)
            if not tabel: tabel="<tr><td colspan=5>Belum ada pemain</td></tr>"

            grid_proyek=""
            for i in range(1,7):
                inputs=""
                for p_idx in range(len(petualang_list)):
                    val = petualang_list[p_idx].investasi.get(i, 0)
                    inputs += f'<input type="number" id="inv{p_idx}_{i}" name="inv{p_idx}_{i}" value="{val}" min="0" style="display:none;width:65px;margin:2px">'
                grid_proyek += f'<div class="proj" id="p{i}" onclick="submitInvest({i})"><div class="no">{i}</div><div class="nama">{nama_proyek(i)}</div><div id="inputBox{i}">{inputs}</div></div>'

            status_text = f"Investasi jalan - {sisa:.1f}s" if status=="running" else "Hasil keluar!"
            hasil_box = f"<div style='font-size:26px;color:#ffd700;margin-top:5px'>Hasil: {nama_proyek(hasil_terakhir)}</div><div style='font-size:12px;color:#4fbdba'>{pemenang_text}</div>" if status=="result" else f"<div style='font-size:32px;color:#4fbdba'>{sisa:.1f}s</div>"

            if menu=='':
                start_idx = URUTAN_RODA.index(posisi_terakhir) if posisi_terakhir in URUTAN_RODA else 0
                html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width">
<title>Petualang Auto v16</title>
<style>
body{{margin:0;padding:0;background:#0a0a1a;color:#eee;font-family:sans-serif;overflow-x:hidden}}
.box{{max-width:1000px;margin:0 auto;padding:60px 10px 10px 10px}}
h1{{text-align:center;color:#4fbdba;margin:5px 0}}
.info{{background:#1a1a2e;padding:10px;border-radius:8px;margin:8px 0;text-align:center}}
.pesan{{background:#e94560;padding:8px;border-radius:8px;margin:8px 0;text-align:center;font-size:12px}}
.timer{{background:#16213e;padding:15px;border-radius:10px;text-align:center;font-size:28px;font-weight:bold;color:#ffd700;margin:10px 0}}
table{{width:100%;border-collapse:collapse;font-size:12px;background:#1a1a2e;border-radius:8px;overflow:hidden}}
th{{background:#0f3460;padding:6px}} td{{border:1px solid #333;padding:5px;text-align:center}}
.grid3x2{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:15px 0}}
.proj{{background:#16213e;border:3px solid #333;border-radius:10px;padding:10px 5px;text-align:center;cursor:pointer;transition:all 0.1s}}
.proj.active{{border-color:#ffd700;box-shadow:0 0 25px #ffd700;animation:pulse 0.5s infinite}}
.proj.running{{border-color:#ffd700;box-shadow:0 0 15px #ffd700}}
.proj.no{{font-size:18px;font-weight:bold;color:#ffd700}}
.proj.nama{{font-size:11px;margin:3px 0}}
@keyframes pulse{{50%{{box-shadow:0 0 10px #ffd700}}}}
.menu-btn{{position:fixed;top:10px;right:10px;background:#16213e;color:#4fbdba;border:none;padding:10px 15px;font-size:22px;border-radius:8px;cursor:pointer;z-index:9999}}
.sidebar{{position:fixed;top:0;right:-300px;width:280px;height:100%;background:#1a1a2e;transition:0.3s;padding:20px;z-index:1000;border-left:2px solid #0f3460;overflow-y:auto}}
.sidebar.show{{right:0}}
.sidebar h3{{color:#4fbdba;text-align:center;margin-top:0}}
.sidebar a{{display:block;padding:12px;margin:8px 0;background:#0f3460;color:#4fbdba;text-decoration:none;border-radius:5px;text-align:center}}
.overlay{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:999}}
.overlay.show{{display:block}}
button{{padding:10px;background:#0f3460;color:#4fbdba;border:none;border-radius:8px;font-weight:bold;cursor:pointer;width:100%;margin-top:8px}}
select{{width:100%;padding:8px;margin:5px 0;background:#0f0f23;color:#eee;border:1px solid #333;border-radius:5px}}
input[type=number]{{width:100%;padding:8px;margin:5px 0;background:#0f0f23;color:#eee;border:1px solid #333;border-radius:5px;text-align:center}}
</style>
<script>
let pemainTerpilih = -1;
let poinPlayers = {json.dumps(poin_list)};
let urutan = {json.dumps(URUTAN_RODA)};
let currentIndex = {start_idx};
let animasiInterval = null;

function pilihPemain(idx) {{
    pemainTerpilih = parseInt(idx);
    document.querySelectorAll('[id^=inv]').forEach(inp => inp.style.display='none');
    if(idx >= 0) {{
        for(let no=1; no<=6; no++) {{
            let inp = document.getElementById('inv'+idx+'_'+no);
            if(inp) inp.style.display='inline-block';
        }}
    }}
}}

function submitInvest(no) {{
    if(pemainTerpilih == -1) {{alert('Pilih pemain dulu!'); return false;}}
    document.getElementById('no_proyek').value = no;
    document.getElementById('idx').value = pemainTerpilih;
    document.getElementById('formInvest').submit();
    return false;
}}

function animasiRoda() {{
    let hasil = {hasil_terakhir};
    let sisa = {sisa};
    let status = '{status}';

    function step() {{
        document.querySelectorAll('.proj').forEach(p=>p.classList.remove('running'));
        let no = urutan[currentIndex % 6];
        let el = document.getElementById('p'+no);
        if(el) el.classList.add('running');
        currentIndex++;

        if(status == 'running' && sisa > 0) {{
            let delay = sisa > 3? 100 : 200 + (3-sisa)*150;
            setTimeout(step, delay);
        }} else if(status!= 'running') {{
            document.querySelectorAll('.proj').forEach(p=>p.classList.remove('running'));
            let el2 = document.getElementById('p'+hasil);
            if(el2) el2.classList.add('active');
        }}
    }}
    step();
}}

function toggleMenu() {{
    document.getElementById('sidebar').classList.toggle('show');
    document.getElementById('overlay').classList.toggle('show');
}}

document.addEventListener('DOMContentLoaded', function() {{
    document.getElementById('overlay').addEventListener('click', function() {{
        document.getElementById('sidebar').classList.remove('show');
        document.getElementById('overlay').classList.remove('show');
    }});
    animasiRoda();
    setInterval(animasiRoda, 2000);
}});
</script></head><body>
<button class="menu-btn" onclick="toggleMenu()">☰</button>
<div class="overlay" id="overlay"></div>
<div class="sidebar" id="sidebar">
<h3>MENU</h3>
<a href="/?menu=pinjam">2. PINJAM</a>
<a href="/?menu=donatur">3. DONATUR</a>
<a href="/?menu=topup">4. TOPUP</a>
<a href="/?menu=shop">5. SHOP</a>
<a href="/?menu=history">6. HISTORY</a>
<a href="/?menu=tambah">8. TAMBAH PEMAIN</a>
<a href="/?menu=edit">9. EDIT/HAPUS</a>
<form method="POST"><input type="hidden" name="aksi" value="keluar"><button style="background:#e94560">7. KELUAR & SAVE</button></form>
</div>
<div class="box">
<h1>🏰 PETUALANG AUTO v16</h1>
<div class="info">💰 Kas: Rp{format_rupiah(bank)} | 🔄 Ronde: {ronde} | Rate: 1 poin = 1000 rupiah</div>
<div class="pesan">{pesan}</div>
<div class="timer">{hasil_box}<div style="font-size:13px;margin-top:5px">{status_text}</div></div>
<h3 style="text-align:center;font-size:15px">Pemain</h3>
<table><tr><th>No</th><th>Nama</th><th>Poin</th><th>Rupiah</th><th>Hutang</th></tr>{tabel}</table>
<h3 style="text-align:center;font-size:14px;margin-top:15px">Pilih Pemain → Klik Kotak</h3>
<select onchange="pilihPemain(this.value)"><option value="-1">-- Pilih Pemain --</option>{options}</select>
<h3 style="text-align:center;font-size:14px;margin-top:15px">Proyek</h3>
<div class="grid3x2">{grid_proyek}</div>
<form method="POST" id="formInvest">
<input type="hidden" name="aksi" value="invest">
<input type="hidden" name="no_proyek" id="no_proyek" value="0">
<input type="hidden" name="idx" id="idx" value="-1">
</form>
</div></body></html>"""
                self.wfile.write(html.encode())
                return

            elif menu=='pinjam':
                html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width">
<title>Pinjam</title>
<style>body{{margin:0;padding:0;background:#0a0a1a;color:#eee;font-family:sans-serif;padding:20px;text-align:center}}
.box{{max-width:400px;margin:auto;background:#1a1a2e;padding:20px;border-radius:10px}}
input,select{{width:100%;padding:10px;margin:8px 0;background:#0f0f23;color:#eee;border:1px solid #333;border-radius:5px}}
button{{width:100%;padding:12px;background:#0f3460;color:#4fbdba;border:none;border-radius:8px;font-weight:bold;cursor:pointer}}
.back{{background:#e94560;margin-top:10px}}
h2{{color:#4fbdba}}</style></head><body>
<div class="box"><h2>2. PINJAM</h2><div class="pesan">{pesan}</div>
<form method="POST">
<input type="hidden" name="menu" value="pinjam">
Pemain<select name="idx">{options}</select>
Jumlah<input type="number" name="jumlah" value="1000">
<button name="aksi" value="pinjam">Pinjam</button>
</form>
<a href="/"><button class="back">← KEMBALI</button></a></div></body></html>"""
                self.wfile.write(html.encode()); return

            elif menu=='donatur':
                html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width">
<title>Donatur</title>
<style>body{{margin:0;padding:0;background:#0a0a1a;color:#eee;font-family:sans-serif;padding:20px;text-align:center}}
.box{{max-width:400px;margin:auto;background:#1a1a2e;padding:20px;border-radius:10px}}
input,select{{width:100%;padding:10px;margin:8px 0;background:#0f0f23;color:#eee;border:1px solid #333;border-radius:5px}}
button{{width:100%;padding:12px;background:#0f3460;color:#4fbdba;border:none;border-radius:8px;font-weight:bold;cursor:pointer}}
.back{{background:#e94560;margin-top:10px}}
h2{{color:#4fbdba}}</style></head><body>
<div class="box"><h2>3. DONATUR</h2><div class="pesan">{pesan}</div>
<form method="POST">
<input type="hidden" name="menu" value="donatur">
<select name="pilih"><option value="1">Ke Pemain</option><option value="2">Ke Kas</option></select>
<select name="idx">{options}</select>
<input type="number" name="jumlah" value="1000">
<button name="aksi" value="donatur">Suntik</button>
</form>
<a href="/"><button class="back">← KEMBALI</button></a></div></body></html>"""
                self.wfile.write(html.encode()); return

            elif menu=='topup':
                html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width">
<title>Topup</title>
<style>body{{margin:0;padding:0;background:#0a0a1a;color:#eee;font-family:sans-serif;padding:20px;text-align:center}}
.box{{max-width:400px;margin:auto;background:#1a1a2e;padding:20px;border-radius:10px}}
input,select{{width:100%;padding:10px;margin:8px 0;background:#0f0f23;color:#eee;border:1px solid #333;border-radius:5px}}
button{{width:100%;padding:12px;background:#0f3460;color:#4fbdba;border:none;border-radius:8px;font-weight:bold;cursor:pointer}}
.back{{background:#e94560;margin-top:10px}}
h2{{color:#4fbdba}}</style></head><body>
<div class="box"><h2>4. TOPUP JUAL BELI</h2><div class="pesan">{pesan}</div>
<form method="POST">
<input type="hidden" name="menu" value="topup">
<select name="idx">{options}</select>
<select name="pilih"><option value="1">Beli Poin 1:1500</option><option value="2">Jual Poin 1000:1</option></select>
<input type="number" name="jumlah" value="1500">
<button name="aksi" value="topup">Proses</button>
</form>
<a href="/"><button class="back">← KEMBALI</button></a></div></body></html>"""
                self.wfile.write(html.encode()); return

            elif menu=='shop':
                html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width">
<title>Shop</title>
<style>body{{margin:0;padding:0;background:#0a0a1a;color:#eee;font-family:sans-serif;padding:20px;text-align:center}}
.box{{max-width:400px;margin:auto;background:#1a1a2e;padding:20px;border-radius:10px}}
input,select{{width:100%;padding:10px;margin:8px 0;background:#0f0f23;color:#eee;border:1px solid #333;border-radius:5px}}
button{{width:100%;padding:12px;background:#0f3460;color:#4fbdba;border:none;border-radius:8px;font-weight:bold;cursor:pointer}}
.back{{background:#e94560;margin-top:10px}}
h2{{color:#4fbdba}}</style></head><body>
<div class="box"><h2>5. SHOP</h2><div class="pesan">{pesan}</div>
<form method="POST">
<input type="hidden" name="menu" value="shop">
<select name="idx">{options}</select>
<select name="no_barang">{''.join([f"<option value='{i}'>{shop[i][0]} Rp{format_rupiah(shop[i][1])}</option>" for i in range(len(shop))])}</select>
<button name="aksi" value="shop">Beli</button>
</form>
<a href="/"><button class="back">← KEMBALI</button></a></div></body></html>"""
                self.wfile.write(html.encode()); return

            elif menu=='history':
                history_str="".join([f"{i}. {nama_proyek(no)}<br>" for i,no in enumerate(history[-50:],1)]) if history else "Belum ada ronde"
                html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width">
<title>History</title>
<style>body{{margin:0;padding:0;background:#0a0a1a;color:#eee;font-family:sans-serif;padding:20px;text-align:center}}
.box{{max-width:400px;margin:auto;background:#1a1a2e;padding:20px;border-radius:10px}}
.back{{width:100%;padding:12px;background:#e94560;border:none;border-radius:8px;font-weight:bold;cursor:pointer;color:#4fbdba}}
h2{{color:#4fbdba}}</style></head><body>
<div class="box"><h2>6. HISTORY</h2>
<div style="height:300px;overflow:auto;font-size:14px;background:#0f0f23;padding:10px;border-radius:5px;text-align:left">{history_str}</div>
<a href="/"><button class="back">← KEMBALI</button></a></div></body></html>"""
                self.wfile.write(html.encode()); return

            elif menu=='tambah':
                html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width">
<title>Tambah Pemain</title>
<style>body{{margin:0;padding:0;background:#0a0a1a;color:#eee;font-family:sans-serif;padding:20px;text-align:center}}
.box{{max-width:400px;margin:auto;background:#1a1a2e;padding:20px;border-radius:10px}}
input{{width:100%;padding:10px;margin:8px 0;background:#0f0f23;color:#eee;border:1px solid #333;border-radius:5px}}
button{{width:100%;padding:12px;background:#0f3460;color:#4fbdba;border:none;border-radius:8px;font-weight:bold;cursor:pointer}}
.back{{background:#e94560;margin-top:10px}}
h2{{color:#4fbdba}}</style></head><body>
<div class="box"><h2>8. TAMBAH PEMAIN</h2><div class="pesan">{pesan}</div>
<form method="POST">
<input type="hidden" name="menu" value="tambah">
<input name="nama" placeholder="Nama baru max 15 huruf" maxlength="15">
<button name="aksi" value="tambah">Tambah</button>
</form>
<a href="/"><button class="back">← KEMBALI</button></a></div></body></html>"""
                self.wfile.write(html.encode()); return

            elif menu=='edit':
                html=f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width">
<title>Edit/Hapus</title>
<style>body{{margin:0;padding:0;background:#0a0a1a;color:#eee;font-family:sans-serif;padding:20px;text-align:center}}
.box{{max-width:400px;margin:auto;background:#1a1a2e;padding:20px;border-radius:10px}}
input,select{{width:100%;padding:10px;margin:8px 0;background:#0f0f23;color:#eee;border:1px solid #333;border-radius:5px}}
button{{width:100%;padding:12px;background:#0f3460;color:#4fbdba;border:none;border-radius:8px;font-weight:bold;cursor:pointer}}
.back{{background:#e94560;margin-top:10px}}
h2{{color:#4fbdba}}</style></head><body>
<div class="box"><h2>9. EDIT/HAPUS PEMAIN</h2><div class="pesan">{pesan}</div>
<form method="POST">
<input type="hidden" name="menu" value="edit">
<select name="idx">{options}</select>
<select name="pilih"><option value="1">Edit Nama</option><option value="2">Hapus</option></select>
<input name="nama_baru" placeholder="Nama baru">
<button name="aksi" value="edit">Proses</button>
</form>
<a href="/"><button class="back">← KEMBALI</button></a></div></body></html>"""
                self.wfile.write(html.encode()); return

        return http.server.SimpleHTTPRequestHandler.do_GET(self)

with socketserver.TCPServer(("",PORT),Handler) as httpd:
    print(f"\n=== PETUALANG AUTO v16 ===")
    print(f"Buka: http://localhost:{PORT}\n")
    httpd.serve_forever()
