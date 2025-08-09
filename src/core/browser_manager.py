import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Union

from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import WebDriverException, TimeoutException, InvalidArgumentException
from webdriver_manager.chrome import ChromeDriverManager
from fake_headers import Headers

# Adjust import path for ConfigLoader and setup_logger
try:
    from .config_loader import ConfigLoader, CONFIG_DIR as APP_CONFIG_DIR # Import CONFIG_DIR
    # Assuming setup_logger is called once globally, so we just get a logger instance.
    # If setup_logger needs to be called here, ensure it's idempotent.
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent)) # Add root src to path
    from src.core.config_loader import ConfigLoader, CONFIG_DIR as APP_CONFIG_DIR # Import CONFIG_DIR

# Define project root relative to this file's location (src/core/browser_manager.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_WDM_CACHE_PATH = PROJECT_ROOT / ".wdm_cache"

# Initialize logger - This assumes setup_logger has been called elsewhere (e.g., in main.py)
# If not, you might need to call setup_logger here or pass a ConfigLoader instance to it.
# For robustness, let's ensure a logger is available.
logger = logging.getLogger(__name__)
if not logger.handlers: # Basic config if no handlers are set up by the main app
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class BrowserManager:
    def __init__(self, account_config: Optional[Dict[str, Any]] = None, config_loader: Optional[ConfigLoader] = None):
        """
        Initializes the BrowserManager.
        Args:
            account_config: Optional account-specific details, including 'cookies'.
            config_loader: Optional ConfigLoader instance. If None, a new one is created.
        """
        self.config_loader = config_loader if config_loader else ConfigLoader()
        self.browser_settings = self.config_loader.get_setting('browser_settings', {})
        self.driver: Optional[WebDriver] = None
        self.account_config = account_config if account_config else {}
        self.cookies_data: Optional[List[Dict[str, Any]]] = None

        # Configure WDM SSL verification from settings if provided
        wdm_ssl_verify_config = self.browser_settings.get('webdriver_manager_ssl_verify')
        if wdm_ssl_verify_config is not None:
            os.environ['WDM_SSL_VERIFY'] = '1' if wdm_ssl_verify_config else '0'
            logger.info(f"WebDriver Manager SSL verification set to: {os.environ['WDM_SSL_VERIFY']}")
        
        self.wdm_cache_path = Path(self.browser_settings.get('webdriver_manager_cache_path', DEFAULT_WDM_CACHE_PATH))
        self.wdm_cache_path.mkdir(parents=True, exist_ok=True) # Ensure cache path exists
        logger.info(f"WebDriver Manager cache path set to: {self.wdm_cache_path.resolve()}")


        if 'cookies' in self.account_config:
            cookies_input = self.account_config['cookies']
            if isinstance(cookies_input, str): # Path to cookie file
                self.cookies_data = self._load_cookies_from_file(cookies_input)
            elif isinstance(cookies_input, list): # Direct list of cookies
                self.cookies_data = cookies_input
            else:
                logger.warning(f"Invalid 'cookies' format in account_config: {cookies_input}. Expected path string or list of cookies.")
        
        # Also check for cookie_file_path field (used in accounts.json)
        elif 'cookie_file_path' in self.account_config:
            cookie_file_path = self.account_config['cookie_file_path']
            if cookie_file_path and cookie_file_path.strip():  # Only if not empty
                self.cookies_data = self._load_cookies_from_file(cookie_file_path)
                logger.info(f"Loaded cookies from cookie_file_path: {cookie_file_path}")
            else:
                logger.warning(f"cookie_file_path is empty for account: {self.account_config.get('account_id', 'unknown')}")

    def _load_cookies_from_file(self, cookie_file_rel_path: str) -> Optional[List[Dict[str, Any]]]:
        """Loads cookies from a JSON file relative to project root or config dir."""
        # Try path relative to APP_CONFIG_DIR first (most common for config-related files)
        config_dir_cookie_path = APP_CONFIG_DIR / cookie_file_rel_path
        # Then try path relative to project root
        project_root_cookie_path = PROJECT_ROOT / cookie_file_rel_path
        
        resolved_path: Optional[Path] = None
        if config_dir_cookie_path.exists() and config_dir_cookie_path.is_file():
            resolved_path = config_dir_cookie_path
            logger.debug(f"Found cookie file relative to config directory: {resolved_path}")
        elif project_root_cookie_path.exists() and project_root_cookie_path.is_file():
            resolved_path = project_root_cookie_path
            logger.debug(f"Found cookie file relative to project root: {resolved_path}")
        else: # Try absolute path if given
            abs_path = Path(cookie_file_rel_path)
            if abs_path.is_absolute() and abs_path.exists() and abs_path.is_file():
                resolved_path = abs_path
                logger.debug(f"Found cookie file at absolute path: {resolved_path}")
        
        if not resolved_path:
            logger.error(f"Cookie file not found at '{cookie_file_rel_path}' (checked config dir, project root, and as absolute).")
            return None
            
        try:
            with resolved_path.open('r', encoding='utf-8') as f:
                cookies = json.load(f)
            logger.info(f"Successfully loaded cookies from {resolved_path.resolve()}")
            return cookies
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from cookie file {resolved_path.resolve()}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading cookies from file {resolved_path.resolve()}: {e}")
            return None

    def _get_user_agent(self) -> str:
        """Generates or retrieves a user agent string based on configuration."""
        ua_generation = self.browser_settings.get('user_agent_generation', 'random') # Default to random
        if ua_generation == 'custom':
            custom_ua = self.browser_settings.get('custom_user_agent')
            if custom_ua and isinstance(custom_ua, str):
                logger.debug(f"Using custom user agent: {custom_ua}")
                return custom_ua
            else:
                logger.warning("User agent generation set to 'custom' but 'custom_user_agent' is invalid or not provided. Falling back to random.")
        
        try:
            header = Headers(headers=True).generate() # Generate a realistic header set
            user_agent = header.get('User-Agent', "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36") # Fallback within try
            logger.debug(f"Generated random user agent: {user_agent}")
            return user_agent
        except Exception as e:
            logger.error(f"Failed to generate random user agent using fake-headers: {e}. Using a hardcoded default.")
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"


    def _configure_driver_options(self, options: ChromeOptions):
        """Applies common and browser-specific options."""
        user_agent = self._get_user_agent()
        options.add_argument(f"user-agent={user_agent}")

        # Headless modu ayarlardan al - varsayılan olarak kapalı
        headless_mode = self.browser_settings.get('headless', False)
        if headless_mode:
            options.add_argument("--headless")
            logger.info("Headless mode enabled")
        else:
            logger.info("Headless mode disabled - browser will be visible")
        
        # Unique user data directory for each browser instance to prevent conflicts
        import uuid
        import tempfile
        import time
        
        # Basit ama etkili benzersizlik
        unique_id = str(uuid.uuid4())[:12]
        timestamp = int(time.time() * 1000) % 1000000  # Milisaniye cinsinden timestamp
        user_data_dir = tempfile.mkdtemp(prefix=f"chrome_user_data_{unique_id}_{timestamp}_")
        options.add_argument(f"--user-data-dir={user_data_dir}")
        logger.info(f"Using unique user data directory: {user_data_dir}")
        
        # Türkçe karakter desteği için encoding ayarları
        options.add_argument("--lang=tr-TR")
        options.add_argument("--accept-lang=tr-TR,tr,en-US,en")
        options.add_argument("--force-device-scale-factor=1")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-translate")
        options.add_argument("--force-color-profile=srgb")
        
        # UTF-8 encoding desteği
        options.add_argument("--force-device-scale-factor=1")
        options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Temel Chrome ayarları
        options.add_argument("--disable-gpu") # Often needed for headless
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Çoklu instance çakışmalarını önlemek için ek ayarlar
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--force-color-profile=srgb")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-domain-reliability")
        options.add_argument("--disable-component-extensions-with-background-pages")
        

        

        

        

        
        # Türkçe karakter desteği için JavaScript'i açık tut
        # options.add_argument("--disable-javascript")  # Bu satırı kaldırdık
        
        # Diğer ayarlar
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")  # Hızlı yükleme için
        

        

        
        window_size = self.browser_settings.get('window_size', '1920,1080') # Default window size
        options.add_argument(f"--window-size={window_size}")

        proxy = self.browser_settings.get('proxy') # e.g. "http://user:pass@host:port"
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")

        additional_options = self.browser_settings.get('driver_options', [])
        if isinstance(additional_options, list):
            for opt in additional_options:
                if isinstance(opt, str):
                    options.add_argument(opt)
                else:
                    logger.warning(f"Ignoring non-string driver option: {opt}")
        else:
            logger.warning(f"'driver_options' in config is not a list: {additional_options}")
        return options

    def get_driver(self) -> WebDriver:
        """Initializes and returns a Selenium WebDriver instance. Raises WebDriverException on failure."""
        if self.driver and self.is_driver_active():
            logger.debug("Returning existing active WebDriver instance.")
            return self.driver

        browser_type = self.browser_settings.get('type', 'chrome').lower()
        logger.info(f"Initializing {browser_type} WebDriver...")
        
        # Determine driver manager path
        driver_manager_install_path = str(self.wdm_cache_path)

                        # Retry logic for Chrome initialization
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if browser_type == 'chrome':
                    options = self._configure_driver_options(ChromeOptions())
                    
                    # Bot tespitini önlemek için Chrome ayarları
                    options.add_argument("--disable-blink-features=AutomationControlled")
                    options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    options.add_experimental_option('useAutomationExtension', False)
                    
                    # Random user agent
                    user_agents = [
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
                    ]
                    import random
                    options.add_argument(f"--user-agent={random.choice(user_agents)}")
                    
                    # Pass service arguments from config if available
                    service_args = self.browser_settings.get('chrome_service_args', [])
                    
                    # Linux'ta local chromedriver'ı kontrol et, yoksa WebDriver Manager kullan
                    import platform
                    if platform.system() == "Windows":
                        # Windows'ta local chromedriver.exe'yi kontrol et
                        local_chromedriver_path = PROJECT_ROOT / "chromedriver.exe"
                        if local_chromedriver_path.exists():
                            logger.info(f"Using local chromedriver: {local_chromedriver_path}")
                            service = ChromeService(str(local_chromedriver_path), service_args=service_args if service_args else None)
                        else:
                            logger.info("Local chromedriver not found, using WebDriver Manager")
                            service = ChromeService(ChromeDriverManager(path=driver_manager_install_path).install(), service_args=service_args if service_args else None)
                    else:
                        # Linux'ta local chromedriver'ı kontrol et, yoksa WebDriver Manager kullan
                        local_chromedriver_path = PROJECT_ROOT / "chromedriver"
                        if local_chromedriver_path.exists():
                            logger.info(f"Using local chromedriver: {local_chromedriver_path}")
                            service = ChromeService(str(local_chromedriver_path), service_args=service_args if service_args else None)
                        else:
                            logger.info("Local chromedriver not found, using WebDriver Manager")
                            service = ChromeService(ChromeDriverManager(path=driver_manager_install_path).install(), service_args=service_args if service_args else None)
                    
                    # Chrome başlatmadan önce daha uzun bekleme
                    import time
                    time.sleep(3)  # 3 saniye bekle
                    
                    self.driver = webdriver.Chrome(service=service, options=options)
                    
                    # Chrome başlatıldıktan sonra daha uzun bekleme
                    time.sleep(5)  # 5 saniye bekle
                    
                    # JavaScript ile bot tespitini önle
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
                    self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
                else:
                    logger.error(f"Unsupported browser type: {browser_type}. Cannot initialize WebDriver.")
                    raise WebDriverException(f"Unsupported browser type: {browser_type}")
                
                page_load_timeout = self.browser_settings.get('page_load_timeout_seconds', 15)  # Reduced to 15 seconds for faster failure
                script_timeout = self.browser_settings.get('script_timeout_seconds', 15)  # Reduced to 15 seconds for faster failure
                self.driver.set_page_load_timeout(page_load_timeout)
                self.driver.set_script_timeout(script_timeout)
                
                logger.info(f"{browser_type.capitalize()} WebDriver initialized successfully.")

                if self.cookies_data:
                    cookie_domain_url = self.browser_settings.get('cookie_domain_url')
                    if not cookie_domain_url:
                        logger.warning("No 'cookie_domain_url' configured in browser_settings. Cookies might not be set correctly for some sites.")
                        # For Twitter, always navigate to x.com first before setting cookies
                        try:
                            logger.debug("Navigating to https://x.com to set cookies.")
                            self.driver.get("https://x.com")
                            import time
                            time.sleep(2)  # Wait for page to load
                        except Exception as e:
                            logger.error(f"Error navigating to x.com for cookies: {e}. Cookies may not be set correctly.")
                    else:
                        try:
                            logger.debug(f"Navigating to {cookie_domain_url} to set cookies.")
                            self.driver.get(cookie_domain_url)
                        except Exception as e:
                            logger.error(f"Error navigating to cookie domain {cookie_domain_url}: {e}. Cookies may not be set correctly.")

                    for cookie_dict in self.cookies_data:
                        # Ensure keys match Selenium's expectations, especially 'expires'
                        selenium_cookie = {}
                        for key, value in cookie_dict.items():
                            if key == 'expires': # Pydantic model uses 'expires' for timestamp
                                selenium_cookie['expiry'] = value # Selenium expects 'expiry' for timestamp
                            elif key == 'httpOnly': # Selenium expects 'httpOnly'
                                selenium_cookie['httpOnly'] = value
                            elif key in ['name', 'value', 'path', 'domain', 'secure', 'sameSite']:
                                selenium_cookie[key] = value
                        
                        try:
                            self.driver.add_cookie(selenium_cookie)
                            logger.debug(f"Cookie set: {selenium_cookie.get('name', 'unknown')}")
                        except Exception as e:
                            logger.warning(f"Failed to set cookie {selenium_cookie.get('name', 'unknown')}: {e}")
                
                # Success - break out of retry loop
                break
                
            except Exception as e:
                logger.warning(f"Chrome initialization attempt {attempt + 1}/{max_retries} failed: {e}")
                
                # Clean up any partial driver
                if hasattr(self, 'driver') and self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
                
                # Force cleanup Chrome processes before retry
                if attempt < max_retries - 1:
                    logger.info(f"Cleaning up Chrome processes before retry {attempt + 2}...")
                    self._force_cleanup_chrome_processes()
                    import time
                    # Daha uzun bekleme süresi
                    wait_time = 10  # Sabit 10 saniye bekle
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    # Last attempt failed
                    logger.error(f"All {max_retries} Chrome initialization attempts failed")
                    raise WebDriverException(f"Failed to initialize Chrome after {max_retries} attempts: {e}")
        
        return self.driver
    
    def _force_cleanup_chrome_processes(self):
        """Force cleanup Chrome processes to resolve session issues"""
        try:
            import subprocess
            import platform
            import time
            
            if platform.system() == "Windows":
                # Windows'ta basit temizlik
                subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], 
                             capture_output=True, timeout=10)
                subprocess.run(["taskkill", "/f", "/im", "chromedriver.exe"], 
                             capture_output=True, timeout=10)
            else:
                # Linux'ta basit temizlik
                subprocess.run(["pkill", "-f", "chrome"], 
                             capture_output=True, timeout=10)
                subprocess.run(["pkill", "-f", "chromedriver"], 
                             capture_output=True, timeout=10)
            
            # Temizlik sonrası bekleme
            time.sleep(3)
            logger.info("Chrome processes force cleaned")
        except Exception as e:
            logger.warning(f"Chrome process cleanup failed: {e}")

    def close_driver(self):
        """Closes the WebDriver session if it's active."""
        if self.driver:
            try:
                # First try to quit gracefully
                self.driver.quit()
                logger.info("WebDriver session closed gracefully.")
            except Exception as e:
                logger.warning(f"Error during graceful WebDriver close: {e}")
                try:
                    # If graceful close fails, try to close forcefully
                    self.driver.close()
                    logger.info("WebDriver session closed forcefully.")
                except Exception as e2:
                    logger.error(f"Error during forceful WebDriver close: {e2}")
            finally:
                self.driver = None
                # Clean up temporary user data directories
                self._cleanup_temp_directories()
        else:
            logger.debug("No WebDriver instance to close.")
    
    def _cleanup_temp_directories(self):
        """Clean up temporary Chrome user data directories."""
        try:
            import tempfile
            import shutil
            import glob
            
            # Find and remove temporary Chrome user data directories
            temp_dir = tempfile.gettempdir()
            chrome_dirs = glob.glob(os.path.join(temp_dir, "chrome_user_data_*"))
            
            for chrome_dir in chrome_dirs:
                try:
                    if os.path.exists(chrome_dir):
                        shutil.rmtree(chrome_dir, ignore_errors=True)
                        logger.debug(f"Cleaned up temporary directory: {chrome_dir}")
                except Exception as e:
                    logger.debug(f"Could not clean up directory {chrome_dir}: {e}")
        except Exception as e:
            logger.debug(f"Error during temp directory cleanup: {e}")

    def navigate_to(self, url: str, ensure_driver: bool = True) -> bool:
        """Navigates to a URL. Optionally ensures driver is active."""
        if ensure_driver and (not self.driver or not self.is_driver_active()):
            logger.info("Driver not active or not initialized. Attempting to get/re-initialize driver.")
            try:
                self.get_driver()
            except WebDriverException:
                logger.error("Failed to initialize driver for navigation.")
                return False
        
        if not self.driver: # Still no driver after attempt
            logger.error("No active WebDriver instance to navigate.")
            return False

        # Retry logic for navigation
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Navigating to {url} (attempt {attempt + 1}/{max_retries})")
                self.driver.get(url)
                
                # Wait for page to load completely with shorter timeout
                import time
                time.sleep(3)  # Reduced from 5 to 3 seconds
                
                # Check if page loaded successfully
                current_url = self.driver.current_url
                if "about:blank" in current_url or "data:text/html" in current_url:
                    logger.warning(f"Page may not have loaded properly. Current URL: {current_url}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying navigation to {url}...")
                        continue
                    else:
                        return False
                        
                return True
                
            except Exception as e:
                logger.warning(f"Navigation attempt {attempt + 1}/{max_retries} failed: {e}")
                
                # Check if it's a session issue
                if "session deleted" in str(e) or "invalid session id" in str(e):
                    logger.info("Session issue detected, reinitializing driver...")
                    try:
                        self.close_driver()
                        self.get_driver()
                    except Exception as reinit_error:
                        logger.error(f"Failed to reinitialize driver: {reinit_error}")
                        return False
                
                # Try to refresh the page once with shorter wait
                if attempt < max_retries - 1:
                    try:
                        logger.info("Attempting to refresh page after navigation failure...")
                        self.driver.refresh()
                        time.sleep(5)  # Reduced from 10 to 5 seconds
                        continue
                    except Exception as refresh_error:
                        logger.warning(f"Refresh also failed: {refresh_error}")
                        continue
                else:
                    # Last attempt failed
                    logger.error(f"All {max_retries} navigation attempts failed for {url}")
                    return False
        
        return False

    def is_driver_active(self) -> bool:
        """Checks if the WebDriver is still responsive."""
        if not self.driver:
            return False
        try:
            # Try a simple command to check responsiveness
            _ = self.driver.current_url
            return True
        except Exception as e:
            # Check for specific session issues
            if "session deleted" in str(e) or "invalid session id" in str(e) or "tab crashed" in str(e):
                logger.warning(f"WebDriver session issue detected: {e}")
                # Clean up the broken driver
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            else:
                logger.warning(f"WebDriver is not responsive: {e}")
            return False

    def check_login_status(self) -> bool:
        """Checks if the user is logged in to Twitter."""
        try:
            if not self.driver:
                self.get_driver()
            
            # Navigate to Twitter home page
            self.navigate_to("https://x.com/home")
            
            # Wait a bit for page to load
            import time
            time.sleep(3)
            
            # Check for login indicators
            current_url = self.driver.current_url
            
            # If redirected to login page, not logged in
            if "login" in current_url.lower() or "i/flow/login" in current_url.lower():
                logger.info("Not logged in - redirected to login page")
                return False
            
            # Check for logout button (indicates logged in)
            try:
                logout_button = self.driver.find_element("xpath", "//a[@data-testid='SideNav_AccountSwitcher_Button']")
                if logout_button:
                    logger.info("Logged in - found account switcher button")
                    return True
            except:
                pass
            
            # Check for tweet compose button (indicates logged in)
            try:
                compose_button = self.driver.find_element("xpath", "//a[@data-testid='SideNav_NewTweet_Button']")
                if compose_button:
                    logger.info("Logged in - found tweet compose button")
                    return True
            except:
                pass
            
            # If we're on home page and no login indicators found, assume logged in
            if "home" in current_url.lower():
                logger.info("On home page - assuming logged in")
                return True
            
            logger.warning("Login status unclear")
            return False
            
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    def login(self) -> bool:
        """Attempts to login using cookies."""
        try:
            if not self.driver:
                self.get_driver()
            
            # Navigate to Twitter
            self.navigate_to("https://x.com")
            
            # Load cookies if available
            if self.cookies_data:
                logger.info("Loading cookies for login...")
                for cookie in self.cookies_data:
                    try:
                        # Remove problematic fields that might cause issues
                        cookie_dict = cookie.copy()
                        for field in ['sameSite', 'httpOnly', 'secure']:
                            if field in cookie_dict:
                                del cookie_dict[field]
                        
                        # Fix domain issues - if cookie has .x.com domain, use x.com for Selenium
                        if 'domain' in cookie_dict and cookie_dict['domain'] == '.x.com':
                            cookie_dict['domain'] = 'x.com'
                            logger.debug(f"Fixed cookie domain from .x.com to x.com for {cookie_dict.get('name', 'unknown')}")
                        
                        self.driver.add_cookie(cookie_dict)
                        logger.debug(f"Added cookie: {cookie_dict.get('name', 'unknown')}")
                    except Exception as e:
                        logger.warning(f"Failed to add cookie {cookie.get('name', 'unknown')}: {e}")
                
                # Refresh page to apply cookies
                self.driver.refresh()
                import time
                time.sleep(3)
                
                # Check if login was successful
                if self.check_login_status():
                    logger.info("Login successful with cookies")
                    return True
                else:
                    logger.warning("Login failed with cookies")
                    return False
            else:
                logger.warning("No cookies available for login")
                return False
                
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False

    def __enter__(self):
        """Initializes driver when entering a 'with' statement."""
        if not self.driver or not self.is_driver_active():
            self.get_driver() # Raises exception on failure
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes driver when exiting a 'with' statement."""
        self.close_driver()


if __name__ == '__main__':
    # Setup basic logging for direct script execution
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Running BrowserManager direct test...")

    # Create dummy config files for testing if they don't exist
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    dummy_settings_file = CONFIG_DIR / 'settings.json'
    dummy_accounts_file = CONFIG_DIR / 'accounts.json' # Not used directly by BM but good for ConfigLoader
    dummy_cookie_file = CONFIG_DIR / "dummy_cookies.json"

    if not dummy_settings_file.exists():
        settings_data = {
            "browser_settings": {
                "type": "chrome",  # or "firefox"
                "headless": True, # Set to False to see the browser
                "window_size": "1280,800",
                "page_load_timeout_seconds": 20,
                "script_timeout_seconds": 20,
                "webdriver_manager_cache_path": str(PROJECT_ROOT / ".wdm_cache_test"), # Test custom cache
                "webdriver_manager_ssl_verify": True, # Explicitly set
                "cookie_domain_url": "https://www.google.com" # Domain for setting cookies
                # "proxy": "http://yourproxy:port" 
            },
            "logging": {"level": "DEBUG"} # Ensure logger is verbose for test
        }
        with dummy_settings_file.open('w') as f:
            json.dump(settings_data, f, indent=4)
        logger.info(f"Created dummy settings: {dummy_settings_file}")

    if not dummy_cookie_file.exists():
        cookie_data = [{"name": "NID", "value": "test_value", "domain": ".google.com", "path": "/"}]
        with dummy_cookie_file.open('w') as f:
            json.dump(cookie_data, f)
        logger.info(f"Created dummy cookie file: {dummy_cookie_file}")
    
    test_account_config = {"name": "test_user", "cookies": "dummy_cookies.json"} # Path relative to config/project root

    logger.info("--- Test 1: Initialize and navigate without 'with' statement ---")
    manager_test1 = BrowserManager(account_config=test_account_config)
    try:
        driver = manager_test1.get_driver()
        if driver:
            logger.info(f"Driver obtained. Active: {manager_test1.is_driver_active()}")
            if manager_test1.navigate_to("https://www.example.com"):
                logger.info(f"Navigated to example.com. Title: {driver.title}")
            else:
                logger.error("Failed to navigate to example.com")
        else:
            logger.error("Failed to get driver in Test 1.")
    except Exception as e:
        logger.error(f"Error in Test 1: {e}", exc_info=True)
    finally:
        manager_test1.close_driver()
        logger.info("Test 1 finished.")

    logger.info("\n--- Test 2: Using 'with' statement ---")
    try:
        with BrowserManager(account_config=test_account_config) as manager_test2:
            logger.info(f"Driver obtained via 'with'. Active: {manager_test2.is_driver_active()}")
            if manager_test2.navigate_to("https://news.ycombinator.com"):
                logger.info(f"Navigated to news.ycombinator.com. Title: {manager_test2.driver.title}")
            else:
                logger.error("Failed to navigate to news.ycombinator.com")
        logger.info(f"After 'with' block, driver should be closed. Active: {manager_test2.is_driver_active()}")
    except Exception as e:
        logger.error(f"Error in Test 2: {e}", exc_info=True)
    finally:
        logger.info("Test 2 finished.")
    
    # Optional: Clean up dummy files
    # logger.info("Cleaning up dummy files...")
    # dummy_settings_file.unlink(missing_ok=True)
    # dummy_cookie_file.unlink(missing_ok=True)
    # import shutil
    # test_cache_path = PROJECT_ROOT / ".wdm_cache_test"
    # if test_cache_path.exists():
    #     shutil.rmtree(test_cache_path)
    logger.info("BrowserManager direct test completed.")
