#!/usr/bin/env python3
"""
Debug script for testing tweet scraper functionality
"""

import os
import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.browser_manager import BrowserManager
from src.core.config_loader import ConfigLoader
from src.features.scraper import TweetScraper
from src.utils.logger import setup_logger

def test_scraper():
    """Test the scraper with different scenarios"""
    
    # Setup
    config = ConfigLoader()
    logger = setup_logger(config)
    
    # Get accounts config
    accounts = config.get_accounts_config()
    test_account = accounts[0] if accounts else None
    
    if test_account:
        logger.info(f"Using account: {test_account.get('account_id')}")
    else:
        logger.info("No account configured, using default session")
    
    # Initialize browser manager
    browser_manager = BrowserManager(account_config=test_account)
    scraper = TweetScraper(browser_manager=browser_manager, account_id=test_account.get('account_id') if test_account else None)
    
    try:
        # Test 1: Simple profile scrape
        logger.info("=== Testing Profile Scrape ===")
        profile_url = "https://x.com/elonmusk"
        tweets = scraper.scrape_tweets_from_profile(profile_url, max_tweets=3)
        logger.info(f"Found {len(tweets)} tweets from profile")
        
        for i, tweet in enumerate(tweets):
            logger.info(f"Tweet {i+1}: ID={tweet.tweet_id}, User=@{tweet.user_handle}, Text='{tweet.text_content[:100]}...'")
        
        # Test 2: Keyword search
        logger.info("\n=== Testing Keyword Search ===")
        keyword_tweets = scraper.scrape_tweets_by_keyword("AI", max_tweets=3)
        logger.info(f"Found {len(keyword_tweets)} tweets for keyword 'AI'")
        
        for i, tweet in enumerate(keyword_tweets):
            logger.info(f"Keyword Tweet {i+1}: ID={tweet.tweet_id}, User=@{tweet.user_handle}, Text='{tweet.text_content[:100]}...'")
        
        # Test 3: Hashtag search
        logger.info("\n=== Testing Hashtag Search ===")
        hashtag_tweets = scraper.scrape_tweets_by_hashtag("#OpenAI", max_tweets=3)
        logger.info(f"Found {len(hashtag_tweets)} tweets for hashtag #OpenAI")
        
        for i, tweet in enumerate(hashtag_tweets):
            logger.info(f"Hashtag Tweet {i+1}: ID={tweet.tweet_id}, User=@{tweet.user_handle}, Text='{tweet.text_content[:100]}...'")
            
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
    finally:
        logger.info("Closing browser...")
        browser_manager.close_driver()

if __name__ == "__main__":
    test_scraper() 