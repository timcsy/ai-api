/**
 * Copy text to the system clipboard.
 *
 * Returns true on success, false otherwise (browser too old, HTTP not
 * localhost, permission denied, etc.). Callers should show a fallback UI
 * with the text shown verbatim so the user can manually select + copy.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (!navigator.clipboard?.writeText) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
