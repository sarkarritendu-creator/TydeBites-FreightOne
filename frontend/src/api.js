/**
 * Thin API client for FreightOne backend.
 * All screens should go through this so timeout / error handling is consistent.
 */

const API = 'https://tydebites-freightone-4kmn.onrender.com';
export default API;

export async function api(path, opts = {}, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API}${path}`, {
      method: opts.method || 'GET',
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      body: opts.body,
      signal: controller.signal,
    });
    const text = await response.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { detail: text };
    }
    if (!response.ok) {
      throw new Error(data.detail || `Request failed (${response.status})`);
    }
    return data;
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Backend request timed out.');
    if (err instanceof TypeError) throw new Error('Cannot reach FreightOne backend.');
    throw err;
  } finally {
    clearTimeout(timer);
  }
}
