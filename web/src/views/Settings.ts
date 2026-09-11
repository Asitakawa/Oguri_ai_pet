import { gsap } from "gsap";
import type { Ctx, View } from "./types";
import { api, describeError } from "../api/client";
import type { MemoryPayload, SettingsPayload } from "../api/types";
import { escapeAttr, escapeHtml } from "../utils";

function el<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

function setMsg(id: string, text: string, ok: boolean): void {
  const m = el(id);
  if (m) {
    m.textContent = text;
    m.classList.toggle("ok", ok);
    m.classList.toggle("err", !ok);
  }
}

const errMsg = (e: unknown) => String((e as Error)?.message ?? e);

function setTextById(id: string, text: string): void {
  const node = el(id);
  if (node) node.textContent = text;
}

export const Settings: View = {
  id: "settings",
  title: "设置",
  icon: "⚙️",
  render() {
    return `
    <div class="view view-settings">
      <div class="load-error" id="settings-load-error" hidden>
        <span id="settings-load-error-text">无法加载设置</span>
        <button class="btn btn-sm" data-action="reload">↻ 重试</button>
      </div>
      <section class="glass-card">
        <header class="card-head"><span class="card-icon">🔑</span><h3>API 设置</h3></header>
        <div class="form-grid">
          <label>厂商
            <select id="set-provider" class="input"></select>
          </label>
          <label>模型
            <select id="set-model" class="input"></select>
          </label>
          <label>API Key
            <span class="key-row">
              <input id="set-key" class="input" type="password" placeholder="sk-…" autocomplete="off" />
              <button class="btn btn-sm" id="set-key-toggle" type="button">👁</button>
            </span>
          </label>
        </div>
        <div class="row-end">
          <span class="form-msg" id="api-msg"></span>
          <button class="btn" data-action="api-test">🔌 测试连接</button>
          <button class="btn btn-primary" data-action="api-save">💾 保存</button>
        </div>
      </section>

      <section class="glass-card">
        <header class="card-head"><span class="card-icon">📏</span><h3>宠物外观</h3></header>
        <div class="form-grid">
          <label>大小 <b id="size-label">100%</b>
            <input id="set-size" type="range" min="50" max="200" step="10" />
          </label>
        </div>
        <div class="row-end">
          <span class="form-msg" id="size-msg"></span>
          <button class="btn" data-action="size-reset">↺ 重置 100%</button>
          <button class="btn btn-primary" data-action="size-save">💾 保存</button>
        </div>
      </section>

      <section class="glass-card">
        <header class="card-head"><span class="card-icon">🔤</span><h3>字体设置</h3></header>
        <div class="form-grid">
          <label>字体族
            <select id="set-font-family" class="input"></select>
          </label>
          <label>字号
            <input id="set-font-size" class="input" type="number" />
          </label>
        </div>
        <div class="font-preview" id="font-preview">小栗帽的回复会变成这样</div>
        <div class="row-end">
          <span class="form-msg" id="font-msg"></span>
          <button class="btn btn-primary" data-action="font-save">💾 保存</button>
        </div>
      </section>

      <section class="glass-card">
        <header class="card-head"><span class="card-icon">🧠</span><h3>聊天记忆</h3></header>
        <div class="form-grid">
          <label>记忆轮数
            <input id="mem-rounds" class="input" type="number" min="5" max="250" />
          </label>
        </div>
        <p class="mem-hint">AI 对话时会把最近 <b id="mem-current">—</b> 轮对话（每轮含一问一答）作为上下文背景。轮数越多小栗帽越记得之前的聊天，但消耗的 token 也越多。范围 <span id="mem-hint-range">—</span>。</p>
        <div class="row-end">
          <span class="form-msg" id="mem-msg"></span>
          <button class="btn" data-action="mem-default">↺ 恢复默认</button>
          <button class="btn btn-primary" data-action="mem-save">💾 保存</button>
        </div>
      </section>

      <section class="glass-card">
        <header class="card-head"><span class="card-icon">🧠</span><h3>长期记忆</h3></header>
        <p class="mem-hint">
          小栗帽会把聊过的内容提炼成关于你的简短事实，跨会话记住。全部存在本机
          <code>facts.json</code>，只在对话时连同上下文发给你自己配置的模型厂商。
        </p>
        <div class="memory-head">
          <label class="switch" title="开启/关闭长期记忆">
            <input type="checkbox" id="mem-enabled" />
            <span></span>
          </label>
          <span class="memory-state" id="mem-state">—</span>
          <span class="spacer"></span>
          <button class="btn btn-sm btn-danger" data-action="mem-clear">🗑 清空全部</button>
        </div>
        <div class="memory-list" id="memory-list"><div class="chat-empty">加载中…</div></div>
        <div class="memory-add">
          <input id="mem-new" class="input" placeholder="手动加一条，例如「训练员叫小林」" />
          <button class="btn" data-action="mem-add">+ 添加</button>
        </div>
      </section>

      <section class="glass-card">
        <header class="card-head"><span class="card-icon">⚙</span><h3>系统设置</h3></header>
        <div class="form-grid cols-2">
          <label>AI 最短间隔(s)<input id="sys-min" class="input" type="number" /></label>
          <label>AI 最长间隔(s)<input id="sys-max" class="input" type="number" /></label>
          <label>预设最短间隔(s)<input id="sys-pmin" class="input" type="number" /></label>
          <label>预设最长间隔(s)<input id="sys-pmax" class="input" type="number" /></label>
        </div>
        <div class="row-end">
          <span class="form-msg" id="sys-msg"></span>
          <button class="btn" data-action="sys-default">↺ 恢复默认</button>
          <button class="btn btn-primary" data-action="sys-save">💾 保存</button>
        </div>
      </section>

      <section class="glass-card">
        <header class="card-head"><span class="card-icon">🖥️</span><h3>进程控制</h3></header>
        <div class="memory-head">
          <label class="switch" title="开机自动启动">
            <input type="checkbox" id="auto-start" />
            <span></span>
          </label>
          <span class="memory-state">开机自动启动小栗帽</span>
        </div>
        <p class="mem-hint">数据目录：<code id="data-dir">—</code></p>
        <div class="row-end">
          <span class="form-msg" id="proc-msg"></span>
          <button class="btn" data-action="restart">🔄 重启桌宠</button>
          <button class="btn btn-danger" data-action="quit">🚪 退出桌宠</button>
        </div>
      </section>
    </div>`;
  },
  async mount(ctx: Ctx) {
    gsap.from(".view-settings .glass-card", { opacity: 0, y: 16, duration: 0.35, stagger: 0.06, ease: "power2.out" });

    // 每次 bind 前先取一次最新设置。失败时不再直接 return——那样六个卡片
    // 会全部没有监听器，变成一个看得见点不动的死表单。
    const bind = async (): Promise<boolean> => {
      const banner = el("settings-load-error");
      const bannerText = el("settings-load-error-text");
      const onReload = () => void bind();
      // render() 刚重建过 DOM，重新挂一次重试按钮
      ctx.root.querySelector("[data-action='reload']")?.addEventListener("click", onReload);

      let s: SettingsPayload | null = null;
      try {
        s = await api.getSettings();
      } catch (e) {
        s = null;
        if (banner && bannerText) {
          bannerText.textContent = describeError(e);
          banner.hidden = false;
        }
      }
      if (!s) {
        if (!(await stillMounted())) return false;
        return false;
      }
      if (banner) banner.hidden = true;

      // await 期间路由可能已经切走，DOM 被整体替换 → 断言会抛 TypeError，
      // 而 router 现在会捕获它，不再是无声的 unhandled rejection
      const provSel = el<HTMLSelectElement>("set-provider");
      const modelSel = el<HTMLSelectElement>("set-model");
      const sizeInput0 = el<HTMLInputElement>("set-size");
      const famSel0 = el<HTMLSelectElement>("set-font-family");
      const sizeNum0 = el<HTMLInputElement>("set-font-size");
      const memInput0 = el<HTMLInputElement>("mem-rounds");
      if (!provSel || !modelSel || !sizeInput0 || !famSel0 || !sizeNum0 || !memInput0) {
        return false; // DOM 已经不属于本视图
      }

      // ---- API ----
      provSel.innerHTML = s.api.providers
        .map((p) => `<option value="${escapeAttr(p.key)}">${escapeHtml(p.name)}</option>`)
        .join("");
      provSel.value = s.api.provider;
      const fillModels = () => {
        const p = s.api.providers.find((x) => x.key === provSel.value);
        const models = p?.models ?? s.api.models;
        modelSel.innerHTML = models.map((m) => `<option>${escapeHtml(m)}</option>`).join("");
        modelSel.value = s.api.model && models.includes(s.api.model) ? s.api.model : (models[0] ?? "");
      };
      fillModels();
      provSel.addEventListener("change", fillModels);
      el("set-key")?.setAttribute(
        "placeholder",
        s.api.keyConfigured ? "已配置（留空则沿用原 Key）" : "sk-…",
      );
      el<HTMLButtonElement>("set-key-toggle")?.addEventListener("click", () => {
        const k = el<HTMLInputElement>("set-key");
        if (k) k.type = k.type === "password" ? "text" : "password";
      });
      const apiPayload = () => ({
        provider: provSel.value,
        model: modelSel.value,
        apiKey: (el<HTMLInputElement>("set-key")?.value ?? "").trim(),
      });

      ctx.root.querySelector("[data-action='api-test']")?.addEventListener("click", async () => {
        setMsg("api-msg", "正在测试连接…", true);
        try {
          const r = await api.testApi(apiPayload());
          setMsg("api-msg", r.message, r.ok);
        } catch (e) {
          setMsg("api-msg", errMsg(e), false);
        }
      });
      ctx.root.querySelector("[data-action='api-save']")?.addEventListener("click", async () => {
        try {
          await api.saveApi(apiPayload());
          setMsg("api-msg", "已保存并即时生效", true);
          const k = el<HTMLInputElement>("set-key");
          if (k) k.value = "";
        } catch (e) {
          setMsg("api-msg", errMsg(e), false);
        }
      });

      // ---- 宠物外观 ----
      const sizeInput = sizeInput0;
      sizeInput.min = String(Math.round(s.pet.minScale * 100));
      sizeInput.max = String(Math.round(s.pet.maxScale * 100));
      sizeInput.value = String(Math.round(s.pet.scale * 100));
      const sizeLabel = el("size-label");
      if (sizeLabel) sizeLabel.textContent = `${sizeInput.value}%`;
      sizeInput.addEventListener("input", () => {
        if (sizeLabel) sizeLabel.textContent = `${sizeInput.value}%`;
      });
      ctx.root.querySelector("[data-action='size-save']")?.addEventListener("click", async () => {
        try {
          // 后端会把 scale 钳到合法区间并回传实际值，用回传值纠正滑杆
          const r = await api.setPetSize(Number(sizeInput.value) / 100);
          const actual = Math.round(r.scale * 100);
          sizeInput.value = String(actual);
          if (sizeLabel) sizeLabel.textContent = `${actual}%`;
          setMsg("size-msg", `已保存 ${actual}%`, true);
        } catch (e) {
          setMsg("size-msg", errMsg(e), false);
        }
      });
      ctx.root.querySelector("[data-action='size-reset']")?.addEventListener("click", () => {
        sizeInput.value = "100";
        if (sizeLabel) sizeLabel.textContent = "100%";
      });

      // ---- 字体 ----
      const famSel = famSel0;
      famSel.innerHTML = s.font.families.map((f) => `<option>${escapeHtml(f)}</option>`).join("");
      famSel.value = s.font.family;
      const sizeNum = sizeNum0;
      sizeNum.min = String(s.font.sizeMin);
      sizeNum.max = String(s.font.sizeMax);
      sizeNum.value = String(s.font.size);
      const preview = el("font-preview");
      const updPreview = () => {
        if (preview) {
          preview.style.fontFamily = famSel.value;
          preview.style.fontSize = `${sizeNum.value}px`;
        }
      };
      famSel.addEventListener("change", updPreview);
      sizeNum.addEventListener("input", updPreview);
      updPreview();
      ctx.root.querySelector("[data-action='font-save']")?.addEventListener("click", async () => {
        try {
          await api.saveFont(famSel.value, Number(sizeNum.value));
          setMsg("font-msg", "已保存并即时生效", true);
        } catch (e) {
          setMsg("font-msg", errMsg(e), false);
        }
      });

      // ---- 系统 ----
      type SysIntervals = Pick<SettingsPayload["system"], "minAutoReply" | "maxAutoReply" | "presetMin" | "presetMax">;
      const sysMap: Record<keyof SysIntervals, string> = {
        minAutoReply: "sys-min",
        maxAutoReply: "sys-max",
        presetMin: "sys-pmin",
        presetMax: "sys-pmax",
      };
      (Object.keys(sysMap) as (keyof typeof sysMap)[]).forEach((k) => {
        const inp = el<HTMLInputElement>(sysMap[k]);
        if (inp) inp.value = String(s.system[k]);
      });
      const readSys = (): SysIntervals => ({
        minAutoReply: Number(el<HTMLInputElement>("sys-min")?.value ?? 0),
        maxAutoReply: Number(el<HTMLInputElement>("sys-max")?.value ?? 0),
        presetMin: Number(el<HTMLInputElement>("sys-pmin")?.value ?? 0),
        presetMax: Number(el<HTMLInputElement>("sys-pmax")?.value ?? 0),
      });
      const setSys = (v: SysIntervals) => {
        (Object.keys(sysMap) as (keyof SysIntervals)[]).forEach((k) => {
          const inp = el<HTMLInputElement>(sysMap[k]);
          if (inp) inp.value = String(v[k]);
        });
      };
      ctx.root.querySelector("[data-action='sys-save']")?.addEventListener("click", async () => {
        try {
          await api.saveSystem(readSys());
          setMsg("sys-msg", "已保存", true);
        } catch (e) {
          setMsg("sys-msg", errMsg(e), false);
        }
      });
      ctx.root.querySelector("[data-action='sys-default']")?.addEventListener("click", () => {
        setSys({ minAutoReply: 60, maxAutoReply: 300, presetMin: 120, presetMax: 600 });
        setMsg("sys-msg", "已填入默认值，记得点保存", true);
      });

      // ---- 聊天记忆（区间与默认值都由后端下发，避免前后端漂移）----
      const memInput = memInput0;
      const memCurrent = el("mem-current");
      const memHint = el("mem-hint-range");
      memInput.min = String(s.system.memoryRoundsMin);
      memInput.max = String(s.system.memoryRoundsMax);
      memInput.value = String(s.system.memoryRounds);
      if (memCurrent) memCurrent.textContent = String(s.system.memoryRounds);
      if (memHint) {
        memHint.textContent = `${s.system.memoryRoundsMin}–${s.system.memoryRoundsMax} 轮`;
      }
      const updMemPreview = () => {
        if (memCurrent) memCurrent.textContent = memInput.value || "—";
      };
      memInput.addEventListener("input", updMemPreview);
      ctx.root.querySelector("[data-action='mem-save']")?.addEventListener("click", async () => {
        const v = Number(memInput.value);
        if (!Number.isFinite(v) || v < s.system.memoryRoundsMin || v > s.system.memoryRoundsMax) {
          setMsg("mem-msg", `请输入 ${s.system.memoryRoundsMin}–${s.system.memoryRoundsMax} 之间的整数`, false);
          return;
        }
        try {
          await api.saveSystem({ memoryRounds: v });
          setMsg("mem-msg", "已保存并即时生效", true);
          updMemPreview();
        } catch (e) {
          setMsg("mem-msg", errMsg(e), false);
        }
      });
      ctx.root.querySelector("[data-action='mem-default']")?.addEventListener("click", () => {
        memInput.value = String(s.system.memoryRoundsDefault);
        updMemPreview();
        setMsg("mem-msg", `已填入默认值 ${s.system.memoryRoundsDefault} 轮，记得点保存`, true);
      });

      // ---- 长期记忆 ----
      let mem: MemoryPayload | null = null;

      const renderMemory = () => {
        const list = el("memory-list");
        const state = el("mem-state");
        const toggle = el<HTMLInputElement>("mem-enabled");
        if (!list) return;
        if (!mem || !mem.available) {
          list.innerHTML = '<div class="chat-empty">长期记忆不可用</div>';
          if (state) state.textContent = "不可用";
          return;
        }
        if (toggle) toggle.checked = mem.enabled;
        if (state) {
          state.textContent = mem.enabled
            ? `已开启 · ${mem.facts.length}${mem.maxFacts ? `/${mem.maxFacts}` : ""} 条`
            : "已关闭（不再提取也不会注入）";
        }
        list.innerHTML = mem.facts.length
          ? mem.facts.map((f) => `
              <div class="memory-item">
                <span class="memory-text">${escapeHtml(f.text)}</span>
                <span class="memory-meta">${escapeHtml(f.created_at || "")}</span>
                <button class="btn btn-sm btn-danger" data-action="mem-del" data-id="${escapeAttr(f.id)}">✕</button>
              </div>`).join("")
          : '<div class="chat-empty">还没有记住什么，多聊几句就有了</div>';
      };

      const loadMemory = async () => {
        try {
          mem = await api.getMemory();
        } catch {
          mem = null;
        }
        renderMemory();
      };

      el<HTMLInputElement>("mem-enabled")?.addEventListener("change", async (e) => {
        const on = (e.target as HTMLInputElement).checked;
        try {
          const r = await api.setMemoryEnabled(on);
          mem = r.memory;
          renderMemory();
        } catch (err) {
          setMsg("mem-msg", errMsg(err), false);
          await loadMemory();
        }
      });
      el("memory-list")?.addEventListener("click", async (e) => {
        const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-action='mem-del']");
        if (!btn) return;
        const id = btn.dataset.id ?? "";
        if (!window.confirm("删除这条记忆？小栗帽会忘掉它。")) return;
        try {
          await api.deleteMemory(id);
        } catch {
          /* ignore */
        }
        await loadMemory();
      });
      ctx.root.querySelector("[data-action='mem-add']")?.addEventListener("click", async () => {
        const inp = el<HTMLInputElement>("mem-new");
        const text = inp?.value.trim() ?? "";
        if (!text) return;
        try {
          const r = await api.addMemory(text);
          mem = r.memory;
          if (inp) inp.value = "";
          renderMemory();
        } catch (err) {
          setMsg("mem-msg", errMsg(err), false);
        }
      });
      ctx.root.querySelector("[data-action='mem-clear']")?.addEventListener("click", async () => {
        if (!window.confirm("清空全部长期记忆？此操作不可恢复。")) return;
        try {
          await api.clearMemory();
        } catch {
          /* ignore */
        }
        await loadMemory();
      });

      // ---- 进程 ----
      const autoCb = el<HTMLInputElement>("auto-start");
      if (autoCb) {
        autoCb.checked = s.systemExtra.autostart;
        autoCb.disabled = !s.systemExtra.autostartSupported;
      }
      setTextById("data-dir", s.systemExtra.dataDir || "未知");
      el<HTMLInputElement>("auto-start")?.addEventListener("change", async (e) => {
        const on = (e.target as HTMLInputElement).checked;
        try {
          const r = await api.setAutostart(on);
          setMsg("proc-msg", r.message, r.ok);
          const cb = el<HTMLInputElement>("auto-start");
          if (cb) cb.checked = r.enabled;
        } catch (err) {
          setMsg("proc-msg", errMsg(err), false);
          const cb = el<HTMLInputElement>("auto-start");
          if (cb) cb.checked = !on;
        }
      });
      ctx.root.querySelector("[data-action='restart']")?.addEventListener("click", async () => {
        if (!window.confirm("确定要重启桌宠吗？重启后页面需用新地址重新打开。")) return;
        try {
          await api.restartPet();
          setMsg("proc-msg", "已发出重启指令，连接即将断开", true);
        } catch (e) {
          setMsg("proc-msg", errMsg(e), false);
        }
      });
      ctx.root.querySelector("[data-action='quit']")?.addEventListener("click", async () => {
        if (!window.confirm("确定要退出桌宠吗？")) return;
        try {
          await api.quitPet();
          setMsg("proc-msg", "已发出退出指令", true);
        } catch (e) {
          setMsg("proc-msg", errMsg(e), false);
        }
      });

      void loadMemory();

      return true;
    };

    /** DOM 是否仍属于本视图（路由切走后 #view-root 会被整体替换） */
    const stillMounted = async (): Promise<boolean> =>
      ctx.root.contains(document.getElementById("settings-load-error"));

    await bind();
  },
};