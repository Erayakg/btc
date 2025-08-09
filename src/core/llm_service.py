import os
import sys
import logging
from typing import Optional, List, Any, Dict
import asyncio

# Import Google Generative AI (Gemini)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Standard API key placeholders to check against
API_KEY_PLACEHOLDERS = {
    "gemini_api_key": "YOUR_GEMINI_API_KEY"
}


class LLMService:
    _instance = None
    _initialized = False
    
    def __new__(cls, config_loader: ConfigLoader):
        if cls._instance is None:
            cls._instance = super(LLMService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config_loader: ConfigLoader):
        if not LLMService._initialized:
            self.config_loader = config_loader
            LLMService._initialized = True
        
        # Her seferinde yeni ayarları al
        self.api_keys: Dict[str, Any] = self.config_loader.get_setting('api_keys', {})
        
        # Get LLM settings from the correct location
        twitter_automation = self.config_loader.get_setting('twitter_automation', {})
        self.llm_settings: Dict[str, Any] = twitter_automation.get('action_config', {})
        
        self.gemini_client: Optional[genai.GenerativeModel] = None
        
        self._initialize_clients()

    def _is_api_key_valid(self, key_name: str, key_value: Optional[str]) -> bool:
        """Checks if an API key is present and not a placeholder."""
        if not key_value:
            return False
        placeholder = API_KEY_PLACEHOLDERS.get(key_name)
        if placeholder and key_value.strip().upper() == placeholder:
            return False
        # Check for common variations if key_name is generic
        if "YOUR_" in key_value.upper() and "_KEY" in key_value.upper(): # A more generic placeholder check
            return False
        return True

    def _initialize_clients(self):
        # Initialize Gemini client
        if GEMINI_AVAILABLE:
            gemini_api_key = self.api_keys.get('gemini_api_key')
            logger.info(f"Gemini API Key (first 10 chars): {gemini_api_key if gemini_api_key else 'None'}...")
            logger.info(f"Gemini API Key valid: {self._is_api_key_valid('gemini_api_key', gemini_api_key)}")

            if self._is_api_key_valid('gemini_api_key', gemini_api_key):
                try:
                    genai.configure(api_key=gemini_api_key)
                    self.gemini_client = genai.GenerativeModel("gemini-1.5-flash")
                    logger.info("Gemini client initialized.")
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini client: {e}", exc_info=True)
            else:
                logger.info("Gemini API key not configured or is a placeholder. Gemini client not initialized.")
        else:
            logger.warning("Gemini SDK not available. Install with: pip install google-generativeai")
        
        # Debug: Available services
        logger.info(f"Available LLM services: {self.get_available_services()}")

    async def generate_text(
        self,
        prompt: str,
        service_preference: Optional[str] = None,
        **call_params: Any # Combined model, max_tokens, temperature, etc.
    ) -> Optional[str]:
        """
        Generate text using Gemini service.
        
        Args:
            prompt: The input prompt
            service_preference: Ignored, always uses Gemini
            **call_params: Additional parameters for the LLM call
            
        Returns:
            Generated text or None if failed
        """
        try:
            # Get LLM settings from the correct location
            twitter_automation = self.config_loader.get_setting('twitter_automation', {})
            action_config = twitter_automation.get('action_config', {})
            
            # Use llm_settings_for_post as default
            service_config = action_config.get('llm_settings_for_post', {})
            
            # Always use Gemini
            if self.gemini_client:
                logger.info(f"Generating text with Gemini")
                
                # Add Turkish instruction to keep responses direct with UTF-8 support
                turkish_prompt = f"{prompt}\n\nLütfen sadece tweet'i yaz, başka açıklama yapma. Direkt cevap ver. Türkçe karakterleri doğru kullan."
                
                # Limit tokens for Gemini to keep tweets short
                max_tokens = call_params.get('max_tokens', 50)  # Default to 50 for Gemini
                
                # Convert async to sync for Gemini with UTF-8 encoding
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self.gemini_client.generate_content, turkish_prompt)
                
                if response and response.text:
                    # UTF-8 encoding ile response'u işle
                    generated_text = response.text.strip()
                    
                    # Türkçe karakterleri kontrol et ve düzelt
                    try:
                        # UTF-8 encoding test
                        generated_text.encode('utf-8')
                        logger.info(f"Text encoding check passed: {generated_text[:50]}...")
                        
                        # Türkçe karakter kontrolü
                        turkish_chars = ['ç', 'ğı', 'ö', 'ş', 'ü', 'Ç', 'Ğ', 'I', 'Ö', 'Ş', 'Ü']
                        has_turkish = any(char in generated_text for char in turkish_chars)
                        if has_turkish:
                            logger.info("Text contains Turkish characters - UTF-8 encoding confirmed")
                        
                    except UnicodeEncodeError as e:
                        logger.warning(f"Encoding issue detected: {e}")
                        # Fallback: ASCII'ye çevir ama uyarı ver
                        generated_text = generated_text.encode('ascii', 'replace').decode('ascii')
                        logger.warning("Converted text to ASCII due to encoding issues")
                        logger.warning("WARNING: Turkish characters may be lost!")
                    
                    # Limit tweet length to 280 characters (Twitter limit)
                    if len(generated_text) > 280:
                        # Daha güvenli kesme - kelime sınırında kes
                        words = generated_text.split()
                        truncated_text = ""
                        for word in words:
                            if len(truncated_text + " " + word) <= 277:  # 3 karakter "..." için yer bırak
                                truncated_text += (" " + word) if truncated_text else word
                            else:
                                break
                        generated_text = truncated_text.strip() + "..."
                    
                    logger.info(f"Successfully generated text with Gemini. Length: {len(generated_text)}")
                    return generated_text
                else:
                    logger.error("Gemini response is empty or invalid")
                    return None
            
            else:
                logger.error("No Gemini client available")
                return None
                
        except Exception as e:
            logger.error(f"Error using Gemini LLM: {e}")
            return None

    def get_available_services(self) -> List[str]:
        """Returns list of available LLM services."""
        available = []
        if self.gemini_client:
            available.append('gemini')
        return available

    def is_service_available(self, service_name: str) -> bool:
        """Check if a specific service is available."""
        if service_name == 'gemini':
            return self.gemini_client is not None
        return False


# Test function for direct execution
async def main_test():
    # Setup basic logging for direct script execution
    logging.basicConfig(level=logging.INFO)
    
    try:
        config_loader = ConfigLoader()
        llm_service = LLMService(config_loader)
        
        # Test text generation
        test_prompt = "Write a short tweet about artificial intelligence."
        logger.info(f"Testing with prompt: {test_prompt}")
        
        result = await llm_service.generate_text(test_prompt)
        
        if result:
            logger.info(f"Generated text: {result}")
        else:
            logger.warning("No text generated. Check API key configuration.")
            
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_test())
