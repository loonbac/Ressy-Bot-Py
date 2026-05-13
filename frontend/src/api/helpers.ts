/**
 * Wrapper around fetch() que agrega headers necesarios.
 * - ngrok-skip-browser-warning: evita la pantalla de advertencia de ngrok
 */
export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set('ngrok-skip-browser-warning', 'true');

  return fetch(input, { ...init, headers });
}
