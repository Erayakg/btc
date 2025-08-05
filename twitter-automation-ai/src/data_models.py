from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

class AccountCookie(BaseModel):
    name: str
    value: str
    domain: Optional[str] = None
    path: Optional[str] = '/'
    expires: Optional[float] = None # Timestamp
    httpOnly: Optional[bool] = False
    secure: Optional[bool] = False
    sameSite: Optional[Literal["Strict", "Lax", "None"]] = None

class LLMSettings(BaseModel):
    service_preference: Optional[str] = Field(None, description="Preferred LLM service for this context: 'gemini', 'openai', 'azure'")
    model_name_override: Optional[str] = Field(None, description="Specific model name for the chosen service")
    max_tokens: int = 150
    temperature: Optional[float] = 0.7
    # Add other common LLM parameters as needed

class ActionConfig(BaseModel): # This can be global or per-account
    # General action timing
    min_delay_between_actions_seconds: int = Field(60, description="Minimum delay between any two actions for an account.")
    max_delay_between_actions_seconds: int = Field(180, description="Maximum delay between any two actions for an account.")

    # Keyword-based tweet generation
    target_keywords: Optional[List[str]] = Field(default_factory=list, description="Target keywords for tweet generation (e.g., ['keyword1', 'keyword2']).")

    # Keyword-based reposting
    enable_keyword_reposts: bool = Field(True, description="Enable reposting tweets based on keywords.")
    max_reposts_per_keyword: int = Field(2, description="Max reposts to make per keyword per run.")

    # Engagement specific controls
    enable_liking_tweets: bool = Field(True, description="Enable liking tweets.")
    max_likes_per_run: int = Field(5, description="Max tweets to like per run.")
    like_tweets_from_keywords: Optional[List[str]] = Field(default_factory=list, description="Keywords to search for tweets to like.")
    avoid_replying_to_own_tweets: bool = Field(True, description="Prevent interacting with the account's own tweets.")

    # LLM settings for different actions
    llm_settings_for_post: LLMSettings = Field(default_factory=LLMSettings)


class AccountConfig(BaseModel):
    account_id: str # e.g., username or a unique ID
    is_active: bool = True
    # Cookies can be a list of cookie objects or a path to a JSON file containing them
    cookies: Optional[List[AccountCookie]] = None 
    cookie_file_path: Optional[str] = None # Relative to config dir or absolute
    
    # Optional: For username/password login if implemented
    username: Optional[str] = None
    password: Optional[str] = None # Consider storing this securely, e.g. env var or encrypted

    # Account-specific settings for content sources (these are now the primary source, not overrides)
    target_keywords: Optional[List[str]] = Field(default_factory=list, description="Keywords specific to this account for targeting.")
    
    # Account-specific LLM preferences (general override for all actions for this account)
    llm_settings_override: Optional[LLMSettings] = Field(None, description="General LLM settings override for this account.")
    # Account-specific action configurations (can include action-specific LLM settings)
    action_config: Optional[ActionConfig] = Field(None, description="Specific action configurations for this account. Overrides global action_config.")


class TweetContent(BaseModel):
    text: str # Can be actual text or a prompt for LLM generation
    media_urls: Optional[List[HttpUrl]] = None # URLs of media to be downloaded/attached
    local_media_paths: Optional[List[str]] = None # Paths to already downloaded media


class ScrapedTweet(BaseModel):
    tweet_id: str
    user_name: Optional[str] = None
    user_handle: Optional[str] = None
    user_is_verified: Optional[bool] = False
    created_at: Optional[datetime] = None # Timestamp of the tweet
    text_content: str
    
    reply_count: Optional[int] = 0
    retweet_count: Optional[int] = 0
    like_count: Optional[int] = 0
    view_count: Optional[int] = 0 # Or analytics_count

    tags: Optional[List[str]] = []
    mentions: Optional[List[str]] = []
    emojis: Optional[List[str]] = []
    
    tweet_url: Optional[HttpUrl] = None
    profile_image_url: Optional[HttpUrl] = None
    
    # Media associated with the tweet
    embedded_media_urls: Optional[List[HttpUrl]] = [] 
    
    # Thread identification
    is_thread_candidate: Optional[bool] = Field(None, description="Initial assessment if tweet might be part of a thread based on simple heuristics from scraper.")
    is_confirmed_thread: Optional[bool] = Field(None, description="LLM-confirmed or DOM-confirmed if it's part of a thread.")
    thread_context_tweets: Optional[List[Dict[str, Any]]] = Field(None, description="Brief context of preceding/succeeding tweets if identified as a thread.")

    # For internal use by scraper
    raw_element_data: Optional[Dict[str, Any]] = None # Store raw Selenium element or its properties if needed


class GlobalSettings(BaseModel):
    # This model can mirror the structure of settings.json for validation
    api_keys: Dict[str, Optional[str]]
    twitter_automation: Dict[str, Any] # Contains default ActionConfig among other things
    logging: Dict[str, str]
    browser_settings: Dict[str, Any]


if __name__ == '__main__':
    # Example usage:
    cookie_example = AccountCookie(name="auth_token", value="somevalue", domain=".x.com")
    llm_pref_example = LLMSettings(service_preference="azure", model_name_override="gpt-4o-custom-deployment")
    
    action_override_example = ActionConfig(
        enable_keyword_reposts=True, 
        max_reposts_per_keyword=2,
        target_keywords=["eğitim", "yapay zeka"],
        like_tweets_from_keywords=["öğrenme", "teknoloji"]
    )
    
    account_example = AccountConfig(
        account_id="user123", 
        cookies=[cookie_example],
        target_keywords=["eğitim", "yapay zeka"],
        llm_settings_override=llm_pref_example,
        action_config=action_override_example
    )
    print("AccountConfig Example:")
    print(account_example.model_dump_json(indent=2))

    tweet_example = ScrapedTweet(
        tweet_id="12345",
        user_name="Test User",
        user_handle="@testuser",
        text_content="This is a test tweet! (1/2)",
        tweet_url="https://x.com/testuser/status/12345",
        is_thread_candidate=True
    )
    print("\nScrapedTweet Example:")
    print(tweet_example.model_dump_json(indent=2))

    default_action_config = ActionConfig()
    print("\nDefault ActionConfig Example:")
    print(default_action_config.model_dump_json(indent=2))
