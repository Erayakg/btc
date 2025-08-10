# twitter_cookie_manager.py
# Türkçe açıklamalar ile: Kalıcı profil + uc + cookie+localStorage+indexedDB kaydetme & yükleme

import os
import json
import time
import random
import tempfile
import shutil
from pathlib import Path

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

# --- Konfigürasyon ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_DIR = os.path.join(PROJECT_ROOT, "confighamit", "accounts")
COOKIE_DIR = os.path.join(PROJECT_ROOT, "confighamit", "configsub")
PROFILE_ROOT = os.path.join(PROJECT_ROOT, "confighamit", "profiles")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "confighamit", "accounts.json")

os.makedirs(ACCOUNTS_DIR, exist_ok=True)
os.makedirs(COOKIE_DIR, exist_ok=True)
os.makedirs(PROFILE_ROOT, exist_ok=True)

# Sabit (deterministic) user-agent - hesap başına aynı kalacak
DEFAULT_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/121.0.0.0 Safari/537.36")

# Zamanlama
CHECK_INTERVAL = 10  # login kontrol aralığı (sn)

# --- Yardımcı fonksiyonlar ---
def profile_path_for_username(username: str) -> str:
    safe = "".join(c for c in username if c.isalnum() or c in ("_", "-")).strip()
    path = os.path.join(PROFILE_ROOT, safe)
    os.makedirs(path, exist_ok=True)
    return path

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- Tarayıcı kurulum ---
def setup_uc_driver(username: str, proxy: str = None, headless: bool = False):
    profile_dir = profile_path_for_username(username)
    options = uc.ChromeOptions()
    # Profil dizini (kalıcı)
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    # Sabit user-agent (hesap için sabit kalacak)
    options.add_argument(f"--user-agent={DEFAULT_USER_AGENT}")
    # Pencere boyutu sabitle
    options.add_argument("--window-size=1200,900")

    # Opsiyonel proxy (örnek: "http://user:pass@ip:port" ya da "ip:port")
    if proxy:
        options.add_argument(f'--proxy-server={proxy}')

    # Undetected chromedriver ile başlat
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        print(f"[ERROR] undetected-chromedriver başlatılamadı: {e}")
        return None

    # Basit navigator.webdriver gizleme (uc genelde halleder)
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception:
        pass

    return driver

# --- Login kontrolü (basit) ---
def check_login_status(driver):
    try:
        url = driver.current_url.lower()
        # X/Twitter ana sayfa tespiti
        if "twitter.com/home" in url or "x.com/home" in url or "/home" in url:
            return True
        # Tweet atmaya yarayan element vs.
        try:
            el = driver.find_element(By.CSS_SELECTOR, '[data-testid="SideNav_NewTweet_Button"], [aria-label="Tweet"]')
            if el:
                return True
        except:
            pass
        # Profil bağlantısı
        try:
            driver.find_element(By.CSS_SELECTOR, '[data-testid="SideNav_AccountSwitcher_Button"]')
            return True
        except:
            pass
        return False
    except Exception:
        return False

# --- Depolama (storage) dump & restore ---
def dump_storage(driver):
    """
    localStorage, sessionStorage, indexedDB (mümkünse) ve cookies'i döndürür.
    """
    result = {"cookies": [], "localStorage": {}, "sessionStorage": {}, "indexedDB": {}}
    try:
        # cookies
        result["cookies"] = driver.get_cookies()
    except Exception as e:
        print(f"[WARN] cookie alınamadı: {e}")

    # localStorage & sessionStorage
    try:
        ls = driver.execute_script("return JSON.stringify(window.localStorage);")
        ss = driver.execute_script("return JSON.stringify(window.sessionStorage);")
        result["localStorage"] = json.loads(ls) if ls else {}
        result["sessionStorage"] = json.loads(ss) if ss else {}
    except Exception as e:
        print(f"[WARN] local/sessionStorage alınamadı: {e}")

    # indexedDB: tarayıcı izin verirse döküm yap
    try:
        idx_js = """
        const done = arguments[0];
        (async () => {
          const out = {};
          if (!('indexedDB' in window)) { done(JSON.stringify(out)); return; }
          try {
            const dbs = await indexedDB.databases ? indexedDB.databases() : [];
            for (const dbInfo of dbs) {
              const name = dbInfo.name;
              if (!name) continue;
              out[name] = {};
              try {
                const req = indexedDB.open(name);
                await new Promise(res => {
                  req.onsuccess = async (e) => {
                    const db = e.target.result;
                    const stores = Array.from(db.objectStoreNames || []);
                    for (const s of stores) {
                      out[name][s] = [];
                      try {
                        const tx = db.transaction(s, 'readonly');
                        const store = tx.objectStore(s);
                        const cursorReq = store.openCursor();
                        await new Promise(r => {
                          cursorReq.onsuccess = (ev) => {
                            const cur = ev.target.result;
                            if (cur) { out[name][s].push(cur.value); cur.continue(); }
                          };
                          tx.oncomplete = () => r();
                          tx.onerror = () => r();
                        });
                      } catch(e) {}
                    }
                    db.close();
                    res();
                  };
                  req.onerror = () => res();
                });
              } catch(e){}
            }
            done(JSON.stringify(out));
          } catch(e){ done(JSON.stringify({})); }
        })();
        """
        raw = driver.execute_async_script(idx_js)
        if raw:
            result["indexedDB"] = json.loads(raw)
    except Exception as e:
        print(f"[WARN] indexedDB alınamadı: {e}")

    return result

