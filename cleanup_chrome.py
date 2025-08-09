#!/usr/bin/env python3
"""
Chrome cleanup script - Manually clean up Chrome processes and temporary directories
"""

import os
import sys
import subprocess
import platform
import tempfile
import glob
import shutil
import time

def cleanup_chrome_processes():
    """Force cleanup all Chrome processes"""
    print("🧹 Chrome process'leri temizleniyor...")
    
    try:
        if platform.system() == "Windows":
            # Windows'ta Chrome process'lerini zorla kapat
            subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], 
                         capture_output=True, timeout=10)
            subprocess.run(["taskkill", "/f", "/im", "chromedriver.exe"], 
                         capture_output=True, timeout=10)
        else:
            # Linux'ta Chrome process'lerini zorla kapat
            subprocess.run(["pkill", "-f", "chrome"], 
                         capture_output=True, timeout=10)
            subprocess.run(["pkill", "-f", "chromedriver"], 
                         capture_output=True, timeout=10)
        
        print("✅ Chrome process'leri temizlendi")
        return True
    except Exception as e:
        print(f"❌ Chrome process'leri temizlenirken hata: {e}")
        return False

def cleanup_temp_directories():
    """Clean up temporary Chrome user data directories"""
    print("🧹 Temporary dizinler temizleniyor...")
    
    freed_space = 0
    cleaned_dirs = 0
    
    try:
        # Find and remove temporary Chrome user data directories
        temp_dir = tempfile.gettempdir()
        chrome_dirs = glob.glob(os.path.join(temp_dir, "chrome_user_data_*"))
        
        for chrome_dir in chrome_dirs:
            try:
                if os.path.exists(chrome_dir):
                    # Calculate directory size before removal
                    dir_size = get_directory_size(chrome_dir)
                    shutil.rmtree(chrome_dir, ignore_errors=True)
                    freed_space += dir_size
                    cleaned_dirs += 1
                    print(f"  📁 {chrome_dir} temizlendi ({dir_size/1024/1024:.2f} MB)")
            except Exception as e:
                print(f"  ❌ {chrome_dir} temizlenirken hata: {e}")
        
        print(f"✅ {cleaned_dirs} temporary dizin temizlendi. Toplam kazanılan alan: {freed_space/1024/1024:.2f} MB")
        return True
    except Exception as e:
        print(f"❌ Temporary dizinler temizlenirken hata: {e}")
        return False

def get_directory_size(path: str) -> int:
    """Calculate directory size in bytes"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
    except Exception:
        pass
    return total_size

def main():
    """Main cleanup function"""
    print("🚀 Chrome Cleanup Script")
    print("=" * 50)
    
    # Clean up processes
    process_cleanup_success = cleanup_chrome_processes()
    
    # Wait a bit for processes to fully terminate
    if process_cleanup_success:
        print("⏳ Process'lerin tamamen kapanması için bekleniyor...")
        time.sleep(2)
    
    # Clean up temporary directories
    dir_cleanup_success = cleanup_temp_directories()
    
    print("=" * 50)
    if process_cleanup_success and dir_cleanup_success:
        print("🎉 Temizlik başarıyla tamamlandı!")
    else:
        print("⚠️  Temizlik kısmen tamamlandı. Bazı işlemler başarısız oldu.")
    
    print("\n💡 Artık otomasyonu yeniden başlatabilirsiniz.")

if __name__ == "__main__":
    main()
