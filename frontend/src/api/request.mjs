export function resolveApiBase(configuredBase, isDevelopment) {
  const configured = configuredBase?.trim();
  if (configured) {
    try {
      const url = new URL(configured);
      if (!['http:', 'https:'].includes(url.protocol)) return null;
      if (!isDevelopment && url.protocol !== 'https:') return null;
      return configured.replace(/\/+$/, '');
    } catch {
      return null;
    }
  }
  return isDevelopment ? 'http://localhost:8000' : null;
}

export async function requestJson(path, {
  baseUrl,
  requestOptions = {},
  timeoutMs = 10000,
  fetchImpl = globalThis.fetch,
}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(`${baseUrl}${path}`, {
      ...requestOptions,
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`API ${response.status}: ${(await response.text()).slice(0, 180)}`);
    }
    return await response.json();
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(`API request timed out after ${timeoutMs}ms`);
    }
    if (error instanceof TypeError) {
      throw new Error(`Unable to connect to API at ${baseUrl}. Check the API URL and network connection.`);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
