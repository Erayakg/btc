import os
import json
import time
import random
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

# Ortak ayarlar
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

def human_like_wait(min_s=1.5, max_s=4.5):
    time.sleep(random.uniform(min_s, max_s))

def login_and_save_cookies(username, password):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36")
    profile_path = os.path.abspath(f"selenium_profiles/{username}")
    options.add_argument(f"--user-data-dir={profile_path}")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        driver.get("https://twitter.com/login")
        human_like_wait(3, 5)

        user_input = driver.find_element(By.NAME, "text")
        user_input.send_keys(username)
        user_input.send_keys(Keys.RETURN)
        human_like_wait()

        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        human_like_wait(5, 8)

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

with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    line = line.strip()
    if not line or ":" not in line:
        continue
    username, password = line.split(":", 1)
    print(f"🔄 {username} giriş yapılıyor...")

    success, cookie_path = login_and_save_cookies(username, password)

    entry = {
        "account_id": username,
        "is_active": success,
        "cookie_file_path": cookie_path if success else ""
    }

    if success:
        entry.update(default_config)

    final_json.append(entry)
    print(f"[{'✓' if success else 'X'}] {username} -> {'BAŞARILI' if success else 'HATA'}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(final_json, f, indent=2, ensure_ascii=False)

print(f"\n✅ Tamamlandı: {OUTPUT_FILE}")
