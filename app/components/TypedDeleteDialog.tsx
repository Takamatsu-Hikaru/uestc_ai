"use client";

import { useEffect, useId, useRef, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { matchesConfirmation } from "@/app/lib/typedConfirm";

export type ImpactItem = { label: string; count: number };

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), [href], select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function TypedDeleteDialog(props: DialogProps) {
  // Mounting the body only while open resets the typed text on every open.
  return props.open ? <TypedDeleteDialogBody {...props} /> : null;
}

type DialogProps = {
  open: boolean;
  title: string;
  warning: string;
  impactItems: ImpactItem[];
  loading?: boolean;
  loadError?: string;
  blockers?: string[];
  expected: string;
  caseInsensitive?: boolean;
  inputLabel: string;
  confirmLabel?: string;
  busy?: boolean;
  error?: string;
  secondaryAction?: { label: string; onClick: () => void; busy?: boolean };
  onCancel: () => void;
  onConfirm: (text: string) => void;
};

function TypedDeleteDialogBody({
  title,
  warning,
  impactItems,
  loading = false,
  loadError,
  blockers = [],
  expected,
  caseInsensitive = false,
  inputLabel,
  confirmLabel = "永久删除",
  busy = false,
  error,
  secondaryAction,
  onCancel,
  onConfirm,
}: DialogProps) {
  const id = useId();
  const [text, setText] = useState("");
  const root = useRef<HTMLElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const canDelete = !loading && !loadError && blockers.length === 0 && !busy && matchesConfirmation(expected, text, caseInsensitive);

  useEffect(() => {
    trigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancelButton.current?.focus();
    return () => trigger.current?.focus();
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab" || !root.current) return;
      const items = Array.from(root.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (!root.current.contains(active)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [busy, onCancel]);

  return <div className="dialog-layer" role="presentation" onMouseDown={(event) => {
    if (event.target === event.currentTarget && !busy) onCancel();
  }}>
    <section ref={root} className="confirm-dialog typed-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby={`${id}-title`} aria-describedby={`${id}-warning`}>
      <header><span className="dialog-alert-icon"><AlertTriangle size={19} /></span><button className="icon-button" type="button" onClick={onCancel} disabled={busy} aria-label="关闭删除窗口"><X size={18} /></button></header>
      <h2 id={`${id}-title`}>{title}</h2>
      <p id={`${id}-warning`} className="dialog-warning">{warning}</p>
      {loading ? <p role="status">正在统计将被删除的数据…</p> : loadError ? <span className="field-error" role="alert">{loadError}</span> : <>
        {blockers.length > 0 && <div className="field-error" role="alert">{blockers.map((message) => <div key={message}>{message}</div>)}</div>}
        <ul className="impact-list" aria-label="将被删除或变更的数据">{impactItems.map((item) => <li key={item.label}><span>{item.label}</span><strong>{item.count}</strong></li>)}</ul>
      </>}
      <label className="confirm-input">
        <span>{inputLabel}：<code>{expected}</code></span>
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") event.preventDefault(); }}
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          disabled={busy}
        />
      </label>
      {error && <span className="field-error" role="alert">{error}</span>}
      <footer>
        <button ref={cancelButton} type="button" className="outline-button" onClick={onCancel} disabled={busy}>取消</button>
        {secondaryAction && <button type="button" className="outline-button" onClick={secondaryAction.onClick} disabled={busy || secondaryAction.busy}>{secondaryAction.busy ? "处理中" : secondaryAction.label}</button>}
        <button type="button" className="danger-button" onClick={() => onConfirm(text)} disabled={!canDelete}>{busy ? "正在删除" : confirmLabel}</button>
      </footer>
    </section>
  </div>;
}
