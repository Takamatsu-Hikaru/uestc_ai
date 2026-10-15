import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL("../" + path, import.meta.url), "utf8");

test("the admin console exposes a mail settings tab", async () => {
  const tabs = await read("app/components/AdminTabs.tsx");
  assert.match(tabs, /href: "\/admin\/mail", label: "邮件服务", icon: Mail/);
  assert.match(tabs, /import \{[^}]*\bMail\b[^}]*\} from "lucide-react"/);
});

test("the mail page drives the admin API and keeps secrets masked", async () => {
  const page = await read("app/admin/mail/page.tsx");
  assert.match(page, /useApiResource<MailSettings>\(allowed \? "\/manage\/mail" : null\)/);
  assert.match(page, /api<MailSettings>\("\/manage\/mail", \{ method: "PUT"/);
  assert.match(page, /api<MailTestResult>\("\/manage\/mail\/test"/);
  assert.match(page, /role === "admin"/);
  // Both secrets are password inputs and never cached in the browser.
  assert.equal((page.match(/type="password"/g) ?? []).length, 2);
  assert.doesNotMatch(page, /localStorage|sessionStorage/);
  // Testing sends the draft so operators can verify before saving.
  assert.match(page, /jsonBody\(\{ recipient, draft: draft\(\) \}\)/);
  assert.match(page, /resend_secret: resendSecret/);
  assert.match(page, /smtp_secret: smtpSecret/);
});

test("mail types and error translations cover the new endpoints", async () => {
  const domain = await read("app/lib/domain.ts");
  assert.match(domain, /export type MailSettings = \{/);
  assert.match(domain, /provider: "resend" \| "smtp"/);
  assert.match(domain, /export type MailTestResult = \{/);
  const api = await read("app/lib/api.ts");
  for (const key of ["email provider is not supported", "invalid smtp host", "invalid smtp port",
    "invalid smtp security", "invalid sender address", "email settings cannot be decrypted",
    "mail encryption key is not configured"]) {
    assert.match(api, new RegExp(`"${key}":`), key);
  }
});

test("the mail route is admin-only and never returns secrets", async () => {
  const route = await read("backend/platform_api/routes/mail.py");
  assert.equal((route.match(/@require_user\("admin"\)/g) ?? []).length, 3);
  assert.match(route, /jsonify\(describe_settings\(\)\)/);
  const models = await read("backend/platform_api/mail_models.py");
  assert.match(models, /"has_smtp_secret": bool\(self\.smtp_secret\)/);
  assert.doesNotMatch(models, /"smtp_secret": self\.smtp_secret/);
});
