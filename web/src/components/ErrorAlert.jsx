import { Alert } from "antd";

/**
 * 可复用的错误提示组件。
 *
 * 只在 error 非空时渲染，error 为空时返回 null。
 *
 * @param {{ error: string, style?: object, onClose?: () => void }} props
 */
export default function ErrorAlert({ error, style, onClose }) {
  if (!error) return null;
  return (
    <Alert
      type="error"
      message={error}
      showIcon
      closable={!!onClose}
      onClose={onClose}
      style={style}
    />
  );
}
