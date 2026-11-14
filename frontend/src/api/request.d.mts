export interface RequestJsonOptions {
  baseUrl: string;
  requestOptions?: RequestInit;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

export declare function resolveApiBase(configuredBase: string | undefined, isDevelopment: boolean): string | null;
export declare function requestJson<T>(path: string, options: RequestJsonOptions): Promise<T>;
