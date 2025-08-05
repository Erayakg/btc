import os
import json
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re
from imap_tools import MailBox, AND
from datetime import datetime, timedelta
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

ACCOUNTS_FILE = "base.json"
COOKIE_DIR = "config"
OUTPUT_FILE = "accounts.json"

os.makedirs(COOKIE_DIR, exist_ok=True)


def human_like_wait(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))


def setup_driver():
    options = FirefoxOptions()
    # options.add_argument("--headless")  # İstersen arkaplanda çalıştır
    options.set_preference("general.useragent.override",
                           "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0")

    driver = webdriver.Firefox(
        service=FirefoxService(GeckoDriverManager().install()),
        options=options
    )
    return driver


def get_latest_gmail_code(email_address, email_password):
    try:
        print("📧 Bağlantı sağlanıyor...")

        with MailBox("imap.gmail.com").login(email_address, email_password) as mailbox:
            since = datetime.now() - timedelta(minutes=10)
            messages = mailbox.fetch(AND(since=since), reverse=True, limit=20)

            for msg in messages:
                subject = msg.subject or ""
                sender = msg.from_ or ""
                text = msg.text or ""

                print(f"📨 {subject[:50]}... | {sender[:30]}")

                if (
                        "twitter" in subject.lower() or
                        "x.com" in subject.lower() or
                        "twitter" in sender.lower() or
                        "x.com" in sender.lower()
                ):
                    print("🎯 Twitter maili bulundu")

                    matches = re.findall(r'\b(\d{6})\b', text)
                    if matches:
                        print(f"✅ Kod bulundu: {matches[0]}")
                        return matches[0]
                    else:
                        print("❌ Kod bulunamadı")
            print("❌ Uygun kod içeren mail bulunamadı")
            return None

    except Exception as e:
        print(f"⚠️ Hata oluştu: {e}")
        return None


def login_and_save_cookies(username, password, email_address=None, email_password=None):
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

        # Email doğrulama isterse
        if email_address and email_password:
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
                        print(f"✅ Kod input alanı bulundu: {selector_type} = {selector_value}")
                        break
                    except:
                        continue

                if code_input:
                    print(f"📧 Email kodu bekleniyor: {email_address}")
                    for attempt in range(3):
                        print(f"🔄 Kod arama denemesi {attempt + 1}/3")
                        code = get_latest_gmail_code(email_address, email_password)
                        if code:
                            print(f"🔑 Kod bulundu: {code}")
                            code_input.clear()
                            code_input.send_keys(code)
                            code_input.send_keys(Keys.RETURN)
                            human_like_wait(3, 5)
                            print(f"✅ Kod girildi, sayfa kontrol ediliyor: {driver.current_url}")
                            break
                        else:
                            print(f"⏳ Kod bulunamadı, 3 saniye bekleniyor...")
                            time.sleep(3)
                else:
                    print("ℹ️ Kod input alanı bulunamadı, email doğrulama gerekmiyor olabilir")

            except Exception as e:
                print(f"⚠️ Email doğrulama sırasında hata: {e}")

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
    email_address = entry.get("emailAddress")
    email_password = entry.get("emailPassword")
    # totpSecret = entry.get("totpSecret")  # Eğer ileride kullanacaksanız, burada alın
    print(f"🔑 Giriş deneniyor: {username}")
    success, cookie_path = login_and_save_cookies(username, password, email_address, email_password)
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