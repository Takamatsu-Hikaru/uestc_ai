// Public introduction aligned with the organizer's 2026-10-13 PDF.
// Task statements, scoring, compute quotas and runtime configuration remain unchanged.
export const WUJIE_SLUG = "wujie-cup-2026";
export const WUJIE_SUMMARY = "「无界杯」是电子科技大学 AI 社主办的首届 AI 比赛，设计算机视觉、Agent 和具身智能三个赛道，分别围绕动作识别、开放世界探索和机械臂操作展开。";

const tracks: Record<string, { name: string; direction: string; summary: string }> = {
  "deep-learning": { name: "A 赛道 · 观行知意", direction: "计算机视觉 · 深度学习", summary: "根据深度视频识别喝水、扫地等 40 类日常动作，完成数据处理与分类模型训练，并根据验证结果改进方法。" },
  "world-exploration": { name: "B 赛道 · 无界探索", direction: "Agent · 开放世界探索", summary: "设计智能体，在仿真开放世界中采集资源、制作工具，逐步完成木制、石器和铁器工具链，并根据环境反馈调整计划。" },
  "embodied-agent": { name: "C 赛道 · 慧眼巧手", direction: "具身智能 · 机器人操作", summary: "开发智能体，在 LIBERO 仿真环境中识别桌面物品、控制机械臂，将碗、罐子等物品抓取并放到指定位置。" },
};

export function competitionSummary(slug: string, fallback: string) {
  return slug === WUJIE_SLUG ? WUJIE_SUMMARY : fallback;
}
export function trackSummary(slug: string, fallback: string) {
  return tracks[slug]?.summary ?? fallback;
}
export function trackName(slug: string, fallback: string) {
  return tracks[slug]?.name ?? fallback;
}
export function trackDirection(slug: string, fallback: string) {
  return tracks[slug]?.direction ?? fallback;
}

export function competitionOverview(slug: string, markdown: string) {
  if (slug !== WUJIE_SLUG) return markdown;
  // Only update the introduction and promotional labels; retain the detailed rules.
  return markdown
    .replace(/^# [^\r\n]+\r?\n[\s\S]*?(?=## 三条赛道)/, "")
    .replace("面向电子科技大学全校同学，欢迎跨专业组队，在具体任务中完成模型训练、智能体开发与实验验证。计算机学院主办、经管学院协办，AI社与计算机学院学生会承办；奖金总额 **30,000元**。", "由 **电子科技大学 AI 社主办**，主要面向 **2025、2026 级本科生**，同时欢迎其他年级及硕博同学参与。一队一至三人，一人仅限一队。")
    .replace("深度学习 · 观行知意", "A 赛道 · 观行知意")
    .replace("世界探索智能体 · 无界探索", "B 赛道 · 无界探索")
    .replace("具身智能体 · 慧眼巧手", "C 赛道 · 慧眼巧手")
    .replace("Minecraft未知世界中的", "仿真开放世界中的")
    .replace("，奖项明细另行公告。", "。");
}
