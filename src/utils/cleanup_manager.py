#!/usr/bin/env python3
"""
Otomatik temizlik yöneticisi - proje çalışırken disk alanını korur
"""

import os
import shutil
import glob
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

class CleanupManager:
    """Disk alanını otomatik olarak temizleyen yönetici"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.cleanup_patterns = [
            # ZIP dosyaları
            "*.zip",
            
            # Eski log dosyaları (1MB'dan büyük)
            "logs/app.log.*",
            
            # Geçici dosyalar
            "*.tmp",
            "*.temp",
            
            # Python cache
            "**/__pycache__",
            "*.pyc",
            "*.pyo",
            
            # Test dosyaları
            "test_*.py",
            "*_test.py",
        ]
    
    def cleanup_before_run(self) -> int:
        """Proje çalıştırılmadan önce temizlik yapar"""
        logger.info("🧹 Çalıştırma öncesi temizlik başlatılıyor...")
        return self._perform_cleanup("before_run")
    
    def cleanup_after_run(self) -> int:
        """Proje çalıştırıldıktan sonra temizlik yapar"""
        logger.info("🧹 Çalıştırma sonrası temizlik başlatılıyor...")
        return self._perform_cleanup("after_run")
    
    def cleanup_logs(self, max_size_mb: int = 1) -> int:
        """Log dosyalarını temizler"""
        freed_space = 0
        log_files = glob.glob(str(self.project_root / "logs" / "*.log*"))
        
        for log_file in log_files:
            try:
                size_mb = os.path.getsize(log_file) / (1024 * 1024)
                if size_mb > max_size_mb:
                    # Dosyayı temizle (içeriğini sil)
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write("")
                    freed_space += size_mb
                    logger.info(f"✅ Log dosyası temizlendi: {log_file} ({size_mb:.2f} MB)")
            except Exception as e:
                logger.warning(f"❌ Log temizlenemedi: {log_file} - {e}")
        
        return int(freed_space * 1024 * 1024)  # Byte cinsinden döndür
    
    def _perform_cleanup(self, stage: str) -> int:
        """Temizlik işlemini gerçekleştirir"""
        total_freed = 0
        
        for pattern in self.cleanup_patterns:
            if stage == "before_run" and pattern in ["*.zip", "**/__pycache__"]:
                # Çalıştırma öncesi sadece belirli dosyaları temizle
                continue
                
            matches = glob.glob(str(self.project_root / pattern), recursive=True)
            for match in matches:
                if os.path.exists(match):
                    try:
                        if os.path.isfile(match):
                            size = os.path.getsize(match)
                            os.remove(match)
                            total_freed += size
                            logger.debug(f"✅ Dosya silindi: {match} ({size/1024:.1f} KB)")
                        elif os.path.isdir(match):
                            size = self._get_dir_size(match)
                            shutil.rmtree(match)
                            total_freed += size
                            logger.debug(f"✅ Klasör silindi: {match} ({size/1024:.1f} KB)")
                    except Exception as e:
                        logger.warning(f"❌ Silinemedi: {match} - {e}")
        
        # Log dosyalarını temizle
        total_freed += self.cleanup_logs()
        
        logger.info(f"🎉 {stage} temizliği tamamlandı! Kazanılan alan: {total_freed/1024/1024:.2f} MB")
        return total_freed
    
    def _get_dir_size(self, path: str) -> int:
        """Klasörün toplam boyutunu hesaplar"""
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
        return total
    
    def get_disk_usage_report(self) -> List[Tuple[str, float]]:
        """Disk kullanım raporu oluşturur"""
        large_files = []
        
        for root, dirs, files in os.walk(self.project_root):
            # Gereksiz klasörleri atla
            dirs[:] = [d for d in dirs if d not in ['.git', '.venv', '__pycache__']]
            
            for file in files:
                try:
                    filepath = os.path.join(root, file)
                    size = os.path.getsize(filepath)
                    if size > 1024 * 1024:  # 1MB'dan büyük
                        rel_path = os.path.relpath(filepath, self.project_root)
                        large_files.append((rel_path, size / (1024 * 1024)))
                except (OSError, FileNotFoundError):
                    pass
        
        return sorted(large_files, key=lambda x: x[1], reverse=True)[:10]

def setup_cleanup_manager() -> CleanupManager:
    """CleanupManager'ı yapılandırır ve döndürür"""
    return CleanupManager()

if __name__ == "__main__":
    # Test için
    logging.basicConfig(level=logging.INFO)
    manager = CleanupManager()
    
    print("🔍 Disk kullanım raporu:")
    for filepath, size_mb in manager.get_disk_usage_report():
        print(f"   {filepath}: {size_mb:.2f} MB")
    
    print("\n🧹 Test temizliği:")
    freed = manager.cleanup_before_run()
    print(f"Kazanılan alan: {freed/1024/1024:.2f} MB")
