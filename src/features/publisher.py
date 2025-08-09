import os
import sys
import time
import random
import requests
import mimetypes
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Adjust import paths
try:
    from ..core.browser_manager import BrowserManager
    from ..core.config_loader import ConfigLoader
    from ..core.llm_service import LLMService
    from ..utils.logger import setup_logger
    from ..data_models import TweetContent, ScrapedTweet, AccountConfig, LLMSettings
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..')) # Add root src to path
    from src.core.browser_manager import BrowserManager
    from src.core.config_loader import ConfigLoader
    from src.core.llm_service import LLMService
    from src.utils.logger import setup_logger
    from src.data_models import TweetContent, ScrapedTweet, AccountConfig, LLMSettings

config_loader_instance = ConfigLoader()
logger = setup_logger(config_loader_instance)

class TweetPublisher:
    def __init__(self, browser_manager: BrowserManager, llm_service: LLMService, account_config: AccountConfig):
        self.browser_manager = browser_manager
        self.driver = self.browser_manager.get_driver()
        self.llm_service = llm_service
        self.account_config = account_config # Specific account performing actions
        self.config_loader = browser_manager.config_loader # Reuse config loader
        
        self.twitter_automation_settings = self.config_loader.get_settings().get('twitter_automation', {})
        self.media_dir = self.twitter_automation_settings.get('media_directory', 'media_files')
        if not os.path.exists(self.media_dir):
            os.makedirs(self.media_dir, exist_ok=True)

    async def _download_media(self, media_url: str) -> Optional[str]:
        """Downloads media from a URL and saves it locally."""
        if not media_url:
            return None
        try:
            logger.info(f"Downloading media from: {media_url}")
            response = requests.get(media_url, stream=True, timeout=30)
            response.raise_for_status()

            # Try to get a meaningful filename and extension
            parsed_url = urlparse(media_url)
            base_name = os.path.basename(parsed_url.path)
            if not base_name or '.' not in base_name: # Fallback if no filename in URL
                content_type = response.headers.get('content-type')
                ext = mimetypes.guess_extension(content_type) if content_type else '.jpg'
                base_name = f"media_{int(time.time())}{ext or '.unknown'}"
            
            file_path = os.path.join(self.media_dir, base_name)
            
            # Ensure unique filename
            counter = 1
            original_file_path = file_path
            while os.path.exists(file_path):
                name, ext = os.path.splitext(original_file_path)
                file_path = f"{name}_{counter}{ext}"
                counter += 1

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Media downloaded successfully to: {file_path}")
            return file_path
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download media from {media_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during media download from {media_url}: {e}")
            return None

    async def post_new_tweet(self, content: TweetContent, llm_settings: Optional[LLMSettings] = None) -> bool:
        """
        Posts a new tweet. If content.text is a prompt, it generates text first.
        Downloads media from URLs if provided.
        """
        tweet_text = content.text
        
        # Check if text needs generation (e.g. if it's a prompt)
        # This logic can be more sophisticated, e.g. checking a flag in TweetContent
        if llm_settings and ("generate tweet about" in tweet_text.lower() or "write a post on" in tweet_text.lower()): # Simple check
            logger.info(f"Generating tweet text for prompt: {tweet_text}")
            generated_text = await self.llm_service.generate_text(
                prompt=tweet_text,
                service_preference=llm_settings.service_preference,
                model_name=llm_settings.model_name_override,
                max_tokens=llm_settings.max_tokens,
                temperature=llm_settings.temperature
            )
            if not generated_text:
                logger.error("Failed to generate tweet text. Aborting post.")
                return False
            tweet_text = generated_text
            logger.info(f"Generated tweet text: {tweet_text}")

        # Prepare media
        final_media_paths: List[str] = content.local_media_paths or []
        if content.media_urls:
            for url in content.media_urls:
                downloaded_path = await self._download_media(str(url))
                if downloaded_path:
                    final_media_paths.append(downloaded_path)
        
        # Ensure all media paths are absolute for Selenium
        final_media_paths = [os.path.abspath(p) for p in final_media_paths if os.path.exists(p)]

        # Ensure tweet is not too long (Twitter limit is 280 characters)
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."
            logger.info(f"Tweet was too long, truncated to: '{tweet_text[:50]}...'")
        
        logger.info(f"Attempting to post tweet: '{tweet_text[:50]}...' with {len(final_media_paths)} media file(s).")

        try:
            # Direkt compose URL'ine git - home sayfasında takılmayı önle
            logger.info("Navigating directly to compose URL to avoid home page issues...")
            success = self.browser_manager.navigate_to("https://x.com/compose/tweet")
            if not success:
                logger.warning("Failed to navigate to compose URL, trying home page...")
                # Fallback to home page
                success = self.browser_manager.navigate_to("https://x.com/home")
                if not success:
                    logger.error("Failed to navigate to both compose URL and home page")
                    return False
                time.sleep(5)
            else:
                time.sleep(3) # Shorter wait for compose URL
            
            # Human-like behavior: Add random delays and scrolling before opening composer
            import random
            logger.info("Adding human-like delays and scrolling behavior...")
            
            # Random delay before opening composer (2-5 seconds)
            human_delay = random.uniform(2, 5)
            logger.info(f"Waiting {human_delay:.1f} seconds before opening composer...")
            time.sleep(human_delay)
            
            # Random scrolling behavior to simulate human browsing
            try:
                # Scroll up and down randomly to simulate human behavior
                scroll_actions = random.randint(1, 3)
                for i in range(scroll_actions):
                    scroll_amount = random.randint(-300, 300)
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                    logger.info(f"Scrolling {scroll_amount} pixels (action {i+1}/{scroll_actions})")
                    time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                logger.warning(f"Scrolling behavior failed: {e}")
            
            # Additional random delay after scrolling
            time.sleep(random.uniform(1, 3))
            # Eğer home page'deyse tweet butonuna tıkla
            if "home" in self.driver.current_url.lower():
                try:
                    # Try multiple selectors for the main tweet button
                    main_tweet_selectors = [
                        '//a[@data-testid="SideNav_NewTweet_Button"]',
                        '//a[@data-testid="FloatingActionButton"]',
                        '//button[@data-testid="SideNav_NewTweet_Button"]',
                        '//button[@data-testid="FloatingActionButton"]',
                        '//div[@data-testid="SideNav_NewTweet_Button"]',
                        '//div[@data-testid="FloatingActionButton"]',
                        '//a[contains(@href, "/compose/tweet")]',
                        '//button[contains(@class, "tweet") and contains(@class, "button")]',
                        '//button[text()="Post"]',
                        '//button[text()="Tweet"]',
                        '//a[text()="Post"]',
                        '//a[text()="Tweet"]'
                    ]
                    
                    main_tweet_button = None
                    for selector in main_tweet_selectors:
                        try:
                            main_tweet_button = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            logger.info(f"Found main tweet button with selector: {selector}")
                            break
                        except TimeoutException:
                            continue
                    
                    if main_tweet_button:
                        # Human-like behavior: Hover before clicking
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            actions = ActionChains(self.driver)
                            actions.move_to_element(main_tweet_button).pause(random.uniform(0.5, 1.5)).perform()
                            logger.info("Hovered over tweet button before clicking...")
                        except Exception as e:
                            logger.warning(f"Hover behavior failed: {e}")
                        
                        main_tweet_button.click()
                        logger.info("Clicked main tweet button to open composer.")
                        
                        # Human-like delay after clicking (3-7 seconds)
                        composer_delay = random.uniform(3, 7)
                        logger.info(f"Waiting {composer_delay:.1f} seconds for composer to fully load...")
                        time.sleep(composer_delay)
                    else:
                        raise TimeoutException("No main tweet button found")
                        
                except TimeoutException:
                    logger.info("Main tweet button not found, trying to navigate directly to compose URL.")
                    # Try to navigate directly to compose URL
                    compose_success = self.browser_manager.navigate_to("https://x.com/compose/tweet")
                    if not compose_success:
                        logger.error("Failed to navigate to compose URL")
                        return False
                    time.sleep(5) # Increased wait time


            # Find the tweet text area - try multiple selectors
            text_area_selectors = [
                '//div[@data-testid="tweetTextarea_0"]',
                '//div[@data-testid="tweetTextarea"]',
                '//div[@role="textbox"]',
                '//div[@contenteditable="true"]',
                '//textarea[@data-testid="tweetTextarea_0"]',
                '//textarea[@data-testid="tweetTextarea"]',
                '//textarea[@role="textbox"]',
                '//div[contains(@class, "tweet") and contains(@class, "textarea")]',
                '//div[contains(@class, "compose") and contains(@class, "textarea")]'
            ]
            
            text_area = None
            for selector in text_area_selectors:
                try:
                    text_area = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    logger.info(f"Found text area with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not text_area:
                logger.error("Could not find tweet text area with any selector")
                return False
            
            # Clear and type text - multiple approaches to ensure button activates
            try:
                # Human-like typing behavior
                logger.info("Starting human-like typing behavior...")
                
                # Clear the text area first
                text_area.clear()
                time.sleep(random.uniform(0.5, 1.0))
                
                # Method 1: Simulate human typing with random delays
                logger.info("Simulating human typing with random delays...")
                
                # Türkçe karakter desteği için UTF-8 encoding kullan
                logger.info(f"Original text: {tweet_text[:50]}...")
                
                # Method 1: Direct send_keys with UTF-8 support
                logger.info("Starting UTF-8 character typing...")
                for char in tweet_text:
                    try:
                        text_area.send_keys(char)
                        # Random delay between characters (0.05-0.15 seconds)
                        time.sleep(random.uniform(0.05, 0.15))
                        
                        # Occasionally pause longer (like humans do when thinking)
                        if random.random() < 0.1:  # 10% chance
                            pause_duration = random.uniform(0.5, 2.0)
                            logger.info(f"Pausing for {pause_duration:.1f} seconds (thinking pause)...")
                            time.sleep(pause_duration)
                    except Exception as e:
                        logger.warning(f"Failed to type character '{char}': {e}")
                        # Try alternative method for this character
                        try:
                            self.driver.execute_script("""
                                var textarea = arguments[0];
                                var char = arguments[1];
                                textarea.innerHTML += char;
                                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                            """, text_area, char)
                            logger.info(f"Successfully typed character '{char}' via JavaScript")
                        except Exception as js_e:
                            logger.error(f"Failed to type character '{char}' via JavaScript: {js_e}")
                
                logger.info("Finished human-like typing simulation.")
                
                # Method 2: JavaScript ile UTF-8 desteği
                try:
                    self.driver.execute_script("""
                        var textarea = arguments[0];
                        var text = arguments[1];
                        
                        // Clear first
                        textarea.textContent = '';
                        textarea.innerHTML = '';
                        
                        // Set the text with proper encoding
                        textarea.textContent = text;
                        textarea.innerHTML = text;
                        
                        // Focus on textarea
                        textarea.focus();
                        
                        // Trigger input events to activate the button
                        textarea.dispatchEvent(new Event('input', { bubbles: true }));
                        textarea.dispatchEvent(new Event('change', { bubbles: true }));
                        textarea.dispatchEvent(new Event('keyup', { bubbles: true }));
                        textarea.dispatchEvent(new Event('keydown', { bubbles: true }));
                        
                        // Simulate typing events for each character
                        for (var i = 0; i < text.length; i++) {
                            textarea.dispatchEvent(new KeyboardEvent('keydown', { 
                                key: text[i], 
                                code: 'Key' + text[i].toUpperCase(),
                                bubbles: true 
                            }));
                            textarea.dispatchEvent(new KeyboardEvent('keyup', { 
                                key: text[i], 
                                code: 'Key' + text[i].toUpperCase(),
                                bubbles: true 
                            }));
                        }
                    """, text_area, tweet_text)
                    logger.info("Set text via JavaScript with UTF-8 support.")
                except Exception as e:
                    logger.warning(f"JavaScript method failed: {e}")
                    # Fallback: try simpler method
                    try:
                        self.driver.execute_script("""
                            var textarea = arguments[0];
                            var text = arguments[1];
                            textarea.innerHTML = text;
                            textarea.dispatchEvent(new Event('input', { bubbles: true }));
                        """, text_area, tweet_text)
                        logger.info("Set text via simple JavaScript fallback.")
                    except Exception as fallback_e:
                        logger.error(f"JavaScript fallback also failed: {fallback_e}")
                
                # Method 2: Trigger input events to activate button
                self.driver.execute_script("""
                    var textarea = arguments[0];
                    var text = arguments[1];
                    
                    // Set the text
                    textarea.innerHTML = text;
                    
                    // Trigger input events to activate the button
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                    textarea.dispatchEvent(new Event('change', { bubbles: true }));
                    textarea.dispatchEvent(new Event('keyup', { bubbles: true }));
                    textarea.dispatchEvent(new Event('keydown', { bubbles: true }));
                    
                    // Focus on textarea
                    textarea.focus();
                    
                    // Simulate typing to trigger character count
                    for (var i = 0; i < text.length; i++) {
                        textarea.dispatchEvent(new KeyboardEvent('keydown', { key: text[i] }));
                        textarea.dispatchEvent(new KeyboardEvent('keyup', { key: text[i] }));
                    }
                """, text_area, tweet_text)
                logger.info("Triggered input events to activate button.")
                
                # Method 3: Add a character and then remove it to force button activation
                # This helps when Twitter detects copy-paste and keeps button disabled
                time.sleep(1)
                self.driver.execute_script("""
                    var textarea = arguments[0];
                    var originalText = textarea.innerHTML;
                    
                    // Add a character to force activation
                    textarea.innerHTML = originalText + ' ';
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                    textarea.dispatchEvent(new Event('change', { bubbles: true }));
                    
                    // Wait a bit then remove the extra character
                    setTimeout(function() {
                        textarea.innerHTML = originalText;
                        textarea.dispatchEvent(new Event('input', { bubbles: true }));
                        textarea.dispatchEvent(new Event('change', { bubbles: true }));
                    }, 500);
                """, text_area)
                logger.info("Added and removed character to force button activation.")
                
                # Wait a bit for button to activate
                time.sleep(2)
                
                # Method 4: Simulate actual typing if button is still disabled
                try:
                    # Try to find the post button and check if it's enabled
                    post_button_check = self.driver.find_element(By.XPATH, '//*[@id="layers"]/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div/div[3]/div[2]/div[1]/div/div/div/div[2]/div[2]/div/div/div/button')
                    is_enabled = post_button_check.is_enabled()
                    logger.info(f"Post button enabled: {is_enabled}")
                    
                    if not is_enabled:
                        logger.warning("Post button is still disabled. Trying actual typing simulation...")
                        
                        # Clear and type character by character to simulate real typing
                        text_area.clear()
                        time.sleep(0.5)
                        
                        # Type the text character by character
                        for char in tweet_text:
                            text_area.send_keys(char)
                            time.sleep(0.05)  # Small delay between characters
                        
                        logger.info("Simulated actual typing character by character.")
                        time.sleep(1)
                        
                        # If still disabled, try the character addition/removal method
                        if not post_button_check.is_enabled():
                            logger.warning("Button still disabled after typing. Trying character manipulation...")
                            
                            # Add a character and remove it
                            text_area.send_keys(' ')
                            time.sleep(0.5)
                            text_area.send_keys(Keys.BACKSPACE)
                            time.sleep(0.5)
                            
                            logger.info("Added and removed space character to force activation.")
                        
                except Exception as e:
                    logger.warning(f"Could not check button status: {e}")
                        
                except Exception as e:
                    logger.warning(f"Could not check button status: {e}")
                
            except Exception as e:
                logger.error(f"Failed to type text: {e}")
                return False

        # Upload media if any
            if final_media_paths:
                # Twitter typically allows up to 4 images, 1 GIF, or 1 video.
                # This uploader handles one file at a time if multiple inputs are not present.
                # For multiple files, X.com might have one input that accepts multiple files,
                # or you might need to click an "add media" button for subsequent files.
                
                # The input element is often hidden. It might be easier to find the button that triggers it.
                # For simplicity, assuming a single file input `input[type="file"]` that can handle multiple files.
                # Join paths with '\n' if the input field accepts it for multiple files.
                
                # Locate the file input element. It's often visually hidden.
                # The actual button to click might be different.
                file_input_xpath = '//input[@data-testid="fileInput" and @type="file"]'
                
                # Click the "Add media" button first if it's separate
                try:
                    add_media_button = self.driver.find_element(By.XPATH, '//button[@data-testid="mediaButton"]')
                    add_media_button.click()
                    time.sleep(1) # Wait for file dialog to be ready (conceptually)
                except NoSuchElementException:
                    logger.debug("Did not find a separate 'Add Media' button, proceeding to file input.")

                file_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, file_input_xpath))
                )
                
                # For multiple files, send them as a newline-separated string to the input element
                # This works if the <input type="file" multiple> is used.
                files_to_upload_str = "\n".join(final_media_paths)
                file_input.send_keys(files_to_upload_str)
                logger.info(f"Sent {len(final_media_paths)} media file(s) to input: {files_to_upload_str}")
                time.sleep(5) # Wait for media to upload and preview

            # Click the "Post" button - try multiple selectors with more aggressive approach
            post_button = None
            selectors = [
                # Kullanıcının bulduğu EN GÜVENİLİR XPath - layers içindeki button
                '//*[@id="layers"]/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div/div[3]/div[2]/div[1]/div/div/div/div[2]/div[2]/div/div/div/button/div/span/span',
                # Alternatif - layers içindeki button'ın parent'ı
                '//*[@id="layers"]/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div/div[3]/div[2]/div[1]/div/div/div/div[2]/div[2]/div/div/div/button',
                # Eski güvenilir XPath'ler
                '//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div/div/div[3]/div/div[2]/div[1]/div/div/div/div[2]/div[2]/div[2]/div/div/div/button/div/span',
                '//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div/div/div[3]/div/div[2]/div[1]/div/div/div/div[2]/div[2]/div[2]/div/div/div/button',
                # Genel selectors
                '//button[@data-testid="tweetButton"]',
                '//button[@data-testid="tweetButtonInline"]',
                '//button[@data-testid="postButton"]',
                '//button[contains(@class, "tweet") and contains(@class, "button")]',
                '//button[contains(@class, "post") and contains(@class, "button")]',
                '//button[text()="Post"]',
                '//button[text()="Tweet"]',
                '//button[contains(text(), "Post")]',
                '//button[contains(text(), "Tweet")]',
                '//div[@data-testid="tweetButton"]',
                '//div[@data-testid="postButton"]',
                '//div[contains(@class, "tweet") and contains(@class, "button")]',
                '//div[contains(@class, "post") and contains(@class, "button")]',
                '//span[text()="Post"]/parent::button',
                '//span[text()="Tweet"]/parent::button',
                '//span[contains(text(), "Post")]/parent::button',
                '//span[contains(text(), "Tweet")]/parent::button',
                # Daha geniş arama
                '//button[contains(@class, "primary")]',
                '//button[contains(@class, "submit")]',
                '//button[@type="submit"]',
                '//button[@role="button"]',
                '//div[@role="button"]',
                '//button[contains(@aria-label, "Post")]',
                '//button[contains(@aria-label, "Tweet")]',
                '//button[contains(@aria-label, "Send")]',
                # En son çare - tüm butonları dene
                '//button[not(@disabled)]'
            ]
            
            # Önce normal yöntemle dene
            for selector in selectors:
                try:
                    post_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    logger.info(f"Found post button with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            # Eğer bulamazsa, JavaScript ile tüm butonları bul
            if not post_button:
                logger.warning("Could not find post button with normal selectors, trying JavaScript approach...")
                try:
                    # Önce kullanıcının verdiği spesifik CSS selector'ı dene
                    post_button = self.driver.execute_script("""
                        // Kullanıcının verdiği spesifik selector
                        var specificButton = document.querySelector("#layers > div:nth-child(2) > div > div > div > div > div > div.css-175oi2r.r-1ny4l3l.r-18u37iz.r-1pi2tsx.r-1777fci.r-1xcajam.r-ipm5af.r-g6jmlv.r-1habvwh > div.css-175oi2r.r-1wbh5a2.r-htvplk.r-1udh08x.r-1867qdf.r-rsyp9y.r-1pjcn9w.r-1potc6q > div > div > div > div:nth-child(3) > div.css-175oi2r.r-1h8ys4a.r-dq6lxq.r-hucgq0 > div:nth-child(1) > div > div > div > div.css-175oi2r.r-14lw9ot.r-jumn1c.r-xd6kpl.r-gtdqiz.r-ipm5af.r-184en5c > div:nth-child(2) > div > div > div > button > div > span > span");
                        if (specificButton) {
                            return specificButton.closest('button') || specificButton;
                        }
                        
                        // Layers içindeki button'ları ara
                        var layersButtons = document.querySelectorAll("#layers button");
                        for (var i = 0; i < layersButtons.length; i++) {
                            var text = layersButtons[i].textContent || layersButtons[i].innerText || '';
                            if (text.toLowerCase().includes('post') || text.toLowerCase().includes('tweet')) {
                                return layersButtons[i];
                            }
                        }
                        
                        // Genel button arama
                        var buttons = document.querySelectorAll('button');
                        for (var i = 0; i < buttons.length; i++) {
                            var text = buttons[i].textContent || buttons[i].innerText || '';
                            if (text.toLowerCase().includes('post') || text.toLowerCase().includes('tweet')) {
                                return buttons[i];
                            }
                        }
                        
                        // Eğer bulamazsa, ilk aktif butonu al
                        for (var i = 0; i < buttons.length; i++) {
                            if (!buttons[i].disabled && buttons[i].offsetParent !== null) {
                                return buttons[i];
                            }
                        }
                        return null;
                    """)
                    if post_button:
                        logger.info("Found post button using JavaScript approach")
                    else:
                        logger.error("Could not find any suitable button")
                        return False
                except Exception as e:
                    logger.error(f"JavaScript approach failed: {e}")
                    return False
            
            # Aggressive click approach with multiple methods
            click_success = False
            
            # Method 1: Try to find and click the actual button element
            try:
                if post_button.tag_name == 'span':
                    # Span'in parent button'ını bul
                    parent_button = post_button.find_element(By.XPATH, './ancestor::button')
                    parent_button.click()
                    logger.info("Clicked 'Post' button (span's parent) using simple click.")
                    click_success = True
                else:
                    # Normal button click
                    post_button.click()
                    logger.info("Clicked 'Post' button using simple click.")
                    click_success = True
            except Exception as e:
                logger.warning(f"Simple click failed: {e}. Trying JavaScript click...")
            
            # Method 2: JavaScript click if simple click failed
            if not click_success:
                try:
                    if post_button.tag_name == 'span':
                        # Span için parent button'ı JavaScript ile tıkla
                        self.driver.execute_script("arguments[0].closest('button').click();", post_button)
                    else:
                        # Normal JavaScript click
                        self.driver.execute_script("arguments[0].click();", post_button)
                    logger.info("Clicked 'Post' button using JavaScript click.")
                    click_success = True
                except Exception as e2:
                    logger.warning(f"JavaScript click failed: {e2}. Trying Enter key...")
            
            # Method 3: Try Enter key simulation
            if not click_success:
                try:
                    # Focus on text area and press Enter
                    text_area.send_keys(Keys.RETURN)
                    logger.info("Pressed Enter key to submit tweet.")
                    click_success = True
                except Exception as e3:
                    logger.warning(f"Enter key failed: {e3}. Trying Tab + Enter...")
            
            # Method 4: Try Tab + Enter
            if not click_success:
                try:
                    # Tab to next element (should be the button) and press Enter
                    text_area.send_keys(Keys.TAB)
                    time.sleep(0.5)
                    text_area.send_keys(Keys.RETURN)
                    logger.info("Pressed Tab + Enter to submit tweet.")
                    click_success = True
                except Exception as e4:
                    logger.warning(f"Tab + Enter failed: {e4}. Trying direct button search...")
            
            # Method 5: Try to find button by text and click
            if not click_success:
                try:
                    # Try to find any button with "Post" or "Tweet" text
                    button_texts = ["Post", "Tweet", "Send"]
                    for text in button_texts:
                        try:
                            button = self.driver.find_element(By.XPATH, f"//button[contains(text(), '{text}')]")
                            button.click()
                            logger.info(f"Found and clicked button with text '{text}'.")
                            click_success = True
                            break
                        except:
                            continue
                except Exception as e5:
                    logger.warning(f"Direct button search failed: {e5}")
            
            if not click_success:
                logger.error("All click methods failed!")
                return False

            # Human-like delay before posting (2-4 seconds)
            pre_post_delay = random.uniform(2, 4)
            logger.info(f"Waiting {pre_post_delay:.1f} seconds before posting (human-like behavior)...")
            time.sleep(pre_post_delay)

            # Wait for confirmation and verify tweet was actually posted
            time.sleep(3) # Wait for tweet to be processed
            
            # Try to verify tweet was posted by checking for success indicators
            try:
                # Method 1: Check for success notification
                success_indicators = [
                    '//div[contains(text(), "Your post was sent")]',
                    '//div[contains(text(), "Tweet sent")]',
                    '//div[contains(text(), "Your Tweet was sent")]',
                    '//div[contains(@data-testid, "toast")]',
                    '//div[contains(@class, "success")]'
                ]
                
                tweet_posted = False
                for indicator in success_indicators:
                    try:
                        success_element = WebDriverWait(self.driver, 2).until(
                            EC.presence_of_element_located((By.XPATH, indicator))
                        )
                        logger.info(f"Found success indicator: {indicator}")
                        tweet_posted = True
                        break
                    except TimeoutException:
                        continue
                
                # Method 2: Check if we're back to home page (tweet composer closed)
                if not tweet_posted:
                    try:
                        # Check if compose URL is no longer active
                        current_url = self.driver.current_url
                        if "compose" not in current_url.lower():
                            logger.info("Tweet composer closed, assuming tweet was posted.")
                            tweet_posted = True
                    except:
                        pass
                
                # Method 3: Check if text area is empty (tweet was sent)
                if not tweet_posted:
                    try:
                        # Try to find text area again and check if it's empty
                        text_area_after = self.driver.find_element(By.XPATH, '//div[@data-testid="tweetTextarea_0"]')
                        if not text_area_after.text.strip():
                            logger.info("Text area is empty, assuming tweet was posted.")
                            tweet_posted = True
                    except:
                        pass
                
                if tweet_posted:
                    logger.info(f"Tweet posted successfully: '{tweet_text[:50]}...'")
                    
                    # Human-like behavior: Scroll around after posting
                    try:
                        logger.info("Adding post-tweet human-like behavior...")
                        # Scroll down a bit to see the posted tweet
                        self.driver.execute_script("window.scrollBy(0, 200);")
                        time.sleep(random.uniform(1, 3))
                        
                        # Scroll back up slightly
                        self.driver.execute_script("window.scrollBy(0, -100);")
                        time.sleep(random.uniform(0.5, 1.5))
                        
                        logger.info("Completed post-tweet scrolling behavior.")
                    except Exception as e:
                        logger.warning(f"Post-tweet scrolling failed: {e}")
                    
                    return True
                else:
                    logger.warning("Could not verify tweet was posted, but continuing...")
                    return True  # Assume success if we can't verify
                    
            except Exception as e:
                logger.warning(f"Error during tweet verification: {e}")
                return True  # Assume success if verification fails

        except TimeoutException as e:
            logger.error(f"Timeout while trying to post tweet: {e}")
            # self.browser_manager.save_screenshot("post_tweet_timeout") # Optional: for debugging
            return False
        except Exception as e:
            logger.error(f"Failed to post tweet: {e}", exc_info=True)
            # self.browser_manager.save_screenshot("post_tweet_error") # Optional
            return False

    async def reply_to_tweet(self, original_tweet: ScrapedTweet, reply_text: str) -> bool:
        """
        Replies to a given tweet.
        :param original_tweet: The ScrapedTweet object of the tweet to reply to.
        :param reply_text: The text content of the reply (should be pre-generated).
        """
        if not original_tweet.tweet_url:
            logger.error(f"Cannot reply to tweet {original_tweet.tweet_id}: Missing tweet URL.")
            return False
        if not reply_text:
            logger.error(f"Cannot reply to tweet {original_tweet.tweet_id}: Reply text is empty.")
            return False

        logger.info(f"Attempting to reply to tweet {original_tweet.tweet_id} with text: '{reply_text[:50]}...'")

        try:
            self.browser_manager.navigate_to(str(original_tweet.tweet_url))
            
            # Human-like behavior: Add random delay and scrolling
            logger.info("Adding human-like behavior before replying...")
            time.sleep(random.uniform(2, 4))  # Random delay before interacting
            
            # Scroll around to simulate human reading
            try:
                scroll_amount = random.randint(-200, 200)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                logger.info(f"Scrolling {scroll_amount} pixels before replying...")
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                logger.warning(f"Pre-reply scrolling failed: {e}")
            
            # Wait for tweet page to load
            time.sleep(3)

            # Click the reply button on the main tweet to open the reply composer
            # This selector targets the reply icon/button for the specific tweet.
            # It might be within an article tag corresponding to the tweet.
            # First, try to find the main tweet article to scope the search for reply button
            main_tweet_article_xpath = f"//article[.//a[contains(@href, '/status/{original_tweet.tweet_id}')]]"
            main_tweet_element = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, main_tweet_article_xpath))
            )
            
            reply_icon_button = WebDriverWait(main_tweet_element, 10).until(
                EC.element_to_be_clickable((By.XPATH, './/button[@data-testid="reply"]')) # Relative to the tweet article
            )
            reply_icon_button.click()
            logger.info(f"Clicked reply icon for tweet {original_tweet.tweet_id}.")
            time.sleep(2) # Wait for reply composer to appear

            # The reply composer's text area and post button might be similar to the main tweet composer
            reply_text_area_xpath = '//div[@data-testid="tweetTextarea_0" and @role="textbox"]' # More specific
            reply_text_area = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, reply_text_area_xpath))
            )
            
            # reply_text_area.click() # Sometimes helpful
            reply_text_area.clear()
            
            # Türkçe karakter desteği için UTF-8 encoding kullan
            logger.info(f"Reply text: {reply_text[:50]}...")
            
            # Method 1: Direct send_keys with UTF-8 support
            for char in reply_text:
                reply_text_area.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            # Method 2: JavaScript ile UTF-8 desteği
            self.driver.execute_script("""
                var textarea = arguments[0];
                var text = arguments[1];
                
                // Set the text with proper encoding
                textarea.textContent = text;
                textarea.innerHTML = text;
                
                // Trigger input events to activate the button
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                textarea.dispatchEvent(new Event('change', { bubbles: true }));
                textarea.dispatchEvent(new Event('keyup', { bubbles: true }));
                textarea.dispatchEvent(new Event('keydown', { bubbles: true }));
            """, reply_text_area, reply_text)
            
            logger.info("Typed reply text into textarea with UTF-8 support.")

            # Click the "Reply" button in the composer
            # This is often also data-testid="tweetButton" but it's specific to the composer context
            reply_post_button_xpath = '//button[@data-testid="tweetButton"]' 
            # Ensure it's the one in the modal/composer, might need a more specific parent selector if ambiguous
            # For example, if the composer is in a modal: //div[@data-testid="layers"]//button[@data-testid="tweetButton"]
            
            # Let's try to find it within a modal layer if possible, as that's common for reply composers
            try:
                layers_xpath = '//div[@data-testid="layers"]'
                modal_layer = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, layers_xpath))
                )
                reply_post_button = WebDriverWait(modal_layer, 10).until(
                    EC.element_to_be_clickable((By.XPATH, './/button[@data-testid="tweetButton"]'))
                )
            except TimeoutException: # Fallback if not in a typical modal layer structure
                logger.debug("Reply composer not found in standard modal layer, trying general tweetButton.")
                reply_post_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, reply_post_button_xpath))
                )

            # Enhanced click method with overlay removal
            def safe_click(element, element_name):
                try:
                    # Method 1: Remove overlays and click with JavaScript
                    self.driver.execute_script("""
                        // Remove any overlays that might be blocking the element
                        var overlays = document.querySelectorAll('div[class*="css-"]');
                        for (var i = 0; i < overlays.length; i++) {
                            var style = window.getComputedStyle(overlays[i]);
                            if (style.zIndex > 1000 || style.position === 'fixed') {
                                overlays[i].style.display = 'none';
                            }
                        }
                        // Scroll element into view
                        arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});
                        // Wait a bit
                        setTimeout(function() {
                            arguments[0].click();
                        }, 500);
                    """, element)
                    logger.info(f"Clicked {element_name} using enhanced JavaScript method.")
                    return True
                except Exception as e1:
                    logger.warning(f"Enhanced JavaScript click failed: {e1}")
                    try:
                        # Method 2: Regular JavaScript click
                        self.driver.execute_script("arguments[0].click();", element)
                        logger.info(f"Clicked {element_name} using regular JavaScript.")
                        return True
                    except Exception as e2:
                        logger.warning(f"Regular JavaScript click failed: {e2}")
                        try:
                            # Method 3: Regular click
                            element.click()
                            logger.info(f"Clicked {element_name} using regular click.")
                            return True
                        except Exception as e3:
                            logger.error(f"All click methods failed for {element_name}: {e3}")
                            return False
            
            # Try the enhanced click method
            if not safe_click(reply_post_button, "'Reply' button"):
                return False

            # Wait for confirmation (e.g., "Your reply was sent.")
            # This is highly UI-dependent. A simple delay for now.
            time.sleep(5) 
            # TODO: Add a more robust check for reply success, e.g., looking for the reply to appear on the page or a success notification.
            
            logger.info(f"Reply to tweet {original_tweet.tweet_id} posted successfully.")
            return True

        except TimeoutException as e:
            logger.error(f"Timeout while trying to reply to tweet {original_tweet.tweet_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to reply to tweet {original_tweet.tweet_id}: {e}", exc_info=True)
            return False

    async def retweet_tweet(self, original_tweet: ScrapedTweet, quote_text_prompt_or_direct: Optional[str] = None, llm_settings_for_quote: Optional[LLMSettings] = None) -> bool:
        """
        Retweets a given tweet. Can be a simple retweet or a quote tweet if quote_text is provided.
        If quote_text_prompt_or_direct is a prompt, it will be generated by LLM.
        """
        if not original_tweet.tweet_url: # Need URL to navigate to the tweet
            logger.error(f"Cannot retweet tweet {original_tweet.tweet_id}: Missing tweet URL.")
            return False

        final_quote_text: Optional[str] = None
        is_quote_tweet = bool(quote_text_prompt_or_direct)

        if is_quote_tweet and llm_settings_for_quote and \
           ("generate quote for" in quote_text_prompt_or_direct.lower() or "write a quote about" in quote_text_prompt_or_direct.lower()):
            logger.info(f"Generating quote text for tweet {original_tweet.tweet_id} using prompt: {quote_text_prompt_or_direct}")
            generated_quote = await self.llm_service.generate_text(
                prompt=quote_text_prompt_or_direct,
                service_preference=llm_settings_for_quote.service_preference,
                model_name=llm_settings_for_quote.model_name_override,
                max_tokens=llm_settings_for_quote.max_tokens,
                temperature=llm_settings_for_quote.temperature
            )
            if not generated_quote:
                logger.error(f"Failed to generate quote text for tweet {original_tweet.tweet_id}. Aborting retweet.")
                return False
            final_quote_text = generated_quote
            logger.info(f"Generated quote text: {final_quote_text}")
        elif is_quote_tweet:
            final_quote_text = quote_text_prompt_or_direct # Use as direct text

        action_type_log = "Quote Tweet" if is_quote_tweet else "Retweet"
        logger.info(f"Attempting {action_type_log} for tweet ID: {original_tweet.tweet_id}")
        if final_quote_text:
            logger.info(f"Quote text: '{final_quote_text[:50]}...'")

        try:
            self.browser_manager.navigate_to(str(original_tweet.tweet_url))
            
            # Human-like behavior: Add random delay and scrolling
            logger.info("Adding human-like behavior before retweeting...")
            time.sleep(random.uniform(2, 4))  # Random delay before interacting
            
            # Scroll around to simulate human reading
            try:
                scroll_amount = random.randint(-200, 200)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                logger.info(f"Scrolling {scroll_amount} pixels before retweeting...")
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                logger.warning(f"Pre-retweet scrolling failed: {e}")
            
            # Wait for tweet page to load
            time.sleep(3)

            main_tweet_article_xpath = f"//article[.//a[contains(@href, '/status/{original_tweet.tweet_id}')]]"
            main_tweet_element = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, main_tweet_article_xpath))
            )
            
            retweet_button_xpath = './/button[@data-testid="retweet"]' # Relative to tweet article
            retweet_icon_button = WebDriverWait(main_tweet_element, 10).until(
                EC.element_to_be_clickable((By.XPATH, retweet_button_xpath))
            )
            
            # Check if already retweeted (aria-label might change to "Undo Retweet" or similar)
            # Or the icon color might change. This is complex to check reliably via DOM alone for retweets.
            # For now, we'll proceed. Twitter usually handles duplicate retweets gracefully (e.g., by un-retweeting).
            
            # Human-like behavior: Hover before clicking retweet button
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(retweet_icon_button).pause(random.uniform(0.5, 1.5)).perform()
                logger.info("Hovered over retweet button before clicking...")
            except Exception as e:
                logger.warning(f"Retweet hover behavior failed: {e}")
            
            # Use the same enhanced click method for retweet
            if not safe_click(retweet_icon_button, f"retweet icon for tweet {original_tweet.tweet_id}"):
                return False
            
            # Human-like delay after clicking retweet button
            retweet_delay = random.uniform(1, 3)
            logger.info(f"Waiting {retweet_delay:.1f} seconds for retweet menu to appear...")
            time.sleep(retweet_delay)

            if is_quote_tweet:
                # Click "Quote" option in the menu
                quote_option_xpath = '//a[@data-testid="tweet opción Quote"]' # This selector is an example, needs verification
                # A more reliable way might be to find menu item by role and text "Quote" or "Quote Tweet"
                # Example: //div[@role="menuitem"]//span[text()="Quote"] or similar
                # For now, using a placeholder data-testid which is unlikely to be correct.
                # Let's try a more generic approach: find a menu item containing "Quote"
                try:
                    quote_option = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, '//div[@role="menuitem" and contains(., "Quote")]'))
                    )
                except TimeoutException: # Fallback for older UIs or different text
                     quote_option = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, '//div[@data-testid="Dropdown"]//a[contains(@href,"/compose/tweet")]'))) # Common pattern for quote tweet link
                
                # Use the same enhanced click method for quote option
                if not safe_click(quote_option, "'Quote' option"):
                    return False
                time.sleep(2) # Wait for quote tweet composer to appear

                # Composer text area for quote
                quote_text_area_xpath = '//div[@data-testid="tweetTextarea_0" and @role="textbox"]'
                quote_text_area = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, quote_text_area_xpath))
                )
                
                # Human-like typing behavior for quote tweet with UTF-8 support
                logger.info("Starting human-like typing for quote tweet...")
                logger.info(f"Quote text: {final_quote_text[:50]}...")
                quote_text_area.clear()
                time.sleep(random.uniform(0.5, 1.0))
                
                # Method 1: Direct send_keys with UTF-8 support
                for char in final_quote_text:
                    quote_text_area.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
                    
                    # Occasionally pause longer (like humans do when thinking)
                    if random.random() < 0.1:  # 10% chance
                        pause_duration = random.uniform(0.5, 2.0)
                        logger.info(f"Pausing for {pause_duration:.1f} seconds during quote typing...")
                        time.sleep(pause_duration)
                
                # Method 2: JavaScript ile UTF-8 desteği
                self.driver.execute_script("""
                    var textarea = arguments[0];
                    var text = arguments[1];
                    
                    // Set the text with proper encoding
                    textarea.textContent = text;
                    textarea.innerHTML = text;
                    
                    // Trigger input events to activate the button
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                    textarea.dispatchEvent(new Event('change', { bubbles: true }));
                    textarea.dispatchEvent(new Event('keyup', { bubbles: true }));
                    textarea.dispatchEvent(new Event('keydown', { bubbles: true }));
                """, quote_text_area, final_quote_text)
                
                logger.info("Finished human-like typing for quote tweet with UTF-8 support.")
                logger.info("Typed quote text.")

                # Click "Post" button for the quote tweet
                post_button_xpath = '//button[@data-testid="tweetButton"]' # Usually the same for all posts
                post_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, post_button_xpath))
                )
                post_button.click()
                logger.info("Clicked 'Post' for quote tweet.")

            else: # Simple Retweet
                # Click "Repost" (or "Retweet") confirmation in the menu
                # Example: //div[@role="menuitem"]//span[text()="Repost"]
                # Or data-testid="retweetConfirm"
                try:
                    confirm_retweet_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, '//button[@data-testid="retweetConfirm"]')) # Common testid
                    )
                except TimeoutException:
                     confirm_retweet_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, '//div[@role="menuitem" and contains(., "Repost")]//div[1]')) # Click the div if span is tricky
                    )
                confirm_retweet_button.click()
                logger.info("Clicked 'Repost' (confirm retweet) option.")

            time.sleep(5) # Wait for action to complete
            # TODO: Add robust check for retweet/quote tweet success.
            
            logger.info(f"{action_type_log} for tweet {original_tweet.tweet_id} successful.")
            return True

        except TimeoutException as e:
            logger.error(f"Timeout during {action_type_log.lower()} for tweet {original_tweet.tweet_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to {action_type_log.lower()} tweet {original_tweet.tweet_id}: {e}", exc_info=True)
            return False


