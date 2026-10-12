import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
from PIL import Image, ImageTk
from .engine import ROOT, process, save_image
from .event_store import EventStore
from .event_ui import EventWindow
from .violations import play_alarm
from .settings import load_confidence


class App:
    def __init__(self, root, store=None, schedule_cleanup=True):
        self.root = root
        self.store = store or EventStore(ROOT / 'data')
        root.title('Baret Tespit • Görsel analiz')
        root.geometry('1100x850')
        root.minsize(850, 620)
        self.events = queue.Queue()
        self.preview = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.worker = None
        self.closing = False
        self.last_frame = None
        self.incident_window = None
        self.alarm_threads = []
        self.save_video = tk.BooleanVar(value=False)
        self.violation_text = tk.StringVar(value='Yeni ihlal bildirimi yok')
        self.maintenance_text = tk.StringVar(value='')
        self.warnings = {}
        self.source = tk.StringVar()
        self.kind = tk.StringVar(value='image')
        self.model = tk.StringVar(value=str(ROOT / 'models' / 'best.pt'))
        self.output = tk.StringVar(value=str(ROOT / 'results'))
        self.status = tk.StringVar(value='Fotoğraf, video veya kamera seçerek başlayın.')
        self.counts = tk.StringVar(value='Baret: 0   |   Baretsiz baş: 0   |   Kişi: 0   |   Kararsız: 0')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=7)
        outer = ttk.Frame(root, padding=18)
        outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer)
        header.pack(fill='x', pady=(0, 8))
        ttk.Label(header, text='BARET TESPİT', font=('Segoe UI', 22, 'bold')).pack(side='left')
        ttk.Button(header, text='Olay kayıtlarını incele', command=self.open_events).pack(side='right')
        ttk.Label(outer, text='Kaynağı seçin, tespiti başlatın ve ihlalleri inceleyin.', font=('Segoe UI', 11)).pack(anchor='w', pady=(0, 12))
        db_text = 'MS SQL Server' if self.store.backend == 'sqlserver' else 'Yerel SQLite'
        self.alert_label = ttk.Label(outer, textvariable=self.violation_text, foreground='#b00020', font=('Segoe UI', 15, 'bold'))
        self.alert_label.pack(anchor='w', pady=5)
        source_panel = ttk.LabelFrame(outer, text='Görüntü kaynağı', padding=10)
        source_panel.pack(fill='x', pady=(4, 8))
        controls = ttk.Frame(source_panel)
        controls.pack(fill='x')
        for text, kind in [('Fotoğraf seç', 'image'), ('Video seç', 'video')]:
            ttk.Button(controls, text=text, command=lambda k=kind: self.choose(k)).pack(side='left', padx=(0, 8))
        ttk.Button(controls, text='Kamerayı seç', command=self.camera).pack(side='left')
        self.camera_id = tk.StringVar(value='0')
        ttk.Label(controls, text='Kamera no:').pack(side='left', padx=(12, 0))
        ttk.Spinbox(controls, from_=0, to=9, width=3, textvariable=self.camera_id).pack(side='left', padx=8)
        ttk.Label(source_panel, textvariable=self.source, wraplength=950).pack(anchor='w', pady=(8, 0))
        options = ttk.Frame(outer)
        options.pack(fill='x', pady=(0, 8))
        ttk.Checkbutton(options, text='Videonun tamamını ayrıca kaydet', variable=self.save_video).pack(side='left')
        self.canvas = tk.Canvas(outer, bg='#122232', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, pady=10)
        self.canvas.create_text(450, 150, text='Tespit sonucu burada görüntülenecek', fill='#d4e3ef', font=('Segoe UI', 16))
        self.canvas.bind('<Configure>', self.resize_preview)
        ttk.Label(outer, textvariable=self.counts, font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Sayılar gösterilen kareye aittir. Sarı kutu: çelişkili tahmin. Tespit yoksa durum bilinmiyor.').pack(anchor='w', pady=4)
        self.progress = ttk.Progressbar(outer, maximum=100)
        self.progress.pack(fill='x', pady=6)
        row = ttk.Frame(outer)
        row.pack(fill='x')
        self.start_button = ttk.Button(row, text='Tespiti ve olay takibini başlat', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(row, text='Durdur', command=self.stop.set, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        ttk.Button(row, text='Gösterilen kareyi kaydet', command=self.snapshot).pack(side='left')
        ttk.Label(outer, textvariable=self.status, wraplength=980).pack(anchor='w', pady=(8, 0))
        ttk.Separator(outer).pack(fill='x', pady=(10, 6))
        ttk.Label(outer, text=f'Kayıt: {db_text} • Operatör: {self.store.identity()[1]}').pack(anchor='w')
        self.warning_label = ttk.Label(outer, textvariable=self.maintenance_text, wraplength=1000, foreground='#a33b00')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<KeyPress-q>', self.quit_key)
        root.bind('<KeyPress-Q>', self.quit_key)
        self.canvas.bind('<Button-1>', lambda _: self.canvas.focus_set())
        root.after(75, self.poll)
        def maintenance():
            self.cleanup_once()
            if schedule_cleanup:
                try:
                    from .maintenance import register_cleanup
                    self.events.put(('warning', ('schedule', register_cleanup(ROOT))))
                except Exception:
                    self.events.put(('warning', ('schedule', 'Arka plan temizliği kurulamadı. Görüntüler uygulama açıkken ve sonraki açılışta temizlenecek.')))
        threading.Thread(target=maintenance, daemon=True).start()
        root.after(60000, self.periodic_cleanup)
        if self.store.warning:
            self.status.set(self.store.warning)

    def cleanup_once(self):
        try:
            self.store.cleanup()
            self.events.put(('warning', ('cleanup', None)))
        except Exception:
            self.events.put(('warning', ('cleanup', 'Bazı olay görüntüleri silinemedi. Sistem yeniden deneyecek.')))

    def update_warning(self, key, message):
        if message:
            self.warnings[key] = message
        else:
            self.warnings.pop(key, None)
        self.maintenance_text.set('\n'.join(self.warnings.values()))
        if self.warnings:
            self.warning_label.pack(anchor='w', pady=(4, 0))
        else:
            self.warning_label.pack_forget()

    def periodic_cleanup(self):
        if self.closing:
            return
        threading.Thread(target=self.cleanup_once, daemon=True).start()
        self.root.after(60000, self.periodic_cleanup)

    def quit_key(self, event):
        if not isinstance(event.widget, (ttk.Entry, ttk.Spinbox, ttk.Combobox, tk.Entry)):
            self.close()

    def open_events(self):
        try:
            if self.incident_window and self.incident_window.window.winfo_exists():
                self.incident_window.window.lift()
                self.incident_window.refresh()
            else:
                self.incident_window = EventWindow(self.root, self.store)
            self.violation_text.set('Olay kayıtları açıldı')
        except Exception as exc:
            messagebox.showerror('Olay kayıtları', str(exc))

    def busy(self):
        return self.worker is not None and self.worker.is_alive()

    def choose(self, kind):
        if self.busy():
            return
        types = [('Fotoğraflar', '*.jpg *.jpeg *.png *.bmp *.webp')] if kind == 'image' else [('Videolar', '*.mp4 *.avi *.mov *.mkv *.wmv')]
        path = filedialog.askopenfilename(filetypes=types + [('Tüm dosyalar', '*.*')])
        if path:
            self.kind.set(kind)
            self.source.set(path)

    def camera(self):
        if not self.busy():
            self.kind.set('camera')
            self.source.set('Kamera ' + self.camera_id.get())

    def resize_preview(self, _=None):
        self.canvas.delete('all')
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.last_frame is None:
            self.canvas.create_text(width // 2, height // 2, text='Tespit sonucu burada görüntülenecek', fill='#d4e3ef', font=('Segoe UI', 16))
            return
        picture = Image.fromarray(cv2.cvtColor(self.last_frame, cv2.COLOR_BGR2RGB))
        picture.thumbnail((max(1, width), max(1, height)))
        self.photo = ImageTk.PhotoImage(picture)
        self.canvas.create_image(width // 2, height // 2, image=self.photo)

    def start(self):
        if self.busy():
            return
        try:
            if not self.source.get():
                raise ValueError('Önce kaynak seçin.')
            source = int(self.camera_id.get()) if self.kind.get() == 'camera' else self.source.get()
            confidence = load_confidence()
        except (ValueError, OSError, tk.TclError) as exc:
            messagebox.showerror('Seçimi kontrol edin', str(exc))
            return
        args = (source, self.kind.get(), self.model.get(), self.output.get(), confidence)
        save_video = self.save_video.get()
        self.stop.clear()
        self.progress['value'] = 0
        self.status.set('Model yükleniyor…')
        self.start_button['state'] = 'disabled'
        self.stop_button['state'] = 'normal'
        def on_frame(*payload):
            try:
                self.preview.get_nowait()
            except queue.Empty:
                pass
            self.preview.put_nowait(payload)
        def work():
            try:
                folder = process(*args, stop=self.stop, callback=on_frame, event_store=self.store,
                                 event_callback=lambda event: self.events.put(('incident', event)),
                                 show_opencv=False,
                                 save_media=save_video)
                self.events.put(('done', ('Durduruldu' if self.stop.is_set() else 'Tamamlandı') + f'. Sonuçlar: {folder}'))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()

    def poll(self):
        try:
            frame, counts, index, total = self.preview.get_nowait()
            self.last_frame = frame
            self.resize_preview()
            self.counts.set(f"Baret: {counts.get('helmet', 0)}   |   Baretsiz baş: {counts.get('head', 0)}   |   Kişi: {counts.get('person', 0)}   |   Kararsız: {counts.get('uncertain', 0)}")
            self.progress['value'] = min(100, index / total * 100) if total else 0
            self.status.set(f'İşleniyor ve kaydediliyor • Kare {index}' + (f' / {total}' if total else ''))
        except queue.Empty:
            pass
        try:
            event, message = self.events.get_nowait()
            if event == 'incident':
                self.violation_text.set('Yeni İhlal Mevcut')
                self.alarm_threads = [t for t in self.alarm_threads if t.is_alive()]
                self.alarm_threads.append(play_alarm(on_error=lambda text: self.events.put(('warning', ('sound', text)))))
                if self.incident_window and self.incident_window.window.winfo_exists():
                    self.incident_window.refresh()
            elif event == 'quit':
                self.close()
            elif event == 'warning':
                self.update_warning(*message)
            else:
                self.status.set(message)
                self.start_button['state'] = 'normal'
                self.stop_button['state'] = 'disabled'
                if event == 'error' and not self.closing:
                    messagebox.showerror('İşlem tamamlanamadı', message)
        except queue.Empty:
            pass
        if self.closing and not self.busy() and not any(t.is_alive() for t in self.alarm_threads) and self.events.empty():
            self.root.destroy()
            return
        self.root.after(75, self.poll)

    def snapshot(self):
        if self.last_frame is None:
            return
        path = filedialog.asksaveasfilename(defaultextension='.jpg', filetypes=[('JPEG', '*.jpg')])
        if path:
            try:
                save_image(path, self.last_frame)
            except Exception as exc:
                messagebox.showerror('Kayıt başarısız', str(exc))

    def close(self):
        self.closing = True
        self.stop.set()
        self.status.set('İşlem durduruluyor, kayıt kapatılıyor…')


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
