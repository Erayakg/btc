import os
import json
import time
import random
import glob
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
import uuid

# Ana dizindeki accounts klasörü
ACCOUNTS_DIR = "confighamit/accounts"
COOKIE_DIR = "confighamit/configsub"
OUTPUT_FILE = "confighamit/accounts.json"

# Çalışma dizinini ana dizine değiştir
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)

print(f"[INFO] Calisma dizini: {os.getcwd()}")
print(f"[INFO] Accounts dizini: {ACCOUNTS_DIR}")
print(f"[INFO] Cookie dizini: {COOKIE_DIR}")
print(f"[INFO] Cikti dosyasi: {OUTPUT_FILE}")

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

def setup_visible_driver():
    """Görünür Chrome driver setup - Manuel login için"""
    try:
        chrome_path = get_chromedriver_path()
        if not chrome_path:
            print("[ERROR] ChromeDriver bulunamadi.")
            return None

        options = ChromeOptions()
        
        # Görünür mod için headless'i kapat
        # options.add_argument("--headless")  # Bu satırı kaldırıyoruz
        
       
        # Bot tespitini önlemek için ayarlar
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        # Windows için geçici dizin
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="chrome_user_data_")
        options.add_argument(f"--user-data-dir={temp_dir}")
        print(f"[INFO] Chrome user data directory: {temp_dir}")
        
        # Pencere boyutu
        options.add_argument("--window-size=1200,800")
        
        # Random user agent
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]
        options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        service = ChromeService(executable_path=chrome_path)
        driver = webdriver.Chrome(service=service, options=options)
        
        # JavaScript ile bot tespitini önle
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        print("[SUCCESS] Chrome basariyla baslatildi (gorunur mod)")
        return driver
    except Exception as e:
        print(f"[ERROR] Chrome baslatilamadi: {e}")
        return None

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

def wait_for_manual_login(driver):
    """Manuel login için bekle - 15 saniyede bir kontrol et"""
    print("[INFO] Manuel login icin bekleniyor...")
    print("[INFO] Lutfen Twitter'da login olun ve ana sayfaya gidin")
    print("[INFO] Login tamamlandiktan sonra bu pencereyi kapatmayin!")
    
    while True:
        try:
            if check_login_status(driver):
                print("[SUCCESS] Login tespit edildi!")
                return True
            
            # Her 15 saniyede bir kontrol et
            time.sleep(15)
            
        except Exception as e:
            print(f"[WARNING] Login kontrol hatasi: {e}")
            time.sleep(15)

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

def manual_login_process():
    """Manuel login süreci - Tek hesap için"""
    print("=" * 80)
    print("[INFO] MANUEL TWITTER LOGIN ISLEMI BASLADI")
    print("=" * 80)
    
    # Kullanıcıdan username al (baştan)
    print("[INPUT] Bu hesabin Twitter kullanici adini girin: ", end="", flush=True)
    username = input().strip()
    if not username:
        print("[ERROR] Kullanici adi bos olamaz")
        return False, ""
    
    print(f"[INFO] {username} icin login baslatiliyor...")
    
    # Chrome'u başlat
    driver = setup_visible_driver()
    if not driver:
        print("[ERROR] Chrome baslatilamadi")
        return False, ""
    
    try:
        # Twitter login sayfasına git
        print("[INFO] Twitter login sayfasina gidiliyor...")
        driver.get("https://twitter.com/login")
        time.sleep(3)
        
        print("[INFO] Chrome penceresi acildi!")
        print("[INFO] Lutfen Twitter'da login olun:")
        print("  1. Email/kullanici adinizi girin")
        print("  2. Sifrenizi girin")
        print("  3. 2FA varsa kodunuzu girin")
        print("  4. Ana sayfaya gidin")
        print("[INFO] Login tamamlandiktan sonra bu pencereyi kapatmayin!")
        
        # Manuel login için bekle
        if wait_for_manual_login(driver):
            print("[SUCCESS] Login basarili! Cerezler kaydediliyor...")
            
            # Çerezleri kaydet
            if save_cookies(driver, username):
                print(f"[SUCCESS] {username} icin cerezler basariyla kaydedildi!")
                
                # accounts.json dosyasını güncelle
                update_accounts_json(username)
                
                return True, username
            else:
                print("[ERROR] Cerezler kaydedilemedi")
                return False, ""
        else:
            print("[ERROR] Login tamamlanmadi")
            return False, ""
            
    except Exception as e:
        print(f"[ERROR] Genel hata: {e}")
        return False, ""
    finally:
        # Chrome'u otomatik kapat
        try:
            driver.quit()
            print("[INFO] Chrome otomatik kapatildi")
        except:
            pass

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

def main():
    """Ana fonksiyon - Sürekli hesap ekleme"""
    print("=" * 80)
    print("[INFO] MANUEL TWITTER LOGIN ARACI - SUREKLI MOD")
    print("=" * 80)
    print("[INFO] Bu araç Chrome'u görünür halde açar ve Twitter'da manuel login yapmanızı sağlar")
    print("[INFO] Login tamamlandıktan sonra çerezler otomatik olarak kaydedilir")
    print("[INFO] Her hesap için yeni Chrome penceresi açılır")
    print("[INFO] Çıkmak için 'q' yazın veya Ctrl+C basın")
    print("=" * 80)
    
    added_accounts = []
    total_attempts = 0
    
    try:
        while True:
            total_attempts += 1
            print(f"\n[INFO] HESAP #{total_attempts} - Yeni Chrome penceresi açılıyor...")
            
            success, username = manual_login_process()
            
            if success and username:
                added_accounts.append(username)
                print("=" * 80)
                print(f"[SUCCESS] HESAP #{total_attempts} BASARILI: {username}")
                print(f"[INFO] Toplam başarılı hesap: {len(added_accounts)}")
                print("=" * 80)
            else:
                print("=" * 80)
                print(f"[ERROR] HESAP #{total_attempts} BASARISIZ")
                print("=" * 80)
            
            # Otomatik olarak devam et (sadece Ctrl+C ile çıkabilir)
            print("\n[INFO] 3 saniye sonra yeni hesap için Chrome açılacak...")
            time.sleep(3)
        
        # Özet
        print("\n" + "=" * 80)
        print("[INFO] ISLEM TAMAMLANDI!")
        print("=" * 80)
        print(f"[INFO] Toplam deneme: {total_attempts}")
        print(f"[INFO] Başarılı hesap: {len(added_accounts)}")
        if added_accounts:
            print(f"[INFO] Eklenen hesaplar: {', '.join(added_accounts)}")
        print("=" * 80)
        
        return len(added_accounts) > 0
        
    except KeyboardInterrupt:
        print("\n[INFO] Kullanıcı tarafindan iptal edildi")
        return False
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        return False

if __name__ == "__main__":
    main()
