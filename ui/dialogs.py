"""UI 对话框"""
import os
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, scrolledtext

from core import config as cfg
from core.ai_providers import (
    get_models,
    get_provider,
    get_provider_list,
    load_api_settings,
    save_api_settings,
    test_connection,
)

_FONT = ('Microsoft YaHei', 10)
_FONT_BOLD = ('Microsoft YaHei', 10, 'bold')
_FONT_TITLE = ('Microsoft YaHei', 13, 'bold')


def _title_bar(win, text):
    tk.Label(win, text=text, font=_FONT_TITLE,
             bg=cfg.C_TITLE_BG, fg=cfg.C_TITLE_FG,
             height=2).pack(fill='x')


def _btn(parent, text, color, command=None, **kw):
    dark = cfg.C_SKY_DEEP if color == cfg.C_SKY else \
            cfg.C_MINT_DEEP if color == cfg.C_MINT else \
            cfg.C_ROSE_DEEP if color == cfg.C_ROSE else \
            cfg.C_ASH
    return tk.Button(parent, text=text, font=_FONT,
                     bg=color, fg='white', relief='flat',
                     bd=0, padx=16, pady=7, cursor='hand2',
                     activebackground=dark, command=command, **kw)


def _label_row(win, text):
    return tk.Label(win, text=text, font=_FONT,
                    bg=cfg.C_BG, fg=cfg.C_ASH_DARK)


