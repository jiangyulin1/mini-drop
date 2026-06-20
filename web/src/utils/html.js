/**
 * 共享工具函数。
 */

/** XSS 安全 HTML 转义（防止 XSS）。转义 & < > " ' 五个关键字符。 */
export function escapeHtml(str) {
  if (typeof str !== "string") return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
