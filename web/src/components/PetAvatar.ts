// 手写 SVG 小栗帽（chibi 头像 v3）：栗色头发 + 白色脸 + 鱼尾白流星 + 琥珀眼
// 配合 CSS 呼吸/耳朵/眨眼动画
export function petAvatarHTML(): string {
  return `
  <div class="pet-avatar-wrap" aria-label="小栗帽">
    <svg viewBox="0 0 200 200" class="pet-avatar">
      <defs>
        <linearGradient id="hairG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#6d453c"/>
          <stop offset="0.55" stop-color="#452c27"/>
          <stop offset="1" stop-color="#2a1b1c"/>
        </linearGradient>
        <linearGradient id="faceG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#fffdf6"/>
          <stop offset="1" stop-color="#f9e9dc"/>
        </linearGradient>
        <linearGradient id="earG" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#5c3d36"/>
          <stop offset="1" stop-color="#33201f"/>
        </linearGradient>
        <radialGradient id="eyeG" cx="0.4" cy="0.35" r="0.8">
          <stop offset="0" stop-color="#edae62"/>
          <stop offset="0.55" stop-color="#a05f2c"/>
          <stop offset="1" stop-color="#4a2a16"/>
        </radialGradient>
      </defs>

      <!-- 后发（栗色） -->
      <path d="M100 16 C68 16 40 32 36 64 C33 86 40 110 50 130 C60 152 76 166 90 172 C97 175 103 175 110 172 C124 166 140 152 150 130 C160 110 167 86 164 64 C160 32 132 16 100 16 Z" fill="url(#hairG)"/>
      <!-- 耳朵（栗外耳 + 粉内耳） -->
      <path class="pet-ear pet-ear-l" d="M42 66 C34 38 52 18 74 26 C79 40 70 58 56 70 C50 75 44 72 42 66 Z" fill="url(#earG)"/>
      <path class="pet-ear pet-ear-l" d="M51 60 C47 44 57 34 68 36 C70 46 65 55 57 61 Z" fill="#f0b0a2"/>
      <path class="pet-ear pet-ear-r" d="M158 66 C166 38 148 18 126 26 C121 40 130 58 144 70 C150 75 156 72 158 66 Z" fill="url(#earG)"/>
      <path class="pet-ear pet-ear-r" d="M149 60 C153 44 143 34 132 36 C130 46 135 55 143 61 Z" fill="#f0b0a2"/>
      <!-- 脸（白色） -->
      <path d="M100 70 C134 70 155 92 155 120 C155 150 134 170 100 170 C66 170 45 150 45 120 C45 92 66 70 100 70 Z" fill="url(#faceG)"/>
      <!-- 前发 / 刘海（栗色） -->
      <path d="M48 102 C47 62 70 44 100 42 C130 44 153 62 152 102 C148 86 136 72 118 70 C130 78 138 92 136 104 C130 84 116 74 100 72 C84 74 70 84 64 104 C62 92 70 78 82 70 C64 72 52 84 48 102 Z" fill="url(#hairG)"/>
      <!-- 头发高光：几缕亮栗色发丝 -->
      <path d="M62 46 Q82 34 102 34" stroke="#8a5a50" stroke-width="3.2" fill="none" stroke-linecap="round" opacity="0.55"/>
      <path d="M70 54 Q88 44 104 44" stroke="#8a5a50" stroke-width="2.4" fill="none" stroke-linecap="round" opacity="0.4"/>
      <path d="M118 34 Q138 40 150 54" stroke="#8a5a50" stroke-width="2.4" fill="none" stroke-linecap="round" opacity="0.35"/>
      <!-- 白色流星（额头） -->
      <path d="M100 52 C106 46 117 49 119 57 C121 74 111 88 100 92 C89 88 79 74 81 57 C83 49 94 46 100 52 Z" fill="#fffdf6"/>
      <!-- 眼睛（大而有神） -->
      <g class="pet-eye">
        <ellipse cx="74" cy="122" rx="13" ry="16" fill="#ffffff"/>
        <circle cx="74" cy="123" r="10" fill="url(#eyeG)"/>
        <circle cx="75" cy="125" r="4.5" fill="#2e1c10"/>
        <circle cx="70" cy="118" r="3.2" fill="#ffffff"/>
        <circle cx="77" cy="126" r="1.6" fill="#ffffff" opacity="0.85"/>
        <path d="M58 110 Q74 101 90 110" stroke="#4a3a36" stroke-width="2.5" fill="none" stroke-linecap="round"/>
      </g>
      <g class="pet-eye">
        <ellipse cx="126" cy="122" rx="13" ry="16" fill="#ffffff"/>
        <circle cx="126" cy="123" r="10" fill="url(#eyeG)"/>
        <circle cx="127" cy="125" r="4.5" fill="#2e1c10"/>
        <circle cx="122" cy="118" r="3.2" fill="#ffffff"/>
        <circle cx="129" cy="126" r="1.6" fill="#ffffff" opacity="0.85"/>
        <path d="M142 110 Q126 101 110 110" stroke="#4a3a36" stroke-width="2.5" fill="none" stroke-linecap="round"/>
      </g>
      <!-- 腮红 -->
      <ellipse cx="55" cy="143" rx="10" ry="5.5" fill="#eba08e" opacity="0.5"/>
      <ellipse cx="145" cy="143" rx="10" ry="5.5" fill="#eba08e" opacity="0.5"/>
      <!-- 嘴（微笑 + 舌） -->
      <path d="M86 152 Q100 163 114 152 Q100 158 86 152 Z" fill="#e89a88"/>
      <path d="M84 150 Q100 160 116 150" stroke="#8a5a50" stroke-width="2.6" fill="none" stroke-linecap="round"/>
    </svg>
  </div>`;
}
