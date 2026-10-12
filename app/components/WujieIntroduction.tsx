import { FileDown } from "lucide-react";

const taskDocuments = [
  { slug: "deep-learning", name: "观行知意" },
  { slug: "world-exploration", name: "无界探索" },
  { slug: "embodied-agent", name: "慧眼巧手" },
];

export function WujieTaskDocuments({ trackSlug }: { trackSlug?: string }) {
  return <div className="wujie-task-documents" aria-label="赛题介绍">{taskDocuments.filter(item => !trackSlug || item.slug === trackSlug).map(item =>
    <a className="wujie-document-link" key={item.slug} href={`/documents/wujie-${item.slug}.pdf`} target="_blank" rel="noreferrer"><FileDown size={16} /><span>{trackSlug ? "赛题介绍" : `${item.name} · 赛题介绍`} <small>PDF</small></span></a>
  )}</div>;
}

export function WujieAudience() {
  return <p className="wujie-audience">主要面向 <strong>2025、2026 级本科生</strong>，同时欢迎其他年级及硕博同学参与。每队 1—3 人，每人限报一队。</p>;
}

export function WujiePrizes() {
  return <section className="wujie-prizes" aria-label="奖金设置">
    <h3>奖金设置</h3>
    <p>总奖池 30,000 元，三个赛道分别设奖：</p>
    <ul>
      <li>一等奖 3,000 元 / 队，每赛道 1 队</li>
      <li>二等奖 2,000 元 / 队，每赛道 2 队</li>
      <li>三等奖 1,000 元 / 队，每赛道 3 队</li>
    </ul>
  </section>;
}
