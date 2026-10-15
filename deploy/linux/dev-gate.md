# 施工中页面与开发访问授权（DEV GATE）

网站在开发期间可以整体挂上「施工中」页面：访客先看到提示页，输入授权码后才进入正式站点。
页面本体在仓库里（[public/under-construction/index.html](../../public/under-construction/index.html)），
开关在 Nginx。授权码只写在服务器配置里，不进仓库、不进前端构建产物。

## 页面

- 路径：`/under-construction/index.html`（开发时也可直接用它预览）。
- 特性：`noindex,nofollow`；标记与样式全部内联，不引用 `/favicon.svg` 等站点资源——否则未解锁时会被网关重定向成死链。
- 文案：标题「网站正在施工中」，说明「开发完成后此页面会移除。如需访问，请输入授权码。」
- 授权码由 Nginx 校验（`/__unlock`），页面本身不含任何密钥；`?e=1` 时显示错误提示。

## 开启

页面放在站点根之外的目录，避免被自己挡住：

```bash
sudo install -d -m 0755 /opt/uestc-ai/gate
sudo install -m 0644 public/under-construction/index.html /opt/uestc-ai/gate/gate.html
```

在 `/etc/nginx/sites-available/uestc-ai` 中，先于 `server` 块加映射（`<CODE>` 换成实际授权码）：

```nginx
map $cookie_uestcai_dev $uestcai_unlocked {
    default      0;
    "<CODE>"     1;
}
```

再在 `server` 块内加网关。`/__unlock` 里比较、`/gate.html` 与 ACME 校验路径必须始终放行：

```nginx
    set $uestcai_gate 1;
    if ($request_uri ~ "^/[.]well-known/") { set $uestcai_gate 0; }
    if ($request_uri ~ "^/gate[.]html")    { set $uestcai_gate 0; }
    if ($request_uri ~ "^/__unlock")       { set $uestcai_gate 0; }
    if ($uestcai_unlocked = 1)             { set $uestcai_gate 0; }
    if ($uestcai_gate = 1) { return 302 /gate.html; }

    location = /gate.html { root /opt/uestc-ai/gate; }
    location = /__unlock {
        if ($arg_code = "<CODE>") {
            add_header Set-Cookie "uestcai_dev=<CODE>; Path=/; Max-Age=2592000; Secure; HttpOnly; SameSite=Lax";
            return 302 /;
        }
        return 302 /gate.html?e=1;
    }
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

改 Nginx 前先备份配置；`nginx -t` 失败时不要 reload。发布新版本不需要改动这一段，
但发布流程里的 Nginx 覆盖要保留它（见 [README.md](README.md) 的发布记录约定）。

## 关闭

删掉上面两个块和 `/opt/uestc-ai/gate/`，再 `nginx -t && systemctl reload nginx`。
已拿到 `uestcai_dev` Cookie 的浏览器会立刻恢复正常访问；其他访客不再被重定向。

## 验证

- 未带 Cookie：`curl -sI https://uestcai.top/` 返回 `302`、`Location: /gate.html`。
- 错误授权码：`/__unlock?code=wrong` 跳到 `/gate.html?e=1`。
- 正确授权码：`302` 回首页并带 `Set-Cookie: uestcai_dev=…`。
- `/gate.html` 始终返回 `200`；`/.well-known/acme-challenge/` 不受影响。
- 恢复公网访问后再确认首页回到 `200`。
