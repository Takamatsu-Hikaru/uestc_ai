import Link from "next/link";
import { ArrowRight, BookOpen, Trophy, Code2, MessageCircle } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
export default function AboutPage() {
  return <AppShell title="关于 AI 社" eyebrow="UESTC AI">
    <section className="club-about-intro"><img src="/visuals/ai-club-logo.png" alt="UESTC AI 社" width={150} height={150} /><div><h2>电子科技大学 AI 社</h2><p>AI 社的同学在这里<strong>学习、做项目，也交流研究和实践中的想法</strong>。入门指南整理了课程、论文与工具，无界杯提供三条不同的赛道；自己的项目和技术笔记，也可以在社区分享。</p></div></section>
    <figure className="club-overview-figure"><a href="/visuals/ai-club-overview.svg" target="_blank" rel="noreferrer"><img src="/visuals/ai-club-overview.svg" alt="AI 社的入门指南、无界杯、项目作品、交流与平台资源总览" width={1680} height={960} /></a></figure>
    <div className="club-about-links"><a href="https://wiki.uestcai.top/" target="_blank" rel="noreferrer"><BookOpen /><strong>AI 科研入门指南</strong><ArrowRight /></a><Link href="/competitions"><Trophy /><strong>无界杯</strong><ArrowRight /></Link><Link href="/works"><Code2 /><strong>项目与作品</strong><ArrowRight /></Link><Link href="/news"><MessageCircle /><strong>文章与交流</strong><ArrowRight /></Link></div>
  </AppShell>;
}
