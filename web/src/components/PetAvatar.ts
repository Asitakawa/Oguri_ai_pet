// 手写 SVG 小栗帽（chibi 头像），配合 CSS 呼吸/耳朵/眨眼动画
export function petAvatarHTML(): string {
  return `
  <div class="pet-avatar-wrap" aria-label="小栗帽">
    <svg viewBox="0 0 200 200" class="pet-avatar">
      <!-- 后发（灰蓝） -->
      <path d="M58 118 C52 66 76 52 100 50 C124 52 148 66 142 118 C150 148 138 172 120 184 C100 196 80 196 62 184 C44 172 50 148 58 118 Z" fill="var(--c-ash)"/>
      <!-- 耳朵 -->
      <path class="pet-ear pet-ear-l" d="M62 76 L42 40 L76 54 Z" fill="var(--c-ash)"/>
      <path class="pet-ear pet-ear-l" d="M57 70 L50 54 L66 60 Z" fill="var(--c-rose)"/>
      <path class="pet-ear pet-ear-r" d="M138 76 L158 40 L124 54 Z" fill="var(--c-ash)"/>
      <path class="pet-ear pet-ear-r" d="M143 70 L150 54 L134 60 Z" fill="var(--c-rose)"/>
      <!-- 脸 -->
      <ellipse cx="100" cy="112" rx="46" ry="48" fill="var(--c-cream)"/>
      <!-- 前发（深灰蓝） -->
      <path d="M56 96 C56 62 78 46 100 44 C122 46 144 62 144 96 C134 76 118 68 100 66 C82 68 66 76 56 96 Z" fill="var(--c-ash-dark)"/>
      <!-- 白色流星刘海 -->
      <path d="M88 58 C94 52 106 52 112 58 C110 78 104 90 100 92 C96 90 90 78 88 58 Z" fill="#fffefb"/>
      <!-- 眼睛 -->
      <ellipse class="pet-eye" cx="78" cy="114" rx="9" ry="11" fill="var(--c-wood)"/>
      <circle cx="75" cy="110" r="3" fill="#fffefb"/>
      <ellipse class="pet-eye" cx="122" cy="114" rx="9" ry="11" fill="var(--c-wood)"/>
      <circle cx="119" cy="110" r="3" fill="#fffefb"/>
      <!-- 腮红 -->
      <ellipse cx="64" cy="132" rx="9" ry="5" fill="var(--c-rose)" opacity="0.85"/>
      <ellipse cx="136" cy="132" rx="9" ry="5" fill="var(--c-rose)" opacity="0.85"/>
      <!-- 嘴 -->
      <path d="M92 134 Q100 142 108 134" stroke="var(--c-wood)" stroke-width="3" fill="none" stroke-linecap="round"/>
    </svg>
  </div>`;
}