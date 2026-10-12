from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk


class EventWindow:
    def __init__(self, parent, store):
        store.require_operator()
        self.store = store
        self.window = tk.Toplevel(parent)
        self.window.title('Olay kayıtları • Operatör incelemesi')
        self.window.geometry('1100x700')
        self.window.minsize(850,600)
        self.records = {}
        self.photo = None
        bar = ttk.Frame(self.window,padding=12)
        bar.pack(fill='x')
        ttk.Label(bar,text='OLAY KAYITLARI',font=('Segoe UI',18,'bold')).pack(side='left')
        self.filter = tk.StringVar(value='Tümü')
        choice=ttk.Combobox(bar,textvariable=self.filter,values=['Tümü','New','Confirmed','False Alarm'],state='readonly',width=15)
        choice.pack(side='right');choice.bind('<<ComboboxSelected>>',lambda _:self.refresh())
        ttk.Label(self.window,text='Turuncu New kayıtları inceleme bekliyor. Sonlandırılmış kayıtlar değiştirilemez.').pack(anchor='w',padx=12)
        ttk.Label(self.window, text='Yanlış alarm görüntüleri hemen, onaylanan ihlal görüntüleri onaydan 30 gün sonra silinir. Olay kayıtları korunur.', wraplength=1000).pack(anchor='w', padx=12, pady=(4, 0))
        columns=('id','camera','date','time','track','status')
        self.tree=ttk.Treeview(self.window,columns=columns,show='headings',height=9)
        for key,title,width in zip(columns,['Olay','Kamera / Kaynak','Tarih','Saat','Takip ID','Durum'],[55,290,100,90,80,120]):
            self.tree.heading(key,text=title);self.tree.column(key,width=width)
        self.tree.tag_configure('New',background='#ffe2ad',foreground='#702d00',font=('Segoe UI',10,'bold'))
        self.tree.pack(fill='x',padx=12,pady=8)
        self.tree.bind('<<TreeviewSelect>>',self.select)
        self.details=tk.StringVar(value='Görüntüyü incelemek için bir olay seçin.')
        ttk.Label(self.window,textvariable=self.details,wraplength=1000).pack(anchor='w',padx=12)
        self.picture=ttk.Label(self.window,text='Olay görüntüsü')
        self.picture.pack(fill='both',expand=True,padx=12,pady=8)
        buttons=ttk.Frame(self.window,padding=12);buttons.pack(fill='x')
        self.confirm=ttk.Button(buttons,text='Confirmed • İhlali onayla',command=lambda:self.review('Confirmed'),state='disabled')
        self.confirm.pack(side='left')
        self.reject=ttk.Button(buttons,text='False Alarm • Yanlış alarm',command=lambda:self.review('False Alarm'),state='disabled')
        self.reject.pack(side='left',padx=8)
        ttk.Button(buttons,text='Yenile',command=self.refresh).pack(side='right')
        self.refresh()
        self.window.after(3000,self.tick)

    def tick(self):
        if self.window.winfo_exists():
            self.refresh()
            self.window.after(3000,self.tick)

    @staticmethod
    def local_time(value):
        dt=value if isinstance(value,datetime) else datetime.fromisoformat(value)
        return dt.replace(tzinfo=timezone.utc).astimezone()

    def refresh(self):
        try:
            selected=self.tree.selection()
            rows=self.store.list_events()
            self.records={str(r['logId']):r for r in rows}
            self.tree.delete(*self.tree.get_children())
            for r in rows:
                if self.filter.get()!='Tümü' and r['status']!=self.filter.get():continue
                date=self.local_time(r['timeStamp'])
                # Display only source name, never snapshotPath.
                source=str(r['sourceName']).replace('\\','/').rsplit('/',1)[-1]
                self.tree.insert('', 'end',iid=str(r['logId']),values=(r['logId'],source,date.strftime('%d.%m.%Y'),date.strftime('%H:%M:%S'),r['trackId'],r['status']),tags=(r['status'],))
            if selected and self.tree.exists(selected[0]):
                self.tree.selection_set(selected[0]);self.select()
            else:
                self.confirm['state']=self.reject['state']='disabled'
        except Exception as exc:
            self.details.set(str(exc))

    def select(self, _=None):
        selected=self.tree.selection()
        if not selected:return
        row=self.records[selected[0]]
        self.details.set(f"Olay {row['logId']} • Takip ID: {row['trackId']} • {row['status']}" + (f" • İnceleyen: {row['reviewedBy']}" if row['reviewedBy'] else ''))
        self.confirm['state']=self.reject['state']='normal' if row['status']=='New' else 'disabled'
        try:
            path=self.store.snapshot_file(row['snapshotPath'])
            if path and path.is_file():
                with Image.open(path) as source:
                    picture=source.copy()
                picture.thumbnail((900,330))
                self.photo=ImageTk.PhotoImage(picture)
                self.picture.configure(image=self.photo,text='')
            else:
                self.photo=None
                self.picture.configure(image='',text='Bu olayın görüntüsü saklama kuralı gereği silinmiş veya mevcut değil.')
        except Exception:
            self.picture.configure(image='',text='Olay görüntüsü yüklenemedi.')

    def review(self, status):
        selected=self.tree.selection()
        if not selected:return
        try:
            self.store.review(int(selected[0]),status)
            self.refresh()
        except Exception as exc:
            messagebox.showerror('İnceleme sonucu',str(exc),parent=self.window)
            self.refresh()
