import os
import json
import time
import random
import imaplib
import email
import re
import ssl
import glob
import threading
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.proxy import Proxy, ProxyType
import random
import time

# Ana dizindeki accounts klasörü - ÖNCE TANIMLA
ACCOUNTS_DIR = "config/accounts"
COOKIE_DIR = "config/configsub"
OUTPUT_FILE = "config/accounts.json"
MAX_WORKERS = 1  # Tek işlem ile çalıştır, daha güvenli

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

# Selenium ve webdriver manager'ı test et
try:
    from selenium import webdriver
    print("[SUCCESS] selenium basariyla import edildi")
except ImportError as e:
    print(f"[ERROR] selenium import hatasi: {e}")
    print("[INFO] Paket yukleniyor: pip install selenium")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium"])
    from selenium import webdriver
    print("[SUCCESS] selenium yuklendi ve import edildi")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    print("[SUCCESS] webdriver_manager basariyla import edildi")
except ImportError as e:
    print(f"[ERROR] webdriver_manager import hatasi: {e}")
    print("[INFO] Paket yukleniyor: pip install webdriver-manager")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "webdriver-manager"])
    from webdriver_manager.chrome import ChromeDriverManager
    print("[SUCCESS] webdriver_manager yuklendi ve import edildi")

# Accounts klasöründeki JSON dosyalarını kontrol et
json_files = glob.glob(os.path.join(ACCOUNTS_DIR, "*.json"))
print(f"[INFO] {ACCOUNTS_DIR} klasorunde {len(json_files)} JSON dosyasi bulundu:")
for file in json_files:
    print(f"  - {os.path.basename(file)}")

