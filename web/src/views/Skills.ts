import { gsap } from "gsap";
import type { Ctx, View } from "./types";
import { api } from "../api/client";
import type { SkillParam } from "../api/types";
import { escapeHtml } from "../utils";

const errMsg = (e: unknown) => String((e as Error)?.message ?? e);

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => {
      const s = String(r.result ?? "");
      resolve(s.slice(s.indexOf(",") + 1));
    };
    r.onerror = () => reject(new Error("读取文件失败"));
    r.readAsDataURL(file);
  });
}

function paramInput(p: SkillParam): string {
  const typeAttr = p.type === "boolean" ? "type=\"checkbox\"" : p.type === "number" ? "type=\"number\"" : "type=\"text\"";
  return `
  <label class="param-field">${escapeHtml(p.name)}${p.required ? " *" : ""}
    <input class="input" data-param="${escapeHtml(p.name)}" data-type="${p.type}" ${typeAttr} placeholder="${escapeHtml(p.description || p.type)}" />
  </label>`;
}

export const Skills: View = {
  id: "skills",
  title: "技能",
  icon: "⚡",
  render() {
    return `
    <div class="view view-skills">
      <section class="glass-card">
        <header class="card-head">
          <span class="card-icon">⚡</span><h3>技能管理</h3>
          <span class="spacer"></span>
          <input type="file" id="skill-file" accept=".py,.zip" hidden />
          <button class="btn" data-action="import">+ 导入技能</button>
          <button class="btn" data-action="refresh">↺ 刷新</button>
        </header>
        <div class="skill-list" id="skill-list"><div class="chat-empty">加载中…</div></div>
      </section>
      <section class="glass-card skill-detail" id="skill-detail" hidden></section>
    </div>`;
  },
  async mount(ctx: Ctx) {
    gsap.from(".view-skills .glass-card", { opacity: 0, y: 16, duration: 0.35, ease: "power2.out" });

    const listEl = () => document.getElementById("skill-list");
    const detailEl = () => document.getElementById("skill-detail");

    const load = async () => {
      try {
        const { skills } = await api.getSkills();
        const el = listEl();
        if (el) {
          el.innerHTML = skills.length
            ? skills.map((s) => `
              <div class="skill-card">
                <div class="skill-head">
                  <b>${escapeHtml(s.name)}</b>
                  <span class="badge ${s.enabled ? "" : "badge-off"}">${s.enabled ? "已启用" : "已停用"}</span>
                </div>
                <p class="skill-desc">${escapeHtml(s.description || "（无描述）")}</p>
                <div class="skill-actions">
                  <label class="switch" title="启用/停用">
                    <input type="checkbox" data-name="${escapeHtml(s.name)}" ${s.enabled ? "checked" : ""}/>
                    <span></span>
                  </label>
                  <button class="btn btn-sm" data-action="detail" data-name="${escapeHtml(s.name)}">📖 详情</button>
                  <button class="btn btn-sm btn-danger" data-action="delete" data-name="${escapeHtml(s.name)}">🗑 删除</button>
                </div>
              </div>`).join("")
            : '<div class="chat-empty">还没有技能，点「+ 导入技能」添加</div>';
        }
      } catch {
        const el = listEl();
        if (el) el.innerHTML = '<div class="chat-empty">无法加载技能（未连接桌宠）</div>';
      }
    };

    const showDetail = async (name: string) => {
      const el = detailEl();
      if (!el) return;
      try {
        const d = await api.getSkillDetail(name);
        el.hidden = false;
        el.innerHTML = `
          <header class="card-head">
            <span class="card-icon">📖</span><h3>${escapeHtml(d.name)}</h3>
            <span class="spacer"></span>
            <button class="btn btn-sm" data-action="detail-close">✕ 关闭</button>
          </header>
          <div class="skill-meta">目录：${escapeHtml(d.dirname)} · 状态：${d.enabled ? "已启用" : "已停用"}</div>
          <div class="skill-desc">${escapeHtml(d.description || "（无描述）")}</div>
          <h4>参数表（喂给 AI 的 function schema）</h4>
          ${d.parameters.length ? `
            <table class="param-table">
              <thead><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr></thead>
              <tbody>${d.parameters.map((p) => `
                <tr><td><code>${escapeHtml(p.name)}</code></td><td>${escapeHtml(p.type)}</td><td>${p.required ? "是" : "否"}</td><td>${escapeHtml(p.description || "")}</td></tr>`).join("")}</tbody>
            </table>` : '<div class="chat-empty">无参数</div>'}
          <h4>SKILL.md 原文</h4>
          <pre class="skill-md">${escapeHtml(d.skillMd || "（无）")}</pre>
          <h4>手动测试执行</h4>
          <div class="skill-test">
            ${d.parameters.length ? d.parameters.map(paramInput).join("") : '<div class="chat-empty">该技能无参数，直接执行</div>'}
            <div class="row-end">
              <span class="form-msg" id="skill-test-msg"></span>
              <button class="btn btn-primary" data-action="execute" data-name="${escapeHtml(d.name)}">▶ 执行</button>
            </div>
            <pre class="skill-result" id="skill-result" hidden></pre>
          </div>`;
      } catch {
        el.hidden = false;
        el.innerHTML = '<div class="chat-empty">无法加载技能详情（未连接桌宠）</div>';
      }
    };

    listEl()?.addEventListener("click", async (e) => {
      const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-action]");
      if (!btn) return;
      const name = btn.dataset.name ?? "";
      if (btn.dataset.action === "detail") {
        await showDetail(name);
      } else if (btn.dataset.action === "delete") {
        if (!window.confirm(`确定删除技能「${name}」？目录和文件将被完全移除，不可恢复。`)) return;
        try {
          await api.deleteSkill(name);
          if (detailEl()) detailEl()!.hidden = true;
          await load();
        } catch {
          /* ignore */
        }
      }
    });

    listEl()?.addEventListener("change", async (e) => {
      const t = e.target as HTMLInputElement;
      if (t.type !== "checkbox" || !t.dataset.name) return;
      try {
        await api.toggleSkill(t.dataset.name, t.checked);
      } catch {
        t.checked = !t.checked;
      }
    });

    detailEl()?.addEventListener("click", async (e) => {
      const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-action]");
      if (!btn) return;
      if (btn.dataset.action === "detail-close") {
        if (detailEl()) detailEl()!.hidden = true;
        return;
      }
      if (btn.dataset.action === "execute") {
        const name = btn.dataset.name ?? "";
        const args: Record<string, unknown> = {};
        detailEl()?.querySelectorAll<HTMLInputElement>("[data-param]").forEach((inp) => {
          const pname = inp.dataset.param ?? "";
          const ptype = inp.dataset.type ?? "string";
          if (ptype === "boolean") {
            args[pname] = inp.checked;
          } else if (ptype === "number") {
            if (inp.value !== "") args[pname] = Number(inp.value);
          } else if (inp.value.trim() !== "") {
            args[pname] = inp.value.trim();
          }
        });
        const msg = document.getElementById("skill-test-msg");
        const result = document.getElementById("skill-result");
        if (msg) {
          msg.textContent = "执行中…";
          msg.classList.add("ok");
          msg.classList.remove("err");
        }
        try {
          const r = await api.executeSkill(name, args);
          if (msg) {
            msg.textContent = "执行完成";
            msg.classList.add("ok");
            msg.classList.remove("err");
          }
          if (result) {
            result.hidden = false;
            result.textContent = r.result || "（无返回）";
          }
        } catch (err) {
          if (msg) {
            msg.textContent = errMsg(err);
            msg.classList.add("err");
            msg.classList.remove("ok");
          }
        }
      }
    });

    ctx.root.querySelector("[data-action='refresh']")?.addEventListener("click", () => void load());
    ctx.root.querySelector("[data-action='import']")?.addEventListener("click", () => {
      const f = document.getElementById("skill-file") as HTMLInputElement | null;
      if (f) f.click();
    });
    const fileInput = document.getElementById("skill-file") as HTMLInputElement | null;
    fileInput?.addEventListener("change", async () => {
      const f = fileInput.files?.[0];
      if (!f) return;
      try {
        const b64 = await fileToBase64(f);
        const r = await api.importSkill(f.name, b64);
        if (r.ok) await load();
        else window.alert(r.message || "导入失败");
      } catch (err) {
        window.alert(errMsg(err));
      } finally {
        fileInput.value = "";
      }
    });

    void load();
  },
};