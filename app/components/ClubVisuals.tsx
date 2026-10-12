import { BookOpen, Code2, Cpu, FileText, ScanEye, Trophy, Boxes, Bot } from "lucide-react";
import { resolveMarkdownUrl } from "@/app/lib/api";

const tracks = {
  "deep-learning": { image: "/visuals/cuhkx.gif", label: "CUHK-X", alt: "CUHK-X 人体动作数据示例", icon: ScanEye, source: "https://github.com/openaiotlab/CUHK-X" },
  "world-exploration": { image: "/visuals/minedojo.webp", label: "MineDojo", alt: "仿真开放世界场景", icon: Boxes, source: "https://minedojo.org/" },
  "embodied-agent": { image: "/visuals/libero-tasks.webp", label: "LIBERO", alt: "LIBERO 机械臂操作场景", icon: Bot, source: "https://libero-project.github.io/main.html" },
};
type TrackKey = keyof typeof tracks;
export { trackSummary } from "@/app/lib/wujiePresentation";
export function trackVisualKey(value: string): TrackKey | undefined {
  if (/deep-learning|human-activity|观行知意|人体|深度学习/.test(value)) return "deep-learning";
  if (/world-exploration|open-world|无界探索|世界探索|Minecraft/i.test(value)) return "world-exploration";
  if (/embodied-agent|robot-arm|慧眼巧手|具身|机械臂|LIBERO/i.test(value)) return "embodied-agent";
}
export function TrackVisual({ value, className = "", source = false }: { value: string; className?: string; source?: boolean }) {
  const key = trackVisualKey(value); if (!key) return null;
  const item = tracks[key]; const Icon = item.icon;
  return <figure className={`club-track-visual visual-${key} ${className}`}>
    {/* Real project assets retain their original colors. */}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={item.image} alt={item.alt} loading="lazy" />
    <span className="visual-project-label"><Icon size={17} />{item.label}</span>
    {source && <figcaption><a href={item.source} target="_blank" rel="noreferrer">{item.label} 项目原页 ↗</a></figcaption>}
  </figure>;
}
export function CompetitionPoster({ className = "" }: { className?: string }) {
  return <a className={`competition-poster ${className}`} href="/visuals/wujie-poster.png" target="_blank" rel="noreferrer" aria-label="查看无界杯完整海报">
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src="/visuals/wujie-poster.webp" alt="2026 无界杯 UESTC AI 挑战赛海报" loading="lazy" width={1086} height={1448} />
  </a>;
}
export function ArticleVisual({ title, slug = "", body = "", className = "" }: { title: string; slug?: string; body?: string; className?: string }) {
  const key = trackVisualKey(`${title} ${slug}`);
  if (key) return <TrackVisual value={key} className={className} />;
  const explicitImage = body.match(/!\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)/)?.[1];
  const image = explicitImage ? resolveMarkdownUrl(explicitImage) : /无界杯|wujie/.test(title + slug) ? "/visuals/wujie-poster.webp" : /AI社|AI 社|uestc-ai-club/.test(title + slug) ? "/ai-mascot.webp" : undefined;
  const Icon = /论文|研究/.test(title) ? BookOpen : /项目|代码|工具/.test(title) ? Code2 : FileText;
  return <div className={`article-cover ${image ? (image === "/ai-mascot.webp" ? "has-image cover-mascot" : "has-image") : "cover-icon"} ${className}`}>
    {image ? <img src={image} alt="" loading="lazy" /> : <Icon size={54} strokeWidth={1.2} />}
  </div>;
}
export const clubEntryIcons = { competitions: Trophy, articles: BookOpen, projects: Code2, api: Cpu };
