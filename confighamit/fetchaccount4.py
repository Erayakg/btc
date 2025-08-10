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

def setup_chrome_driver():
    """Chrome driver setup - Gelişmiş anti-detection ile"""
    try:
        chrome_path = get_chromedriver_path()
        if not chrome_path:
            print("[ERROR] ChromeDriver bulunamadi.")
            return None

        options = ChromeOptions()
        
        # Yeni profil kullan - Takılma sorununu önlemek için
        import tempfile
        import platform
        if platform.system() == "Windows":
            # Geçici profil dizini oluştur
            temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
            options.add_argument(f"--user-data-dir={temp_dir}")
            print(f"[INFO] Yeni Chrome profili kullaniliyor: {temp_dir}")
        else:
            # Linux/Mac için
            temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
            options.add_argument(f"--user-data-dir={temp_dir}")
            print(f"[INFO] Yeni Chrome profili kullaniliyor: {temp_dir}")
        
        # Gelişmiş bot tespitini önlemek için ayarlar
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")  # Hızlı yükleme için
        
        # Automation işaretlerini gizle
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Chrome sürümü spoof
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-default-apps")
        
        # Pencere boyutu - gerçek kullanıcı gibi
        window_sizes = [
            "1366,768", "1920,1080", "1440,900", "1536,864", "1600,900"
        ]
        options.add_argument(f"--window-size={random.choice(window_sizes)}")
        
        # Güncel ve gerçek user agent'lar
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        # Platform ve dil ayarları
        options.add_argument("--lang=tr-TR,tr,en-US,en")
        options.add_argument("--accept-lang=tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7")
        
        service = ChromeService(executable_path=chrome_path)
        driver = webdriver.Chrome(service=service, options=options)
        
        # JavaScript ile webdriver özelliklerini gizle
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array")
        driver.execute_script("delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise")
        driver.execute_script("delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol")
        
        # Navigator özelliklerini düzenle
        driver.execute_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)
        
        driver.execute_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['tr-TR', 'tr', 'en-US', 'en']
            });
        """)
        
        print("[SUCCESS] Chrome basariyla baslatildi (gelişmiş anti-detection ile)")
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

def simulate_human_behavior(driver):
    """İnsan benzeri davranış simule et"""
    try:
        # Mouse hareketlerini simule et
        actions = ActionChains(driver)
        
        # Rastgele koordinatlarda mouse hareketi
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            actions.move_by_offset(x, y)
            time.sleep(random.uniform(0.1, 0.3))
        
        actions.perform()
        
        # Sayfa scrolling
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/4);")
        time.sleep(random.uniform(0.5, 1.0))
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(random.uniform(0.3, 0.7))
        
    except Exception as e:
        print(f"[INFO] İnsan benzeri davranış simule edilemedi: {e}")

def wait_for_page_load(driver, timeout=10):
    """Sayfanın tamamen yüklenmesini bekle"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        # Ekstra bekleme
        time.sleep(random.uniform(1, 2))
        return True
    except TimeoutException:
        print("[WARNING] Sayfa yükleme zaman aşımı")
        return False
    except Exception as e:
        print(f"[WARNING] Sayfa yükleme kontrol hatası: {e}")
        return False

