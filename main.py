"""
MythosCards Exporter - Main Application
CLI ve GUI interface'leri
"""

"""
MythosCards Exporter - Main Application
CLI ve GUI interface'leri
"""

import sys
import logging
import os
import queue
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import click
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from images import process_image_mapping, validate_image_inputs, validate_matching_preview
from shorten import process_shortening, validate_shortening_preview, validate_shorten_inputs
from datetime import datetime

# Path düzeltmesi PyInstaller için
if getattr(sys, 'frozen', False):
    # PyInstaller exe modunda
    application_path = sys._MEIPASS
else:
    # Normal Python modunda
    application_path = Path(__file__).parent

sys.path.insert(0, str(application_path))

# Normal import'lar
import utils
import io_ops
import headers
import validate
import expand
import sorters
import export
from version import PROGRAM_NAME, PROGRAM_VERSION

# Fonksiyon referansları
setup_logging = utils.setup_logging
get_outputs_dir = utils.get_outputs_dir
ProgressTracker = utils.ProgressTracker
MythosError = utils.MythosError
read_checklist_excel = io_ops.read_checklist_excel
normalize_headers = headers.normalize_headers
validate_checklist = validate.validate_checklist
create_dry_run_report = validate.create_dry_run_report
expand_checklist_rows = expand.expand_checklist_rows
export_card_lines = export.export_card_lines
create_export_config = export.create_export_config
validate_export_requirements = export.validate_export_requirements

logger = logging.getLogger(__name__)


def process_checklist(input_file: Path,
                     output_dir: Path,
                     per_series: bool = True,
                     dry_run: bool = True,
                     locale_pref: str = "tr") -> Dict[str, Any]:
    """Ana checklist işleme fonksiyonu"""
    
    result = {
        'success': False,
        'files': [],
        'errors': [],
        'warnings': [],
        'summary': {},
        'dry_run_report': None
    }
    
    try:
        logger.info(f"Checklist işleme başlıyor: {input_file}")
        
        # 1. Excel dosyasını oku
        data = read_checklist_excel(input_file)
        logger.info(f"Veri okundu: {len(data)} satır, {len(data.columns)} sütun")
        
        # 2. Header'ları işle
        header_processor = normalize_headers(list(data.columns))
        if header_processor.has_errors():
            result['errors'].extend(header_processor.errors)
            logger.error("Header hatası tespit edildi")
        
        # 3. Doğrulama
        # 3. Doğrulama
        validation_result = validate_checklist(data, header_processor)
        result['errors'].extend(validation_result.errors)
        result['warnings'].extend(validation_result.warnings)

        # 4. Her durumda dry_run_report oluştur
        dry_run_report = create_dry_run_report(validation_result)
        result['dry_run_report'] = dry_run_report
        logger.info("Validation raporu oluşturuldu")

        # Sadece dry_run=True ise blocking error'da dur
        if not validation_result.is_valid and dry_run:
            logger.error("Blocking hatalar mevcut, işlem durduruluyor")
            result['success'] = False
            return result
                
        # 5. Satır genişletme
        expansion_result = expand_checklist_rows(data, header_processor)
        result['errors'].extend(expansion_result.errors)
        result['warnings'].extend(expansion_result.warnings)
        
        if not expansion_result.lines:
            result['errors'].append({
                'type': 'No Output',
                'message': 'Hiç kart satırı oluşturulamadı'
            })
            return result
        
        logger.info(f"Genişletme tamamlandı: {len(expansion_result.lines)} kart")
        
        # 6. Export gereksinim kontrolü
        export_issues = validate_export_requirements(expansion_result.lines)
        if export_issues:
            for issue in export_issues:
                result['errors'].append({
                    'type': 'Export Validation',
                    'message': issue
                })
            return result
        
        # 7. Export
        export_config = create_export_config(
            str(input_file),
            str(output_dir),
            per_series,
            dry_run,
            locale_pref
        )
        
        exported_files = export_card_lines(
            expansion_result.lines,
            result['errors'],
            result['warnings'],
            export_config,
            per_series
        )
        
        result['files'] = exported_files
        result['summary'] = expansion_result.summary
        result['success'] = len(exported_files) > 0
        
        logger.info(f"İşlem tamamlandı: {len(exported_files)} dosya oluşturuldu")
        
    except Exception as e:
        logger.error(f"İşlem hatası: {str(e)}")
        result['errors'].append({
            'type': 'Processing Error',
            'message': str(e)
        })
    
    return result


# CLI Implementation
@click.group()
@click.version_option(version=PROGRAM_VERSION, prog_name=PROGRAM_NAME)
def cli():
    """MythosCards Exporter - Checklist'ten kart listesi oluşturucu"""
    setup_logging()


@cli.command('list')
@click.option('--in', 'input_file', required=True, type=click.Path(exists=True),
              help='Giriş Excel dosyası')
@click.option('--outdir', default=None, type=click.Path(),
              help='Çıktı dizini (varsayılan: Documents/MythosCards/Outputs)')
@click.option('--per-series', default=True, type=bool,
              help='Her seri için ayrı dosya oluştur')
@click.option('--dry-run', default=True, type=bool,
              help='Önce doğrulama raporu göster')
@click.option('--locale', default='tr', type=click.Choice(['tr', 'ascii']),
              help='Sıralama locale\'i')

def list_command(input_file, outdir, per_series, dry_run, locale):
    """Checklist'i kart listesine çevir"""
    
    input_path = Path(input_file)
    output_dir = Path(outdir) if outdir else get_outputs_dir()
    
    click.echo(f"📁 Giriş: {input_path}")
    click.echo(f"📁 Çıktı: {output_dir}")
    click.echo(f"⚙️  Ayarlar: per-series={per_series}, dry-run={dry_run}, locale={locale}")
    click.echo()
    
    result = process_checklist(
        input_path, output_dir, per_series, dry_run, locale
    )
    
    # Dry-run raporu göster
    if dry_run and result.get('dry_run_report'):
        report = result['dry_run_report']
        click.echo("📋 KURAL RAPORU (ÖNİZLEME)")
        click.echo("=" * 50)
        
        summary = report['summary']
        click.echo(f"Toplam Satır: {summary['total_rows']}")
        click.echo(f"Toplam Hata: {summary['total_errors']} (Engelleyici: {summary['blocking_errors']})")
        click.echo(f"Toplam Uyarı: {summary['total_warnings']}")
        click.echo()
        
        # Hataları göster
        if result['errors']:
            click.echo("❌ HATALAR:")
            for error in result['errors'][:5]:  # İlk 5 hata
                click.echo(f"  Satır {error.get('row', '?')}: {error.get('message', '')}")
            if len(result['errors']) > 5:
                click.echo(f"  ... ve {len(result['errors'])-5} hata daha")
            click.echo()
        
        # Uyarıları göster
        if result['warnings']:
            click.echo("⚠️  UYARILAR:")
            for warning in result['warnings'][:3]:  # İlk 3 uyarı
                click.echo(f"  Satır {warning.get('row', '?')}: {warning.get('message', '')}")
            if len(result['warnings']) > 3:
                click.echo(f"  ... ve {len(result['warnings'])-3} uyarı daha")
            click.echo()
        
        recommendation = report['recommendation']
        click.echo(f"💡 Öneri: {recommendation}")
        
        # Blocking error varsa durdur
        if summary['blocking_errors'] > 0:
            if not click.confirm("⚠️  Engelleyici hatalar mevcut. Yine de devam etmek istiyor musunuz?"):
                click.echo("❌ İşlem iptal edildi.")
                sys.exit(1)
            
            # Hatalar olsa da devam et
            result = process_checklist(
                input_path, output_dir, per_series, False, locale  # dry_run=False
            )
    
    # Sonuçları göster
    if result['success']:
        click.echo("✅ İŞLEM BAŞARILI!")
        click.echo(f"📄 {len(result['files'])} dosya oluşturuldu:")
        for file_path in result['files']:
            click.echo(f"  📄 {file_path}")
        
        if result['summary']:
            summary = result['summary']
            click.echo(f"\n📊 Özet: {summary.get('total_cards', 0)} kart, {summary.get('total_players', 0)} oyuncu")
    else:
        click.echo("❌ İŞLEM BAŞARISIZ!")
        if result['errors']:
            click.echo("Hatalar:")
            for error in result['errors']:
                click.echo(f"  ❌ {error.get('message', '')}")
        sys.exit(1)
