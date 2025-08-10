import os
import json
import time
import random
import glob
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import uuid

# Ana dizindeki accounts klasörü
ACCOUNTS_DIR = "confighamit/accounts"
COOKIE_DIR = "confighamit/configsub"
OUTPUT_FILE = "confighamit/accounts.json"
ACCOUNTS_FILE = "hesaplar.txt"

# Çalışma dizinini ana dizine değiştir
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)

print(f"[INFO] Calisma dizini: {os.getcwd()}")
print(f"[INFO] Accounts dizini: {ACCOUNTS_DIR}")
print(f"[INFO] Cookie dizini: {COOKIE_DIR}")
print(f"[INFO] Cikti dosyasi: {OUTPUT_FILE}")
print(f"[INFO] Hesaplar dosyasi: {ACCOUNTS_FILE}")

# accounts klasörünü oluştur
os.makedirs(ACCOUNTS_DIR, exist_ok=True)
os.makedirs(COOKIE_DIR, exist_ok=True)

def get_chromedriver_path():
    """
    ChromeDriver'ı yerel olarak bul
    """
    import platform
    
    # Platform'a göre chromedriver dosya adını belirle
    if platform.system() == "Windows":
        chromedriver_name = "chromedriver.exe"
    else:
        chromedriver_name = "chromedriver"
    
    # Önce manuel/geçerli bir yol dene
    local_paths = [
        os.path.join(os.getcwd(), chromedriver_name),  # Ana dizinde
        os.path.join(os.getcwd(), "chromedriver-win64", "chromedriver.exe"),  # Windows klasörü
        "/usr/local/bin/chromedriver",
        "/usr/bin/chromedriver"
    ]
    
    for path in local_paths:
        if os.path.exists(path):
            print(f"[INFO] ChromeDriver bulundu: {path}")
            return path

    # Eğer bulamazsan hata ver
    print(f"[ERROR] ChromeDriver bulunamadi: {os.path.join(os.getcwd(), chromedriver_name)}")
    return None

def setup_driver():
    """Gelişmiş Chrome driver setup - Bot tespitini önlemek için"""
    try:
        chrome_path = get_chromedriver_path()
        if not chrome_path:
            print("[ERROR] ChromeDriver bulunamadi.")
            return None

        options = ChromeOptions()
        
        # Görünür mod için headless'i kapat
        # options.add_argument("--headless")  # Bu satırı kaldırıyoruz
        
        # Bot tespitini önlemek için gelişmiş ayarlar
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Cache ve geçici dosyaları temizlemek için ayarlar
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        options.add_argument("--disable-javascript")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-domain-reliability")
        options.add_argument("--disable-component-extensions-with-background-pages")
        
        # Cache temizleme
        options.add_argument("--disable-application-cache")
        options.add_argument("--disable-cache")
        options.add_argument("--disable-offline-load-stale-cache")
        options.add_argument("--disk-cache-size=0")
        options.add_argument("--media-cache-size=0")
        
        # Windows için geçici dizin (her seferinde yeni)
        import tempfile
        import uuid
        temp_base_dir = os.path.join(os.getcwd(), "temp_chrome_data")
        os.makedirs(temp_base_dir, exist_ok=True)
        
        # Benzersiz user data directory oluştur
        unique_id = str(uuid.uuid4())[:8]
        user_data_dir = os.path.join(temp_base_dir, f"chrome_user_data_{unique_id}")
        os.makedirs(user_data_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={user_data_dir}")
        print(f"[INFO] Chrome user data directory: {user_data_dir}")
        
        # Pencere boyutu
        options.add_argument("--window-size=1920,1080")
        
        # Random user agent
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        service = ChromeService(executable_path=chrome_path)
        driver = webdriver.Chrome(service=service, options=options)
        
        # JavaScript ile bot tespitini önle
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        print("[SUCCESS] Chrome basariyla baslatildi (gorunur mod - bot tespiti onlendi)")
        return driver
    except Exception as e:
        print(f"[ERROR] Chrome baslatilamadi: {e}")
        return None

def parse_account_line(line):
    """Hesap satırını parse et: username:password:email:hash"""
    try:
        parts = line.strip().split(':')
        if len(parts) >= 4:
            return {
                'username': parts[0],
                'password': parts[1],
                'email': parts[2],
                'hash': parts[3]
            }
        else:
            print(f"[ERROR] Gecersiz hesap format: {line}")
            return None
    except Exception as e:
        print(f"[ERROR] Hesap parse hatasi: {e}")
        return None

def read_accounts_from_file():
    """hesaplar.txt dosyasından hesapları oku"""
    accounts = []
    
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"[ERROR] {ACCOUNTS_FILE} dosyasi bulunamadi!")
        return accounts
    
    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if line and not line.startswith('#'):  # Boş satırları ve yorumları atla
                account = parse_account_line(line)
                if account:
                    accounts.append(account)
                    print(f"[INFO] Hesap #{line_num}: {account['username']}")
        
        print(f"[INFO] Toplam {len(accounts)} hesap okundu")
        return accounts
        
    except Exception as e:
        print(f"[ERROR] Dosya okuma hatasi: {e}")
        return accounts