def automatic_login(driver, account):
    """Otomatik Twitter login - İnsan benzeri davranış ile"""
    try:
        username = account['username']
        password = account['password']
        email = account['email']
        
        print(f"[INFO] {username} icin otomatik login baslatiliyor...")
        
        # Twitter login sayfasına git
        print("[INFO] Twitter login sayfasina gidiliyor...")
        driver.get("https://twitter.com/login")
        
        # Sayfanın yüklenmesini bekle
        wait_for_page_load(driver)
        
        # İnsan benzeri davranış simule et
        simulate_human_behavior(driver)
        
        # Rastgele bekleme süresi (2-4 saniye)
        wait_time = random.uniform(2, 4)
        time.sleep(wait_time)
        
        # Sayfanın yüklenmesini bekle
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
        except TimeoutException:
            print("[ERROR] Login sayfası yüklenemedi")
            return False
        
        # Username girişi - İnsan benzeri
        try:
            print(f"[INFO] Username giriliyor: {username}")
            username_input = driver.find_element(By.NAME, "text")
            
            # Element'e odaklan
            username_input.click()
            time.sleep(random.uniform(0.3, 0.7))
            
            # Mevcut içeriği temizle
            username_input.clear()
            time.sleep(random.uniform(0.2, 0.5))
            
            # İnsan benzeri typing
            for char in username:
                username_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))  # Her karakter için rastgele gecikme
            
            # Enter'dan önce kısa bekle
            time.sleep(random.uniform(0.5, 1.0))
            username_input.send_keys(Keys.RETURN)
            
            # Sayfanın yüklenmesini bekle
            time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            print(f"[ERROR] Username giriş hatasi: {e}")
            return False
        
        # Eğer telefon/email doğrulaması gelirse
        try:
            # Email/telefon input'u var mı kontrol et (unusual activity için)
            additional_input = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
            
            if additional_input:
                print("[INFO] Ek dogrulama talep ediliyor - Email giriliyor...")
                additional_input.click()
                time.sleep(random.uniform(0.3, 0.7))
                additional_input.clear()
                
                # Email'i insan benzeri şekilde gir
                for char in email:
                    additional_input.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
                
                time.sleep(random.uniform(0.5, 1.0))
                additional_input.send_keys(Keys.RETURN)
                time.sleep(random.uniform(2, 4))
                
        except TimeoutException:
            print("[INFO] Ek dogrulama gerekmiyor")
        except Exception as e:
            print(f"[INFO] Ek dogrulama kontrol hatasi: {e}")
        
        # Password girişi - İnsan benzeri
        try:
            print("[INFO] Password giriliyor...")
            password_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            
            # Element'e odaklan
            password_input.click()
            time.sleep(random.uniform(0.3, 0.7))
            
            # Mevcut içeriği temizle
            password_input.clear()
            time.sleep(random.uniform(0.2, 0.5))
            
            # İnsan benzeri typing
            for char in password:
                password_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))  # Her karakter için rastgele gecikme
            
            # Enter'dan önce kısa bekle
            time.sleep(random.uniform(0.5, 1.0))
            password_input.send_keys(Keys.RETURN)
            
            # Login işleminin tamamlanmasını bekle
            time.sleep(random.uniform(3, 6))
            
        except Exception as e:
            print(f"[ERROR] Password giriş hatasi: {e}")
            return False
        
        # Bot doğrulaması için uzun bekleme
        print(f"[INFO] {username} icin login durumu kontrol ediliyor...")
        print("[INFO] Eğer bot doğrulaması gelirse manuel olarak geçirin!")
        print("[INFO] Login tamamlandıktan sonra bu pencereyi kapatmayın!")
        
        # Sürekli login durumunu kontrol et
        max_wait_time = 120  # 2 dakika maksimum bekleme
        check_interval = 3   # Her 3 saniyede bir kontrol et
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                current_url = driver.current_url
                
                # Bot doğrulaması kontrolleri
                if any(keyword in current_url.lower() for keyword in ["challenge", "verify", "captcha", "suspicious", "confirm"]):
                    print(f"[WARNING] {username} - Bot doğrulaması tespit edildi! Manuel olarak geçirin...")
                    print(f"[INFO] URL: {current_url}")
                elif "login" in current_url or "signin" in current_url:
                    print(f"[INFO] {username} - Hala login sayfasında...")
                else:
                    # Login başarılı mı kontrol et
                    if check_login_status(driver):
                        print(f"[SUCCESS] {username} icin login basarili!")
                        return True
                
                time.sleep(check_interval)
                elapsed_time += check_interval
                
                # Progress bilgisi
                if elapsed_time % 15 == 0:  # Her 15 saniyede bir bilgi ver
                    remaining_time = max_wait_time - elapsed_time
                    print(f"[INFO] {username} - Bekleniyor... Kalan süre: {remaining_time} saniye")
                
            except Exception as e:
                print(f"[WARNING] Login kontrol hatasi: {e}")
                time.sleep(check_interval)
                elapsed_time += check_interval
        
        print(f"[ERROR] {username} icin login zaman aşımı (2 dakika)")
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
    driver = setup_chrome_driver()
    if not driver:
        print("[ERROR] Chrome baslatilamadi")
        return False
    
    try:
        # Kısa bekleme - driver'ın tamamen hazır olması için
        time.sleep(random.uniform(1, 2))
        
        # Otomatik login
        if automatic_login(driver, account):
            print(f"[SUCCESS] {account['username']} icin login basarili! Cerezler kaydediliyor...")
            
            # Başarılı login sonrası kısa bekleme
            time.sleep(random.uniform(2, 4))
            
            # Çerezleri kaydet
            if save_cookies(driver, account['username']):
                print(f"[SUCCESS] {account['username']} icin cerezler basariyla kaydedildi!")
                
                # accounts.json dosyasını güncelle
                update_accounts_json(account['username'])
                
                print(f"[INFO] {account['username']} icin islem tamamlandi!")
                print("[INFO] Chrome penceresi manuel olarak kapatilabilir")
                
                # Başarılı hesap için driver'ı kapat
                try:
                    driver.quit()
                    print(f"[INFO] {account['username']} icin Chrome penceresi kapatildi")
                except:
                    pass
                
                return True
            else:
                print("[ERROR] Cerezler kaydedilemedi")
                return False
        else:
            print(f"[ERROR] {account['username']} icin login basarisiz")
            print("[INFO] Chrome penceresi açık bırakıldı - Manuel kontrol için")
            return False
            
    except Exception as e:
        print(f"[ERROR] Genel hata: {e}")
        return False
    except KeyboardInterrupt:
        print(f"[INFO] {account['username']} işlemi kullanıcı tarafından iptal edildi")
        try:
            driver.quit()
        except:
            pass
        return False

def main():
    """Ana fonksiyon - Hesapları işle"""
    print("=" * 80)
    print("[INFO] CHROME ILE OTOMATIK TWITTER LOGIN ARACI")
    print("=" * 80)
    print(f"[INFO] Bu araç {ACCOUNTS_FILE} dosyasından hesapları okur")
    print("[INFO] Her hesap için otomatik Twitter login yapar")
    print("[INFO] Chrome penceresi görünür modda açılır")
    print("[INFO] Yeni Chrome profili kullanılır - Takılma sorunu önlenir")
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
                time.sleep(1)  # Sadece 1 saniye bekle
        
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

if __name__ == "__main__":
    main()

