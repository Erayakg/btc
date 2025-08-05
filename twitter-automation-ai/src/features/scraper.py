import os
import sys
import time
import re
import random
from typing import List, Optional, Tuple
from datetime import datetime, timezone

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains

# Adjust import paths
try:
    from ..core.browser_manager import BrowserManager
    from ..core.config_loader import ConfigLoader
    from ..utils.logger import setup_logger
    from ..data_models import ScrapedTweet
    from ..utils.scroller import Scroller
    from ..utils.progress import Progress
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..')) # Add root src to path
    from src.core.browser_manager import BrowserManager
    from src.core.config_loader import ConfigLoader
    from src.utils.logger import setup_logger
    from src.data_models import ScrapedTweet
    from src.utils.scroller import Scroller
    from src.utils.progress import Progress

config = ConfigLoader()
logger = setup_logger(config)

class TweetScraper:
    def __init__(self, browser_manager: BrowserManager, account_id: Optional[str] = None):
        self.browser_manager = browser_manager
        self.driver = self.browser_manager.get_driver()
        self.actions = ActionChains(self.driver)
        self.config_loader = browser_manager.config_loader
        self.scroller = Scroller(self.driver)
        self.account_id = account_id

        self.scrape_settings = self.config_loader.get_twitter_automation_setting("scraper_config", {})
        self.default_max_tweets = self.config_loader.get_twitter_automation_setting("max_tweets_per_scrape", 50)
        # REDUCED DELAYS
        self.scroll_delay_min = self.scrape_settings.get("scroll_delay_min_seconds", 0.3)  # was 1.5
        self.scroll_delay_max = self.scrape_settings.get("scroll_delay_max_seconds", 0.7)  # was 3.5
        self.no_new_tweets_scroll_limit = self.scrape_settings.get("no_new_tweets_scroll_limit", 3) # was 5

    def _wait_for_page_load(self, timeout: int = 7) -> bool:  # was 15
        """Wait for page to load with multiple strategies"""
        wait_strategies = [
            '//article[@data-testid="tweet"]',
            '//div[@data-testid="cellInnerDiv"]',
            '//div[@role="article"]',
            '//div[contains(@data-testid, "tweet")]',
            '//article[contains(@class, "css-")]',
            '//div[contains(@class, "css-") and contains(@class, "tweet")]',
            '//div[contains(@class, "css-")]//article',
            '//div[@data-testid="cellInnerDiv"]//div[contains(@class, "css-")]'
        ]
        for strategy in wait_strategies:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, strategy))
                )
                logger.info(f"Page loaded successfully with strategy: {strategy}")
                return True
            except TimeoutException:
                logger.debug(f"Strategy {strategy} timed out")
                continue
        logger.warning("All wait strategies timed out")
        return False

    def _get_tweet_cards_from_page(self) -> List[WebElement]:
        try:
            selectors = [
                '//article[@data-testid="tweet"]',
                '//div[@data-testid="cellInnerDiv"]//article',
                '//div[@data-testid="cellInnerDiv"]//div[contains(@class, "css-")]',
                '//div[@role="article"]',
                '//div[contains(@data-testid, "tweet")]',
                '//article[contains(@class, "css-")]',
                '//div[contains(@class, "css-") and contains(@class, "tweet")]',
                '//div[contains(@class, "css-")]//div[contains(@class, "css-")]',
                '//div[@data-testid="cellInnerDiv"]//div[contains(@class, "css-")]//div[contains(@class, "css-")]'
            ]
            all_elements = []
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        logger.info(f"Found {len(elements)} potential tweet elements with selector: {selector}")
                        all_elements.extend(elements)
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            unique_elements = []
            seen_texts = set()
            for element in all_elements:
                try:
                    text_elements = element.find_elements(By.XPATH, './/span[contains(text(), "@")] | .//div[contains(@class, "css-")]//span')
                    if text_elements:
                        element_text = element.text.strip()
                        if len(element_text) > 10 and element_text not in seen_texts:
                            unique_elements.append(element)
                            seen_texts.add(element_text)
                except Exception:
                    continue
            logger.info(f"Found {len(unique_elements)} unique tweet cards after filtering")
            return unique_elements
        except Exception as e:
            logger.error(f"Error finding tweet cards: {e}")
            return []

    def _parse_tweet_card(self, card_element: WebElement) -> Optional[ScrapedTweet]:
        try:
            user_name = None
            user_name_selectors = [
                './/div[@data-testid="User-Name"]//span[1]//span',
                './/div[@data-testid="User-Name"]//span[1]',
                './/span[contains(text(), "@")]/preceding-sibling::span[1]',
                './/div[contains(@class, "css-")]//span[contains(text(), "@")]/preceding-sibling::span[1]',
                './/div[@data-testid="User-Name"]//span[not(contains(text(), "@"))]',
                './/span[not(contains(text(), "@")) and not(contains(text(), "·"))][1]'
            ]
            for selector in user_name_selectors:
                try:
                    user_name_element = card_element.find_element(By.XPATH, selector)
                    user_name = user_name_element.text.strip()
                    if user_name and len(user_name) > 0:
                        break
                except NoSuchElementException:
                    continue
            user_handle = None
            user_handle_selectors = [
                './/div[@data-testid="User-Name"]//span[contains(text(), "@")]',
                './/span[contains(text(), "@")]',
                './/a[contains(@href, "/status/")]/ancestor::article//span[contains(text(), "@")]',
                './/div[contains(@class, "css-")]//span[contains(text(), "@")]'
            ]
            for selector in user_handle_selectors:
                try:
                    user_handle_element = card_element.find_element(By.XPATH, selector)
                    user_handle = user_handle_element.text.strip()
                    if user_handle and user_handle.startswith('@'):
                        break
                except NoSuchElementException:
                    continue
            text_content = ""
            text_selectors = [
                './/div[@data-testid="tweetText"]//span | .//div[@data-testid="tweetText"]//a',
                './/div[@data-testid="tweetText"]',
                './/div[contains(@class, "css-") and contains(@class, "tweetText")]//span | .//div[contains(@class, "css-") and contains(@class, "tweetText")]//a',
                './/div[contains(@class, "css-")]//span[not(contains(text(), "@"))]',
                './/span[not(contains(text(), "@")) and not(contains(text(), "·"))]',
                './/div[contains(@class, "css-")]//span[not(contains(text(), "@")) and not(contains(text(), "·"))]'
            ]
            for selector in text_selectors:
                try:
                    text_elements = card_element.find_elements(By.XPATH, selector)
                    tweet_text_parts = []
                    for el in text_elements:
                        try:
                            text = el.text.strip()
                            if text and not text.startswith('@') and not text.startswith('·') and len(text) > 1:
                                tweet_text_parts.append(text)
                        except StaleElementReferenceException:
                            continue
                    text_content = " ".join(tweet_text_parts).strip()
                    if text_content and len(text_content) > 10:
                        break
                except Exception:
                    continue
            if not text_content:
                logger.debug("No meaningful text content found for tweet card")
                return None
            tweet_id = None
            tweet_url = None
            url_selectors = [
                './/a[contains(@href, "/status/") and .//time]',
                './/a[contains(@href, "/status/")]',
                './/time/parent::a[contains(@href, "/status/")]',
                './/a[contains(@href, "/status/")]',
                './/div[contains(@class, "css-")]//a[contains(@href, "/status/")]'
            ]
            for selector in url_selectors:
                try:
                    link_element = card_element.find_element(By.XPATH, selector)
                    href = link_element.get_attribute("href")
                    if href and "/status/" in href:
                        tweet_url = href
                        tweet_id = href.split("/status/")[-1].split("?")[0]
                        break
                except NoSuchElementException:
                    continue
            if not tweet_id:
                import hashlib
                content_hash = hashlib.md5(text_content.encode()).hexdigest()[:8]
                tweet_id = f"temp_{content_hash}"
                logger.warning(f"Could not find tweet link/ID element for a card. Using temporary ID: {tweet_id}")
            created_at_dt = None
            try:
                time_element = card_element.find_element(By.XPATH, ".//time")
                datetime_str = time_element.get_attribute("datetime")
                if datetime_str:
                    created_at_dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            except NoSuchElementException:
                logger.debug(f"Timestamp not found for tweet ID {tweet_id}")
            def get_count(testid: str) -> int:
                count_selectors = [
                    f'.//button[@data-testid="{testid}"]//span[@data-testid="app-text-transition-container"]//span',
                    f'.//button[@data-testid="{testid}"]//span',
                    f'.//div[@data-testid="{testid}"]//span',
                    f'.//button[contains(@aria-label, "{testid}")]//span',
                    f'.//div[contains(@class, "css-")]//button[contains(@aria-label, "{testid}")]//span'
                ]
                for selector in count_selectors:
                    try:
                        element = card_element.find_element(By.XPATH, selector)
                        text = element.text.strip()
                        if not text: continue
                        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
                        if 'M' in text: return int(float(text.replace('M', '')) * 1000000)
                        return int(text)
                    except (NoSuchElementException, ValueError):
                        continue
                return 0
            reply_count = get_count("reply")
            retweet_count = get_count("retweet")
            like_count = get_count("like")
            view_count = 0
            view_selectors = [
                './/a[contains(@href, "/analytics")]//span[@data-testid="app-text-transition-container"]//span',
                './/a[contains(@href, "/analytics")]//span',
                './/div[contains(@aria-label, "view")]//span'
            ]
            for selector in view_selectors:
                try:
                    view_element = card_element.find_element(By.XPATH, selector)
                    text = view_element.text.strip()
                    if text:
                        if 'K' in text:
                            view_count = int(float(text.replace('K', '')) * 1000)
                        elif 'M' in text:
                            view_count = int(float(text.replace('M', '')) * 1000000)
                        else:
                            view_count = int(text)
                        break
                except (NoSuchElementException, ValueError):
                    continue
            tags = []
            tag_selectors = [
                './/a[contains(@href, "src=hashtag_click")]',
                './/a[contains(@href, "/hashtag/")]',
                './/span[contains(text(), "#")]'
            ]
            for selector in tag_selectors:
                try:
                    tag_elements = card_element.find_elements(By.XPATH, selector)
                    tags = [tag.text for tag in tag_elements if tag.text]
                    if tags:
                        break
                except Exception:
                    continue
            mentions = []
            mention_selectors = [
                './/div[@data-testid="tweetText"]//a[contains(text(), "@")]',
                './/a[contains(text(), "@")]',
                './/span[contains(text(), "@")]'
            ]
            for selector in mention_selectors:
                try:
                    mention_elements = card_element.find_elements(By.XPATH, selector)
                    mentions = [mention.text for mention in mention_elements if mention.text]
                    if mentions:
                        break
                except Exception:
                    continue
            profile_image_url = None
            img_selectors = [
                './/div[@data-testid="Tweet-User-Avatar"]//img',
                './/img[contains(@alt, "profile")]',
                './/img[contains(@class, "css-")]'
            ]
            for selector in img_selectors:
                try:
                    img_element = card_element.find_element(By.XPATH, selector)
                    profile_image_url = img_element.get_attribute("src")
                    if profile_image_url:
                        break
                except NoSuchElementException:
                    continue
            embedded_media_urls = []
            media_selectors = [
                './/div[@data-testid="tweetPhoto"]//img | .//div[contains(@data-testid, "videoPlayer")]//video',
                './/img[contains(@class, "css-")] | .//video',
                './/div[contains(@data-testid, "media")]//img | .//div[contains(@data-testid, "media")]//video'
            ]
            for selector in media_selectors:
                try:
                    media_elements = card_element.find_elements(By.XPATH, selector)
                    for media_el in media_elements:
                        src = media_el.get_attribute("src") or media_el.get_attribute("poster")
                        if src and src not in embedded_media_urls:
                            embedded_media_urls.append(src)
                    if embedded_media_urls:
                        break
                except Exception:
                    continue
            is_verified = False
            verified_selectors = [
                './/*[local-name()="svg" and @data-testid="icon-verified"]',
                './/svg[@data-testid="icon-verified"]',
                './/div[contains(@aria-label, "verified")]'
            ]
            for selector in verified_selectors:
                try:
                    card_element.find_element(By.XPATH, selector)
                    is_verified = True
                    break
                except NoSuchElementException:
                    continue
            is_thread_candidate = False
            thread_indicators = [r'\(\d+/\d+\)', r'\d+/\d+', 'thread', '🧵', r'1\.', r'a\.', r'i\.']
            for indicator in thread_indicators:
                if re.search(indicator, text_content, re.IGNORECASE):
                    is_thread_candidate = True
                    break
            return ScrapedTweet(
                tweet_id=tweet_id,
                user_name=user_name,
                user_handle=user_handle,
                user_is_verified=is_verified,
                created_at=created_at_dt,
                text_content=text_content,
                reply_count=reply_count,
                retweet_count=retweet_count,
                like_count=like_count,
                view_count=view_count,
                tags=tags,
                mentions=mentions,
                tweet_url=tweet_url,
                profile_image_url=profile_image_url,
                embedded_media_urls=list(set(embedded_media_urls)),
                is_thread_candidate=is_thread_candidate
            )
        except Exception as e:
            logger.error(f"Error parsing tweet card: {e}", exc_info=True)
            return None

    def scrape_tweets_from_url(
        self,
        url: str,
        search_type: str,
        max_tweets: Optional[int] = None,
        stop_if_no_new_tweets_count: Optional[int] = None
    ) -> List[ScrapedTweet]:
        if max_tweets is None:
            max_tweets = self.default_max_tweets
        if stop_if_no_new_tweets_count is None:
            stop_if_no_new_tweets_count = self.no_new_tweets_scroll_limit
        logger.info(f"Navigating to {url} for scraping ({search_type}). Max tweets: {max_tweets}")
        self.browser_manager.navigate_to(url)
        time.sleep(2) # BIG change: 10 -> 2 seconds
        if not self._wait_for_page_load(7): # was 20
            logger.warning("Page load timeout, proceeding anyway")
            try:
                self.driver.execute_script("window.scrollTo(0, 1000);")
                time.sleep(1) # was 5
            except Exception as e:
                logger.debug(f"Could not perform initial scroll: {e}")

        scraped_tweets: List[ScrapedTweet] = []
        seen_tweet_ids = set()
        scroll_attempts_with_no_new_tweets = 0
        progress = Progress(0, max_tweets)
        while len(scraped_tweets) < max_tweets:
            try:
                logger.info(f"Attempting to find tweet cards on page. Current scraped count: {len(scraped_tweets)}")
                tweet_card_elements = self._get_tweet_cards_from_page()
                if not tweet_card_elements:
                    logger.warning("No tweet card elements found on the page.")
                    try:
                        page_source = self.driver.page_source
                        if "tweet" in page_source.lower():
                            logger.info("Page contains 'tweet' text, but no tweet elements found")
                        else:
                            logger.warning("Page doesn't seem to contain tweet content")
                    except Exception as e:
                        logger.error(f"Could not get page source for debugging: {e}")
                    scroll_attempts_with_no_new_tweets += 1
                    if scroll_attempts_with_no_new_tweets >= stop_if_no_new_tweets_count:
                        logger.info(f"No new tweets found after {stop_if_no_new_tweets_count} scrolls. Stopping.")
                        break
                    if not self.scroller.scroll_page():
                        logger.info("Scroll failed, ending scrape")
                        break
                    time.sleep(random.uniform(self.scroll_delay_min, self.scroll_delay_max))
                    continue
                new_tweets_found_this_scroll = 0
                logger.info(f"Found {len(tweet_card_elements)} tweet card elements to process")
                for i, card_el in enumerate(tweet_card_elements):
                    if len(scraped_tweets) >= max_tweets:
                        break
                    logger.debug(f"Processing tweet card {i+1}/{len(tweet_card_elements)}")
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card_el)
                        time.sleep(0.15) # was 0.5
                    except Exception as scroll_err:
                        logger.debug(f"Could not scroll tweet card into view: {scroll_err}")
                    parsed_tweet = self._parse_tweet_card(card_el)
                    if parsed_tweet:
                        if parsed_tweet.tweet_id not in seen_tweet_ids:
                            scraped_tweets.append(parsed_tweet)
                            seen_tweet_ids.add(parsed_tweet.tweet_id)
                            new_tweets_found_this_scroll += 1
                            logger.info(f"Successfully parsed tweet {parsed_tweet.tweet_id} from {parsed_tweet.user_handle}")
                            # Use set_progress instead of print_progress
                            progress.set_progress(len(scraped_tweets), f"Found {len(scraped_tweets)} tweets")
                        else:
                            logger.debug(f"Tweet {parsed_tweet.tweet_id} already seen, skipping")
                    else:
                        logger.debug(f"Failed to parse tweet card {i+1}")
                if new_tweets_found_this_scroll == 0:
                    scroll_attempts_with_no_new_tweets += 1
                    logger.info(f"No new tweets found in this scroll. Attempt {scroll_attempts_with_no_new_tweets}/{stop_if_no_new_tweets_count}")
                else:
                    scroll_attempts_with_no_new_tweets = 0
                if scroll_attempts_with_no_new_tweets >= stop_if_no_new_tweets_count:
                    logger.info(f"Stopping scrape for {url}: No new tweets after {stop_if_no_new_tweets_count} consecutive empty scrolls.")
                    break
                if len(scraped_tweets) >= max_tweets:
                    logger.info(f"Reached max_tweets ({max_tweets}) for {url}.")
                    break
                if not self.scroller.scroll_page():
                    logger.info(f"End of page or scroll error for {url}.")
                    break
                time.sleep(random.uniform(self.scroll_delay_min, self.scroll_delay_max))
            except TimeoutException:
                logger.warning(f"Timeout during tweet scraping for {url}. May proceed with fewer tweets.")
                break
            except StaleElementReferenceException:
                logger.warning("Encountered stale element reference, attempting to re-fetch cards.")
                time.sleep(0.2) # was 1
                continue
            except Exception as e:
                logger.error(f"Unhandled exception during scraping {url}: {e}", exc_info=True)
                break
        logger.info(f"Finished scraping for {url}. Found {len(scraped_tweets)} tweets.")
        return scraped_tweets

    def scrape_tweets_by_keyword(self, keyword: str, max_tweets: Optional[int] = None) -> List[ScrapedTweet]:
        """Scrape tweets by keyword or hashtag"""
        # Hashtag kontrolü
        if keyword.startswith('#'):
            # Hashtag için explore sayfasına git
            hashtag = keyword[1:]  # # işaretini kaldır
            search_url = f"https://x.com/search?q=%23{hashtag}&src=typed_query&f=live"
            logger.info(f"Searching for hashtag: {keyword} using explore URL: {search_url}")
        else:
            # Normal keyword için arama yap
            search_url = f"https://x.com/search?q={keyword.replace(' ', '%20')}&f=live"
            logger.info(f"Searching for keyword: {keyword} using search URL: {search_url}")
        
        return self.scrape_tweets_from_url(search_url, "keyword", max_tweets)

    def scrape_tweets_from_profile(self, profile_url: str, max_tweets: Optional[int] = None) -> List[ScrapedTweet]:
        return self.scrape_tweets_from_url(profile_url, "profile", max_tweets)

    def scrape_tweets_by_hashtag(self, hashtag: str, max_tweets: Optional[int] = None) -> List[ScrapedTweet]:
        """Scrape tweets by hashtag"""
        url = f"https://x.com/search?q=%23{hashtag}&src=typed_query&f=live"
        return self.scrape_tweets_from_url(url, "hashtag", max_tweets)

    def scrape_tweets_from_feed(self, max_tweets: Optional[int] = None) -> List[ScrapedTweet]:
        """Scrape tweets from the main feed/home timeline"""
        logger.info("Starting to scrape tweets from feed/home timeline")
        
        try:
            # Navigate to home timeline
            self.driver.get("https://x.com/home")
            time.sleep(2)
            
            if not self._wait_for_page_load():
                logger.error("Failed to load home timeline")
                return []
            
            # Use the same scraping logic as other methods
            return self.scrape_tweets_from_url("https://x.com/home", "feed", max_tweets)
            
        except Exception as e:
            logger.error(f"Error scraping tweets from feed: {e}")
            return []