class UIDialogs:
    def __init__(self, pet):
        self.pet = pet

    @staticmethod
    def _center_window(win, w, h):
        win.update_idletasks()
        cx = (win.winfo_screenwidth() // 2) - (w // 2)
        cy = (win.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{cx}+{cy}")

    @staticmethod
    def _window(pet, title, w, h):
        win = tk.Toplevel(pet.root)
        win.title(title)
        win.geometry(f"{w}x{h}")
        win.resizable(False, False)
        win.configure(bg=cfg.C_BG)
        win.transient(pet.root)
        win.grab_set()
        win.update_idletasks()
        cx = (win.winfo_screenwidth() // 2) - (w // 2)
        cy = (win.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{cx}+{cy}")
        return win

    # ── 缩放 ──────────────────────────────────
    def show_size_menu(self):
        p = self.pet
        win = self._window(p, "调整大小", 300, 220)
        _title_bar(win, "📏  调整桌宠大小")

        pct_label = tk.Label(win, text=f"{int(p.scale_factor * 100)}%",
                             font=('Microsoft YaHei', 26, 'bold'),
                             bg=cfg.C_BG, fg=cfg.C_ASH_DARK)
        pct_label.pack(pady=(18, 2))

        size_var = tk.DoubleVar(value=p.scale_factor)
        tk.Scale(win, from_=p.min_scale, to=p.max_scale,
                 resolution=0.1, orient='horizontal', variable=size_var,
                 font=_FONT, bg=cfg.C_BG,
                 troughcolor=cfg.C_ASH_LIGHT, length=200,
                 showvalue=False, activebackground=cfg.C_ASH,
                 ).pack(pady=6)

        def preview(*_):
            v = size_var.get()
            pct_label.config(text=f"{int(v * 100)}%")
            p._resize_pet(v)
        size_var.trace('w', preview)

        frame = tk.Frame(win, bg=cfg.C_BG)
        frame.pack(pady=(8, 16))
        _btn(frame, "↺ 重置", cfg.C_ROSE,
             command=lambda: (size_var.set(1.0), p._resize_pet(1.0),
                              pct_label.config(text="100%")),
             ).pack(side='left', padx=6)
        _btn(frame, "✓ 确定", cfg.C_MINT,
             command=win.destroy).pack(side='left', padx=6)

    # ── 系统设置 ──────────────────────────────
    def show_settings(self):
        p = self.pet
        win = self._window(p, "设置", 380, 350)
        _title_bar(win, "⚙  系统设置")

        cnt = p.chat_history.stats.get('total_messages', 0)
        tk.Label(win, text=f"已保存 {cnt // 2} 轮聊天记录",
                 font=_FONT, bg=cfg.C_BG,
                 fg=cfg.C_ASH_DARK).pack(pady=(14, 6))

        frame = tk.Frame(win, bg=cfg.C_BG)
        frame.pack(pady=4)

        ai_min_v = tk.IntVar(value=p.min_auto_reply_time)
        ai_max_v = tk.IntVar(value=p.max_auto_reply_time)
        pr_min_v = tk.IntVar(value=p.preset_min_interval)
        pr_max_v = tk.IntVar(value=p.preset_max_interval)

        mem_v = tk.IntVar(value=cfg.MEMORY_CONTEXT_SIZE // 2)
        rows = [("AI最短", ai_min_v, 0, 9999), ("AI最长", ai_max_v, 1, 9999),
                ("预设最短", pr_min_v, 0, 9999), ("预设最长", pr_max_v, 1, 9999),
                ("记忆轮数", mem_v, 10, 500)]
        for label, var, lo, hi in rows:
            row = tk.Frame(frame, bg=cfg.C_BG)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=label, font=_FONT, bg=cfg.C_BG,
                     fg=cfg.C_TEXT, width=10, anchor='e').pack(side='left', padx=6)
            tk.Spinbox(row, from_=lo, to=hi, textvariable=var,
                       font=_FONT, width=6, bg='white',
                       fg=cfg.C_TEXT, relief='flat', bd=1,
                       ).pack(side='left', padx=4)
            unit = "轮（1轮=我问+你答）" if label == "记忆轮数" else "秒"
            tk.Label(row, text=unit, font=_FONT, bg=cfg.C_BG,
                     fg=cfg.C_ASH_DARK).pack(side='left')

        def do_save():
            for a, b, msg in [(ai_min_v, ai_max_v, "AI"), (pr_min_v, pr_max_v, "预设")]:
                if a.get() > b.get():
                    messagebox.showerror("错误", f"{msg}最短不能大于最长")
                    return
            p.min_auto_reply_time = ai_min_v.get()
            p.max_auto_reply_time = ai_max_v.get()
            p.preset_min_interval = pr_min_v.get()
            p.preset_max_interval = pr_max_v.get()
            cfg.MIN_AUTO_REPLY = ai_min_v.get()
            cfg.MAX_AUTO_REPLY = ai_max_v.get()
            cfg.PRESET_MIN_INTERVAL = pr_min_v.get()
            cfg.PRESET_MAX_INTERVAL = pr_max_v.get()
            cfg.MEMORY_CONTEXT_SIZE = mem_v.get() * 2
            cfg._save()
            p.show_talk("设置已保存")
            p.root.after(2000, p.hide_talk)
            win.destroy()

        frame2 = tk.Frame(win, bg=cfg.C_BG)
        frame2.pack(pady=(10, 0))
        _btn(frame2, "↺ 默认", cfg.C_ROSE,
             command=lambda: (
                 ai_min_v.set(cfg.DEFAULT_MIN_AUTO_REPLY), ai_max_v.set(cfg.DEFAULT_MAX_AUTO_REPLY),
                 pr_min_v.set(120), pr_max_v.set(600), mem_v.set(200)),
             ).pack(side='left', padx=6)
        _btn(frame2, "✓ 保存", cfg.C_MINT,
             command=do_save).pack(side='left', padx=6)

    # ── API 设置 ──────────────────────────────
    def show_api_settings(self):
        p = self.pet
        settings = load_api_settings()
        providers = get_provider_list()
        win = self._window(p, "API 配置", 440, 400)
        _title_bar(win, "🔑  大模型 API 配置")

        configured = bool(settings.get("api_key") and len(settings["api_key"]) > 10)
        pi = get_provider(settings["provider"])
        pd = pi["name"] if pi else settings["provider"]
        st = f"当前: {pd} / {settings['model']}" if configured else "未配置"
        sf = cfg.C_MINT_DEEP if configured else cfg.C_ROSE_DEEP
        _label_row(win, st).pack(pady=(14, 8))
        # override color
        for w in win.winfo_children():
            if isinstance(w, tk.Label) and w.cget('text') == st:
                w.config(fg=sf, font=_FONT_BOLD)

        # 厂商
        f1 = tk.Frame(win, bg=cfg.C_BG)
        f1.pack(fill='x', padx=30, pady=6)
        tk.Label(f1, text="厂商", font=_FONT, bg=cfg.C_BG,
                 fg=cfg.C_ASH_DARK, width=6, anchor='e').pack(side='left')
        prov_var = tk.StringVar()
        prov_names = [n for _, n in providers]
        prov_keys = [k for k, _ in providers]
        ci = prov_keys.index(settings["provider"]) if settings["provider"] in prov_keys else 0
        dd = tk.OptionMenu(f1, prov_var, *prov_names)
        dd.config(font=_FONT, bg='white', relief='flat', width=22,
                  indicatoron=False, highlightthickness=0)
        dd.pack(side='left', padx=8)
        prov_var.set(prov_names[ci])

        # 模型
        f2 = tk.Frame(win, bg=cfg.C_BG)
        f2.pack(fill='x', padx=30, pady=6)
        tk.Label(f2, text="模型", font=_FONT, bg=cfg.C_BG,
                 fg=cfg.C_ASH_DARK, width=6, anchor='e').pack(side='left')
        model_var = tk.StringVar()
        model_dd = tk.OptionMenu(f2, model_var, "---")
        model_dd.config(font=_FONT, bg='white', relief='flat', width=30,
                        indicatoron=False, highlightthickness=0)
        model_dd.pack(side='left', padx=8)

        def on_prov_change(*_):
            name = prov_var.get()
            for k, n in providers:
                if n == name:
                    models = get_models(k)
                    model_var.set(
                        settings["model"] if settings["model"] in models and k == settings["provider"]
                        else (models[0] if models else "---")
                    )
                    m = model_dd["menu"]
                    m.delete(0, "end")
                    for md in models:
                        m.add_command(label=md, command=lambda v=md: model_var.set(v))
                    break
        prov_var.trace('w', on_prov_change)
        on_prov_change()

        # Key
        f3 = tk.Frame(win, bg=cfg.C_BG)
        f3.pack(fill='x', padx=30, pady=6)
        tk.Label(f3, text="Key", font=_FONT, bg=cfg.C_BG,
                 fg=cfg.C_ASH_DARK, width=6, anchor='e').pack(side='left')
        key_var = tk.StringVar(value=settings.get("api_key", ""))
        key_entry = tk.Entry(f3, textvariable=key_var, show="*",
                             font=_FONT, bg='white',
                             fg=cfg.C_TEXT, relief='flat', bd=1, width=28)
        key_entry.pack(side='left', padx=8)

        kv = [False]
        def toggle_key():
            kv[0] = not kv[0]
            key_entry.config(show="" if kv[0] else "*")
            btn_tk.config(text="🙈" if kv[0] else "👁")
        btn_tk = tk.Button(f3, text="👁", font=_FONT,
                           bg='white', relief='flat', bd=0, cursor='hand2',
                           command=toggle_key)
        btn_tk.pack(side='left')

        # 结果提示
        rl = _label_row(win, "")
        rl.pack(pady=6)

        bf = tk.Frame(win, bg=cfg.C_BG)
        bf.pack(pady=8)

        def _get_pk():
            name = prov_var.get()
            for k, n in providers:
                if n == name:
                    return k
            return "volcengine"

        def set_btns(v):
            for b in [bt, bs, bc]:
                b.config(state='normal' if v else 'disabled')

        def do_test():
            pk = _get_pk()
            k = key_var.get()
            m = model_var.get()
            if not k or len(k) < 10:
                rl.config(text="请先填写 API Key", fg=cfg.C_ROSE_DEEP)
                return
            set_btns(False)
            rl.config(text="正在测试…", fg=cfg.C_ASH_DARK)
            def _run():
                ok, msg = test_connection(pk, k, m)
                p.root.after(0, lambda: (
                    rl.config(text=msg, fg=cfg.C_MINT_DEEP if ok else cfg.C_ROSE_DEEP),
                    set_btns(True),
                ))
            threading.Thread(target=_run, daemon=True).start()

        def do_save():
            pk = _get_pk()
            m = model_var.get()
            k = key_var.get()
            if not k or len(k) < 10:
                rl.config(text="API Key 太短", fg=cfg.C_ROSE_DEEP)
                return
            save_api_settings(pk, m, k)
            p.ai.switch(pk, m, k)
            rl.config(text="已保存", fg=cfg.C_MINT_DEEP)
            p.show_talk("API 设置已保存")
            p.root.after(2000, p.hide_talk)

        bt = _btn(bf, "📡 测试连接", cfg.C_SKY, command=do_test)
        bt.pack(side='left', padx=4)
        bs = _btn(bf, "💾 保存", cfg.C_MINT, command=do_save)
        bs.pack(side='left', padx=4)
        bc = _btn(bf, "✕ 关闭", cfg.C_ROSE, command=win.destroy)
        bc.pack(side='left', padx=4)

    # ── 聊天记录 ──────────────────────────────
    def show_chat_history(self):
        p = self.pet
        if not p.chat_history:
            p.show_talk(cfg.NO_HISTORY)
            return

        win = self._window(p, "聊天记录", 580, 480)
        _title_bar(win, "📋  聊天记录")

        sv = tk.StringVar()
        tk.Entry(win, textvariable=sv, font=_FONT,
                 bg='white', fg=cfg.C_TEXT, width=32,
                 relief='flat', bd=1,
                 ).pack(pady=(10, 5), padx=12, anchor='w')

        ta = scrolledtext.ScrolledText(
            win, wrap=tk.WORD, font=('Microsoft YaHei', 10),
            bg=cfg.C_PANEL_BG, fg=cfg.C_TEXT, relief='flat', bd=0,
        )
        ta.pack(fill='both', expand=True, padx=12, pady=4)

        def render(ft=""):
            ta.delete(1.0, tk.END)
            records = p.chat_history.search(ft) if ft else p.chat_history.history
            for m in reversed(records[-200:]):
                r = "👤 训练员" if m["role"] == "user" else "🐱 小栗帽"
                ta.insert(tk.END, f"{m['timestamp']}  {r}\n{m['content']}\n")
                ta.insert(tk.END, "─" * 50 + "\n\n")
        sv.trace('w', lambda *a: render(sv.get()))
        render()

        bf = tk.Frame(win, bg=cfg.C_BG)
        bf.pack(fill='x', padx=12, pady=10)
        _btn(bf, "📤 导出", cfg.C_SKY,
             command=lambda: self._export_chat_history(win),
             ).pack(side='left', padx=4)
        _btn(bf, "✕ 关闭", cfg.C_ROSE,
             command=win.destroy).pack(side='right', padx=4)
        win.bind('<Escape>', lambda e: win.destroy())

    def _export_chat_history(self, parent):
        p = self.pet
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            parent=parent, title="导出聊天记录",
            initialfile=f"chat_history_{ts}.txt",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt")],
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("小栗帽聊天记录导出\n" + "=" * 50 + "\n\n")
                for m in p.chat_history.history:
                    r = "训练员" if m["role"] == "user" else "小栗帽"
                    f.write(f"[{m['timestamp']}] {r}: {m['content']}\n\n")
            p.show_talk(cfg.EXPORT_OK.format(name=os.path.basename(path)))

    # ── 字体设置 ──────────────────────────────
    def show_font_settings(self):
        p = self.pet
        win = self._window(p, "字体设置", 400, 420)
        _title_bar(win, "🔤  字体设置")

        # 快速筛选中文字体（纯关键词，不卡 UI）
        all_f = sorted(f for f in tkfont.families() if not f.startswith("@"))
        kw = ["song", "hei", "kai", "fang", "ming", "yuan", "yahei",
              "simsun", "simhei", "kaiti", "fangsong", "dengxian",
              "noto", "cjk", "chinese", "han", "gothic", "mincho",
              "wenquan", "sarasa", "puhui", "zcool", "alibaba",
              "source", "serif", "sans", "mono", "arial", "ms",
              "microsoft", "times", "courier", "helvetica",
              "宋", "黑", "楷", "仿", "明", "圆", "雅", "刚",
              "霞", "鹜", "楷", "纱", "等", "线", "方", "站",
              "庞", "优", "标", "问", "藏", "濑", "户",
              "デ", "ゴ", "角", "goth", "minc"]
        cn = list(dict.fromkeys(f for f in all_f if any(k in f.lower() for k in kw)))
        fb = ["Microsoft YaHei", "SimSun", "SimHei", "KaiTi", "FangSong",
              "DengXian", "NSimSun", "YouYuan", "Microsoft JhengHei"]
        for f in fb:
            if f in all_f and f not in cn:
                cn.append(f)

        if not cn:
            cn = ["Microsoft YaHei", "SimSun", "SimHei"]

        # 字号
        sf = tk.Frame(win, bg=cfg.C_BG)
        sf.pack(fill='x', padx=16, pady=(10, 4))
        tk.Label(sf, text="字号", font=_FONT, bg=cfg.C_BG,
                 fg=cfg.C_ASH_DARK).pack(side='left')
        sv = tk.IntVar(value=cfg.FONT_SIZE)
        tk.Spinbox(sf, from_=cfg.FONT_SIZE_MIN, to=cfg.FONT_SIZE_MAX,
                   textvariable=sv, font=_FONT, width=6,
                   bg='white', fg=cfg.C_TEXT, relief='flat', bd=1,
                   ).pack(side='left', padx=6)

        # 字体列表
        lf = tk.Frame(win, bg=cfg.C_BG)
        lf.pack(fill='both', expand=True, padx=16, pady=2)
        sb = tk.Scrollbar(lf, orient='vertical')
        lb = tk.Listbox(lf, font=_FONT, bg='white', fg=cfg.C_TEXT,
                        relief='flat', bd=0, highlightthickness=0,
                        exportselection=False, yscrollcommand=sb.set)
        sb.config(command=lb.yview)
        sb.pack(side='right', fill='y')
        lb.pack(side='left', fill='both', expand=True)

        for fam in cn:
            lb.insert(tk.END, fam)
        sel = tk.StringVar(value=cfg.FONT_FAMILY if cfg.FONT_FAMILY in cn else cn[0])

        def pick(ev=None):
            idx = lb.curselection()
            if idx:
                sel.set(cn[idx[0]])
                up()

        def pv(*_):
            up()

        def up(*_):
            f = sel.get()
            s = max(cfg.FONT_SIZE_MIN, min(cfg.FONT_SIZE_MAX, sv.get()))
            pl.config(font=(f, s))

        lb.bind('<<ListboxSelect>>', pick)
        lb.bind('<Enter>', lambda e: lb.bind_all(
            '<MouseWheel>', lambda e: lb.yview_scroll(int(-1 * (e.delta / 120)), 'units')))
        lb.bind('<Leave>', lambda e: lb.unbind_all('<MouseWheel>'))

        if sel.get() in cn:
            lb.selection_set(cn.index(sel.get()))

        # 预览
        pl = tk.Label(win, text="小栗帽的回复会变成这样",
                      bg=cfg.C_PANEL_BG, fg=cfg.C_TEXT,
                      relief='flat', bd=0, height=2)
        pl.pack(fill='x', padx=16, pady=(4, 2))
        up()

        # 底部
        bf = tk.Frame(win, bg=cfg.C_BG)
        bf.pack(pady=(0, 10))
        _btn(bf, "✓ 保存", cfg.C_MINT, command=lambda: (
            setattr(cfg, 'FONT_FAMILY', sel.get()),
            setattr(cfg, 'FONT_SIZE', max(cfg.FONT_SIZE_MIN, min(cfg.FONT_SIZE_MAX, sv.get()))),
            p.show_talk("字体设置已保存"),
            p.root.after(2000, p.hide_talk), win.destroy(),
        )).pack(side='left', padx=4)
        _btn(bf, "✕ 关闭", cfg.C_ROSE, command=win.destroy).pack(side='left', padx=4)

    # ── 技能管理 ──────────────────────────────
    def show_skill_manager(self):
        p = self.pet
        win = self._window(p, "技能管理", 580, 420)
        _title_bar(win, "⚡  技能管理")

        def refresh():
            for w in lf.winfo_children():
                w.destroy()
            skills = p.skill_manager.list_skills()
            if not skills:
                _label_row(lf, "暂无可用技能").pack(pady=30)
                return
            for sk in skills:
                # 第一行：复选框 + 名称 + 删除按钮
                row1 = tk.Frame(lf, bg=cfg.C_BG, bd=0)
                row1.pack(fill='x', padx=12, pady=(3, 0))

                var = tk.BooleanVar(value=sk["enabled"])
                def toggle(nm=sk["name"], v=var):
                    p.skill_manager.toggle(nm, v.get())
                tk.Checkbutton(row1, variable=var, command=toggle,
                               bg=cfg.C_BG, activebackground=cfg.C_BG,
                               highlightthickness=0).pack(side='left')

                tk.Label(row1, text=sk["name"],
                         font=_FONT_BOLD, bg=cfg.C_BG,
                         fg=cfg.C_TEXT, anchor='w',
                         ).pack(side='left', padx=(4, 0))

                def do_del(nm=sk["name"]):
                    if messagebox.askyesno("确认删除", f"删除技能「{nm}」？\n技能目录和文件将被完全移除，不可恢复。"):
                        p.skill_manager.remove_skill(nm)
                        refresh()
                _btn(row1, "删除", cfg.C_ROSE, command=do_del).pack(side='right', padx=2)

                # 第二行：描述（超出 25 字自动换行）
                desc = sk.get("description", "")
                if desc:
                    tk.Label(lf, text=desc, font=('Microsoft YaHei', 9),
                             bg=cfg.C_BG, fg=cfg.C_ASH_DARK, anchor='w',
                             wraplength=350, justify='left',
                             ).pack(fill='x', padx=(40, 12), pady=(1, 2))

                # 分隔线
                tk.Frame(lf, height=1, bg=cfg.C_ASH_LIGHT).pack(fill='x', padx=12)

        container = tk.Frame(win, bg=cfg.C_BG)
        container.pack(fill='both', expand=True, padx=6, pady=6)
        canvas = tk.Canvas(container, bg=cfg.C_BG, highlightthickness=0)
        sb = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
        lf = tk.Frame(canvas, bg=cfg.C_BG)
        lf.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=lf, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        canvas.bind('<Enter>', lambda e: canvas.bind_all(
            '<MouseWheel>', lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))
        refresh()

        bf = tk.Frame(win, bg=cfg.C_BG, highlightbackground=cfg.C_ASH_LIGHT, highlightthickness=1)
        bf.pack(fill='x', padx=0, pady=0)
        inner_bf = tk.Frame(bf, bg=cfg.C_BG)
        inner_bf.pack(fill='x', padx=12, pady=6)
        _btn(inner_bf, "+ 添加技能", cfg.C_SKY,
             command=lambda: self._add_skill_dlg(win, refresh),
             ).pack(side='left', padx=4)
        _btn(inner_bf, "↻ 刷新", cfg.C_ASH,
             command=refresh).pack(side='left', padx=4)
        _btn(inner_bf, "✕ 关闭", cfg.C_ROSE,
             command=win.destroy).pack(side='right', padx=4)

    def _add_skill_dlg(self, parent, refresh_cb):
        path = filedialog.askopenfilename(
            parent=parent, title="选择技能",
            filetypes=[("技能包", "*.zip"), ("Python 文件", "*.py"), ("所有文件", "*.*")],
        )
        if not path:
            return
        pet = self.pet
        is_zip = path.lower().endswith(".zip")
        ok, msg = pet.skill_manager.add_skill_zip(path) if is_zip else pet.skill_manager.add_skill(path)
        if ok:
            pet.show_talk("技能添加成功")
            pet.root.after(2000, pet.hide_talk)
        else:
            messagebox.showerror("添加失败", msg)
        refresh_cb()

    # ── 游戏管理 ──────────────────────────────
    def show_game_manager(self):
        p = self.pet
        win = self._window(p, "游戏管理", 380, 280)
        _title_bar(win, "🎮  游戏管理")

        if p.game_manager.is_active():
            act = p.game_manager._active
            tk.Label(win, text=f"正在游玩：{act.NAME}",
                     font=_FONT_BOLD, bg=cfg.C_BG,
                     fg=cfg.C_MINT_DEEP).pack(pady=(12, 4))

        lf = tk.Frame(win, bg=cfg.C_BG)
        lf.pack(fill='both', expand=True, padx=16, pady=6)

        for key, gname, enabled in p.game_manager.list_all():
            row = tk.Frame(lf, bg=cfg.C_BG, bd=0)
            row.pack(fill='x', pady=3)
            var = tk.BooleanVar(value=enabled)
            def toggle(k=key, v=var):
                p.game_manager.set_enabled(k, v.get())
            tk.Checkbutton(row, variable=var, command=toggle,
                           bg=cfg.C_BG, activebackground=cfg.C_BG,
                           highlightthickness=0).pack(side='left')
            tk.Label(row, text=gname, font=_FONT_BOLD, bg=cfg.C_BG,
                     fg=cfg.C_TEXT).pack(side='left', padx=(4, 0))
            tk.Frame(lf, height=1, bg=cfg.C_ASH_LIGHT).pack(fill='x', padx=4)

        bf = tk.Frame(win, bg=cfg.C_BG)
        bf.pack(pady=(10, 0))
        if p.game_manager.is_active():
            _btn(bf, "⏹ 退出游戏", cfg.C_ROSE,
                 command=lambda: (p.game_manager.stop(), win.destroy()),
                 ).pack(side='left', padx=4)
        _btn(bf, "✕ 关闭", cfg.C_ASH,
             command=win.destroy).pack(side='left', padx=4)
