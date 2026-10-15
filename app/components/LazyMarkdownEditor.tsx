"use client";
import { lazy, Suspense } from "react";
import type { ComponentProps } from "react";
import type { MarkdownEditor as Editor } from "@/app/components/MarkdownEditor";
const MarkdownEditor = lazy(() => import("@/app/components/MarkdownEditor").then((module) => ({ default: module.MarkdownEditor })));

export function LazyMarkdownEditor(props: ComponentProps<typeof Editor>) {
  return <Suspense fallback={<label className="form-field"><span>{props.label}</span>
    <textarea name={props.name} value={props.value} required={props.required}
      rows={12} onChange={(event) => props.onChange(event.target.value)} />
    <small role="status">编辑器正在加载，可先填写内容。</small></label>}>
    <MarkdownEditor {...props} />
  </Suspense>;
}
