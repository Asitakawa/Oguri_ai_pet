import { gsap } from "gsap";
import type { Ctx, View } from "./types";
import { api } from "../api/client";
import type { SettingsPayload } from "../api/types";

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

export const Settings: View = {
  id: "settings",
  title: "设置",
  icon: "⚙️",
  render() {
    return `
    <div class="view view-settings">
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
        <header class="card-head"><span class="card-icon">⚙</span><h3>系统设置</h3></header>
        <div class="form-grid cols-3">
          <label>AI 最短间隔(s)<input id="sys-min" class="input" type="number" /></label>
          <label>AI 最长间隔(s)<input id="sys-max" class="input" type="number" /></label>
          <label>预设最短间隔(s)<input id="sys-pmin" class="input" type="number" /></label>
          <label>预设最长间隔(s)<input id="sys-pmax" class="input" type="number" /></label>
          <label>记忆轮数<input id="sys-mem" class="input" type="number" /></label>
        </div>
        <div class="row-end">
          <span class="form-msg" id="sys-msg"></span>
          <button class="btn" data-action="sys-default">↺ 恢复默认</button>
          <button class="btn btn-primary" data-action="sys-save">💾 保存</button>
        </div>
      </section>

      <section class="glass-card">
        <header class="card-head"><span class="card-icon">🖥️</span><h3>进程控制</h3></header>
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

    const s = await api.getSettings().catch(() => null);
    if (!s) {
      setMsg("api-msg", "无法加载设置（未连接桌宠）", false);
      return;
    }

    // ---- API ----
    const provSel = el<HTMLSelectElement>("set-provider")!;
    const modelSel = el<HTMLSelectElement>("set-model")!;
    provSel.innerHTML = s.api.providers
      .map((p) => `<option value="${p.key}">${p.name}</option>`)
      .join("");
    provSel.value = s.api.provider;
    const fillModels = () => {
      const p = s.api.providers.find((x) => x.key === provSel.value);
      const models = p?.models ?? s.api.models;
      modelSel.innerHTML = models.map((m) => `<option>${m}</option>`).join("");
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
    const sizeInput = el<HTMLInputElement>("set-size")!;
    sizeInput.min = String(Math.round(s.pet.minScale * 100));
    sizeInput.max = String(Math.round(s.pet.maxScale * 100));
    sizeInput.value = String(Math.round(s.pet.scale * 100));
    const sizeLabel = el("size-label");
    sizeInput.addEventListener("input", () => {
      if (sizeLabel) sizeLabel.textContent = `${sizeInput.value}%`;
    });
    ctx.root.querySelector("[data-action='size-save']")?.addEventListener("click", async () => {
      try {
        await api.setPetSize(Number(sizeInput.value) / 100);
        setMsg("size-msg", "已保存", true);
      } catch (e) {
        setMsg("size-msg", errMsg(e), false);
      }
    });
    ctx.root.querySelector("[data-action='size-reset']")?.addEventListener("click", () => {
      sizeInput.value = "100";
      if (sizeLabel) sizeLabel.textContent = "100%";
    });

    // ---- 字体 ----
    const famSel = el<HTMLSelectElement>("set-font-family")!;
    famSel.innerHTML = s.font.families.map((f) => `<option>${f}</option>`).join("");
    famSel.value = s.font.family;
    const sizeNum = el<HTMLInputElement>("set-font-size")!;
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
        setMsg("font-msg", "已保存（气泡字体下次生效）", true);
      } catch (e) {
        setMsg("font-msg", errMsg(e), false);
      }
    });

    // ---- 系统 ----
    const sysMap = {
      minAutoReply: "sys-min",
      maxAutoReply: "sys-max",
      presetMin: "sys-pmin",
      presetMax: "sys-pmax",
      memoryRounds: "sys-mem",
    } as const;
    (Object.keys(sysMap) as (keyof typeof sysMap)[]).forEach((k) => {
      const inp = el<HTMLInputElement>(sysMap[k]);
      if (inp) inp.value = String(s.system[k]);
    });
    const readSys = () => ({
      minAutoReply: Number(el<HTMLInputElement>("sys-min")?.value ?? 0),
      maxAutoReply: Number(el<HTMLInputElement>("sys-max")?.value ?? 0),
      presetMin: Number(el<HTMLInputElement>("sys-pmin")?.value ?? 0),
      presetMax: Number(el<HTMLInputElement>("sys-pmax")?.value ?? 0),
      memoryRounds: Number(el<HTMLInputElement>("sys-mem")?.value ?? 0),
    });
    const setSys = (v: SettingsPayload["system"]) => {
      (Object.keys(sysMap) as (keyof typeof sysMap)[]).forEach((k) => {
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
      setSys({ minAutoReply: 60, maxAutoReply: 300, presetMin: 120, presetMax: 600, memoryRounds: 200 });
      setMsg("sys-msg", "已填入默认值，记得点保存", true);
    });

    // ---- 进程 ----
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
  },
};