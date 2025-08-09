import asyncio
import sys
import os
import time
import random
import signal
import threading
from datetime import datetime, timezone

# Ensure src directory is in Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config_loader import ConfigLoader
from core.browser_manager import BrowserManager
from core.llm_service import LLMService
from utils.logger import setup_logger
from utils.file_handler import FileHandler
from utils.cleanup_manager import CleanupManager
from data_models import AccountConfig, TweetContent, LLMSettings, ScrapedTweet, ActionConfig
from features.scraper import TweetScraper
from features.publisher import TweetPublisher
from features.engagement import TweetEngagement
from features.analyzer import TweetAnalyzer

# Initialize main config loader and logger
main_config_loader = ConfigLoader()
logger = setup_logger(main_config_loader)


def apply_overrides(account_dict):
    """Override ana alanları, override field varsa onunla doldur."""
    field_map = {
        'target_keywords_override': 'target_keywords',
        'competitor_profiles_override': 'competitor_profiles',
        'news_sites_override': 'news_sites',
        'research_paper_sites_override': 'research_paper_sites',
        'llm_settings_override': 'llm_settings',
        'action_config_override': 'action_config'
    }
    for override_field, base_field in field_map.items():
        if override_field in account_dict:
            account_dict[base_field] = account_dict[override_field]
    return account_dict


