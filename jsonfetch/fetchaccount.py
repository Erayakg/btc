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
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

# Sadece aynı dizindeki accounts klasörü
ACCOUNTS_DIR = "accounts"
COOKIE_DIR = "config"
OUTPUT_FILE = "accounts.json"
MAX_WORKERS = 1  # Tek işlem ile çalıştır, daha güvenli

# accounts klasörünü oluştur
os.makedirs(ACCOUNTS_DIR, exist_ok=True)
os.makedirs(COOKIE_DIR, exist_ok=True)

def human_like_wait(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def get_geckodriver_path():
    """
    GeckoDriver'ı yerel olarak bul, yoksa bir kez indir.
    """
    # Önce manuel/geçerli bir yol dene
    local_paths = [
        os.path.join(os.getcwd(), "geckodriver.exe"),
        os.path.join(os.getcwd(), "geckodriver"),
        "/usr/local/bin/geckodriver",
        "/usr/bin/geckodriver"
    ]
    for path in local_paths:
        if os.path.exists(path):
            return path

    # Eğer bulamazsan webdriver_manager ile indir
    try:
        from webdriver_manager.firefox import GeckoDriverManager
        gecko_path = GeckoDriverManager().install()
        return gecko_path
    except Exception as e:
        print(f"❌ GeckoDriver indirilemedi: {e}")
        return None

def setup_driver():
    """Basitleştirilmiş Firefox driver setup"""
    try:
        gecko_path = get_geckodriver_path()
        if not gecko_path:
            print("❌ GeckoDriver bulunamadı veya indirilemedi.")
            return None

        options = FirefoxOptions()
        # options.add_argument("--headless")  # Headless modu açmak için bu satırı aktif edin!
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference("useAutomationExtension", False)
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("media.volume_scale", "0.0")

        service = FirefoxService(executable_path=gecko_path)
        driver = webdriver.Firefox(service=service, options=options)
        print("✅ Firefox başarıyla başlatıldı")
        return driver
    except Exception as e:
        print(f"❌ Firefox başlatılamadı: {e}")
        return None

def check_existing_cookie(username):
    """Hesabın zaten cookie'si var mı kontrol et"""
    cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies.json")
    if os.path.exists(cookie_path):
        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
                if cookies and len(cookies) > 0:
                    print(f"✅ {username} için cookie zaten mevcut, atlanıyor")
                    return True
        except:
            pass
    return False

def get_2fa_code_from_totp_secret(totp_secret):
    """totpSecret ile web sitesinden 2FA kodu al"""
    driver = None
    try:
        driver = setup_driver()
        if not driver:
            return None

        print(f"🔐 TOTP Secret ile 2FA kodu alınıyor...")
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
        print(f"✅ TOTP Secret ile 2FA kodu bulundu: {code}")
        driver.quit()
        return code
    except Exception as e:
        print(f"❌ TOTP Secret ile 2FA kodu alınamadı: {e}")
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
        print(f"⚠️ Email içeriği okuma hatası: {e}")
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
            print(f"🔍 IMAP sunucusu deneniyor: {server}:{port}")
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
                    print(f"🔍 Arama kriteri: {criteria}")
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
                                print(f"📧 İlgili email bulundu: {subject}")
                                body = get_email_content(email_message)
                                print(f" Email içeriği uzunluğu: {len(body)} karakter")
                                code = find_verification_code(body)
                                if code:
                                    print(f"✅ IMAP ile 2FA kodu bulundu: {code}")
                                    mail.close()
                                    mail.logout()
                                    return code
                                else:
                                    print("❌ Bu email'de kod bulunamadı")
                        except Exception as e:
                            print(f"⚠️ Email okuma hatası: {e}")
                            continue
                except Exception as e:
                    print(f"⚠️ Arama kriteri hatası ({criteria}): {e}")
                    continue
            mail.close()
            mail.logout()
        except Exception as e:
            print(f"❌ IMAP sunucusu hatası ({server}:{port}): {e}")
            continue
    print("❌ Hiçbir IMAP sunucusundan kod alınamadı")
    return None

def get_2fa_code_from_email_web(email_address, email_password):
    """tbkod.pages.dev sitesinden email ile 2FA kodunu al"""
    driver = None
    try:
        driver = setup_driver()
        if not driver:
            return None
        print(f" Web sitesinden 2FA kodu alınıyor: {email_address}")
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
            print(f"✅ Web sitesinden 2FA kodu bulundu: {code}")
            driver.quit()
            return code
        except:
            print("❌ Web sitesinden kod elementi bulunamadı")
            driver.quit()
            return None
    except Exception as e:
        print(f"❌ Web sitesinden 2FA kodu alınamadı: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return None

def get_2fa_code(totp_secret=None, email_address=None, email_password=None):
    """Sırayla 2FA kodu almayı dene: 1. TOTP Secret, 2. Email Web, 3. IMAP"""
    print(f" 2FA kodu alınıyor...")
    if totp_secret and totp_secret.strip():
        print("🔐 TOTP Secret ile deneniyor...")
        code = get_2fa_code_from_totp_secret(totp_secret)
        if code:
            return code
    if email_address and email_password:
        print(" Web sitesinden email ile deneniyor...")
        code = get_2fa_code_from_email_web(email_address, email_password)
        if code:
            return code
    if email_address and email_password:
        print(" IMAP ile deneniyor...")
        code = get_2fa_code_from_email_imap_advanced(email_address, email_password)
        if code:
            return code
    print("❌ Hiçbir yöntemle 2FA kodu alınamadı")
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
                print(f"✅ 2FA input alanı bulundu: {selector_type} = {selector_value}")
                return True, code_input
            except:
                continue
        return False, None
    except Exception as e:
        print(f"⚠️ 2FA kontrol sırasında hata: {e}")
        return False, None

def login_and_save_cookies(username, password, totp_secret=None, email_address=None, email_password=None):
    driver = None
    try:
        driver = setup_driver()
        if not driver:
            print(f"❌ Firefox başlatılamadı ({username})")
            return False, ""
        print(f"🌐 Twitter'a gidiliyor... ({username})")
        driver.get("https://twitter.com/login")
        human_like_wait(3, 5)
        print(f"👤 Kullanıcı adı giriliyor: {username}")
        user_input = driver.find_element(By.NAME, "text")
        user_input.send_keys(username)
        user_input.send_keys(Keys.RETURN)
        human_like_wait(3, 5)
        print(f" Şifre giriliyor... ({username})")
        pass_input = driver.find_element(By.NAME, "password")
        pass_input.send_keys(password)
        pass_input.send_keys(Keys.RETURN)
        human_like_wait(5, 8)
        current_url = driver.current_url
        print(f"🔍 Sayfa kontrol ediliyor: {current_url} ({username})")
        if ("home" in current_url or "notifications" in current_url or
                "twitter.com/home" in current_url or "x.com/home" in current_url):
            print(f"✅ Giriş başarılı, 2FA gerekmiyor ({username})")
        else:
            if totp_secret or (email_address and email_password):
                print(f"🔍 2FA gerekli mi kontrol ediliyor... ({username})")
                needs_2fa, code_input = check_if_2fa_needed(driver)
                if needs_2fa and code_input:
                    print(f"📱 2FA gerekli, kod alınıyor... ({username})")
                    code = get_2fa_code(totp_secret, email_address, email_password)
                    if code:
                        print(f"🔑 2FA kodu bulundu: {code} ({username})")
                        code_input.clear()
                        code_input.send_keys(code)
                        code_input.send_keys(Keys.RETURN)
                        human_like_wait(3, 5)
                        print(f"✅ 2FA kodu girildi, sayfa kontrol ediliyor: {driver.current_url} ({username})")
                    else:
                        print(f"❌ 2FA kodu alınamadı. ({username})")
                        driver.quit()
                        return False, ""
                else:
                    print(f"ℹ️ 2FA gerekmiyor veya input alanı bulunamadı ({username})")
        for _ in range(random.randint(1, 3)):
            driver.execute_script(f"window.scrollBy(0, {random.randint(300, 800)})")
            human_like_wait(1, 2)
        current_url = driver.current_url
        print(f"🎯 Final URL: {current_url} ({username})")
        if ("home" in current_url or "notifications" in current_url or
                "twitter.com/home" in current_url or "x.com/home" in current_url):
            cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies.json")
            with open(cookie_path, "w", encoding="utf-8") as f:
                json.dump(driver.get_cookies(), f, indent=2)
            print(f"✅ Giriş başarılı, cookie kaydedildi: {cookie_path} ({username})")
            driver.quit()
            return True, cookie_path.replace("\\", "/")
        else:
            print(f"❌ Giriş başarısız, URL: {current_url} ({username})")
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid='error']")
                for error in error_elements:
                    print(f"🚨 Hata mesajı: {error.text} ({username})")
            except:
                pass
            driver.quit()
            return False, ""
    except Exception as e:
        print(f"❌ Genel hata: {e} ({username})")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return False, ""

def process_account(account_data):
    """Tek bir hesabı işle"""
    username = account_data.get("username")
    password = account_data.get("password")
    totp_secret = account_data.get("totpSecret")
    email_address = account_data.get("emailAddress")
    email_password = account_data.get("emailPassword")
    if check_existing_cookie(username):
        return {
            "account_id": username,
            "is_active": True,
            "cookie_file_path": f"config/{username}_cookies.json",
            "skipped": True
        }
    print(f"🔑 İşleniyor: {username}")
    try:
        success, cookie_path = login_and_save_cookies(username, password, totp_secret, email_address, email_password)
    except Exception as e:
        print(f"❌ Hesap işleme hatası ({username}): {e}")
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
    print(f"[{'✓' if success else 'X'}] {username} {'(cookie kaydedildi)' if success else '(başarısız)'}")
    return account

def get_all_json_files():
    """Sadece accounts klasöründeki tüm JSON dosyalarını oku"""
    all_accounts = []
    json_files = glob.glob(os.path.join(ACCOUNTS_DIR, "*.json"))
    print(f"📁 {ACCOUNTS_DIR} klasöründe {len(json_files)} JSON dosyası bulundu")
    for file_path in json_files:
        try:
            print(f"📄 Dosya okunuyor: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
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
        except Exception as e:
            print(f"❌ Dosya okuma hatası ({file_path}): {e}")
            continue
    print(f"✅ Toplam {len(all_accounts)} hesap bulundu")
    return all_accounts

if __name__ == "__main__":
    print(f" {ACCOUNTS_DIR} klasöründeki JSON dosyalarından hesaplar okunuyor...")
    base_accounts = get_all_json_files()
    if not base_accounts:
        print(f"❌ {ACCOUNTS_DIR} klasöründe hiç hesap bulunamadı!")
        print(f" Lütfen JSON dosyalarınızı {ACCOUNTS_DIR} klasörüne koyun")
        sys.exit(1)
    print(f"🚀 {MAX_WORKERS} paralel işlem ile {len(base_accounts)} hesap işleniyor...")
    accounts = []
    skipped_count = 0
    success_count = 0
    failed_count = 0
    print(f"🔄 {len(base_accounts)} hesap işleniyor...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_account = {executor.submit(process_account, account): account for account in base_accounts}
        for future in as_completed(future_to_account):
            try:
                account = future.result()
                accounts.append(account)
                if account.get("skipped", False):
                    skipped_count += 1
                elif account.get("is_active", False):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                print(f"❌ Hesap işleme hatası: {e}")
                failed_count += 1
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)
    print(f"\n🎯 İşlem tamamlandı!")
    print(f" Özet:")
    print(f"   ✅ Başarılı: {success_count}")
    print(f"   ⏭️ Atlanan (zaten cookie var): {skipped_count}")
    print(f"   ❌ Başarısız: {failed_count}")
    print(f"   📁 Toplam: {len(accounts)}")
    print(f"   📄 Çıktı: {OUTPUT_FILE}")