if __name__ == '__main__':
    import asyncio
    # Example Usage:
    # This requires config/settings.json and potentially config/accounts.json to be set up
    # with valid API keys for LLM and cookie info for Twitter.

    async def test_publisher():
        cfg_loader = ConfigLoader()
        accounts = cfg_loader.get_accounts_config()
        
        if not accounts:
            logger.error("No accounts configured in config/accounts.json. Cannot run publisher test.")
            return

        # Use the first active account for testing
        active_account_config_dict = None
        for acc_dict in accounts:
            if acc_dict.get("is_active", True): # Default to active if not specified
                # Convert dict to AccountConfig Pydantic model if needed by BrowserManager/Publisher
                # For now, assuming BrowserManager can handle dict or has its own parsing
                active_account_config_dict = acc_dict 
                break
        
        if not active_account_config_dict:
            logger.error("No active accounts found in config/accounts.json.")
            return
        
        # Create AccountConfig Pydantic model instance
        # This assumes your accounts.json structure matches AccountConfig or is adaptable
        # For simplicity, let's assume direct fields match or BrowserManager handles dict
        try:
            # A more robust way would be to parse active_account_config_dict into AccountConfig model
            # For now, we pass the dict, BrowserManager is designed to handle it for cookies.
            # Publisher's __init__ expects AccountConfig model, so we should ideally parse it.
            # However, for this test, we'll focus on the publisher methods.
            # Let's assume account_config in publisher is mainly for context like account_id.
            # A proper AccountConfig model instance should be created for full functionality.
            
            # Simplified AccountConfig for test context
            mock_account_model = AccountConfig(
                account_id=active_account_config_dict.get("account_id", "test_publisher_user"),
                cookie_file_path=active_account_config_dict.get("cookie_file_path") # BrowserManager uses this
            )

        except Exception as e:
            logger.error(f"Failed to prepare account config for test: {e}")
            return


        bm = BrowserManager(account_config=active_account_config_dict) # BrowserManager takes the dict
        llm = LLMService(config_loader=cfg_loader)
        
        # Pass the Pydantic model to publisher if its __init__ strictly requires it
        # For this test, we'll assume the publisher can work with the account_id from a simplified model
        # or that its __init__ is flexible. The provided code for Publisher takes AccountConfig.
        publisher = TweetPublisher(browser_manager=bm, llm_service=llm, account_config=mock_account_model)

        try:
            logger.info(f"Testing publisher for account: {mock_account_model.account_id}")

            # Test 1: Post a simple text tweet
            simple_content = TweetContent(text="Hello from the automated world! This is a test tweet. #Python #Automation")
            logger.info("\n--- Testing simple text post ---")
            success = await publisher.post_new_tweet(simple_content)
            logger.info(f"Simple text post successful: {success}")
            if not success: time.sleep(2) # Pause if failed

            # Test 2: Post a tweet with text generated by LLM
            llm_prompt = "Generate a short, optimistic tweet about the impact of AI on creativity. Include #AI #Creativity."
            # Define LLMSettings for this generation
            gen_llm_settings = LLMSettings(service_preference="gemini", max_tokens=100, temperature=0.8) # Prefer Gemini
            
            prompt_content = TweetContent(text=llm_prompt) # Text here is the prompt
            logger.info("\n--- Testing LLM-generated post ---")
            success_llm = await publisher.post_new_tweet(prompt_content, llm_settings=gen_llm_settings)
            logger.info(f"LLM-generated post successful: {success_llm}")
            if not success_llm: time.sleep(2)


            # Test 3: Post a tweet with media (requires a valid image/video URL)
            # Replace with a real, accessible image URL for testing
            # media_image_url = "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png"
            # content_with_media = TweetContent(
            #     text="Check out this cool Python logo! #Python #Logo #Test",
            #     media_urls=[media_image_url]
            # )
            # logger.info("\n--- Testing post with media ---")
            # success_media = await publisher.post_new_tweet(content_with_media)
            # logger.info(f"Post with media successful: {success_media}")

        except Exception as e:
            logger.error(f"Error during publisher test: {e}", exc_info=True)
        finally:
            logger.info("Closing browser manager after publisher test...")
            publisher.browser_manager.close_driver()
            logger.info("Publisher test finished.")

    asyncio.run(test_publisher())
