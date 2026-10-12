import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";

export default function AboutPage() {
  return (
    <AppShell title="关于我们" eyebrow="ABOUT UESTC AI">
      <section className="about-page" aria-labelledby="about-page-statement">
        <span className="about-page-mark">UESTC / AI</span>
        <div className="about-layout">
          <h2 id="about-page-statement" className="about-statement">从浩瀚数据中提炼世界规律，把复杂压缩为你能理解的语言与行动。</h2>
          <div className="about-copy">
            <p>我们相信智能的核心是同理心，真正的价值在于与人链接。UESTC AI 社不只是屏幕背后的工具，更希望成为你现实中的伙伴。</p>
            <p>读懂你的文字，看见你的世界，激发你的灵感，与你共同探索智能的边界。</p>
            <div className="about-links">
              <Link href="/competitions">探索赛事 <ArrowRight size={15} /></Link>
              <Link href="/works">查看作品 <ArrowRight size={15} /></Link>
              <Link href="/news">阅读动态 <ArrowRight size={15} /></Link>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
