import { keyReady, WINDOW_KEY_HEADER } from "./window-key";

const nativeFetch = window.fetch.bind(window);
window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = new URL(input instanceof Request ? input.url : String(input), location.href);
  if (url.origin !== location.origin || !url.pathname.startsWith("/api/")) return nativeFetch(input, init);
  const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
  const write = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
  const key = await keyReady;
  if (!write && !key) return nativeFetch(input, init);
  const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
  if (write) headers.set("x-formcut-local", "1");
  if (key) headers.set(WINDOW_KEY_HEADER, key);
  return nativeFetch(input, { ...init, headers });
};
