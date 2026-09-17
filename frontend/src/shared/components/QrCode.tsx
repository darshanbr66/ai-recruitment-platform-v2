import QRCode from "qrcode";
import { useEffect, useRef } from "react";

/** Renders a QR code for `value` entirely client-side (the `qrcode`
 * package — no network call to a third-party QR image service, which
 * would otherwise leak the registration link to an external host). */
export function QrCode({ value, size = 176, filename = "qr-code.png" }: {
  value: string;
  size?: number;
  filename?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    void QRCode.toCanvas(canvasRef.current, value, { width: size, margin: 1 });
  }, [value, size]);

  function download() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = filename;
    link.click();
  }

  return (
    <div className="stack-sm" style={{ alignItems: "flex-start" }}>
      <canvas ref={canvasRef} width={size} height={size} style={{ borderRadius: 8 }} />
      <button type="button" className="btn btn-ghost btn-sm" onClick={download}>
        Download QR
      </button>
    </div>
  );
}