def restore_storage(driver, storage_dump):
    """
    cookie + local/sessionStorage + indexedDB (sınırlı restore) yükler.
    NOT: indexedDB'nin tam restore'u bazı durumlarda çalışmayabilir; script tabanlı eklemeler yapılır.
    """
    # 1) Gerekli domain'e git (cookie eklemek için)
    try:
        driver.get("https://twitter.com/")
        time.sleep(2)
    except Exception:
        pass

    # 2) Cookies ekle
    if storage_dump.get("cookies"):
        for c in storage_dump["cookies"]:
            # cookie dict'inin bazı alanları eksik olabilir; selenium.add_cookie için uygun formata getir
            cookie = {k: v for k, v in c.items() if k in ("name", "value", "path", "domain", "secure", "httpOnly", "expiry")}
            try:
                # Chrome, domain uyuşmazsa hata verebilir; domain'i temizle ve tekrar deneyebiliriz
                driver.add_cookie(cookie)
            except Exception:
                # try without domain
                cookie.pop("domain", None)
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass

    # 3) localStorage & sessionStorage set et
    try:
        ls_json = json.dumps(storage_dump.get("localStorage", {}))
        ss_json = json.dumps(storage_dump.get("sessionStorage", {}))
        script = f"window.localStorage.clear(); const ls = {ls_json}; for(const k in ls){{ window.localStorage.setItem(k, JSON.stringify(ls[k]).replace(/^\"|\"$/g, '')); }};"
        script += f"window.sessionStorage.clear(); const ss = {ss_json}; for(const k in ss){{ window.sessionStorage.setItem(k, JSON.stringify(ss[k]).replace(/^\"|\"$/g, '')); }};"
        driver.execute_script(script)
    except Exception as e:
        print(f"[WARN] local/sessionStorage yüklenemedi: {e}")

    # 4) indexedDB restore (basit yol: her obje için put)
    try:
        idx = storage_dump.get("indexedDB", {})
        if idx:
            # JS ile her db/STORE içine add yap
            set_idx_js = ["const done = arguments[0]; (async ()=>{ try{"]
            set_idx_js.append("const payload = " + json.dumps(idx) + ";")
            set_idx_js.append("""
              for (const dbName in payload) {
                const stores = payload[dbName];
                const req = indexedDB.open(dbName);
                await new Promise(res => {
                  req.onupgradeneeded = (e) => {
                    const db = e.target.result;
                    for (const s in stores) {
                      if (!db.objectStoreNames.contains(s)) {
                        db.createObjectStore(s, { autoIncrement: true });
                      }
                    }
                  };
                  req.onsuccess = (e) => {
                    const db = e.target.result;
                    const tx = db.transaction(Object.keys(stores), 'readwrite');
                    for (const s in stores) {
                      try {
                        const store = tx.objectStore(s);
                        const arr = stores[s] || [];
                        for (const obj of arr) {
                          try { store.put(obj); } catch(e){}
                        }
                      } catch(e){}
                    }
                    tx.oncomplete = ()=> { db.close(); res(); };
                    tx.onerror = ()=> { db.close(); res(); };
                  };
                  req.onerror = ()=> res();
                });
              }
            """)
            set_idx_js.append("done(true); }catch(e){ done(false);} })();")
            driver.execute_async_script("\n".join(set_idx_js))
    except Exception as e:
        print(f"[WARN] indexedDB yüklenemedi: {e}")

    # 5) Son olarak sayfayı yenile
    try:
        driver.refresh()
        time.sleep(2)
    except Exception:
        pass

