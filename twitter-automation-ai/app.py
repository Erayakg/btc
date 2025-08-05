from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import json
import os
import subprocess
import threading
import time
from datetime import datetime
import sys
import logging

# src dizinini Python path'ine ekle
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.core.config_loader import ConfigLoader

# Logger'ı tanımla
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = 'twitter_automation_secret_key'

# Global değişkenler
current_process = None
process_logs = []
is_running = False
automation_stats = {
    'total_tweets': 0,
    'total_likes': 0,
    'total_reposts': 0,
    'active_accounts': 0
}

def load_settings():
    """Mevcut ayarları yükle"""
    try:
        config_loader = ConfigLoader()
        return config_loader.get_settings()
    except Exception as e:
        return {}

def save_settings(settings):
    """Ayarları kaydet"""
    try:
        config_path = 'config/settings.json'
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ayar kaydetme hatası: {e}")
        return False

def run_main_python():
    """main.py'yi çalıştır"""
    global current_process, is_running, process_logs, automation_stats
    
    is_running = True
    process_logs = []
    automation_stats = {
        'total_tweets': 0,
        'total_likes': 0,
        'total_reposts': 0,
        'active_accounts': 0
    }
    
    try:
        # main.py'yi çalıştır - headless mod için environment variable set et
        env = os.environ.copy()
        env['BROWSER_HEADLESS'] = 'true'  # Firefox'un görünmemesi için
        
        # Settings dosyasının güncel olduğundan emin ol
        logger.info("Güncel settings.json dosyası kullanılıyor...")
        
        current_process = subprocess.Popen(
            [sys.executable, 'src/main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env
        )
        
        # Logları oku ve istatistikleri güncelle
        for line in iter(current_process.stdout.readline, ''):
            if line:
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_entry = f"[{timestamp}] {line.strip()}"
                process_logs.append(log_entry)
                print(log_entry)
                
                # İstatistikleri güncelle
                if "Tweet basariyla atildi" in line or "AI Tweet basariyla atildi" in line:
                    automation_stats['total_tweets'] += 1
                elif "Tweet beğenildi" in line or "like_success" in line:
                    automation_stats['total_likes'] += 1
                elif "Repost basariyla atildi" in line or "repost_success" in line:
                    automation_stats['total_reposts'] += 1
                elif "Account" in line and "is_active" in line:
                    automation_stats['active_accounts'] += 1
        
        current_process.wait()
        
    except Exception as e:
        error_msg = f"Hata: {str(e)}"
        process_logs.append(error_msg)
        print(error_msg)
    finally:
        is_running = False
        current_process = None

@app.route('/')
def index():
    """Ana sayfa"""
    return app.send_static_file('web_interface.html')

@app.route('/api/save-settings', methods=['POST'])
def save_settings_route():
    """Ayarları kaydet"""
    try:
        data = request.get_json()
        
        # Mevcut ayarları yükle
        current_settings = load_settings()
        
        # API keys'i güncelle
        if 'api_keys' in data:
            if 'api_keys' not in current_settings:
                current_settings['api_keys'] = {}
            
            for key, value in data['api_keys'].items():
                current_settings['api_keys'][key] = value
        
        # Yeni ayarları güncelle
        if 'twitter_automation' in data:
            if 'twitter_automation' not in current_settings:
                current_settings['twitter_automation'] = {}
            
            # Twitter automation ayarlarını güncelle
            if 'response_interval_seconds' in data['twitter_automation']:
                current_settings['twitter_automation']['response_interval_seconds'] = data['twitter_automation']['response_interval_seconds']
            if 'tweets_per_account' in data['twitter_automation']:
                current_settings['twitter_automation']['tweets_per_account'] = data['twitter_automation']['tweets_per_account']
            
            # Action config'i parse et
            if 'action_config' in data['twitter_automation']:
                action_config_data = data['twitter_automation']['action_config']
                
                action_config = {
                    'enable_liking_tweets': action_config_data.get('enable_liking_tweets', True),
                    'max_likes_per_run': int(action_config_data.get('max_likes_per_run', 5)),
                    'like_tweets_from_keywords': action_config_data.get('like_tweets_from_keywords', []),
                    'enable_keyword_reposts': action_config_data.get('enable_keyword_reposts', True),
                    'max_reposts_per_keyword': int(action_config_data.get('max_reposts_per_keyword', 2)),
                    'target_keywords': action_config_data.get('target_keywords', []),
                    'llm_settings_for_post': {
                        'service_preference': 'gemini',
                        'model_name_override': action_config_data.get('llm_settings_for_post', {}).get('model_name_override', 'gemini-1.5-flash'),
                        'max_tokens': int(action_config_data.get('llm_settings_for_post', {}).get('max_tokens', 50)),
                        'temperature': float(action_config_data.get('llm_settings_for_post', {}).get('temperature', 0.7))
                    }
                }
                
                current_settings['twitter_automation']['action_config'] = action_config
        
        # Ayarları kaydet
        if save_settings(current_settings):
            return jsonify({'success': True, 'message': 'Ayarlar başarıyla kaydedildi!'})
        else:
            return jsonify({'success': False, 'message': 'Ayarlar kaydedilirken hata oluştu!'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'})

@app.route('/api/start-automation', methods=['POST'])
def start_automation():
    """Otomasyonu başlat"""
    global is_running
    
    if is_running:
        return jsonify({'success': False, 'message': 'Otomasyon zaten çalışıyor!'})
    
    # Arka planda main.py'yi çalıştır
    thread = threading.Thread(target=run_main_python)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Otomasyon başlatıldı!'})

@app.route('/api/stop-automation', methods=['POST'])
def stop_automation():
    """Otomasyonu durdur"""
    global current_process, is_running
    
    if current_process and is_running:
        try:
            current_process.terminate()
            # 5 saniye bekle, eğer hala çalışıyorsa force kill
            current_process.wait(timeout=5)
        except:
            current_process.kill()
        
        is_running = False
        current_process = None
        return jsonify({'success': True, 'message': 'Otomasyon durduruldu!'})
    else:
        is_running = False
        current_process = None
        return jsonify({'success': True, 'message': 'Otomasyon zaten durmuştu!'})

@app.route('/api/get-status')
def get_status():
    """Durum bilgisini al"""
    global is_running, process_logs
    
    # Son 50 logu al ve timestamp'leri düzelt
    recent_logs = []
    if process_logs:
        recent_logs = process_logs[-50:]
    
    return jsonify({
        'is_running': is_running,
        'logs': recent_logs
    })

@app.route('/api/get-stats')
def get_stats():
    """İstatistikleri al"""
    global automation_stats
    
    return jsonify(automation_stats)

@app.route('/api/get-logs')
def get_logs():
    """Logları al"""
    global process_logs
    
    # Son 100 logu al
    recent_logs = []
    if process_logs:
        recent_logs = process_logs[-100:]
    
    return jsonify({'logs': recent_logs})

@app.route('/api/get-settings')
def get_settings():
    """Mevcut ayarları al"""
    settings = load_settings()
    return jsonify(settings)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 