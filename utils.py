"""
MythosCards Exporter - Utility Functions
Yardımcı fonksiyonlar ve ortak işlemler
"""

import os
import logging
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
import pytz
from platformdirs import user_documents_dir


def setup_logging() -> None:
    """Logging sistemini kurma"""
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"run-{today}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def ist_timestamp() -> str:
    """İstanbul timezone'ında timestamp"""
    ist_tz = pytz.timezone('Europe/Istanbul')
    now = datetime.now(ist_tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


def get_user_documents_dir() -> Path:
    """Kullanıcının Documents klasörünü al"""
    return Path(user_documents_dir())


def get_app_data_dir() -> Path:
    """Uygulama için Documents altında klasör"""
    docs_dir = get_user_documents_dir()
    app_dir = docs_dir / "MythosCards"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_outputs_dir() -> Path:
    """Çıktılar için klasör"""
    outputs_dir = get_app_data_dir() / "Outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir


def safe_filename(name: str) -> str:
    """Güvenli dosya adı oluşturma"""
    # Windows/macOS için geçersiz karakterleri temizle
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    
    # Çoklu alt çizgileri tek yapma
    while '__' in name:
        name = name.replace('__', '_')
    
    return name.strip('_')


def handle_file_collision(base_path: Path) -> Path:
    """Dosya çakışması durumunda yeni isim üret"""
    if not base_path.exists():
        return base_path
    
    # Timestamp ekle
    ist_tz = pytz.timezone('Europe/Istanbul')
    now = datetime.now(ist_tz)
    timestamp = now.strftime("_%Y-%m-%d_%H-%M_IST")
    
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    
    new_path = parent / f"{stem}{timestamp}{suffix}"
    
    # Hala çakışma varsa _v2, _v3... ekle
    counter = 2
    while new_path.exists():
        new_path = parent / f"{stem}{timestamp}_v{counter}{suffix}"
        counter += 1
    
    return new_path


def get_system_info() -> dict:
    """Sistem bilgilerini al"""
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'architecture': platform.architecture()[0],
        'machine': platform.machine(),
        'processor': platform.processor()
    }


def normalize_text(text: str) -> str:
    """Metin normalizasyonu (boşluklar vs.)"""
    if not isinstance(text, str):
        return str(text).strip()
    
    return text.strip()


def is_numeric_value(value) -> bool:
    """Değerin sayısal olup olmadığını kontrol et"""
    if value is None:
        return False
    
    if isinstance(value, (int, float)):
        return not (value != value)  # NaN kontrolü
    
    try:
        float(str(value))
        return True
    except (ValueError, TypeError):
        return False


def safe_int(value, default: int = 0) -> int:
    """Güvenli integer dönüşümü"""
    if is_numeric_value(value):
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return default
    return default


def get_current_user() -> str:
    """Mevcut kullanıcı adını al"""
    return os.environ.get('USERNAME', os.environ.get('USER', 'Unknown'))


def create_series_dir(series_name: str) -> Path:
    """Seri için çıktı klasörü oluştur"""
    safe_name = safe_filename(series_name)
    series_dir = get_outputs_dir() / safe_name
    series_dir.mkdir(parents=True, exist_ok=True)
    return series_dir


class ProgressTracker:
    """İlerleme takibi için basit sınıf"""
    
    def __init__(self, total: int, callback=None):
        self.total = total
        self.current = 0
        self.callback = callback
    
    def update(self, increment: int = 1):
        """İlerleme güncelle"""
        self.current += increment
        if self.callback:
            percentage = (self.current / self.total) * 100 if self.total > 0 else 0
            self.callback(self.current, self.total, percentage)
    
    def set_callback(self, callback):
        """Callback fonksiyonu ayarla"""
        self.callback = callback


# Exception sınıfları
class MythosError(Exception):
    """Base exception sınıfı"""
    pass


class ValidationError(MythosError):
    """Doğrulama hatası"""
    pass


class HeaderError(MythosError):
    """Header ile ilgili hata"""
    pass


class ExportError(MythosError):
    """Export ile ilgili hata"""
    pass


class FileOperationError(MythosError):
    """Dosya işlemi hatası"""
    pass


# Logger instance
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Test amaçlı
    setup_logging()
    print(f"Documents dir: {get_user_documents_dir()}")
    print(f"App data dir: {get_app_data_dir()}")
    print(f"IST Time: {ist_timestamp()}")
    print(f"System info: {get_system_info()}")