def check_login_status(driver):
    """Login durumunu kontrol et"""
    try:
        current_url = driver.current_url
        print(f"[INFO] Mevcut URL: {current_url}")
        
        # Twitter ana sayfasında mı kontrol et
        if ("home" in current_url or "notifications" in current_url or
            "twitter.com/home" in current_url or "x.com/home" in current_url):
            print("[SUCCESS] Login basarili - Ana sayfada")
            return True
        
        # Login sayfasında mı kontrol et
        if "login" in current_url or "signin" in current_url:
            print("[INFO] Hala login sayfasında")
            return False
        
        # Profil sayfasında mı kontrol et
        if "twitter.com/" in current_url and "/status/" not in current_url:
            print("[SUCCESS] Login basarili - Profil sayfasında")
            return True
        
        # Diğer durumlar için sayfa içeriğini kontrol et
        try:
            # Tweet butonu var mı kontrol et
            tweet_button = driver.find_element(By.CSS_SELECTOR, '[data-testid="SideNav_NewTweet_Button"]')
            if tweet_button:
                print("[SUCCESS] Login basarili - Tweet butonu bulundu")
                return True
        except:
            pass
        
        try:
            # Sidebar menü var mı kontrol et
            sidebar = driver.find_element(By.CSS_SELECTOR, '[data-testid="SideNav_AccountSwitcher_Button"]')
            if sidebar:
                print("[SUCCESS] Login basarili - Sidebar bulundu")
                return True
        except:
            pass
        
        print("[INFO] Login durumu belirsiz")
        return False
        
    except Exception as e:
        print(f"[ERROR] Login durumu kontrol hatasi: {e}")
        return False

def automatic_login(driver, account):
    """Otomatik Twitter login - Bot doğrulaması için manuel bekleme"""
    try:
        username = account['username']
        password = account['password']
        email = account['email']
        
        print(f"[INFO] {username} icin otomatik login baslatiliyor...")
        
        # Twitter login sayfasına git
        print("[INFO] Twitter login sayfasina gidiliyor...")
        driver.get("https://twitter.com/login")
        time.sleep(3)
        
        # Username girişi (config/fetchaccount.py mantığına göre)
        try:
            print(f"[INFO] Username giriliyor: {username}")
            username_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
            username_input.click()
            time.sleep(0.5)
            username_input.clear()
            username_input.send_keys(username)  # Username kullan, email değil
            time.sleep(1)
            username_input.send_keys(Keys.RETURN)  # Enter'a bas
            time.sleep(3)
            
        except Exception as e:
            print(f"[ERROR] Username giriş hatasi: {e}")
            return False
        
        # Password girişi
        try:
            print("[INFO] Password giriliyor...")
            password_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.click()
            time.sleep(0.5)
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(1)
            password_input.send_keys(Keys.RETURN)  # Enter'a bas
            time.sleep(5)
            
        except Exception as e:
            print(f"[ERROR] Password giriş hatasi: {e}")
            return False
        
        # Bot doğrulaması için manuel bekleme
        print(f"[INFO] {username} icin bot doğrulaması kontrol ediliyor...")
        print("[INFO] Eğer bot doğrulaması gelirse manuel olarak geçirin!")
        print("[INFO] Login tamamlandıktan sonra bu pencereyi kapatmayın!")
        
        # Sürekli login durumunu kontrol et (bot doğrulaması için)
        max_wait_time = 300  # 5 dakika maksimum bekleme
        check_interval = 10  # Her 10 saniyede bir kontrol et
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                if check_login_status(driver):
                    print(f"[SUCCESS] {username} icin login basarili!")
                    return True
                
                # Bot doğrulaması var mı kontrol et
                current_url = driver.current_url
                if "challenge" in current_url or "verify" in current_url or "captcha" in current_url:
                    print(f"[INFO] {username} - Bot doğrulaması tespit edildi! Manuel olarak geçirin...")
                
                time.sleep(check_interval)
                elapsed_time += check_interval
                
                if elapsed_time % 30 == 0:  # Her 30 saniyede bir bilgi ver
                    remaining_time = max_wait_time - elapsed_time
                    print(f"[INFO] {username} - Hala bekleniyor... Kalan süre: {remaining_time} saniye")
                
            except Exception as e:
                print(f"[WARNING] Login kontrol hatasi: {e}")
                time.sleep(check_interval)
                elapsed_time += check_interval
        
        print(f"[ERROR] {username} icin login zaman aşımı (5 dakika)")
        return False
            
    except Exception as e:
        print(f"[ERROR] Otomatik login hatasi: {e}")
        return False

