import os
import json
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

ACCOUNTS_FILE = "base3.json"
COOKIE_DIR = "config"
OUTPUT_FILE = "accounts.json"

os.makedirs(COOKIE_DIR, exist_ok=True)

def human_like_wait(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def setup_driver():
    options = FirefoxOptions()
    options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"  # Firefox'un tam yolu

    # 1. Bu dosyanın bulunduğu klasörü al (örneğin clean4.py)""""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # 2. Proje kök dizinine çık
    PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

    GECKODRIVER_PATH = os.path.join(PROJECT_ROOT, "geckodriver-v0.36.0-win32", "geckodriver.exe")
    print(GECKODRIVER_PATH)
    
    # Firefox'u tamamen gizle
    options.headless = True
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--disable-javascript")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    options.add_argument("--mute-audio")
    
    # Firefox özel ayarları
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0")
    options.set_preference("dom.webnotifications.enabled", False)
    options.set_preference("media.volume_scale", "0.0")
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf")
    options.set_preference("pdfjs.disabled", True)
    options.set_preference("browser.tabs.remote.autostart", False)
    options.set_preference("browser.tabs.remote.autostart.2", False)
    
    driver = webdriver.Firefox(
        service=FirefoxService(
        executable_path=GECKODRIVER_PATH),
        options=options
    )
    return driver

def get_totp_code_from_web(totp_secret):
    driver = setup_driver()
    try:
        driver.get("https://tbkod.pages.dev/")
        human_like_wait(1, 2)
        # Secret input alanını bul ve secret'ı yaz
        totp_input = driver.find_element(By.XPATH, '//*[@id="2faSecret"]')
        totp_input.clear()
        totp_input.send_keys(totp_secret)
        # Butonu bul ve tıkla
        btn = driver.find_element(By.XPATH, "//button[contains(., '2FA Kod Al')]")
        btn.click()
        human_like_wait(1, 2)
        # Kodu oku
        code_el = driver.find_element(By.XPATH, '//*[@id="2faCode"]/h5/strong')
        code = code_el.text.strip()
        driver.quit()
        return code
    except Exception as e:
        print(f"2FA kod alınamadı: {e}")
        driver.quit()
        return None

def login_and_save_cookies(username, password, totp_secret=None):
    driver = setup_driver()
    try:
        print(f"🌐 Twitter'a gidiliyor...")
        driver.get("https://twitter.com/login")
        human_like_wait(3, 5)

        print(f"👤 Kullanıcı adı giriliyor: {username}")
        user_input = driver.find_element(By.NAME, "text")
        user_input.send_keys(username)
        user_input.send_keys(Keys.RETURN)
        human_like_wait(3, 5)

        print(f"🔒 Şifre giriliyor...")
        pass_input = driver.find_element(By.NAME, "password")
        pass_input.send_keys(password)
        pass_input.send_keys(Keys.RETURN)
        human_like_wait(5, 8)

        print(f"🔍 Sayfa kontrol ediliyor: {driver.current_url}")

        # 2FA gerekli mi?
        if totp_secret:
            try:
                code_input = None
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
                        break
                    except:
                        continue
                if code_input:
                    print(f"📱 2FA kodu alınıyor...")
                    code = get_totp_code_from_web(totp_secret)
                    if code:
                        print(f"🔑 2FA kodu bulundu: {code}")
                        code_input.clear()
                        code_input.send_keys(code)
                        code_input.send_keys(Keys.RETURN)
                        human_like_wait(3, 5)
                        print(f"✅ 2FA kodu girildi, sayfa kontrol ediliyor: {driver.current_url}")
                    else:
                        print("❌ 2FA kodu alınamadı.")
                        driver.quit()
                        return False, ""
                else:
                    print("ℹ️ 2FA input alanı bulunamadı, doğrulama gerekmiyor olabilir")
            except Exception as e:
                print(f"⚠️ 2FA doğrulama sırasında hata: {e}")

        # Sayfada biraz gezinelim
        print("🔄 Sayfada geziniliyor...")
        for _ in range(random.randint(1, 3)):
            driver.execute_script(f"window.scrollBy(0, {random.randint(300, 800)})")
            human_like_wait(1, 2)

        current_url = driver.current_url
        print(f"🎯 Final URL: {current_url}")

        if ("home" in current_url or "notifications" in current_url or
                "twitter.com/home" in current_url or "x.com/home" in current_url):
            cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies.json")
            with open(cookie_path, "w", encoding="utf-8") as f:
                json.dump(driver.get_cookies(), f, indent=2)
            print(f"✅ Giriş başarılı, cookie kaydedildi: {cookie_path}")
            driver.quit()
            return True, cookie_path.replace("\\", "/")
        else:
            print(f"❌ Giriş başarısız, URL: {current_url}")
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid='error']")
                for error in error_elements:
                    print(f"🚨 Hata mesajı: {error.text}")
            except:
                pass
            driver.quit()
            return False, ""
    except Exception as e:
        print(f"❌ Genel hata: {e}")
        driver.quit()
        return False, ""

# Yeni JSON formatı için hesapları oku
accounts = []
with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
    base_accounts = json.load(f)

for entry in base_accounts:
    username = entry.get("username")
    password = entry.get("password")
    totp_secret = entry.get("totpSecret")
    print(f"🔑 Giriş deneniyor: {username}")
    success, cookie_path = login_and_save_cookies(username, password, totp_secret)
    account = {
        "account_id": username,
        "is_active": success,
        "cookie_file_path": cookie_path if success else ""
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

    accounts.append(account)
    print(f"[{'✓' if success else 'X'}] {username} {'(cookie kaydedildi)' if success else '(başarısız)'}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(accounts, f, indent=2, ensure_ascii=False)

print(f"\n🎯 {len(accounts)} hesap işlendi. Çıktı: {OUTPUT_FILE}")