def human_like_wait(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def random_mouse_movement(driver):
    """Random fare hareketleri"""
    try:
        actions = ActionChains(driver)
        # Random koordinatlara fare hareketi
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        actions.move_by_offset(x, y)
        actions.perform()
        time.sleep(random.uniform(0.5, 1.5))
    except:
        pass

def human_like_typing(element, text):
    """İnsan gibi yavaş yazma"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

def random_scroll(driver):
    """Random scroll hareketleri"""
    try:
        scroll_amount = random.randint(100, 500)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
        time.sleep(random.uniform(0.5, 1.0))
    except:
        pass

def get_chromedriver_path():
    """
    ChromeDriver'ı yerel olarak bul, yoksa bir kez indir.
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
            print("[ERROR] ChromeDriver bulunamadi veya indirilemedi.")
            return None

        options = ChromeOptions()
        
        # Bot tespitini önlemek için ayarlar
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Headless modu ekle (Chrome gizli çalışsın)
        options.add_argument("--headless")
        
        # Boş disk alanı olan dizini kullan (/home/erayb/btc)
        import uuid
        temp_base_dir = "/home/erayb/btc/temp_chrome_data"
        os.makedirs(temp_base_dir, exist_ok=True)
        
        # Benzersiz user data directory oluştur
        unique_id = str(uuid.uuid4())[:8]
        user_data_dir = os.path.join(temp_base_dir, f"chrome_user_data_{unique_id}")
        os.makedirs(user_data_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={user_data_dir}")
        print(f"[INFO] Chrome user data directory: {user_data_dir}")
        
        # Disk alanı sorunlarını önlemek için ek ayarlar
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
        
        # Random user agent
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        # Proxy ayarları - Kapatıldı (sorun yaratıyor)
        # proxy_list = [
        #     "http://185.199.229.156:7492",
        #     "http://185.199.228.220:7492", 
        #     "http://185.199.231.45:7492",
        #     "http://188.74.210.207:6286",
        #     "http://188.74.183.10:8279",
        #     "http://188.74.210.21:6100",
        #     "http://45.155.68.129:8133",
        #     "http://154.85.124.51:5836",
        #     "http://45.8.106.59:8000",
        #     "http://103.149.162.194:80"
        # ]
        # # Random proxy seç
        # selected_proxy = random.choice(proxy_list)
        # options.add_argument(f"--proxy-server={selected_proxy}")
        # print(f"[INFO] Proxy kullaniliyor: {selected_proxy}")
        print(f"[INFO] Proxy kullanilmiyor - yerel baglanti")
        
        # Pencere boyutu
        options.add_argument("--window-size=1920,1080")
        
        # Ek güvenlik ayarları
        # options.add_argument("--disable-web-security")
        # options.add_argument("--allow-running-insecure-content")
        # options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Proxy authentication (eğer gerekirse)
        # options.add_argument("--proxy-auth=username:password")
        
        # Ek bot tespit önleme - Sadece gerekli olanlar
        # options.add_argument("--disable-blink-features")
        # options.add_argument("--disable-extensions")
        # options.add_argument("--disable-plugins")
        # options.add_argument("--disable-images")  # Hızlı yükleme için
        
        service = ChromeService(executable_path=chrome_path)
        driver = webdriver.Chrome(service=service, options=options)
        
        # JavaScript ile bot tespitini önle
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        print("[SUCCESS] Chrome basariyla baslatildi (headless mod)")
        return driver
    except Exception as e:
        print(f"[ERROR] Chrome baslatilamadi: {e}")
        return None

def check_existing_cookie(username):
    """Hesabın zaten cookie'si var mı kontrol et"""
    cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies.json")
    if os.path.exists(cookie_path):
        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
                if cookies and len(cookies) > 0:
                    print(f"[SUCCESS] {username} icin cookie zaten mevcut, atlaniyor")
                    return True
        except Exception as e:
            print(f"[WARNING] Cookie okuma hatasi ({username}): {e}")
    return False

def get_2fa_code_from_totp_secret(totp_secret):
    """totpSecret ile web sitesinden 2FA kodu al"""
    driver = None
    try:
        driver = setup_driver()
        if not driver:
            return None

        print(f"[INFO] TOTP Secret ile 2FA kodu aliniyor...")
        driver.get("https://tbkod.pages.dev/")
        human_like_wait(2, 3)

        totp_input = driver.find_element(By.XPATH, '//*[@id="2faSecret"]')
        totp_input.clear()
        totp_input.send_keys(totp_secret)
        human_like_wait(1, 2)

        btn = driver.find_element(By.XPATH, "//button[contains(., '2FA Kod Al')]")
        btn.click()
        human_like_wait(2, 3)

        code_el = driver.find_element(By.XPATH, '//*[@id="2faCode"]/h5/strong')
        code = code_el.text.strip()
        print(f"[SUCCESS] TOTP Secret ile 2FA kodu bulundu: {code}")
        driver.quit()
        return code
    except Exception as e:
        print(f"[ERROR] TOTP Secret ile 2FA kodu alinamadi: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return None

def get_email_content(email_message):
    """Email içeriğini farklı formatlardan okumaya çalış"""
    body = ""
    try:
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        body += part.get_payload(decode=True).decode('latin-1', errors='ignore')
                elif content_type == "text/html":
                    try:
                        html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        clean_text = re.sub(r'<[^>]+>', '', html_content)
                        body += clean_text
                    except:
                        pass
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = email_message.get_payload(decode=True).decode('latin-1', errors='ignore')
    except Exception as e:
        print(f"[WARNING] Email icerigi okuma hatasi: {e}")
    return body

def find_verification_code(text):
    """Farklı formatlarda doğrulama kodunu ara"""
    patterns = [
        r'\b\d{6}\b',  # 6 haneli kod
        r'\b\d{4}\b',  # 4 haneli kod
        r'\b\d{8}\b',  # 8 haneli kod
        r'verification code[:\s]*(\d{4,8})',
        r'code[:\s]*(\d{4,8})',
        r'kod[:\s]*(\d{4,8})',
        r'(\d{4,8})',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            longest_match = max(matches, key=len)
            if len(longest_match) >= 4:
                return longest_match
    return None

def get_2fa_code_from_email_imap_advanced(email_address, email_password):
    """Gelişmiş IMAP ile email'den 2FA kodunu al"""
    imap_servers = [
        ("outlook.office365.com", 993),
        ("outlook.office365.com", 143),
        ("smtp-mail.outlook.com", 993),
        ("imap-mail.outlook.com", 993),
        ("imap-mail.outlook.com", 143),
    ]
    for server, port in imap_servers:
        try:
            print(f"[INFO] IMAP sunucusu deneniyor: {server}:{port}")
            if port == 993:
                mail = imaplib.IMAP4_SSL(server, port)
            else:
                mail = imaplib.IMAP4(server, port)
                mail.starttls()
            mail.login(email_address, email_password)
            mail.select("INBOX")
            search_criteria = [
                "ALL",
                "UNSEEN",
                "FROM twitter.com",
                "FROM x.com",
                "SUBJECT verification",
                "SUBJECT code",
                "SUBJECT twitter",
                "SUBJECT x.com",
                "BODY verification",
                "BODY code",
            ]
            for criteria in search_criteria:
                try:
                    print(f"[INFO] Arama kriteri: {criteria}")
                    _, messages = mail.search(None, criteria)
                    email_list = messages[0].split()
                    if not email_list:
                        continue
                    for i in range(min(20, len(email_list))):
                        email_id = email_list[-(i+1)]
                        try:
                            _, msg_data = mail.fetch(email_id, "(RFC822)")
                            email_body = msg_data[0][1]
                            email_message = email.message_from_bytes(email_body)
                            subject = email_message["subject"] or ""
                            from_addr = email_message["from"] or ""
                            relevant_keywords = [
                                "twitter", "x.com", "verification", "code", "kod",
                                "doğrulama", "confirm", "security", "güvenlik"
                            ]
                            is_relevant = any(keyword in subject.lower() or keyword in from_addr.lower()
                                              for keyword in relevant_keywords)
                            if is_relevant:
                                print(f"[INFO] Ilgili email bulundu: {subject}")
                                body = get_email_content(email_message)
                                print(f"[INFO] Email icerigi uzunlugu: {len(body)} karakter")
                                code = find_verification_code(body)
                                if code:
                                    print(f"[SUCCESS] IMAP ile 2FA kodu bulundu: {code}")
                                    mail.close()
                                    mail.logout()
                                    return code
                                else:
                                    print("[ERROR] Bu email'de kod bulunamadi")
                        except Exception as e:
                            print(f"[WARNING] Email okuma hatasi: {e}")
                            continue
                except Exception as e:
                    print(f"[WARNING] Arama kriteri hatasi ({criteria}): {e}")
                    continue
            mail.close()
            mail.logout()
        except Exception as e:
            print(f"[ERROR] IMAP sunucusu hatasi ({server}:{port}): {e}")
            continue
    print("[ERROR] Hicbir IMAP sunucusundan kod alinamadi")
    return None

def get_2fa_code_from_email_web(email_address, email_password):
    """tbkod.pages.dev sitesinden email ile 2FA kodunu al"""
    driver = None
    try:
        driver = setup_driver()
        if not driver:
            return None
        print(f"[INFO] Web sitesinden 2FA kodu aliniyor: {email_address}")
        driver.get("https://tbkod.pages.dev/")
        human_like_wait(2, 3)
        email_input = driver.find_element(By.XPATH, '//*[@id="emailAddress"]')
        email_input.clear()
        email_input.send_keys(email_address)
        human_like_wait(1, 2)
        password_input = driver.find_element(By.XPATH, '//*[@id="emailPassword"]')
        password_input.clear()
        password_input.send_keys(email_password)
        human_like_wait(1, 2)
        email_btn = driver.find_element(By.XPATH, '/html/body/div/div[1]/div[2]/div/div[3]')
        email_btn.click()
        human_like_wait(3, 5)
        try:
            code_element = driver.find_element(By.XPATH, "//h5/strong")
            code = code_element.text.strip()
            print(f"[SUCCESS] Web sitesinden 2FA kodu bulundu: {code}")
            driver.quit()
            return code
        except:
            print("[ERROR] Web sitesinden kod elementi bulunamadi")
            driver.quit()
            return None
    except Exception as e:
        print(f"[ERROR] Web sitesinden 2FA kodu alinamadi: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return None

def get_2fa_code(totp_secret=None, email_address=None, email_password=None):
    """Sırayla 2FA kodu almayı dene: 1. TOTP Secret, 2. Email Web, 3. IMAP"""
    print(f"[INFO] 2FA kodu aliniyor...")
    if totp_secret and totp_secret.strip():
        print("[INFO] TOTP Secret ile deneniyor...")
        code = get_2fa_code_from_totp_secret(totp_secret)
        if code:
            return code
    if email_address and email_password:
        print("[INFO] Web sitesinden email ile deneniyor...")
        code = get_2fa_code_from_email_web(email_address, email_password)
        if code:
            return code
    if email_address and email_password:
        print("[INFO] IMAP ile deneniyor...")
        code = get_2fa_code_from_email_imap_advanced(email_address, email_password)
        if code:
            return code
    print("[ERROR] Hicbir yontemle 2FA kodu alinamadi")
    return None

def check_if_2fa_needed(driver):
    """2FA gerekli mi kontrol et"""
    try:
        selectors = [
            (By.NAME, "text"),
            (By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']"),
            (By.CSS_SELECTOR, "input[placeholder*='kod']"),
            (By.CSS_SELECTOR, "input[placeholder*='code']"),
            (By.CSS_SELECTOR, "input[type='text']")
        ]
        for selector_type, selector_value in selectors:
            try:
                code_input = driver.find_element(selector_type, selector_value)
                print(f"[SUCCESS] 2FA input alani bulundu: {selector_type} = {selector_value}")
                return True, code_input
            except:
                continue
        return False, None
    except Exception as e:
        print(f"[WARNING] 2FA kontrol sirasinda hata: {e}")
        return False, None

def login_and_save_cookies(username, password, totp_secret=None, email_address=None, email_password=None, driver=None):
    # Her hesap için yeni Chrome instance kullan
    print(f"[INFO] {username} - Chrome baslatiliyor...")
    driver = setup_driver()
    if not driver:
        print(f"[ERROR] {username} - Chrome baslatilamadi")
        return False, ""
    
    print(f"[INFO] {username} - Chrome baslatildi, Twitter'a gidiliyor...")
    try:
        driver.get("https://twitter.com/login")
        human_like_wait(3, 5)
        
        # Random fare hareketleri
        random_mouse_movement(driver)
        
        print(f"[INFO] Kullanici adi giriliyor: {username}")
        user_input = driver.find_element(By.NAME, "text")
        user_input.click()
        human_like_wait(0.5, 1.0)
        human_like_typing(user_input, username)
        human_like_wait(1, 2)
        user_input.send_keys(Keys.RETURN)
        human_like_wait(3, 5)
        
        # Random scroll
        random_scroll(driver)
        
        print(f"[INFO] Sifre giriliyor... ({username})")
        pass_input = driver.find_element(By.NAME, "password")
        pass_input.click()
        human_like_wait(0.5, 1.0)
        human_like_typing(pass_input, password)
        human_like_wait(1, 2)
        pass_input.send_keys(Keys.RETURN)
        human_like_wait(5, 8)
        current_url = driver.current_url
        print(f"[INFO] Sayfa kontrol ediliyor: {current_url} ({username})")
        if ("home" in current_url or "notifications" in current_url or
                "twitter.com/home" in current_url or "x.com/home" in current_url):
            print(f"[SUCCESS] Giris basarili, 2FA gerekmiyor ({username})")
        else:
            if totp_secret or (email_address and email_password):
                print(f"[INFO] 2FA gerekli mi kontrol ediliyor... ({username})")
                needs_2fa, code_input = check_if_2fa_needed(driver)
                if needs_2fa and code_input:
                    print(f"[INFO] 2FA gerekli, kod aliniyor... ({username})")
                    code = get_2fa_code(totp_secret, email_address, email_password)
                    if code:
                        print(f"[SUCCESS] 2FA kodu bulundu: {code} ({username})")
                        code_input.click()
                        human_like_wait(0.5, 1.0)
                        code_input.clear()
                        human_like_typing(code_input, code)
                        human_like_wait(1, 2)
                        code_input.send_keys(Keys.RETURN)
                        human_like_wait(3, 5)
                        print(f"[SUCCESS] 2FA kodu girildi, sayfa kontrol ediliyor: {driver.current_url} ({username})")
                    else:
                        print(f"[ERROR] 2FA kodu alinamadi. ({username})")
                        driver.quit()
                        return False, ""
                else:
                    print(f"[INFO] 2FA gerekmiyor veya input alani bulunamadi ({username})")
        # Random scroll hareketleri
        for _ in range(random.randint(2, 4)):
            random_scroll(driver)
            random_mouse_movement(driver)
            human_like_wait(1, 2)
        current_url = driver.current_url
        print(f"[INFO] Final URL: {current_url} ({username})")
        if ("home" in current_url or "notifications" in current_url or
                "twitter.com/home" in current_url or "x.com/home" in current_url):
            cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies.json")
            with open(cookie_path, "w", encoding="utf-8") as f:
                json.dump(driver.get_cookies(), f, indent=2)
            print(f"[SUCCESS] Giris basarili, cookie kaydedildi: {cookie_path} ({username})")
            driver.quit()  # Her başarılı girişten sonra Chrome'u kapat
            # Geçici dosyaları temizle
            cleanup_single_temp_files(username)
            return True, f"config/configsub/{username}_cookies.json"
        else:
            print(f"[ERROR] Giris basarisiz, URL: {current_url} ({username})")
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid='error']")
                for error in error_elements:
                    print(f"[ERROR] Hata mesaji: {error.text} ({username})")
            except:
                pass
            driver.quit()  # Başarısız girişten sonra da Chrome'u kapat
            # Geçici dosyaları temizle
            cleanup_single_temp_files(username)
            return False, ""
    except Exception as e:
        print(f"[ERROR] Genel hata: {e} ({username})")
        try:
            driver.quit()
        except:
            pass
        # Geçici dosyaları temizle
        cleanup_single_temp_files(username)
        return False, ""

def process_account(account_data):
    """Tek bir hesabı işle"""
    username = account_data.get("username")
    password = account_data.get("password")
    totp_secret = account_data.get("totpSecret")
    email_address = account_data.get("emailAddress")
    email_password = account_data.get("emailPassword")
    
    print(f"[INFO] {username} - Hesap bilgileri kontrol ediliyor...")
    
    if check_existing_cookie(username):
        print(f"[INFO] {username} - Cookie zaten mevcut, atlaniyor")
        return {
            "account_id": username,
            "is_active": True,
            "cookie_file_path": f"config/configsub/{username}_cookies.json",
            "skipped": True
        }
    
    print(f"[INFO] {username} - Yeni giris deneniyor...")
    print(f"[INFO] {username} - 2FA durumu: {'Var' if totp_secret or (email_address and email_password) else 'Yok'}")
    
    try:
        success, cookie_path = login_and_save_cookies(username, password, totp_secret, email_address, email_password)
    except Exception as e:
        print(f"[ERROR] {username} - Hesap isleme hatasi: {e}")
        success, cookie_path = False, ""
    account = {
        "account_id": username,
        "is_active": success,
        "cookie_file_path": cookie_path if success else "",
        "skipped": False
    }
    if success:
        account.update({
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
        })
    print(f"[{'SUCCESS' if success else 'ERROR'}] {username} {'(cookie kaydedildi)' if success else '(basarisiz)'}")
    return account

def get_all_json_files():
    """Sadece accounts klasöründeki tüm JSON dosyalarını oku"""
    all_accounts = []
    json_files = glob.glob(os.path.join(ACCOUNTS_DIR, "*.json"))
    print(f"[INFO] {ACCOUNTS_DIR} klasorunde {len(json_files)} JSON dosyasi bulundu")
    
    for file_path in json_files:
        try:
            print(f"[INFO] Dosya okunuyor: {os.path.basename(file_path)}")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            file_accounts = 0
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        username = entry.get("username") or entry.get("account_id")
                        password = entry.get("password")
                        totp_secret = entry.get("totpSecret")
                        email_address = entry.get("emailAddress")
                        email_password = entry.get("emailPassword")
                        if username and password:
                            all_accounts.append({
                                "username": username,
                                "password": password,
                                "totpSecret": totp_secret,
                                "emailAddress": email_address,
                                "emailPassword": email_password
                            })
                            file_accounts += 1
            elif isinstance(data, dict):
                username = data.get("username") or data.get("account_id")
                password = data.get("password")
                totp_secret = data.get("totpSecret")
                email_address = data.get("emailAddress")
                email_password = data.get("emailPassword")
                if username and password:
                    all_accounts.append({
                        "username": username,
                        "password": password,
                        "totpSecret": totp_secret,
                        "emailAddress": email_address,
                        "emailPassword": email_password
                    })
                    file_accounts += 1
            
            print(f"[INFO] {os.path.basename(file_path)} - {file_accounts} hesap okundu")
            
        except Exception as e:
            print(f"[ERROR] Dosya okuma hatasi ({os.path.basename(file_path)}): {e}")
            continue
    
    print(f"[SUCCESS] Toplam {len(all_accounts)} hesap bulundu")
    return all_accounts

def main():
    """Ana fonksiyon - Flask'tan çağrılabilir"""
    print("=" * 80)
    print("[INFO] TWITTER HESAP EKLEME ISLEMI BASLADI")
    print("=" * 80)
    
    print(f"[INFO] {ACCOUNTS_DIR} klasorundeki JSON dosyalarindan hesaplar okunuyor...")
    base_accounts = get_all_json_files()
    if not base_accounts:
        print(f"[ERROR] {ACCOUNTS_DIR} klasorunde hic hesap bulunamadi!")
        print(f"[INFO] Lutfen JSON dosyalarinizi {ACCOUNTS_DIR} klasorune koyun")
        return False
    
    print("-" * 80)
    print("[INFO] HESAP DETAYLARI:")
    print(f"[INFO] Toplam hesap sayisi: {len(base_accounts)}")
    print(f"[INFO] Paralel islem sayisi: {MAX_WORKERS}")
    print("-" * 80)
    
    accounts = []
    skipped_count = 0
    success_count = 0
    failed_count = 0
    current_count = 0
    
    print("[INFO] HESAP ISLEME BASLADI...")
    print("-" * 80)
    
    # Her hesap için ayrı Chrome instance kullan
    for account in base_accounts:
        current_count += 1
        username = account.get("username", "Bilinmeyen")
        
        print(f"[INFO] [{current_count}/{len(base_accounts)}] {username} isleniyor...")
        
        try:
            account_result = process_account(account)
            accounts.append(account_result)
            
            if account_result.get("skipped", False):
                skipped_count += 1
                print(f"[SUCCESS] [{current_count}/{len(base_accounts)}] {username} - ATLANDI (zaten cookie var)")
            elif account_result.get("is_active", False):
                success_count += 1
                print(f"[SUCCESS] [{current_count}/{len(base_accounts)}] {username} - BASARILI (cookie kaydedildi)")
            else:
                failed_count += 1
                print(f"[ERROR] [{current_count}/{len(base_accounts)}] {username} - BASARISIZ")
                
        except Exception as e:
            print(f"[ERROR] [{current_count}/{len(base_accounts)}] {username} - HATA: {e}")
            failed_count += 1
    
    # Sonuçları kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)
    
    print("-" * 80)
    print("[INFO] ISLEM TAMAMLANDI!")
    print("=" * 80)
    print("[INFO] DETAYLI OZET:")
    print(f"[INFO] Toplam hesap sayisi: {len(base_accounts)}")
    print(f"[INFO] Basarili giris: {success_count}")
    print(f"[INFO] Atlanan (zaten cookie var): {skipped_count}")
    print(f"[INFO] Basarisiz giris: {failed_count}")
    print(f"[INFO] Basari orani: %{((success_count + skipped_count) / len(base_accounts) * 100):.1f}")
    print(f"[INFO] Cikti dosyasi: {OUTPUT_FILE}")
    
    if success_count > 0:
        print(f"[SUCCESS] {success_count} hesap basariyla cookie kaydedildi")
    if skipped_count > 0:
        print(f"[INFO] {skipped_count} hesap zaten cookie'ye sahip oldugu icin atlandi")
    if failed_count > 0:
        print(f"[ERROR] {failed_count} hesap basarisiz oldu")
    
    print("=" * 80)
    
    # Geçici dosyaları temizle
    cleanup_temp_files()
    
    return True

def cleanup_single_temp_files(username):
    """Tek bir hesap için geçici Chrome dosyalarını temizle"""
    try:
        import shutil
        import glob
        
        temp_base_dir = "/home/erayb/btc/temp_chrome_data"
        if os.path.exists(temp_base_dir):
            chrome_dirs = glob.glob(os.path.join(temp_base_dir, "chrome_user_data_*"))
            
            for chrome_dir in chrome_dirs:
                try:
                    if os.path.exists(chrome_dir):
                        shutil.rmtree(chrome_dir, ignore_errors=True)
                        print(f"[INFO] {username} - Geçici dosya temizlendi: {chrome_dir}")
                except Exception as e:
                    print(f"[WARNING] {username} - Temizleme hatasi {chrome_dir}: {e}")
    except Exception as e:
        print(f"[WARNING] {username} - Geçici dosya temizleme hatasi: {e}")

def cleanup_temp_files():
    """Geçici Chrome dosyalarını temizle"""
    try:
        import shutil
        import glob
        
        temp_base_dir = "/home/erayb/btc/temp_chrome_data"
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