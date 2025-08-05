import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

ACCOUNTS_FILE = "accounts.txt"
COOKIE_DIR = "config"
OUTPUT_FILE = "accounts.json"

os.makedirs(COOKIE_DIR, exist_ok=True)

# Ortak bilgiler
default_config = {
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

def login_and_save_cookies(username, password):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920x1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        driver.get("https://twitter.com/login")
        time.sleep(3)

        # Kullanıcı adı gir
        driver.find_element(By.NAME, "text").send_keys(username)
        driver.find_element(By.XPATH, "//span[text()='Next']").click()
        time.sleep(3)

        # Şifre gir
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//span[text()='Log in']").click()
        time.sleep(5)

        if "home" in driver.current_url:
            cookie_path = os.path.join(COOKIE_DIR, f"{username}_cookies.json")
            with open(cookie_path, "w") as f:
                json.dump(driver.get_cookies(), f)

            driver.quit()
            return True, cookie_path.replace("\\", "/")
        else:
            driver.quit()
            return False, ""
    except Exception as e:
        driver.quit()
        return False, ""

# Ana işlem
final_json = []

with open(ACCOUNTS_FILE, "r") as f:
    lines = f.readlines()

for index, line in enumerate(lines):
    line = line.strip()
    if not line or ":" not in line:
        continue
    username, password = line.split(":", 1)
    success, cookie_path = login_and_save_cookies(username, password)

    entry = {
        "account_id": username,
        "is_active": success,
        "cookie_file_path": cookie_path
    }

    if success:
        entry.update(default_config)

    final_json.append(entry)
    print(f"[{'✓' if success else 'X'}] {username}")

# Kaydet
with open(OUTPUT_FILE, "w") as f:
    json.dump(final_json, f, indent=2)

print(f"\n🟢 Tüm hesaplar işlendi. Çıktı: {OUTPUT_FILE}")
