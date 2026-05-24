/**
 * Trigger a browser download via blob URL + <a download>.
 * Uses a transient anchor element to avoid relying on popup permission.
 */
export function triggerDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

/**
 * Fetch a binary response (CSV / JSON file) with the session cookie attached.
 * Throws on non-2xx.
 */
export async function apiBlob(path: string): Promise<Blob> {
  const res = await fetch(path, { credentials: "include" });
  if (!res.ok) {
    throw new Error(`Download failed: ${res.status} ${res.statusText}`);
  }
  return res.blob();
}