if __name__ == '__main__':
    dummy_cookie_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
    dummy_cookie_file = os.path.join(dummy_cookie_dir, "dummy_scraper_cookies.json")
    if not os.path.exists(dummy_cookie_dir):
        os.makedirs(dummy_cookie_dir)
    if not os.path.exists(dummy_cookie_file):
        with open(dummy_cookie_file, 'w') as f:
            import json
            json.dump([{"name": "test_cookie", "value": "test_value", "domain": ".x.com"}], f)
    cfg_loader = ConfigLoader()
    accounts = cfg_loader.get_accounts_config()
    test_account_cfg = None
    if accounts:
        test_account_cfg = accounts[0]
        logger.info(f"Using account config for: {test_account_cfg.get('account_id')}")
    else:
        logger.info("No accounts configured in accounts.json, running scraper without specific account cookies.")
    bm = BrowserManager(account_config=test_account_cfg)
    scraper = TweetScraper(browser_manager=bm, account_id=test_account_cfg.get('account_id') if test_account_cfg else "default_session")
    try:
        logger.info("Starting scraper test...")
        keyword_to_scrape = "AI ethics"
        logger.info(f"\n--- Scraping for keyword: {keyword_to_scrape} ---")
        keyword_tweets = scraper.scrape_tweets_by_keyword(keyword_to_scrape, max_tweets=5)
        for i, tweet in enumerate(keyword_tweets):
            logger.info(f"Keyword Tweet {i+1}: ID={tweet.tweet_id}, User={tweet.user_handle}, Text='{tweet.text_content[:50]}...'")
        profile_to_scrape = "https://x.com/elonmusk"
        logger.info(f"\n--- Scraping profile: {profile_to_scrape} ---")
        profile_tweets = scraper.scrape_tweets_from_profile(profile_to_scrape, max_tweets=5)
        for i, tweet in enumerate(profile_tweets):
            logger.info(f"Profile Tweet {i+1}: ID={tweet.tweet_id}, User={tweet.user_handle}, Text='{tweet.text_content[:50]}...'")
        hashtag_to_scrape = "#OpenAI"
        logger.info(f"\n--- Scraping for hashtag: {hashtag_to_scrape} ---")
        hashtag_tweets = scraper.scrape_tweets_by_hashtag(hashtag_to_scrape, max_tweets=5)
        for i, tweet in enumerate(hashtag_tweets):
            logger.info(f"Hashtag Tweet {i+1}: ID={tweet.tweet_id}, User={tweet.user_handle}, Text='{tweet.text_content[:50]}...'")
    except Exception as e:
        logger.error(f"Error during scraper test: {e}", exc_info=True)
    finally:
        logger.info("Closing browser manager...")
        scraper.browser_manager.close_driver()
        logger.info("Scraper test finished.")