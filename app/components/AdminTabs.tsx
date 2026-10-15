"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { KeyRound, Mail, ScrollText, Users } from "lucide-react";

const items = [
  { href: "/admin/users", label: "用户与角色", icon: Users },
  { href: "/admin/invites", label: "注册邀请码", icon: KeyRound },
  { href: "/admin/mail", label: "邮件服务", icon: Mail },
  { href: "/admin/audit", label: "审计记录", icon: ScrollText },
];

export function AdminTabs() {
  const pathname = usePathname();
  return <nav className="admin-tabs" aria-label="系统管理">{items.map(({ href, label, icon: Icon }) => <Link className={pathname.startsWith(href) ? "active" : ""} href={href} key={href}><Icon size={15} />{label}</Link>)}</nav>;
}
