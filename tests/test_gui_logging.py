"""
TkinterTextHandler unit testleri.

Backend logger.info/warning/error mesajlarının Tkinter Text widget'a
düzgün bir şekilde, doğru tag'lerle, thread-safe olarak yazıldığını
doğrular.

Bu testler bir Tk root oluşturur ama widget görünmez (root.withdraw).
CI ortamında display olmadığı için bazı testler skip edilebilir
(tk.TclError yakalanıp pytest.skip).
"""

import logging
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# tkinter import (display olmadan da modül yüklenebilir)
import tkinter as tk


@pytest.fixture
def tk_root():
    """Test için Tk root + temizlik. Display yoksa skip."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk display yok: {exc}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def text_widget(tk_root):
    """Test için Text widget + renk tag'leri uygulanmış"""
    from main import configure_text_tags
    text = tk.Text(tk_root)
    configure_text_tags(text)
    return text


@pytest.fixture
def handler(text_widget):
    """TkinterTextHandler instance"""
    from main import TkinterTextHandler
    h = TkinterTextHandler(text_widget, drain_interval_ms=10)
    yield h
    h.close()


def _drain_and_wait(root, handler, max_wait_ms=500):
    """Queue'nun drain olmasını bekle (root.update + sleep ile)"""
    deadline = time.monotonic() + (max_wait_ms / 1000.0)
    while time.monotonic() < deadline:
        root.update()
        if handler._queue.empty():
            # Bir iki tur daha update ki text widget yazsın
            for _ in range(3):
                root.update()
                time.sleep(0.02)
            return
        time.sleep(0.02)


class TestTkinterTextHandlerBasics:
    """Temel emit + format + tag testleri"""

    def test_info_message_appears_in_widget(self, tk_root, text_widget, handler):
        logger = logging.getLogger("test.gui.info")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("Merhaba dünya")
        _drain_and_wait(tk_root, handler)

        content = text_widget.get("1.0", tk.END)
        assert "Merhaba dünya" in content

    def test_warning_gets_warning_tag(self, tk_root, text_widget, handler):
        logger = logging.getLogger("test.gui.warn")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.warning("Bir uyarı")
        _drain_and_wait(tk_root, handler)

        # İlk satırda hangi tag var?
        tags = text_widget.tag_names("1.0")
        assert "warning" in tags, f"Beklenen 'warning' tag, gelen: {tags}"

    def test_error_gets_error_tag(self, tk_root, text_widget, handler):
        logger = logging.getLogger("test.gui.err")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.error("Bir hata")
        _drain_and_wait(tk_root, handler)

        tags = text_widget.tag_names("1.0")
        assert "error" in tags

    def test_success_message_gets_success_tag(self, tk_root, text_widget, handler):
        logger = logging.getLogger("test.gui.success")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("✅ TAMAMLANDI")
        _drain_and_wait(tk_root, handler)

        tags = text_widget.tag_names("1.0")
        assert "success" in tags

    def test_format_includes_time_and_level(self, tk_root, text_widget, handler):
        logger = logging.getLogger("test.gui.fmt")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("test mesajı")
        _drain_and_wait(tk_root, handler)

        content = text_widget.get("1.0", tk.END)
        # Default format: HH:MM:SS LEVEL  message
        assert "INFO" in content
        assert "test mesajı" in content


class TestTkinterTextHandlerThreadSafety:
    """Farklı thread'lerden gelen mesajlar ana thread'de güvenli yazılır"""

    def test_messages_from_multiple_threads_arrive(self, tk_root, text_widget, handler):
        logger = logging.getLogger("test.gui.thread")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        def worker(n: int):
            for i in range(5):
                logger.info(f"thread-{n} msg-{i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Mesajların drain olmasını bekle
        _drain_and_wait(tk_root, handler, max_wait_ms=1000)

        content = text_widget.get("1.0", tk.END)
        # 3 thread × 5 mesaj = 15 satır beklenir
        for i in range(3):
            for j in range(5):
                assert f"thread-{i} msg-{j}" in content, (
                    f"thread-{i} msg-{j} bulunamadı. Content: {content[:500]}"
                )


class TestTkinterTextHandlerCleanup:
    """Handler kapatıldığında patlamamali, widget destroy sonrası sessiz olmalı"""

    def test_close_stops_emitting(self, tk_root, text_widget):
        from main import TkinterTextHandler
        h = TkinterTextHandler(text_widget)
        h.close()

        logger = logging.getLogger("test.gui.closed")
        logger.handlers = [h]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        # Close sonrası emit hata vermemeli
        logger.info("kapandıktan sonra")
        # widget bilgi almamış olmalı
        tk_root.update()
        content = text_widget.get("1.0", tk.END)
        assert "kapandıktan sonra" not in content

    def test_destroyed_widget_does_not_crash(self, tk_root):
        from main import TkinterTextHandler, configure_text_tags
        text = tk.Text(tk_root)
        configure_text_tags(text)
        h = TkinterTextHandler(text, drain_interval_ms=10)

        # Widget yok et
        text.destroy()

        logger = logging.getLogger("test.gui.destroyed")
        logger.handlers = [h]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        # Bu çağrı silent fail olmalı (handler self-closes)
        logger.info("destroyed widget'a")
        tk_root.update()
        time.sleep(0.05)
        tk_root.update()
        # Patlamadıysa OK
        h.close()