# --- Kaydet / yükle işlevleri ---
def save_all_for_user(driver, username):
    dump = dump_storage(driver)
    cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies_plus.json")
    save_json(cookie_path, dump)
    print(f"[SUCCESS] Depolama ({len(dump.get('cookies', []))} cookie) kaydedildi -> {cookie_path}")
    return cookie_path

def load_all_for_user(username):
    cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies_plus.json")
    return load_json(cookie_path)

# --- accounts.json güncelle ---
def update_accounts_json(username, cookie_file_path):
    accounts = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except:
            accounts = []

    found = False
    for a in accounts:
        if a.get("account_id") == username:
            a["is_active"] = True
            a["cookie_file_path"] = cookie_file_path
            found = True
            break

    if not found:
        accounts.append({
            "account_id": username,
            "is_active": True,
            "cookie_file_path": cookie_file_path,
        })

    save_json(OUTPUT_FILE, accounts)
    print(f"[SUCCESS] accounts.json güncellendi: {OUTPUT_FILE}")

# --- Manuel login + kaydet süreci ---
def manual_login_flow(username, proxy=None, auto_restore=False):
    """
    Eğer önce kaydedilmiş depolama varsa -> restore (auto_restore True ise)
    Daha sonra kullanıcı manuel login yapar; login algılanınca depolama kaydedilir.
    """
    driver = setup_uc_driver(username, proxy=proxy, headless=False)
    if not driver:
        print("[ERROR] Tarayıcı başlatılamadı.")
        return False

    try:
        # Eğer daha önce kaydedilmiş depolama varsa, yüklemeyi dene
        if auto_restore:
            saved = load_all_for_user(username)
            if saved:
                try:
                    print("[INFO] Önceki depolama yükleniyor...")
                    restore_storage(driver, saved)
                    time.sleep(3)
                except Exception as e:
                    print(f"[WARN] Depolama yüklenirken hata: {e}")

        # Git login sayfasına
        driver.get("https://twitter.com/login")
        print("[INFO] Twitter login sayfası açıldı. Lütfen manuel giriş yapın (email/kullanıcı, şifre, 2FA).")

        # Manuel login bekle
        start = time.time()
        max_wait = 15  # maksimum bekleme süresi (10 dakika) — istersen artır
        while True:
            if check_login_status(driver):
                print("[SUCCESS] Login tespit edildi.")
                cookie_file = save_all_for_user(driver, username)
                update_accounts_json(username, cookie_file)
                return True

            if time.time() - start > max_wait:
                print("[ERROR] Login yapılmadı: Zaman aşımı.")
                return False

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n[INFO] Kullanıcı iptal etti.")
        return False
    except WebDriverException as e:
        print(f"[ERROR] Tarayıcı hatası: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        return False
    finally:
        try:
            driver.quit()
        except:
            pass

# --- Hızlı CLI kullanımı ---
def main():
    print("="*60)
    print("TWITTER X MANUEL LOGIN & STORAGE KAYIT ARACI")
    print("="*60)
    username = input("Kaydetmek istediğin hesap kullanıcı adını gir: ").strip()
    if not username:
        print("Kullanıcı adı boş olamaz.")
        return

    proxy = input("Proxy kullanmak istiyor musun? (örnek http://ip:port) / boş bırak = hayır: ").strip() or None
    auto_restore_choice = input("Varsa önceki depolamayı otomatik yükle (recommended)? (e/h): ").strip().lower() or "e"
    auto_restore = auto_restore_choice.startswith("e")

    print(f"[INFO] Profil dizini: {profile_path_for_username(username)}")
    print("[INFO] Tarayıcı başlatılıyor...")
    ok = manual_login_flow(username, proxy=proxy, auto_restore=auto_restore)
    if ok:
        print("[SUCCESS] İşlem tamamlandı.")
    else:
        print("[ERROR] İşlem başarısız oldu.")

if __name__ == "__main__":
    main()
