const nativeFetch = window.fetch.bind(window);
window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = new URL(input instanceof Request ? input.url : String(input), location.href);
  const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
  if (url.origin === location.origin && url.pathname.startsWith("/api/") && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    headers.set("x-formcut-local", "1");
    return nativeFetch(input, { ...init, headers });
  }
  return nativeFetch(input, init);
};