@cli.command('images')
@click.option('--excel', required=True, type=click.Path(exists=True),
              help='Part 1 Excel çıktı dosyası')
@click.option('--imgdir', required=True, type=click.Path(exists=True),
              help='Görsel dosyalarının klasörü')
@click.option('--date', default=None, type=str,
              help='YYYYMMDD format (varsayılan: bugün)')
@click.option('--skip-preview', is_flag=True, default=False,
              help='Ön doğrulamayı atla')
def images_command(excel, imgdir, date, skip_preview):
    """Part 2: Görselleri kartlara eşleştir"""

    click.echo(f"Excel: {excel}")
    click.echo(f"Görseller: {imgdir}")
    click.echo(f"Tarih: {date or 'bugün'}")

    # Validation
    issues = validate_image_inputs(excel, imgdir)
    if issues:
        click.echo("HATA:")
        for issue in issues:
            click.echo(f"  - {issue}")
        sys.exit(1)

    try:
        # ÖN DOĞRULAMA (eğer atlanmadıysa)
        if not skip_preview:
            click.echo("\n" + "="*50)
            click.echo("ÖN DOĞRULAMA - Eşleştirme İstatistikleri")
            click.echo("="*50)

            preview = validate_matching_preview(excel, imgdir, date, strict_mode=False)

            click.echo(f"📊 Toplam Kart: {preview['total_cards']}")
            click.echo(f"🔍 Unique Kombinasyon: {preview['unique_combinations']}")
            click.echo(f"🖼️  Toplam Görsel: {preview['total_images']}")
            click.echo(f"⚡ Performans: {preview['performance_gain']} hızlı")

            click.echo("\nTAHMİNİ EŞLEŞMEsı:")
            est = preview['estimated_matches']
            click.echo(f"  ✅ Bulunacak: {est['found']} (%{est['found_percent']:.1f})")
            click.echo(f"  ❌ Eksik: {est['missing']} (%{est['missing_percent']:.1f})")
            click.echo(f"  ⚠️  Çakışma: {est['conflict']} (%{est['conflict_percent']:.1f})")
            click.echo("="*50 + "\n")

            # Kullanıcıya sor
            if est['missing_percent'] > 50:
                if not click.confirm(f"⚠️  UYARI: %{est['missing_percent']:.1f} eksik olacak. Devam edilsin mi?"):
                    click.echo("❌ İşlem iptal edildi")
                    sys.exit(0)

        click.echo("🚀 Görsel eşleştirme başlıyor...")
        result = process_image_mapping(excel, imgdir, date, add_date_prefix=False, strict_mode=False)

        # Sonuç
        click.echo(f"\n✅ TAMAMLANDI!")
        click.echo(f"Toplam: {result['total_cards']}")
        click.echo(f"Bulunan: {result['found_count']}")
        click.echo(f"Eksik: {result['missing_count']}")
        click.echo(f"Çakışma: {result['conflict_count']}")
        click.echo(f"Başarı: {result['success_rate']:.1f}%")

        if result['warnings']:
            click.echo(f"\nUYARILAR ({len(result['warnings'])}):")
            for w in result['warnings'][:5]:
                click.echo(f"  Satır {w['row']}: {w['message']}")

    except Exception as e:
        click.echo(f"❌ HATA: {str(e)}")
        sys.exit(1)

# GUI Implementation

# Renk paleti — açık tema, log seviyelerine göre
LOG_COLORS = {
    'DEBUG': '#757575',     # açık gri
    'INFO': '#1F1F1F',      # koyu gri (varsayılan)
    'WARNING': '#B8860B',   # koyu turuncu
    'ERROR': '#C62828',     # kırmızı
    'CRITICAL': '#B71C1C',  # koyu kırmızı
    'SUCCESS': '#2E7D32',   # yeşil (özel custom level değil, mesaj içeriğine göre)
}


class TkinterTextHandler(logging.Handler):
    """
    Backend logger mesajlarını Tkinter Text widget'a yazan handler.

    Thread-safe: gelen log kayıtları queue'ya konur, ana thread periyodik
    olarak queue'yu drain edip Text widget'a yazar. Backend uzun süren
    işlemler farklı thread'den log atsa bile widget güvenle güncellenir.

    Seviyelere göre Text tag uygular (renkli gösterim için widget tarafında
    tag_configure çağrılmış olmalı).
    """

    def __init__(self, text_widget: tk.Text, drain_interval_ms: int = 100):
        super().__init__()
        self.text_widget = text_widget
        self.drain_interval_ms = drain_interval_ms
        self._queue: "queue.Queue[logging.LogRecord]" = queue.Queue()
        self._closed = False
        self.setFormatter(logging.Formatter('%(asctime)s %(levelname)-5s %(message)s',
                                            datefmt='%H:%M:%S'))
        # Drain'i başlat
        self._schedule_drain()

    def emit(self, record: logging.LogRecord) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(record)
        except Exception:
            self.handleError(record)

    def _schedule_drain(self) -> None:
        if self._closed:
            return
        try:
            self.text_widget.after(self.drain_interval_ms, self._drain)
        except tk.TclError:
            # Widget destroyed — sessizce kapan
            self._closed = True

    def _drain(self) -> None:
        if self._closed:
            return
        try:
            while True:
                record = self._queue.get_nowait()
                msg = self.format(record)
                tag = self._tag_for_record(record)
                try:
                    self.text_widget.insert(tk.END, msg + "\n", (tag,))
                    self.text_widget.see(tk.END)
                except tk.TclError:
                    self._closed = True
                    return
        except queue.Empty:
            pass
        finally:
            self._schedule_drain()

    @staticmethod
    def _tag_for_record(record: logging.LogRecord) -> str:
        """Log seviyesine göre Text widget tag adı"""
        if record.levelno >= logging.ERROR:
            return 'error'
        if record.levelno >= logging.WARNING:
            return 'warning'
        # INFO içinde "✅" veya "TAMAMLANDI" geçen mesajları success say
        msg = str(record.msg)
        if '✅' in msg or 'TAMAMLANDI' in msg or 'BAŞARILI' in msg:
            return 'success'
        if record.levelno >= logging.INFO:
            return 'info'
        return 'debug'

    def close(self) -> None:
        self._closed = True
        super().close()


def configure_text_tags(text_widget: tk.Text) -> None:
    """Log Text widget'ı için renk tag'lerini ayarla"""
    text_widget.tag_configure('info', foreground=LOG_COLORS['INFO'])
    text_widget.tag_configure('warning', foreground=LOG_COLORS['WARNING'])
    text_widget.tag_configure('error', foreground=LOG_COLORS['ERROR'])
    text_widget.tag_configure('success', foreground=LOG_COLORS['SUCCESS'])
    text_widget.tag_configure('debug', foreground=LOG_COLORS['DEBUG'])