def save_cookies(driver, username):
    """Çerezleri kaydet"""
    try:
        cookies = driver.get_cookies()
        if not cookies:
            print("[ERROR] Cerez bulunamadi")
            return False
        
        cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies.json")
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        
        print(f"[SUCCESS] Cerezler kaydedildi: {cookie_path}")
        print(f"[INFO] Toplam {len(cookies)} cerez kaydedildi")
        return True
        
    except Exception as e:
        print(f"[ERROR] Cerez kaydetme hatasi: {e}")
        return False

def update_accounts_json(username):
    """accounts.json dosyasını güncelle"""
    try:
        accounts_file = OUTPUT_FILE
        accounts = []
        
        # Mevcut accounts.json dosyasını oku
        if os.path.exists(accounts_file):
            try:
                with open(accounts_file, "r", encoding="utf-8") as f:
                    accounts = json.load(f)
            except:
                accounts = []
        
        # Yeni hesabı ekle veya güncelle
        account_exists = False
        for account in accounts:
            if account.get("account_id") == username:
                account["is_active"] = True
                account["cookie_file_path"] = f"confighamit/configsub/{username}_cookies.json"
                account_exists = True
                print(f"[INFO] {username} hesabi guncellendi")
                break
        
        if not account_exists:
            new_account = {
                "account_id": username,
                "is_active": True,
                "cookie_file_path": f"confighamit/configsub/{username}_cookies.json",
                "target_keywords_override": [
                    "Artificial General Intelligence",
                    "Large Language Models applications",
                    "AI Ethics in practice",
                    "Future of AI"
                ],
                "competitor_profiles_override": [
                    "https://x.com/OpenAI",
                    "https://x.com/DeepMind",
                    "https://x.com/MetaAI"
                ],
                "news_sites_override": [
                    "https://techcrunch.com/category/artificial-intelligence/",
                    "https://www.technologyreview.com/artificial-intelligence/"
                ],
                "research_paper_sites_override": [
                    "https://arxiv.org/list/cs.AI/pastweek?show=10"
                ],
                "llm_settings_override": {
                    "service_preference": "openai",
                    "model_name_override": "gpt-4o",
                    "max_tokens": 200,
                    "temperature": 0.7
                },
                "action_config_override": {
                    "min_delay_between_actions_seconds": 90,
                    "max_delay_between_actions_seconds": 240,
                    "enable_competitor_reposts": True,
                    "max_posts_per_competitor_run": 2,
                    "min_likes_for_repost_candidate": 20,
                    "min_retweets_for_repost_candidate": 5,
                    "enable_thread_analysis": True,
                    "llm_settings_for_post": {
                        "service_preference": "openai",
                        "model_name_override": "gpt-4o",
                        "max_tokens": 250,
                        "temperature": 0.72
                    }
                }
            }
            accounts.append(new_account)
            print(f"[INFO] {username} hesabi eklendi")
        
        # Dosyayı kaydet
        with open(accounts_file, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
        
        print(f"[SUCCESS] accounts.json dosyasi guncellendi: {accounts_file}")
        
    except Exception as e:
        print(f"[ERROR] accounts.json guncelleme hatasi: {e}")

def process_single_account(account):
    """Tek hesap için login işlemi"""
    print("=" * 80)
    print(f"[INFO] HESAP ISLEMI: {account['username']}")
    print("=" * 80)
    
    # Chrome'u başlat
    driver = setup_driver()
    if not driver:
        print("[ERROR] Chrome baslatilamadi")
        return False
    
    try:
        # Otomatik login
        if automatic_login(driver, account):
            print(f"[SUCCESS] {account['username']} icin login basarili! Cerezler kaydediliyor...")
            
            # Çerezleri kaydet
            if save_cookies(driver, account['username']):
                print(f"[SUCCESS] {account['username']} icin cerezler basariyla kaydedildi!")
                
                # accounts.json dosyasını güncelle
                update_accounts_json(account['username'])
                
                print(f"[INFO] {account['username']} icin islem tamamlandi!")
                print("[INFO] Chrome penceresi manuel olarak kapatilabilir")
                return True
            else:
                print("[ERROR] Cerezler kaydedilemedi")
                return False
        else:
            print(f"[ERROR] {account['username']} icin login basarisiz")
            return False
            
    except Exception as e:
        print(f"[ERROR] Genel hata: {e}")
        return False
    finally:
        # Chrome'u otomatik kapatma - manuel kapatma için kaldırıldı
        print(f"[INFO] {account['username']} icin Chrome penceresi acik birakildi")
        print("[INFO] Manuel olarak kapatabilirsiniz")
        # driver.quit() satırını kaldırdık

def main():
    """Ana fonksiyon - Hesapları işle"""
    print("=" * 80)
    print("[INFO] OTOMATIK TWITTER LOGIN ARACI (GORUNUR MOD)")
    print("=" * 80)
    print(f"[INFO] Bu araç {ACCOUNTS_FILE} dosyasından hesapları okur")
    print("[INFO] Her hesap için otomatik Twitter login yapar")
    print("[INFO] Chrome penceresi görünür modda açılır")
    print("[INFO] Başarılı loginler için çerezler kaydedilir")
    print("=" * 80)
    
    # Hesapları oku
    accounts = read_accounts_from_file()
    if not accounts:
        print("[ERROR] Islenecek hesap bulunamadi!")
        return False
    
    successful_accounts = []
    failed_accounts = []
    
    try:
        for i, account in enumerate(accounts, 1):
            print(f"\n[INFO] HESAP #{i}/{len(accounts)}: {account['username']}")
            
            success = process_single_account(account)
            
            if success:
                successful_accounts.append(account['username'])
                print(f"[SUCCESS] HESAP #{i} BASARILI: {account['username']}")
            else:
                failed_accounts.append(account['username'])
                print(f"[ERROR] HESAP #{i} BASARISIZ: {account['username']}")
            
            # Hesaplar arası bekleme kaldırıldı - hemen devam et
            if i < len(accounts):
                print("[INFO] Bir sonraki hesaba geçiliyor...")
                time.sleep(2)  # Sadece 2 saniye bekle
        
        # Özet
        print("\n" + "=" * 80)
        print("[INFO] ISLEM TAMAMLANDI!")
        print("=" * 80)
        print(f"[INFO] Toplam hesap: {len(accounts)}")
        print(f"[INFO] Başarılı: {len(successful_accounts)}")
        print(f"[INFO] Başarısız: {len(failed_accounts)}")
        
        if successful_accounts:
            print(f"[INFO] Başarılı hesaplar: {', '.join(successful_accounts)}")
        
        if failed_accounts:
            print(f"[INFO] Başarısız hesaplar: {', '.join(failed_accounts)}")
        
        print("=" * 80)
        
        return len(successful_accounts) > 0
        
    except KeyboardInterrupt:
        print("\n[INFO] Kullanıcı tarafindan iptal edildi")
        return False
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        return False
    finally:
        # Geçici dosyaları temizle
        cleanup_temp_files()

def cleanup_temp_files():
    """Geçici Chrome dosyalarını temizle"""
    try:
        import shutil
        import glob
        
        temp_base_dir = os.path.join(os.getcwd(), "temp_chrome_data")
        if os.path.exists(temp_base_dir):
            chrome_dirs = glob.glob(os.path.join(temp_base_dir, "chrome_user_data_*"))
            
            for chrome_dir in chrome_dirs:
                try:
                    if os.path.exists(chrome_dir):
                        shutil.rmtree(chrome_dir, ignore_errors=True)
                        print(f"[INFO] Temizlendi: {chrome_dir}")
                except Exception as e:
                    print(f"[WARNING] Temizleme hatasi {chrome_dir}: {e}")
            
            print(f"[INFO] {len(chrome_dirs)} geçici Chrome dizini temizlendi")
    except Exception as e:
        print(f"[WARNING] Geçici dosya temizleme hatasi: {e}")

if __name__ == "__main__":
    main()