class TwitterOrchestrator:
    def __init__(self):
        self.config_loader = main_config_loader
        self.file_handler = FileHandler(self.config_loader)
        self.global_settings = self.config_loader.get_settings()
        self.accounts_data = self.config_loader.get_accounts_config()
        
        self.processed_action_keys = self.file_handler.load_processed_action_keys() # Load processed action keys
        self.global_tweets = []  # Global olarak üretilen tweetler
        self.global_repost_tweets = []  # Global olarak üretilen repost tweetler
        
        # Otomatik temizlik yöneticisi
        self.cleanup_manager = CleanupManager()
        
        # Signal handling için
        self.shutdown_event = threading.Event()
        self.browser_managers = []  # Açık browser manager'ları takip et

    async def _generate_global_tweets(self, target_keywords: list, llm_settings: LLMSettings, tweet_count: int, user_handle: str = None) -> list:
        """Kullanıcıdan gelen sayı kadar tweet üretir. Anahtar kelimeler azsa döngüyle tekrar eder. Kullanıcı adı varsa tweetin sonuna ekler."""
        logger.info(f"Global tweet üretimi başlıyor... Hedef tweet sayısı: {tweet_count}")
        llm_service = LLMService(config_loader=self.config_loader)
        global_tweets = []
        
        if not target_keywords:
            logger.warning("Tweet üretimi için anahtar kelime yok!")
            return []
        

        
        for i in range(tweet_count):
            keyword = target_keywords[i % len(target_keywords)]
            logger.info(f"Global tweet üretimi için keyword: '{keyword}' (tweet {i+1}/{tweet_count})")
            
            if keyword.startswith('#'):
                hashtag_without_hash = keyword[1:]
                prompt = f"'{hashtag_without_hash}' hashtag'i ile ilgili etkileyici bir tweet yaz. Sadece tweet'i yaz, başka açıklama yapma."
            else:
                prompt = f"'{keyword}' konusu ile ilgili etkileyici bir tweet yaz. Sadece tweet'i yaz, başka açıklama yapma."
            
            logger.info(f"Global tweet üretimi prompt: {prompt}")
            generated_text = await llm_service.generate_text(
                prompt=prompt,
                model=llm_settings.model_name_override,
                max_tokens=llm_settings.max_tokens,
                temperature=llm_settings.temperature
            )
            
            if generated_text:
                logger.info(f"Global tweet üretildi: {generated_text[:100]}...")
                
                # Tweet uzunluğunu kontrol et
                final_tweet_text = generated_text
                if user_handle:
                    # @ işareti yoksa ekle
                    if not user_handle.startswith('@'):
                        user_handle = f"@{user_handle}"
                    final_tweet_text = f"{generated_text} {user_handle}"
                    if len(final_tweet_text) > 280:
                        max_text_length = 279 - len(f" {user_handle}") - 3  # 3 karakter ... için
                        final_tweet_text = f"{generated_text[:max_text_length]}... {user_handle}"
                else:
                    if len(generated_text) > 280:
                        final_tweet_text = f"{generated_text[:277]}..."
                
                global_tweets.append(final_tweet_text)
                logger.info(f"Global tweet eklendi: {final_tweet_text[:50]}...")
            else:
                logger.error(f"Global tweet üretilemedi! Keyword: {keyword}")
        
        logger.info(f"Global tweet üretimi tamamlandı. Toplam {len(global_tweets)} tweet üretildi.")
        return global_tweets

    async def _generate_global_repost_tweets(self, scraped_tweets: list, llm_settings: LLMSettings) -> list:
        """Tüm hesaplar için ortak kullanılacak repost tweetleri üretir."""
        logger.info("Global repost tweet üretimi başlıyor...")
        
        llm_service = LLMService(config_loader=self.config_loader)
        global_repost_tweets = []
        
        # Her scraped tweet için bir repost tweet üret
        for scraped_tweet in scraped_tweets:
            logger.info(f"Global repost tweet üretimi için tweet: '{scraped_tweet.text_content[:50]}...'")
            
            # AI repost üretimi için prompt
            prompt = f"Bu tweet'i etkileyici bir şekilde yeniden yaz: '{scraped_tweet.text_content}' - {scraped_tweet.user_handle or 'bir kullanıcı'} tarafından. Sadece tweet'i yaz, başka açıklama yapma."
            
            logger.info(f"Global repost tweet üretimi prompt: {prompt}")
            
            # AI tweet üretimi
            generated_text = await llm_service.generate_text(
                prompt=prompt,
                model=llm_settings.model_name_override,
                max_tokens=llm_settings.max_tokens,
                temperature=llm_settings.temperature
            )
            
            if generated_text:
                logger.info(f"Global repost tweet üretildi: {generated_text[:100]}...")
                
                # Kullanıcı adını tweet'in sonuna ekle
                if scraped_tweet.user_handle:
                    final_tweet_text = f"{generated_text} @{scraped_tweet.user_handle}"
                else:
                    final_tweet_text = generated_text
                
                # Tweet uzunluğunu kontrol et (280 karakter sınırı)
                if len(final_tweet_text) > 280:
                    # Kullanıcı adını ekleyecek yer bırak (1 karakter daha az)
                    max_text_length = 279 - len(f" @{scraped_tweet.user_handle}") - 3  # 3 karakter "..." için
                    final_tweet_text = f"{generated_text[:max_text_length]}... @{scraped_tweet.user_handle}"
                
                global_repost_tweets.append({
                    'tweet_text': final_tweet_text,
                    'original_tweet_id': scraped_tweet.tweet_id,
                    'original_user_handle': scraped_tweet.user_handle
                })
                logger.info(f"Global repost tweet eklendi: {final_tweet_text[:50]}...")
            else:
                logger.error(f"Global repost tweet üretilemedi! Tweet ID: {scraped_tweet.tweet_id}")
        
        logger.info(f"Global repost tweet üretimi tamamlandı. Toplam {len(global_repost_tweets)} repost tweet üretildi.")
        return global_repost_tweets

    async def _process_account(self, account_dict: dict):
        """Processes tasks for a single Twitter account."""
        
        # Create AccountConfig Pydantic model from the dictionary
        try:
            # A simple way to map, assuming keys in dict match model fields or are handled by default values
            # account_config_data = {k: account_dict.get(k) for k in AccountConfig.model_fields.keys() if account_dict.get(k) is not None}
            # if 'cookies' in account_dict and isinstance(account_dict['cookies'], str): # If 'cookies' is a file path string
            #     account_config_data['cookie_file_path'] = account_dict['cookies']
            #     if 'cookies' in account_config_data: del account_config_data['cookies'] # Avoid conflict if model expects List[AccountCookie]
            
            # Use Pydantic's parse_obj method for robust parsing from dict
            account = AccountConfig.model_validate(account_dict) # Replaced AccountConfig(**account_dict) for better validation
            
        except Exception as e: # Catch Pydantic ValidationError specifically if needed
            logger.error(f"Failed to parse account configuration for {account_dict.get('account_id', 'UnknownAccount')}: {e}. Skipping account.")
            return

        if not account.is_active:
            logger.info(f"Account {account.account_id} is inactive. Skipping.")
            return

        logger.info(f"--- Starting processing for account: {account.account_id} ---")
        
        browser_manager = None
        try:
            browser_manager = BrowserManager(account_config=account_dict) # Pass original dict for cookie path handling
            
            # Browser manager'ı listeye ekle (temizlik için)
            self.browser_managers.append(browser_manager)
            
            # Login kontrolü yap
            logger.info(f"[{account.account_id}] Checking login status...")
            is_logged_in = await asyncio.to_thread(browser_manager.check_login_status)
            
            if not is_logged_in:
                logger.warning(f"[{account.account_id}] Not logged in. Attempting to login...")
                login_success = await asyncio.to_thread(browser_manager.login)
                if not login_success:
                    logger.error(f"[{account.account_id}] Login failed. Skipping account.")
                    return
                logger.info(f"[{account.account_id}] Login successful.")
            else:
                logger.info(f"[{account.account_id}] Already logged in.")
            
            llm_service = LLMService(config_loader=self.config_loader)
            
            # Initialize feature modules with the current account's context
            scraper = TweetScraper(browser_manager, account_id=account.account_id)
            publisher = TweetPublisher(browser_manager, llm_service, account) # Publisher needs AccountConfig model
            engagement = TweetEngagement(browser_manager, account) # Engagement needs AccountConfig model

            # --- Define actions based on global and account-specific settings ---
            automation_settings = self.global_settings.get('twitter_automation', {}) # Global settings for twitter_automation
            
            # Determine current ActionConfig: account's action_config > global default action_config
            global_action_config_dict = automation_settings.get('action_config', {}) # Global default action_config
            current_action_config = account.action_config or ActionConfig(**global_action_config_dict) # account.action_config is now the primary source if it exists

            # Initialize TweetAnalyzer
            analyzer = TweetAnalyzer(llm_service, account_config=account)

            # Determine LLM settings for different actions:
            # Priority: Account's general LLM override -> Action-specific LLM settings from current_action_config
            llm_for_post = account.llm_settings_override or current_action_config.llm_settings_for_post
            
            # Get tweets per account limit
            tweets_per_account = automation_settings.get('tweets_per_account', 3)
            tweets_made_this_account = 0
            
            # Action 1: Global tweetleri kullanarak tweet atma
            # Sadece web arayüzünden gelen target_keywords kullan
            target_keywords_for_account = []
            
            if automation_settings and 'action_config' in automation_settings and automation_settings['action_config'].get('target_keywords'):
                target_keywords_for_account = automation_settings['action_config']['target_keywords']
                logger.info(f"[{account.account_id}] Using target keywords from web interface: {target_keywords_for_account}")
            else:
                logger.info(f"[{account.account_id}] No target keywords from web interface. Skipping tweet generation.")
            
            if target_keywords_for_account and tweets_made_this_account < tweets_per_account and self.global_tweets:
                logger.info(f"[{account.account_id}] Global tweetleri kullanarak tweet atma başlıyor. {len(self.global_tweets)} global tweet mevcut.")
                
                # Her hesap için random 3 tweet seç
                import random
                selected_tweets = random.sample(self.global_tweets, min(tweets_per_account, len(self.global_tweets)))
                
                for i, global_tweet in enumerate(selected_tweets):
                    if tweets_made_this_account >= tweets_per_account:
                        logger.info(f"[{account.account_id}] Tweet limiti doldu ({tweets_per_account}). Durduruluyor.")
                        break
                    
                    logger.info(f"[{account.account_id}] Global tweet {i+1} atılıyor: {global_tweet[:50]}...")
                    
                    new_tweet_content = TweetContent(text=global_tweet)
                    success = await publisher.post_new_tweet(new_tweet_content, llm_settings=llm_for_post)
                    
                    if success:
                        logger.info(f"[{account.account_id}] Global tweet {i+1} başarıyla atıldı!")
                        tweets_made_this_account += 1
                        # Tweetten sonra home'a dön, bekle ve scroll yap
                        try:
                            publisher.browser_manager.navigate_to("https://x.com/home")
                            wait_time = random.uniform(4, 8)
                            logger.info(f"[{account.account_id}] Home sayfasında {wait_time:.1f} sn bekleniyor...")
                            await asyncio.sleep(wait_time)
                            # Scroll aşağı-yukarı
                            for _ in range(random.randint(1, 3)):
                                scroll_amount = random.randint(-400, 400)
                                publisher.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                                logger.info(f"[{account.account_id}] Home'da {scroll_amount} px scroll yapıldı.")
                                await asyncio.sleep(random.uniform(0.7, 1.5))
                        except Exception as e:
                            logger.warning(f"[{account.account_id}] Home/scroll işlemi sırasında hata: {e}")
                        await asyncio.sleep(random.uniform(1, 3))  # Daha kısa bekleme
                    else:
                        logger.error(f"[{account.account_id}] Global tweet {i+1} atılamadı!")
                
                logger.info(f"[{account.account_id}] Global tweet atma tamamlandı. Toplam tweet atıldı: {tweets_made_this_account}")
            else:
                logger.info(f"[{account.account_id}] Global tweet yok veya tweet limiti doldu. Tweet atma atlanıyor.")

            # Action 2: Global repost tweetleri kullanarak repost etme
            if automation_settings and 'action_config' in automation_settings and automation_settings['action_config'].get('enable_keyword_reposts') and self.global_repost_tweets:
                logger.info(f"[{account.account_id}] Global repost tweetleri kullanarak repost etme başlıyor. {len(self.global_repost_tweets)} global repost tweet mevcut.")
                
                # Global repost tweetleri sırayla kullan
                for i, repost_data in enumerate(self.global_repost_tweets):
                    if tweets_made_this_account >= tweets_per_account:
                        logger.info(f"[{account.account_id}] Tweet limiti doldu ({tweets_per_account}). Durduruluyor.")
                        break
                    
                    logger.info(f"[{account.account_id}] Global repost tweet {i+1} atılıyor: {repost_data['tweet_text'][:50]}...")
                    
                    # Gerçek retweet fonksiyonunu çağır
                    from src.data_models import ScrapedTweet
                    scraped_tweet = ScrapedTweet(
                        tweet_id=repost_data['original_tweet_id'],
                        user_handle=repost_data.get('original_user_handle'),
                        text_content=repost_data['tweet_text'],
                        tweet_url=f"https://x.com/{repost_data.get('original_user_handle','')}/status/{repost_data['original_tweet_id']}"
                    )
                    success = await publisher.retweet_tweet(scraped_tweet)
                    
                    if success:
                        logger.info(f"[{account.account_id}] Global repost tweet {i+1} başarıyla retweetlendi!")
                        action_key = f"repost_{account.account_id}_{repost_data['original_tweet_id']}"
                        self.file_handler.save_processed_action_key(action_key, timestamp=datetime.now().isoformat())
                        self.processed_action_keys.add(action_key)
                        tweets_made_this_account += 1
                        await asyncio.sleep(random.uniform(1, 3))  # Daha kısa bekleme
                    else:
                        logger.error(f"[{account.account_id}] Global repost tweet {i+1} retweetlenemedi!")
                
                logger.info(f"[{account.account_id}] Global repost tweet atma tamamlandı. Toplam tweet atıldı: {tweets_made_this_account}")
            elif automation_settings and 'action_config' in automation_settings and automation_settings['action_config'].get('enable_keyword_reposts'):
                logger.info(f"[{account.account_id}] Keyword reposts enabled, but no global repost tweets available for this account.")

            # Action 3: Like tweets
            if automation_settings and 'action_config' in automation_settings and automation_settings['action_config'].get('enable_liking_tweets'):
                keywords_to_like = automation_settings['action_config'].get('like_tweets_from_keywords', []) or []
                
                # Anahtar kelimeler varsa keyword-based beğenme yap
                if keywords_to_like:
                    logger.info(f"[{account.account_id}] Starting to like tweets based on {len(keywords_to_like)} keywords.")
                    likes_done_this_run = 0
                    for keyword in keywords_to_like:
                        max_likes = automation_settings['action_config'].get('max_likes_per_run', 5)
                        if likes_done_this_run >= max_likes:
                            break
                        logger.info(f"[{account.account_id}] Searching for tweets with keyword '{keyword}' to like.")
                        tweets_to_potentially_like = await asyncio.to_thread(
                            scraper.scrape_tweets_by_keyword,
                            keyword,
                            max_tweets=max_likes * 2 # Fetch more to have options
                        )
                        for tweet_to_like in tweets_to_potentially_like:
                            if likes_done_this_run >= max_likes:
                                break
                            
                            # Anahtar kelime kontrolü - tweet'te gerçekten var mı?
                            tweet_text_lower = tweet_to_like.text_content.lower() if tweet_to_like.text_content else ""
                            keyword_lower = keyword.lower()
                            
                            # Hashtag kontrolü
                            if keyword.startswith('#'):
                                # Hashtag için özel kontrol
                                hashtag_without_hash = keyword[1:].lower()
                                if f"#{hashtag_without_hash}" in tweet_text_lower or f"#{hashtag_without_hash}" in tweet_text_lower:
                                    should_like = True
                                else:
                                    should_like = False
                            else:
                                # Normal keyword kontrolü
                                should_like = keyword_lower in tweet_text_lower
                            
                            if not should_like:
                                logger.debug(f"[{account.account_id}] Tweet doesn't contain keyword '{keyword}': {tweet_text_lower[:50]}...")
                                continue
                            
                            action_key = f"like_{account.account_id}_{tweet_to_like.tweet_id}"
                            if action_key in self.processed_action_keys:
                                logger.info(f"[{account.account_id}] Already liked or processed tweet {tweet_to_like.tweet_id}. Skipping.")
                                continue
                            
                            avoid_own_tweets = automation_settings['action_config'].get('avoid_replying_to_own_tweets', False)
                            if avoid_own_tweets and tweet_to_like.user_handle and account.account_id.lower() in tweet_to_like.user_handle.lower():
                                logger.info(f"[{account.account_id}] Skipping own tweet {tweet_to_like.tweet_id} for liking.")
                                continue

                            logger.info(f"[{account.account_id}] Attempting to like tweet {tweet_to_like.tweet_id} with keyword '{keyword}': {tweet_text_lower[:50]}...")
                            like_success = await engagement.like_tweet(tweet_id=tweet_to_like.tweet_id, tweet_url=str(tweet_to_like.tweet_url) if tweet_to_like.tweet_url else None)
                            
                            if like_success:
                                self.file_handler.save_processed_action_key(action_key, timestamp=datetime.now().isoformat())
                                self.processed_action_keys.add(action_key)
                                likes_done_this_run += 1
                                await asyncio.sleep(random.uniform(1, 2))  # Çok kısa bekleme
                            else:
                                logger.warning(f"[{account.account_id}] Failed to like tweet {tweet_to_like.tweet_id}.")
                else:
                    logger.info(f"[{account.account_id}] Liking enabled but no keywords configured. Skipping like operations.")
            
            logger.info(f"[{account.account_id}] Finished processing tasks for this account. Total tweets made: {tweets_made_this_account}")

        except Exception as e:
            logger.error(f"[{account.account_id or 'UnknownAccount'}] Unhandled error during account processing: {e}", exc_info=True)
        finally:
            if browser_manager:
                try:
                    browser_manager.close_driver()
                    # Browser manager'ı listeden çıkar
                    if browser_manager in self.browser_managers:
                        self.browser_managers.remove(browser_manager)
                except Exception as e:
                    logger.warning(f"Browser kapatılırken hata: {e}")
            
            # Safely log account ID
            account_id_for_log = account_dict.get('account_id', 'UnknownAccount')
            if 'account' in locals() and hasattr(account, 'account_id'):
                account_id_for_log = account.account_id
            logger.info(f"--- Finished processing for account: {account_id_for_log} ---")
            # The delay_between_accounts_seconds will now apply after each account finishes,
            # but accounts will start concurrently.
            # If a delay *between starts* is needed, a different mechanism (e.g., semaphore with delays) is required.
            await asyncio.sleep(self.global_settings.get('delay_between_accounts_seconds', 10)) # Reduced default for concurrent example

    async def run(self):
        logger.info("Twitter Orchestrator starting...")
        
        # Çalıştırma öncesi temizlik
        try:
            freed_space = self.cleanup_manager.cleanup_before_run()
            logger.info(f"Çalıştırma öncesi temizlik tamamlandı. Kazanılan alan: {freed_space/1024/1024:.2f} MB")
        except Exception as e:
            logger.warning(f"Çalıştırma öncesi temizlik başarısız: {e}")
        
        if not self.accounts_data:
            logger.warning("No accounts found in configuration. Orchestrator will exit.")
            return

        # Global tweet üretimi - başlangıçta bir kez yapılır
        automation_settings = self.global_settings.get('twitter_automation', {})
        target_keywords_for_global_tweets = []
        
        # Sadece web arayüzünden gelen target_keywords'ü al
        if automation_settings and 'action_config' in automation_settings and automation_settings['action_config'].get('target_keywords'):
            target_keywords_for_global_tweets = automation_settings['action_config']['target_keywords']
            logger.info(f"Global tweet üretimi için web arayüzünden target_keywords alındı: {target_keywords_for_global_tweets}")
        else:
            logger.warning("Web arayüzünden target_keywords bulunamadı. Global tweet üretimi atlanıyor.")
            return
        
        # Global tweet üretimi
        if target_keywords_for_global_tweets:
            logger.info("Global tweet üretimi başlıyor...")
            
            # LLM ayarlarını al
            llm_settings_for_global_tweets = None
            
            # Sadece web arayüzünden gelen LLM ayarlarını al
            if automation_settings and 'action_config' in automation_settings and automation_settings['action_config'].get('llm_settings_for_post'):
                llm_settings_dict = automation_settings['action_config']['llm_settings_for_post']
                llm_settings_for_global_tweets = LLMSettings(**llm_settings_dict)
                logger.info(f"Global tweet üretimi için web arayüzünden LLM ayarları alındı: {llm_settings_for_global_tweets}")
            else:
                logger.warning("Web arayüzünden LLM ayarları bulunamadı. Global tweet üretimi atlanıyor.")
                return
            
            if llm_settings_for_global_tweets:
                tweets_per_account = automation_settings.get('tweets_per_account', 3)
                user_handle = automation_settings.get('action_config', {}).get('user_handle', None)
                self.global_tweets = await self._generate_global_tweets(target_keywords_for_global_tweets, llm_settings_for_global_tweets, tweets_per_account, user_handle=user_handle)
                logger.info(f"Global tweet üretimi tamamlandı. Toplam {len(self.global_tweets)} tweet üretildi.")
                
                # Global repost tweet üretimi
                if automation_settings and 'action_config' in automation_settings and automation_settings['action_config'].get('enable_keyword_reposts'):
                    logger.info("Global repost tweet üretimi başlıyor...")
                    
                    # İlk hesaptan scraper oluştur (sadece browser için)
                    if self.accounts_data:
                        first_account = apply_overrides(self.accounts_data[0])
                        first_browser_manager = BrowserManager(account_config=first_account)
                        first_scraper = TweetScraper(first_browser_manager, account_id=first_account.get('account_id', 'default'))
                        
                        # Tüm keywordler için tweet scrape et
                        all_scraped_tweets = []
                        max_reposts = automation_settings['action_config'].get('max_reposts_per_keyword', 3)
                        
                        for keyword in target_keywords_for_global_tweets:
                            scraped_tweets_for_keyword = await asyncio.to_thread(
                                first_scraper.scrape_tweets_by_keyword,
                                keyword,
                                max_tweets=max_reposts * 2
                            )
                            all_scraped_tweets.extend(scraped_tweets_for_keyword)
                        
                        # Global repost tweetleri üret
                        self.global_repost_tweets = await self._generate_global_repost_tweets(all_scraped_tweets, llm_settings_for_global_tweets)
                        logger.info(f"Global repost tweet üretimi tamamlandı. Toplam {len(self.global_repost_tweets)} repost tweet üretildi.")
                        
                        # Browser'ı kapat
                        first_browser_manager.close_driver()
                    else:
                        logger.warning("Hesap bulunamadı. Global repost tweet üretimi atlanıyor.")
            else:
                logger.warning("LLM ayarları bulunamadı. Global tweet üretimi atlanıyor.")
        else:
            logger.warning("Target keywords bulunamadı. Global tweet üretimi atlanıyor.")

        # Sadece aktif hesapları filtrele (status: true olanlar)
        active_accounts = [account for account in self.accounts_data if account.get('is_active', False)]
        inactive_accounts = [account for account in self.accounts_data if not account.get('is_active', False)]
        
        logger.info(f"Toplam {len(self.accounts_data)} hesap bulundu:")
        logger.info(f"  - Aktif hesaplar: {len(active_accounts)}")
        logger.info(f"  - Pasif hesaplar: {len(inactive_accounts)}")
        
        if not active_accounts:
            logger.warning("Hiç aktif hesap bulunamadı! İşlem sonlandırılıyor.")
            return
        
        # Hesap gruplarını oluştur - sadece aktif hesaplar için 10'lu gruplar
        batch_settings = automation_settings.get('batch_processing', {})
        batch_size = 10  # Aktif hesaplar için 10'lu gruplar
        delay_between_batches = batch_settings.get('delay_between_batches_seconds', 180)  # Varsayılan 3 dakika
        
        account_batches = []
        
        for i in range(0, len(active_accounts), batch_size):
            batch = active_accounts[i:i + batch_size]
            account_batches.append(batch)
        
        logger.info(f"Aktif {len(active_accounts)} hesap {len(account_batches)} gruba bölündü (her grupta {batch_size} hesap)")
        logger.info(f"Grup bekleme süresi: {delay_between_batches} saniye")
        
        # Her grup için sırayla işle
        total_processed = 0
        for batch_index, account_batch in enumerate(account_batches, 1):
            logger.info(f"=== GRUP {batch_index}/{len(account_batches)} İŞLENİYOR ({len(account_batch)} hesap) ===")
            
            # Bu grup için concurrent processing
            tasks = []
            for account_dict in account_batch:
                account_dict = apply_overrides(account_dict)  # <-- BURADA OVERRIDE'LARI AKTAR!
                tasks.append(self._process_account(account_dict))
            
            logger.info(f"Grup {batch_index}: {len(tasks)} hesap eşzamanlı işleniyor...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Bu grubun sonuçlarını kontrol et
            successful_in_batch = 0
            for i, result in enumerate(results):
                account_id = account_batch[i].get('account_id', f"AccountIndex_{i}")
                if isinstance(result, Exception):
                    logger.error(f"Grup {batch_index} - Hesap {account_id} hatası: {result}", exc_info=result)
                else:
                    logger.info(f"Grup {batch_index} - Hesap {account_id} başarıyla tamamlandı.")
                    successful_in_batch += 1
            
            total_processed += successful_in_batch
            logger.info(f"Grup {batch_index} tamamlandı: {successful_in_batch}/{len(account_batch)} başarılı")
            
            # Son grup değilse, bir sonraki grup için bekle
            if batch_index < len(account_batches):
                logger.info(f"Bir sonraki grup için {delay_between_batches} saniye bekleniyor...")
                await asyncio.sleep(delay_between_batches)
        
        logger.info(f"Tüm gruplar tamamlandı! Toplam {total_processed}/{len(active_accounts)} aktif hesap başarıyla işlendi.")
        
        # Çalıştırma sonrası temizlik
        try:
            freed_space = self.cleanup_manager.cleanup_after_run()
            logger.info(f"Çalıştırma sonrası temizlik tamamlandı. Kazanılan alan: {freed_space/1024/1024:.2f} MB")
        except Exception as e:
            logger.warning(f"Çalıştırma sonrası temizlik başarısız: {e}")
    
    def cleanup_all_browsers(self):
        """Tüm açık browser'ları kapat"""
        logger.info("Tüm browser'lar kapatılıyor...")
        for browser_manager in self.browser_managers[:]:  # Copy list to avoid modification during iteration
            try:
                browser_manager.close_driver()
                self.browser_managers.remove(browser_manager)
            except Exception as e:
                logger.warning(f"Browser kapatılırken hata: {e}")
        logger.info("Tüm browser'lar kapatıldı.")
    
    def signal_handler(self, signum, frame):
        """Signal handler for graceful shutdown"""
        logger.info(f"Signal {signum} alındı. Güvenli kapatma başlatılıyor...")
        self.shutdown_event.set()
        self.cleanup_all_browsers()


if __name__ == "__main__":
    orchestrator = TwitterOrchestrator()
    
    # Signal handler'ları ayarla
    signal.signal(signal.SIGINT, orchestrator.signal_handler)
    signal.signal(signal.SIGTERM, orchestrator.signal_handler)
    
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logger.info("Orchestrator run interrupted by user.")
    except Exception as e:
        logger.critical(f"Orchestrator failed with critical error: {e}", exc_info=True)
    finally:
        # Tüm browser'ları kapat
        orchestrator.cleanup_all_browsers()
        
        # Son temizlik
        try:
            freed_space = orchestrator.cleanup_manager.cleanup_after_run()
            logger.info(f"Son temizlik tamamlandı. Kazanılan alan: {freed_space/1024/1024:.2f} MB")
        except Exception as e:
            logger.warning(f"Son temizlik başarısız: {e}")
        
        logger.info("Orchestrator shutdown complete.")