class MythosGUI:
    """GUI uygulaması"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{PROGRAM_NAME} v{PROGRAM_VERSION}")
        self.root.geometry("1100x800")
        self.root.minsize(900, 600)
        
        # Kapanma kontrolü
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._is_closing = False
        
        # Variables
        self.input_file_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(get_outputs_dir()))
        self.per_series_var = tk.BooleanVar(value=True)
        self.dry_run_var = tk.BooleanVar(value=True)
        self.turkish_sort_var = tk.BooleanVar(value=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.image_dir_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y%m%d"))
        self.part2_excel_var = tk.StringVar()
        self.add_date_var = tk.BooleanVar(value=False)

        # Part 3 variables
        self.part3_excel_var = tk.StringVar()
        self.part3_image_dir_var = tk.StringVar()
        self.max_length_var = tk.IntVar(value=97)

        # İşlem sırasında disable edilecek butonların listesi
        # setup_ui içinde doldurulur
        self._action_buttons: List[ttk.Button] = []

        self.setup_ui()
        self._collect_action_buttons()

        # Logger köprüsü — backend logger.info/warning/error mesajları
        # otomatik olarak GUI log alanına düşer (renkli, sıralı, thread-safe)
        self.gui_log_handler = TkinterTextHandler(self.log_text)
        setup_logging(gui_handler=self.gui_log_handler)
        self.logger = logging.getLogger("mythos.gui")

        # Sonuç paneli son güncelleme zamanı (boş başlangıçta)
        self._last_summary: Optional[str] = None
        # İşlem süresi ölçümü için
        self._op_start_time: Optional[float] = None


    def setup_ui(self):
        """
        UI kurulumu — Notebook + PanedWindow yapısı:
        - Üst: 3 sekme (Part 1/2/3)
        - Alt: Log + Sonuç paneli (sash ile resize edilebilir)
        - En alt: 3 segmentli status bar + progress
        """

        # Main frame
        main_frame = ttk.Frame(self.root, padding="8")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(main_frame, text=PROGRAM_NAME, font=('Arial', 13, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 6))

        # PanedWindow — üst: notebook, alt: log+summary
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))

        # === ÜST PANE: Notebook (3 sekme) ===
        self.notebook = ttk.Notebook(paned)
        paned.add(self.notebook, weight=2)

        # Sekme 1: Part 1
        part1_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(part1_frame, text="  Part 1: Kart Listesi  ")
        
        # Input file
        ttk.Label(part1_frame, text="Giriş Excel:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(part1_frame, textvariable=self.input_file_var, width=45).grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(part1_frame, text="Seç", command=self.select_input_file, width=6).grid(row=0, column=2)
        
        # Output directory
        ttk.Label(part1_frame, text="Çıktı Dizini:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(part1_frame, textvariable=self.output_dir_var, width=45).grid(row=1, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(part1_frame, text="Seç", command=self.select_output_dir, width=6).grid(row=1, column=2)
        
        # Seçenekler - daha kompakt
        options_subframe = ttk.Frame(part1_frame)
        options_subframe.grid(row=2, column=0, columnspan=3, pady=(8, 4), sticky=tk.W)
        
        ttk.Checkbutton(options_subframe, text="Her seri için ayrı dosya", 
                    variable=self.per_series_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(options_subframe, text="Türkçe sıralama", 
                    variable=self.turkish_sort_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(options_subframe, text="Hata durumunda durdur", 
                    variable=self.dry_run_var).pack(side=tk.LEFT)
        
        # Butonlar
        buttons_frame = ttk.Frame(part1_frame)
        buttons_frame.grid(row=3, column=0, columnspan=3, pady=(4, 0))
        ttk.Button(buttons_frame, text="Doğrula", command=self.validate_only, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons_frame, text="Oluştur", command=self.generate, width=12).pack(side=tk.LEFT, padx=3)
        
        part1_frame.columnconfigure(1, weight=1)

        # Sekme 2: Part 2
        part2_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(part2_frame, text="  Part 2: Görsel Eşleştirme  ")
        
        # Excel dosyası
        ttk.Label(part2_frame, text="Excel Dosyası:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(part2_frame, textvariable=self.part2_excel_var, width=45).grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(part2_frame, text="Seç", command=self.select_part2_excel, width=6).grid(row=0, column=2)
        
        # Görsel klasörü
        ttk.Label(part2_frame, text="Görsel Klasörü:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(part2_frame, textvariable=self.image_dir_var, width=45).grid(row=1, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(part2_frame, text="Seç", command=self.select_image_dir, width=6).grid(row=1, column=2)
        
        
        # Tarih checkbox ve entry - tek satırda
        date_options_frame = ttk.Frame(part2_frame)
        date_options_frame.grid(row=2, column=0, columnspan=3, pady=(8, 0))

        # Checkbox: Tarih Ekle
        ttk.Checkbutton(
            date_options_frame,
            text="Tarih Ekle",
            variable=self.add_date_var
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Tarih entry
        ttk.Label(date_options_frame, text="Tarih:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(date_options_frame, textvariable=self.date_var, width=10).pack(side=tk.LEFT, padx=(0, 15))

        # Butonlar - Part 1'deki gibi
        ttk.Button(
            date_options_frame,
            text="Kontrol Et",
            command=self.validate_images_preview,
            width=12
        ).pack(side=tk.LEFT, padx=3)

        ttk.Button(
            date_options_frame,
            text="Görselleri Eşleştir",
            command=self.match_images,
            width=18
        ).pack(side=tk.LEFT, padx=3)

        part2_frame.columnconfigure(1, weight=1)

        # Sekme 3: Part 3
        part3_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(part3_frame, text="  Part 3: Dosya Adı Kısaltma  ")

        # Excel dosyası
        ttk.Label(part3_frame, text="Excel Dosyası:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(part3_frame, textvariable=self.part3_excel_var, width=45).grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(part3_frame, text="Seç", command=self.select_part3_excel, width=6).grid(row=0, column=2)

        # Görsel klasörü
        ttk.Label(part3_frame, text="Görsel Klasörü:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(part3_frame, textvariable=self.part3_image_dir_var, width=45).grid(row=1, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(part3_frame, text="Seç", command=self.select_part3_image_dir, width=6).grid(row=1, column=2)

        # Max uzunluk ve butonlar
        part3_options_frame = ttk.Frame(part3_frame)
        part3_options_frame.grid(row=2, column=0, columnspan=3, pady=(8, 0))

        ttk.Label(part3_options_frame, text="Max Uzunluk:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(part3_options_frame, textvariable=self.max_length_var, width=5).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(part3_options_frame, text="karakter").pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(part3_options_frame, text="Kontrol Et", command=self.validate_shortening, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(part3_options_frame, text="Kısalt", command=self.shorten_filenames, width=12).pack(side=tk.LEFT, padx=3)

        part3_frame.columnconfigure(1, weight=1)

        # === ALT PANE: Log + Sonuç paneli ===
        bottom_pane = ttk.Frame(paned)
        paned.add(bottom_pane, weight=3)
        bottom_pane.columnconfigure(0, weight=1)
        bottom_pane.rowconfigure(0, weight=1)

        # === Log alanı (alt pane'in üstü) ===
        log_frame = ttk.LabelFrame(bottom_pane, text="Log", padding="5")
        log_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Toolbar — filtre + temizle + kaydet
        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 4))
        ttk.Button(log_toolbar, text="Tümü", width=8,
                   command=lambda: self._set_log_filter('all')).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(log_toolbar, text="Uyarılar", width=10,
                   command=lambda: self._set_log_filter('warnings')).pack(side=tk.LEFT, padx=4)
        ttk.Button(log_toolbar, text="Hatalar", width=10,
                   command=lambda: self._set_log_filter('errors')).pack(side=tk.LEFT, padx=4)
        ttk.Button(log_toolbar, text="Temizle", width=10,
                   command=self._clear_log).pack(side=tk.LEFT, padx=4)
        ttk.Button(log_toolbar, text="Kaydet…", width=10,
                   command=self._save_log).pack(side=tk.LEFT, padx=4)

        # Text widget — 18 satır, monospace
        self.log_text = tk.Text(log_frame, height=18, width=80, wrap=tk.WORD,
                                font=('Consolas', 9))
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))

        # Renk tag'lerini uygula
        configure_text_tags(self.log_text)

        # === Sonuç paneli (alt pane'in altı, kalıcı) ===
        self.summary_frame = ttk.LabelFrame(bottom_pane, text="Sonuç", padding="8")
        self.summary_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(6, 0))
        self.summary_label = ttk.Label(
            self.summary_frame,
            text="Henüz işlem yapılmadı.",
            font=('Arial', 9),
            justify=tk.LEFT,
            anchor=tk.W,
        )
        self.summary_label.pack(fill=tk.X, expand=True)

        # === Status bar (en alt, 3 segmentli) ===
        # Progress bar üstte tam genişlik
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame, variable=self.progress_var, maximum=100, mode='determinate'
        )
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(4, 2))

        # Status segmentleri
        status_bar = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=1)
        status_bar.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E))
        status_bar.columnconfigure(1, weight=1)

        # Sol: durum
        self.status_state_var = tk.StringVar(value="Hazır")
        ttk.Label(status_bar, textvariable=self.status_state_var,
                  width=22, anchor=tk.W, padding=(4, 2)).grid(row=0, column=0, sticky=tk.W)
        # Orta: detay (adım/yüzde)
        self.status_detail_var = tk.StringVar(value="")
        ttk.Label(status_bar, textvariable=self.status_detail_var,
                  anchor=tk.W, padding=(4, 2)).grid(row=0, column=1, sticky=(tk.W, tk.E))
        # Sağ: süre
        self.status_time_var = tk.StringVar(value="")
        ttk.Label(status_bar, textvariable=self.status_time_var,
                  width=14, anchor=tk.E, padding=(4, 2)).grid(row=0, column=2, sticky=tk.E)

        # Geriye uyumluluk: eski self.status_var kullanan kodlar var
        # → status_detail_var'a alias yap
        self.status_var = self.status_detail_var

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)  # PanedWindow büyür
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)  # toolbar üstte, text aşağı genişler

    def on_closing(self):
        """Pencere kapatma olayını handle et"""
        if self._is_closing:
            return
        
        self._is_closing = True
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
    
    def select_input_file(self):
        """Giriş dosyası seç"""
        filename = filedialog.askopenfilename(
            title="Excel Dosyası Seç",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if filename:
            self.input_file_var.set(filename)
    
    def select_output_dir(self):
        """Çıktı dizini seç"""
        dirname = filedialog.askdirectory(title="Çıktı Dizini Seç")
        if dirname:
            self.output_dir_var.set(dirname)
    
    def log_message(self, message: str):
        """
        Log mesajı ekle.

        Mesajı hem Text widget'a doğrudan yazar (geriye uyumluluk için
        mevcut çağrı yerleri çalışmaya devam etsin), hem de mesaj içeriğine
        göre uygun renk tag'i uygular.
        """
        tag = self._tag_for_message(message)
        self.log_text.insert(tk.END, f"{message}\n", (tag,))
        self.log_text.see(tk.END)
        self.root.update()

    @staticmethod
    def _tag_for_message(message: str) -> str:
        """Mesaj içeriğine göre renk tag'i tahmin et"""
        m = message.lower()
        if '❌' in message or 'hata' in m or 'başarısız' in m:
            return 'error'
        if '⚠' in message or 'uyarı' in m or 'çakışma' in m:
            return 'warning'
        if '✅' in message or 'tamamlandı' in m or 'başarılı' in m:
            return 'success'
        return 'info'

    def _set_log_filter(self, mode: str) -> None:
        """
        Log filtresi: 'all' → hepsi, 'warnings' → sadece warning+error,
        'errors' → sadece error. Text tag elide ile gizler.
        """
        # Önce her şeyi göster
        for tag in ('info', 'warning', 'error', 'success', 'debug'):
            self.log_text.tag_configure(tag, elide=False)

        if mode == 'warnings':
            for tag in ('info', 'debug', 'success'):
                self.log_text.tag_configure(tag, elide=True)
        elif mode == 'errors':
            for tag in ('info', 'warning', 'debug', 'success'):
                self.log_text.tag_configure(tag, elide=True)
        # 'all' için zaten hepsi açık

    def _clear_log(self) -> None:
        """Log alanını temizle"""
        self.log_text.delete(1.0, tk.END)

    def _save_log(self) -> None:
        """Log içeriğini .txt dosyasına kaydet"""
        filename = filedialog.asksaveasfilename(
            title="Log Kaydet",
            defaultextension=".txt",
            filetypes=[("Text dosyası", "*.txt"), ("Tüm dosyalar", "*.*")],
            initialfile=f"mythos-log-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt",
        )
        if not filename:
            return
        try:
            content = self.log_text.get(1.0, tk.END)
            Path(filename).write_text(content, encoding='utf-8')
            messagebox.showinfo("Kaydedildi", f"Log kaydedildi:\n{filename}")
        except Exception as exc:
            messagebox.showerror("Hata", f"Log kaydedilemedi: {exc}")

    def _show_summary(self, title: str, lines: List[str]) -> None:
        """
        Sonuç panelini güncelle.

        title: panel başlığı (örn. "Part 2 • 14:32:15")
        lines: satır satır metin (emoji + içerik)
        """
        now = datetime.now().strftime('%H:%M:%S')
        self.summary_frame.configure(text=f"Sonuç — {title} • {now}")
        self.summary_label.configure(text="\n".join(lines))
        self._last_summary = title

    def _begin_op(self, op_name: str = "İşlem") -> None:
        """İşlem başlangıcı — süre ölçümü + status bar set"""
        self._op_start_time = time.monotonic()
        self.status_state_var.set("İşlem devam ediyor")
        self.status_detail_var.set(f"{op_name} başlıyor…")
        self.status_time_var.set("")
        self._set_action_buttons_enabled(False)
        self.root.update_idletasks()

    def _finish_op(self, ok: bool = True) -> None:
        """İşlem sonu — status bar set + butonları aç"""
        elapsed = self._elapsed_op()
        if ok:
            self.status_state_var.set("Tamamlandı")
        else:
            self.status_state_var.set("Hata")
        self.status_time_var.set(f"{elapsed:.1f}s")
        self._set_action_buttons_enabled(True)
        self.root.update_idletasks()

    def _elapsed_op(self) -> float:
        """İşlem süresi (saniye, başlangıç yoksa 0)"""
        if self._op_start_time is None:
            return 0.0
        return time.monotonic() - self._op_start_time

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        """
        Tüm "işlem başlatan" butonların state'ini değiştir.
        İşlem sırasında çift tıklama / paralel işlem tuzağını engellemek için.
        """
        state = 'normal' if enabled else 'disabled'
        for btn in self._action_buttons:
            try:
                btn.configure(state=state)
            except tk.TclError:
                pass

    def _collect_action_buttons(self) -> None:
        """
        Tüm aksiyon (işlem başlatan) butonlarını rekürsif olarak topla.
        Mevcut UI kodunu değiştirmeden text-bazlı whitelist ile çalışır.
        """
        action_texts = {
            "Doğrula",            # Part 1
            "Oluştur",            # Part 1
            "Kontrol Et",         # Part 2 / Part 3
            "Görselleri Eşleştir",  # Part 2
            "Kısalt",             # Part 3
        }

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button):
                    text = child.cget('text').strip()
                    if text in action_texts:
                        self._action_buttons.append(child)
                walk(child)

        walk(self.root)

    @staticmethod
    def _format_user_error(exc: BaseException) -> str:
        """
        Exception'ı kullanıcıya gösterilecek anlaşılır mesaja çevir.
        Tam stack trace zaten log dosyasına yazılıyor (FileHandler);
        kullanıcı ekranda sade bir özet görsün.
        """
        if isinstance(exc, FileNotFoundError):
            return f"Dosya bulunamadı: {exc.filename or exc}"
        if isinstance(exc, PermissionError):
            return (
                f"Dosya başka programda açık olabilir, kapatıp tekrar dene: "
                f"{exc.filename or exc}"
            )
        if isinstance(exc, ValueError):
            return f"Excel formatı/verisi uygun değil: {exc}"
        msg = str(exc) or exc.__class__.__name__
        # Çok uzunsa kısalt
        if len(msg) > 200:
            msg = msg[:200] + "…"
        return f"Beklenmedik hata: {msg}\n(Tam detay için logs/ klasörüne bak)"
    
    def update_progress(self, current: int, total: int, percentage: float):
        """Progress bar güncelle"""
        self.progress_var.set(percentage)
        self.status_var.set(f"İşlem devam ediyor... {current}/{total} ({percentage:.1f}%)")
        self.root.update()
    
    def validate_only(self):
        """Sadece doğrulama yap"""
        if not self.input_file_var.get():
            messagebox.showerror("Hata", "Lütfen giriş dosyası seçin")
            return
        
        self.log_text.delete(1.0, tk.END)
        self.log_message("Doğrulama başlıyor...")
        
        try:
            input_path = Path(self.input_file_var.get())
            output_dir = Path(self.output_dir_var.get())
            
            # Progress tracker
            progress = ProgressTracker(3, self.update_progress)
            
            data = read_checklist_excel(input_path)
            header_processor = normalize_headers(list(data.columns))
            validation_result = validate_checklist(data, header_processor)
            dry_run_report = create_dry_run_report(validation_result)

            result = {
                'dry_run_report': dry_run_report,
                'errors': validation_result.errors,
                'warnings': validation_result.warnings
            }
            
            progress.update()
            
            if result.get('dry_run_report'):
                report = result['dry_run_report']
                summary = report['summary']
                
                self.log_message(f"📊 Toplam Satır: {summary['total_rows']}")
                self.log_message(f"❌ Hata: {summary['total_errors']} (Engelleyici: {summary['blocking_errors']})")
                self.log_message(f"⚠️  Uyarı: {summary['total_warnings']}")
                
                # DETAYLAR EKLENDI:
                if result['errors']:
                    self.log_message("\n=== HATALAR ===")
                    for i, error in enumerate(result['errors'][:5], 1):
                        self.log_message(f"{i}. Satır {error.get('row', '?')}, Sütun '{error.get('column', '?')}':")
                        self.log_message(f"   {error.get('message', '')}")
                    
                    if len(result['errors']) > 5:
                        self.log_message(f"... ve {len(result['errors'])-5} hata daha")
                
                if result['warnings']:
                    self.log_message("\n=== UYARILAR ===")
                    for i, warning in enumerate(result['warnings'][:3], 1):
                        self.log_message(f"{i}. Satır {warning.get('row', '?')}: {warning.get('message', '')}")
                    
                    if len(result['warnings']) > 3:
                        self.log_message(f"... ve {len(result['warnings'])-3} uyarı daha")
                
                self.log_message(f"\n💡 Öneri: {report['recommendation']}")
                
                if summary['blocking_errors'] == 0:
                    self.log_message("✅ Doğrulama BAŞARILI!")
                    messagebox.showinfo("Başarılı", "Doğrulama başarılı! İşleme devam edebilirsiniz.")
                else:
                    self.log_message("❌ Doğrulama BAŞARISIZ!")
                    messagebox.showwarning("Uyarı", "Engelleyici hatalar mevcut! Lütfen Excel dosyasını düzeltin.")
            
            progress.update(3)  # Tamamla
            self.status_var.set("Doğrulama tamamlandı")
            
        except Exception as e:
            self.log_message(f"❌ Doğrulama hatası: {str(e)}")
            messagebox.showerror("Hata", f"Doğrulama hatası: {str(e)}")
            self.status_var.set("Hata")
        
        finally:
            # Progress bar'ı sıfırla
            self.progress_var.set(0)
            
    
    def generate(self):
        """Ana işlemi başlat"""
        if not self.input_file_var.get():
            messagebox.showerror("Hata", "Lütfen giriş dosyası seçin")
            return
        
        self.log_text.delete(1.0, tk.END)
        self.log_message("Part 1: Checklist İşleme başlıyor...")
        self._begin_op("Part 1 — Checklist İşleme")

        try:
            input_path = Path(self.input_file_var.get())
            output_dir = Path(self.output_dir_var.get())
            
            # Progress tracker
            progress = ProgressTracker(5, self.update_progress)
            
            self.log_message(f"📁 Giriş: {input_path.name}")
            self.log_message(f"📁 Çıktı: {output_dir}")
            progress.update()
            
            # Hata durdurma seçeneği
            # Hata durdurma seçeneği
            stop_on_error = self.dry_run_var.get()

            # Eğer hata durdurma açıksa önce validation yap
            if stop_on_error:
                # Önce sadece validation
                data = read_checklist_excel(input_path)
                header_processor = normalize_headers(list(data.columns))
                validation_result = validate_checklist(data, header_processor)
                
                if not validation_result.is_valid:
                    self.log_message("\n" + "="*50)
                    self.log_message("İŞLEM DURDURULDU - HATALAR TESPİT EDİLDİ")
                    self.log_message("="*50)
                    
                    for i, error in enumerate(validation_result.errors[:3], 1):
                        self.log_message(f"{i}. Satır {error.get('row', '?')}: {error.get('message', '')}")
                    
                    if len(validation_result.errors) > 3:
                        self.log_message(f"... ve {len(validation_result.errors)-3} hata daha")
                    
                    self.log_message("ÇÖZÜM: Lütfen Excel dosyanızı düzeltin ve tekrar deneyin")
                    messagebox.showerror("İşlem Durduruldu", 
                        f"{len(validation_result.errors)} hata tespit edildi.\nDetaylar için log'u kontrol edin.")
                    self.status_var.set("Hatalar nedeniyle durduruldu")
                    return

            result = process_checklist(
                input_path, 
                output_dir,
                per_series=self.per_series_var.get(),
                dry_run=False,
                locale_pref='tr' if self.turkish_sort_var.get() else 'ascii'
            )

            progress.update(2)

            if result['success']:
                self.log_message("✅ İşlem BAŞARILI!")
                self.log_message(f"📄 {len(result['files'])} dosya oluşturuldu:")
                
                for file_path in result['files']:
                    self.log_message(f"  📄 {Path(file_path).name}")
                
            if result['summary']:
                summary = result['summary']
                
                # İmzalı ve normal kart sayılarını hesapla
                signed_count = 0
                normal_count = 0
                base_count = 0
                
                if 'variants' in summary:
                    for variant_data in summary['variants'].values():
                        signed_count += variant_data.get('signed', 0)
                        normal_count += variant_data.get('normal', 0)
                
                total_cards = summary.get('total_cards', 0)
                total_players = summary.get('total_players', 0)
                
                base_count = total_cards - normal_count - signed_count

                self.log_message(f"📊 {total_cards} kart, {total_players} oyuncu")
                self.log_message(f"📝 {normal_count} normal, ✍️ {signed_count} imzalı, 🏆 {base_count} base kart")

                # Kalıcı özet paneli güncelle
                elapsed = self._elapsed_op()
                error_count = len(result.get('errors', []))
                warn_count = len(result.get('warnings', []))
                summary_lines = [
                    f"📄  {len(result['files'])} dosya oluşturuldu",
                    f"📊  {total_cards} kart   •   {total_players} oyuncu",
                    f"📝  {normal_count} normal   •   ✍️ {signed_count} imzalı   •   🏆 {base_count} base",
                    f"⏱  {elapsed:.1f} saniye   •   {error_count} hata   •   {warn_count} uyarı",
                ]
                self._show_summary("Part 1 — Checklist İşleme", summary_lines)
                            # Hata ve uyarıları da göster
                if result.get('errors'):
                    self.log_message(f"\n⚠️ İşlem {len(result['errors'])} hata ile tamamlandı:")
                    for i, error in enumerate(result['errors'][:3], 1):
                        self.log_message(f"  {i}. Satır {error.get('row', '?')}: {error.get('message', '')}")
                    if len(result['errors']) > 3:
                        self.log_message(f"  ... ve {len(result['errors'])-3} hata daha")
                
                if result.get('warnings'):
                    self.log_message(f"\n📋 {len(result['warnings'])} uyarı:")
                    for i, warning in enumerate(result['warnings'][:2], 1):
                        self.log_message(f"  {i}. Satır {warning.get('row', '?')}: {warning.get('message', '')}")
                    if len(result['warnings']) > 2:
                        self.log_message(f"  ... ve {len(result['warnings'])-2} uyarı daha")
                
                progress.update(5)  # Tamamla
                self.status_var.set("İşlem başarılı!")
                
                # Başarı mesajı ve dosya açma seçeneği
                if messagebox.askyesno("Başarılı", 
                    f"İşlem başarıyla tamamlandı!\n{len(result['files'])} dosya oluşturuldu.\n\nÇıktı klasörünü açmak ister misiniz?"):
                    import os
                    import platform
                    
                    # Klasörü aç
                    if platform.system() == "Windows":
                        os.startfile(output_dir)
                    elif platform.system() == "Darwin":  # macOS
                        os.system(f"open '{output_dir}'")
                    else:  # Linux
                        os.system(f"xdg-open '{output_dir}'")
            
            else:
                self.log_message("❌ İşlem BAŞARISIZ!")
                
                if result['errors']:
                    self.log_message("Hatalar:")
                    for error in result['errors'][:5]:
                        self.log_message(f"  ❌ {error.get('message', '')}")
                
                self.status_var.set("İşlem başarısız!")
                messagebox.showerror("Hata", "İşlem başarısız! Detaylar için log'u kontrol edin.")
        
        except Exception as e:
            user_msg = self._format_user_error(e)
            self.logger.error(f"Part 1 hatası: {e}", exc_info=True)
            self.log_message(f"❌ {user_msg}")
            messagebox.showerror("Hata", user_msg)
            self._finish_op(ok=False)

        finally:
            self.progress_var.set(0)
            if self.status_state_var.get() == "İşlem devam ediyor":
                # success path _finish_op çağırmadıysa (örn. dry-run validation
                # durması) yine de butonları aç ve duruma uygun status set
                self._finish_op(ok=True)
        
    def select_image_dir(self):
        """Görsel klasörü seçici"""
        dirname = filedialog.askdirectory(title="Görsel Klasörünü Seç")
        if dirname:
            self.image_dir_var.set(dirname)

    def select_part2_excel(self):
        """Part 2 için Excel seç"""
        filename = filedialog.askopenfilename(
            title="Part 1 Excel Çıktısını Seç",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if filename:
            self.part2_excel_var.set(filename)

    def validate_images_preview(self):
        """Part 2: Görsel eşleştirme önizleme - Sadece kontrol, eşleştirme yapma"""
        excel_file = self.part2_excel_var.get()
        if not excel_file:
            messagebox.showerror("Hata", "Lütfen Excel dosyası seçin")
            return

        if not self.image_dir_var.get():
            messagebox.showerror("Hata", "Lütfen görsel klasörü seçin")
            return

        self.log_text.delete(1.0, tk.END)
        self.log_message("Part 2: Görsel Eşleştirme Kontrolü...")

        # Tarih ekleme durumunu logla
        add_date = self.add_date_var.get()
        if add_date:
            self.log_message(f"📅 Tarih eklenecek: {self.date_var.get()}")
        else:
            self.log_message("📅 Tarih ekleme KAPALI")

        try:
            # ÖN DOĞRULAMA - Preview/İstatistik
            self.log_message("\n" + "="*50)
            self.log_message("ÖN DOĞRULAMA - Eşleştirme İstatistikleri")
            self.log_message("="*50)

            preview = validate_matching_preview(
                excel_file,
                self.image_dir_var.get(),
                self.date_var.get() if add_date else None,
                strict_mode=False  # Açıklamalı dosya isimleri için kapalı
            )

            # Preview sonuçlarını logla
            self.log_message(f"📊 Toplam Kart: {preview['total_cards']}")
            self.log_message(f"🔍 Unique Kombinasyon: {preview['unique_combinations']}")
            self.log_message(f"🖼️  Toplam Görsel: {preview['total_images']}")
            self.log_message(f"⚡ Performans Kazancı: {preview['performance_gain']} hızlı")
            self.log_message(f"🔒 Strict Mode: {'AÇIK (fazla kelime reddedilir)' if preview['strict_mode'] else 'KAPALI'}")

            self.log_message("\nTAHMİNİ EŞLEŞMEsı:")
            est = preview['estimated_matches']
            self.log_message(f"  ✅ Bulunacak: {est['found']} (%{est['found_percent']:.1f})")
            self.log_message(f"  ❌ Eksik: {est['missing']} (%{est['missing_percent']:.1f})")
            self.log_message(f"  ⚠️  Çakışma: {est['conflict']} (%{est['conflict_percent']:.1f})")

            # Detaylı sonuçları göster (ilk 5)
            if preview['detailed_results']:
                self.log_message("\nDetaylı Önizleme (ilk 5 kombinasyon):")
                for i, detail in enumerate(preview['detailed_results'][:5], 1):
                    status_icon = "✅" if detail['status'] == 'found' else "❌" if detail['status'] == 'missing' else "⚠️"
                    self.log_message(f"  {status_icon} {detail['combination']} → {detail['card_count']} kart")
                    if detail['matched_file']:
                        self.log_message(f"     Dosya: {detail['matched_file']}")

            self.log_message("\n" + "="*50)

            # Sonuç mesajı
            if est['found_percent'] >= 80:
                self.log_message("✅ Kontrol BAŞARILI! Eşleştirme yapabilirsiniz.")
                messagebox.showinfo(
                    "Kontrol Başarılı",
                    f"Eşleştirme kontrolü tamamlandı!\n\n"
                    f"✅ Bulunacak: {est['found']} kart (%{est['found_percent']:.1f})\n"
                    f"❌ Eksik: {est['missing']} kart (%{est['missing_percent']:.1f})\n\n"
                    f"'Görselleri Eşleştir' butonuna tıklayarak devam edebilirsiniz."
                )
            elif est['missing_percent'] > 50:
                self.log_message("⚠️  UYARI: Yarıdan fazla kart eşleşmeyecek!")
                messagebox.showwarning(
                    "Dikkat - Çok Eksik",
                    f"UYARI: Kartların %{est['missing_percent']:.1f}'si eşleşmeyecek!\n\n"
                    f"✅ Bulunacak: {est['found']} kart\n"
                    f"❌ Eksik: {est['missing']} kart\n\n"
                    f"Lütfen görsel dosyalarını kontrol edin."
                )
            else:
                self.log_message("💡 Öneri: Eşleştirme yapabilirsiniz.")
                messagebox.showinfo(
                    "Kontrol Tamamlandı",
                    f"Eşleştirme kontrolü tamamlandı!\n\n"
                    f"✅ Bulunacak: {est['found']} kart (%{est['found_percent']:.1f})\n"
                    f"❌ Eksik: {est['missing']} kart (%{est['missing_percent']:.1f})"
                )

        except Exception as e:
            self.log_message(f"❌ Kontrol hatası: {str(e)}")
            messagebox.showerror("Hata", f"Kontrol hatası: {str(e)}")     

    def match_images(self):
            """Görsel eşleştirme işlemi - Direkt eşleştir (ön doğrulama yok)"""
            # Excel kontrolü
            excel_file = self.part2_excel_var.get()
            if not excel_file:
                messagebox.showerror("Hata", "Lütfen Excel dosyası seçin")
                return

            if not self.image_dir_var.get():
                messagebox.showerror("Hata", "Lütfen görsel klasörü seçin")
                return

            self.log_text.delete(1.0, tk.END)
            self.log_message("Part 2: Görsel Eşleştirme başlıyor...")
            self._begin_op("Part 2 — Görsel Eşleştirme")

            # Tarih ekleme durumunu logla
            add_date = self.add_date_var.get()
            if add_date:
                self.log_message(f"📅 Tarih eklenecek: {self.date_var.get()}")
            else:
                self.log_message("📅 Tarih ekleme KAPALI")

            self.log_message(f"🔒 Strict Mode: KAPALI (fazla kelime tolere edilir)")
            self.log_message("\n🚀 Eşleştirme başlıyor...\n")

            try:
                result = process_image_mapping(
                    excel_file,
                    self.image_dir_var.get(),
                    self.date_var.get() if add_date else None,
                    add_date_prefix=add_date,
                    strict_mode=False  # Açıklamalı dosya isimleri için kapalı
                )

                self.log_message(f"✅ TAMAMLANDI!")
                self.log_message(f"✅ Bulunan: {result['found_count']}/{result['total_cards']}")
                self.log_message(f"❌ Eksik: {result['missing_count']}")
                self.log_message(f"⚠️ Çakışma: {result['conflict_count']}")
                self.log_message(f"📈 Başarı Oranı: {result['success_rate']:.1f}%")

                if result['warnings']:
                    self.log_message(f"\n--- UYARILAR ({len(result['warnings'])}) ---")
                    for w in result['warnings'][:5]:
                        self.log_message(f"  Satır {w['row']}: {w['message']}")
                    if len(result['warnings']) > 5:
                        self.log_message(f"  ... ve {len(result['warnings'])-5} uyarı daha")

                # Kalıcı özet paneli güncelle
                elapsed = self._elapsed_op()
                warn_count = len(result.get('warnings', []))
                summary_lines = [
                    f"✅  {result['found_count']} / {result['total_cards']} kart eşleşti  ({result['success_rate']:.1f}%)",
                    f"❌  {result['missing_count']} kart eksik (görseli yok)",
                    f"⚠️  {result['conflict_count']} çakışma (manuel kontrol gerek)",
                    f"⏱  {elapsed:.1f} saniye   •   {warn_count} uyarı",
                ]
                self._show_summary("Part 2 — Görsel Eşleştirme", summary_lines)

                # Sonuç mesajı oluştur
                msg = (
                    f"Eşleştirme tamamlandı!\n\n"
                    f"✅ Bulunan: {result['found_count']}/{result['total_cards']}\n"
                    f"❌ Eksik: {result['missing_count']}\n"
                    f"📈 Başarı: {result['success_rate']:.1f}%\n"
                )
                if result['conflict_count'] > 0:
                    msg += f"\n⚠️ {result['conflict_count']} çakışma var!"

                msg += "\n\nExcel dosyasının bulunduğu klasörü açmak ister misiniz?"

                if messagebox.askyesno("Tamamlandı", msg):
                    import os
                    import platform
                    # Excel dosyasının bulunduğu klasörü aç
                    excel_dir = os.path.dirname(excel_file)
                    if platform.system() == "Windows":
                        os.startfile(excel_dir)
                    elif platform.system() == "Darwin":  # macOS
                        os.system(f"open '{excel_dir}'")
                    else:  # Linux
                        os.system(f"xdg-open '{excel_dir}'")

            except Exception as e:
                user_msg = self._format_user_error(e)
                self.logger.error(f"Part 2 hatası: {e}", exc_info=True)
                self.log_message(f"❌ {user_msg}")
                messagebox.showerror("Hata", user_msg)
                self._finish_op(ok=False)
            else:
                self._finish_op(ok=True)

    # === PART 3 METHODS ===

    def select_part3_excel(self):
        """Part 3 için Excel seç"""
        filename = filedialog.askopenfilename(
            title="Excel Dosyası Seç",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if filename:
            self.part3_excel_var.set(filename)

    def select_part3_image_dir(self):
        """Part 3 için görsel klasörü seç"""
        dirname = filedialog.askdirectory(title="Görsel Klasörünü Seç")
        if dirname:
            self.part3_image_dir_var.set(dirname)

    def validate_shortening(self):
        """Part 3: Kısaltma ön doğrulaması"""
        excel_file = self.part3_excel_var.get()
        if not excel_file:
            messagebox.showerror("Hata", "Lütfen Excel dosyası seçin")
            return

        if not self.part3_image_dir_var.get():
            messagebox.showerror("Hata", "Lütfen görsel klasörü seçin")
            return

        self.log_text.delete(1.0, tk.END)
        self.log_message("Bölüm 3: Kısaltma Kontrolü...")
        self.log_message(f"Max uzunluk: {self.max_length_var.get()} karakter")

        try:
            preview = validate_shortening_preview(
                excel_file,
                self.part3_image_dir_var.get(),
                self.max_length_var.get()
            )

            self.log_message(f"\n📊 Toplam Dosya: {preview['total_files']}")
            self.log_message(f"✂️  Kısaltılacak: {preview['needs_shortening']}")
            self.log_message(f"✅ Zaten Uygun: {preview['already_ok']}")

            if preview['examples']:
                self.log_message("\nÖrnekler:")
                for ex in preview['examples']:
                    self.log_message(f"  {ex['original']}")
                    self.log_message(f"  → {ex['new']} ({ex['saved_chars']} karakter kısaldı)")

            if preview['needs_shortening'] == 0:
                messagebox.showinfo("Kontrol Tamamlandı", "Tüm dosyalar zaten uygun uzunlukta!")
            else:
                messagebox.showinfo(
                    "Kontrol Tamamlandı",
                    f"{preview['needs_shortening']} dosya kısaltılacak.\n"
                    f"'Kısalt' butonuna tıklayarak devam edebilirsiniz."
                )

        except Exception as e:
            self.log_message(f"❌ Kontrol hatası: {str(e)}")
            messagebox.showerror("Hata", f"Kontrol hatası: {str(e)}")

    def shorten_filenames(self):
        """Part 3: Dosya adlarını kısalt"""
        excel_file = self.part3_excel_var.get()
        if not excel_file:
            messagebox.showerror("Hata", "Lütfen Excel dosyası seçin")
            return

        if not self.part3_image_dir_var.get():
            messagebox.showerror("Hata", "Lütfen görsel klasörü seçin")
            return

        self.log_text.delete(1.0, tk.END)
        self.log_message("Bölüm 3: Dosya Adı Kısaltma başlıyor...")
        self.log_message(f"Max uzunluk: {self.max_length_var.get()} karakter")
        self._begin_op("Part 3 — Dosya Adı Kısaltma")

        try:
            result = process_shortening(
                excel_file,
                self.part3_image_dir_var.get(),
                self.max_length_var.get()
            )

            self.log_message(f"\n✅ TAMAMLANDI!")
            self.log_message(f"📊 Toplam Dosya: {result['total_files']}")
            self.log_message(f"✂️  Kısaltılan: {result['shortened_count']}")
            self.log_message(f"⏭️  Atlanan (zaten uygun): {result['skipped_count']}")

            if result['error_count'] > 0:
                self.log_message(f"❌ Hata: {result['error_count']}")

            if result['backup_dir']:
                self.log_message(f"\n💾 Yedek: {result['backup_dir']}")

            # Kalıcı özet paneli güncelle
            elapsed = self._elapsed_op()
            summary_lines = [
                f"📊  {result['total_files']} dosya tarandı",
                f"✂️  {result['shortened_count']} kısaltıldı   •   ⏭️ {result['skipped_count']} zaten uygun",
                f"❌  {result.get('error_count', 0)} hata",
                f"⏱  {elapsed:.1f} saniye",
            ]
            self._show_summary("Part 3 — Dosya Adı Kısaltma", summary_lines)

            # Anlaşılır sonuç mesajı
            msg = result.get('message', f"Kısaltılan: {result['shortened_count']} dosya")
            msg += "\n\nExcel dosyasının bulunduğu klasörü açmak ister misiniz?"

            if messagebox.askyesno("Tamamlandı", msg):
                import os
                import platform
                excel_dir = os.path.dirname(excel_file)
                if platform.system() == "Windows":
                    os.startfile(excel_dir)
                elif platform.system() == "Darwin":
                    os.system(f"open '{excel_dir}'")
                else:
                    os.system(f"xdg-open '{excel_dir}'")

        except Exception as e:
            user_msg = self._format_user_error(e)
            self.logger.error(f"Part 3 hatası: {e}", exc_info=True)
            self.log_message(f"❌ {user_msg}")
            messagebox.showerror("Hata", user_msg)
            self._finish_op(ok=False)
        else:
            self._finish_op(ok=True)

    def _find_latest_excel(self):
        """En son Excel dosyasını bul"""
        try:
            output_dir = Path(self.output_dir_var.get())
            excel_files = list(output_dir.rglob("*_Excel.xlsx"))
            if excel_files:
                return max(excel_files, key=lambda f: f.stat().st_mtime)
            return None
        except:
            return None
            
    def run(self):
        """GUI'yi başlat"""
        self.root.mainloop()


def launch_gui():
    """GUI'yi başlat - tek seferlik"""
    import atexit
    import os
    
    # Program kapanırken kesin çıkış
    def force_exit():
        os._exit(0)
    
    atexit.register(force_exit)
    
    app = MythosGUI()
    
    # Root window'a özel kapanma davranışı
    def quit_app():
        app.root.quit()
        app.root.destroy()
        os._exit(0)
    
    app.root.protocol("WM_DELETE_WINDOW", quit_app)
    
    try:
        app.root.mainloop()
    finally:
        os._exit(0)

def main():
    """Ana entry point - basitleştirilmiş"""
    if len(sys.argv) > 1:
        cli()
    else:
        launch_gui()

if __name__ == "__main__":
    main()

# Additional utility functions
def quick_process(input_file: str, 
                 output_dir: Optional[str] = None,
                 per_series: bool = True) -> bool:
    """Hızlı işleme (API kullanımı için)"""
    
    try:
        setup_logging()
        
        input_path = Path(input_file)
        if not input_path.exists():
            logger.error(f"Dosya bulunamadı: {input_path}")
            return False
        
        output_path = Path(output_dir) if output_dir else get_outputs_dir()
        
        result = process_checklist(
            input_path, 
            output_path,
            per_series=per_series,
            dry_run=False,  # Hızlı işlem için dry-run yok
            locale_pref='tr'
        )
        
        if result['success']:
            logger.info(f"Hızlı işlem başarılı: {len(result['files'])} dosya")
            return True
        else:
            logger.error("Hızlı işlem başarısız")
            return False
    
    except Exception as e:
        logger.error(f"Hızlı işlem hatası: {str(e)}")
        return False


def batch_process(input_files: List[str],
                 output_base_dir: Optional[str] = None) -> Dict[str, bool]:
    """Toplu işleme"""
    
    results = {}
    
    try:
        setup_logging()
        output_base = Path(output_base_dir) if output_base_dir else get_outputs_dir()
        
        for input_file in input_files:
            input_path = Path(input_file)
            file_output_dir = output_base / input_path.stem
            
            logger.info(f"Toplu işlem: {input_path.name}")
            
            success = quick_process(str(input_path), str(file_output_dir), per_series=True)
            results[input_file] = success
        
        successful_count = sum(1 for success in results.values() if success)
        logger.info(f"Toplu işlem tamamlandı: {successful_count}/{len(input_files)} başarılı")
        
    except Exception as e:
        logger.error(f"Toplu işlem hatası: {str(e)}")
    
    return results


def create_sample_config() -> Dict[str, Any]:
    """Örnek config oluştur"""
    return {
        'per_series_export': True,
        'dry_run_enabled': True,
        'locale_preference': 'tr',
        'turkish_sorting': True,
        'auto_backup': False,
        'log_level': 'INFO',
        'output_format': 'xlsx'
    }


def validate_input_file(file_path: str) -> Tuple[bool, List[str]]:
    """Giriş dosyasını doğrula"""
    
    issues = []
    
    try:
        path = Path(file_path)
        
        if not path.exists():
            issues.append("Dosya mevcut değil")
            return False, issues
        
        if not path.suffix.lower() in ['.xlsx', '.xls']:
            issues.append("Dosya Excel formatında değil")
        
        # Dosya boyutu kontrolü (100MB limit)
        if path.stat().st_size > 100 * 1024 * 1024:
            issues.append("Dosya çok büyük (>100MB)")
        
        # Temel Excel okuma testi
        try:
            data = read_checklist_excel(path)
            if len(data) == 0:
                issues.append("Excel dosyası boş")
            elif len(data.columns) < 3:
                issues.append("Çok az sütun var (minimum 3 gerekli)")
        except Exception as e:
            issues.append(f"Excel okuma hatası: {str(e)}")
        
        return len(issues) == 0, issues
    
    except Exception as e:
        issues.append(f"Dosya kontrolü hatası: {str(e)}")
        return False, issues


# Command-line shortcuts
def cli_quick():
    """Hızlı CLI komutu"""
    
    @click.command()
    @click.argument('input_file', type=click.Path(exists=True))
    @click.option('--output', '-o', default=None, help='Çıktı dizini')
    def quick(input_file, output):
        """Hızlı işleme (dry-run olmadan)"""
        
        click.echo(f"Hızlı işleme: {input_file}")
        
        success = quick_process(input_file, output, per_series=True)
        
        if success:
            click.echo("✅ İşlem başarılı!")
        else:
            click.echo("❌ İşlem başarısız!")
            sys.exit(1)
    
    return quick


# Export işlemleri için kullanılabilecek shortcuts
if __name__ == "__main__":
    # Direct execution
    main()


# Version info
def print_version_info():
    """Versiyon bilgilerini yazdır"""
    print(f"{PROGRAM_NAME} v{PROGRAM_VERSION}")
    print("Python Libraries:")
    
    try:
        import pandas as pd
        print(f"  - pandas: {pd.__version__}")
    except ImportError:
        print("  - pandas: ❌ Not installed")
    
    try:
        import openpyxl
        print(f"  - openpyxl: {openpyxl.__version__}")
    except ImportError:
        print("  - openpyxl: ❌ Not installed")
    
    try:
        import xlsxwriter
        print(f"  - xlsxwriter: {xlsxwriter.__version__}")
    except ImportError:
        print("  - xlsxwriter: ❌ Not installed")
    
    try:
        import icu #type: ignore   CALISMIYOR
        version = getattr(icu, 'ICU_VERSION', 'Available')
        print(f"  - PyICU: {version} ✅")
    except ImportError:
        print("  - PyICU: ❌ Not available (fallback kullanılacak)")
    except Exception as e:
        print(f"  - PyICU: ⚠️ Error - {str(e)}")
    
    try:
        import tkinter
        print(f"  - tkinter: ✅ Available")
    except ImportError:
        print("  - tkinter: ❌ Not available (GUI çalışmayacak)")


# Module test
def run_self_test():
    """Kendi kendine test"""
    
    print("=== MythosCards Exporter Self Test ===")
    print_version_info()
    print()
    
    # Import testleri
    try:
        from . import utils, io_ops, headers, validate, expand, sorters, export
        print("✅ Tüm modüller başarıyla import edildi")
    except ImportError as e:
        print(f"❌ Import hatası: {e}")
        return False
    
    # Logging test
    try:
        setup_logging()
        logger.info("Self test başlatıldı")
        print("✅ Logging sistemi çalışıyor")
    except Exception as e:
        print(f"❌ Logging hatası: {e}")
        return False
    
    # Directory test
    try:
        output_dir = get_outputs_dir()
        print(f"✅ Çıktı dizini: {output_dir}")
    except Exception as e:
        print(f"❌ Directory hatası: {e}")
        return False
    
    print("✅ Self test başarılı!")
    return True


if __name__ == "__main__":
    main()
