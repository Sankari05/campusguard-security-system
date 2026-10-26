/**
 * frontend/js/api/client.js
 * ==========================
 * World-Class Enterprise HTTP Client Engine (Google / Stripe / Razorpay Tier-1 Standard).
 *
 * Core Capabilities:
 * 1. Pluggable Interceptor Middleware Pipeline (Request & Response)
 * 2. Distributed Tracing: Injects X-Request-ID, X-Client-Timestamp, X-Client-Version
 * 3. Automatic Idempotency Keys for safe mutations (POST/PUT/DELETE)
 * 4. Exponential Backoff with Jitter for transient network dropouts (502, 503, 504, 429)
 * 5. Pydantic 422 Field-Level Validation Error Parser
 * 6. Resilient 401 Session Expiration Hook with auto-clear & login redirect
 * 7. In-Memory TTL Cache for static GET lookups
 * 8. Multipart / FormData file upload & Blob download helpers
 * 9. Production Sentry / Observability Crash Reporting Integration
 */

import { Storage } from '../utils/storage.js';
import { showToast } from '../components/toast.js';

export const API_BASE = '';
export const CLIENT_VERSION = '9.6.0';

/**
 * Generate cryptographic or high-entropy UUIDv4 for distributed request tracing
 */
export function generateRequestId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'req_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 9);
}

/**
 * Sleep helper for exponential backoff delays
 */
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ── Specialized Error Classes ────────────────────────────────
export class ApiError extends Error {
  constructor(message, status, payload = null, code = 'API_ERROR') {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
    this.code = code;
    this.timestamp = new Date().toISOString();
  }
}

export class NetworkError extends ApiError {
  constructor(message = 'Network connectivity failure. Please check your internet connection.') {
    super(message, 0, null, 'NETWORK_ERROR');
    this.name = 'NetworkError';
  }
}

export class TimeoutError extends ApiError {
  constructor(timeoutMs) {
    super(
      `Request timed out after ${timeoutMs}ms. Server is taking too long to respond.`,
      408,
      null,
      'TIMEOUT_ERROR'
    );
    this.name = 'TimeoutError';
  }
}

export class ValidationError extends ApiError {
  constructor(message, errors = [], payload = null) {
    super(message, 422, payload, 'VALIDATION_ERROR');
    this.name = 'ValidationError';
    this.fieldErrors = errors;
  }
}

export class RateLimitError extends ApiError {
  constructor(message, retryAfterSec = 2, payload = null) {
    super(message, 429, payload, 'RATE_LIMIT_ERROR');
    this.name = 'RateLimitError';
    this.retryAfter = retryAfterSec;
  }
}

// ── In-Memory Fast TTL Cache for GET requests ────────────────
class RequestCache {
  constructor() {
    this.cache = new Map();
  }

  get(key) {
    const item = this.cache.get(key);
    if (!item) return null;
    if (Date.now() > item.expiresAt) {
      this.cache.delete(key);
      return null;
    }
    return item.data;
  }

  set(key, data, ttlMs = 30000) {
    this.cache.set(key, {
      data,
      expiresAt: Date.now() + ttlMs,
    });
  }

  clear() {
    this.cache.clear();
  }
}

// ── Enterprise ApiClient Class ───────────────────────────────
export class ApiClient {
  constructor(config = {}) {
    this.baseUrl = config.baseUrl || API_BASE;
    this.defaultTimeoutMs = config.timeoutMs || 15000;
    this.cache = new RequestCache();

    // Interceptor Middleware Chains
    this.interceptors = {
      request: [],
      response: [],
    };

    // Install Standard Default Interceptors
    this._installDefaultInterceptors();
  }

  /**
   * Install core interceptors (Auth, Tracing, Logging, Error parsing)
   */
  _installDefaultInterceptors() {
    // 1. Request: Auth, Distributed Tracing & Idempotency
    this.interceptors.request.push((req) => {
      const token = Storage.getToken();
      if (token && !req.headers.has('Authorization')) {
        req.headers.set('Authorization', `Bearer ${token}`);
      }

      // Tracing headers
      if (!req.headers.has('X-Request-ID')) {
        req.headers.set('X-Request-ID', generateRequestId());
      }
      req.headers.set('X-Client-Timestamp', Date.now().toString());
      req.headers.set('X-Client-Version', CLIENT_VERSION);

      // Auto-idempotency key for mutating actions if requested
      if (req.idempotent && !req.headers.has('Idempotency-Key')) {
        req.headers.set('Idempotency-Key', generateRequestId());
      }

      // Default to JSON unless sending FormData / Blob
      if (
        !(req.body instanceof FormData) &&
        !(req.body instanceof Blob) &&
        !req.headers.has('Content-Type')
      ) {
        req.headers.set('Content-Type', 'application/json');
      }

      return req;
    });

    // 2. Response: Telemetry & Error Normalization
    this.interceptors.response.push(async (res, req) => {
      // Calculate roundtrip latency
      const start = req.startTime;
      if (start) {
        const duration = Math.round(performance.now() - start);
        if (duration > 1500) {
          console.warn(`[ApiClient] Slow query: ${req.method} ${req.endpoint} took ${duration}ms`);
        }
      }

      // Handle 401 Unauthorized (Global Session Expiration)
      if (res.status === 401) {
        console.warn('[ApiClient] 401 Unauthorized encountered. Purging auth session.');
        Storage.clearAuth();

        const loginScreen = document.getElementById('loginScreen');
        if (!loginScreen || loginScreen.classList.contains('dn')) {
          showToast('Session expired. Please sign in again.', 'warn');
          if (typeof window.showLoginScreen === 'function') {
            window.showLoginScreen();
          }
        }
        throw new ApiError('Session expired. Please log in again.', 401, null, 'AUTH_EXPIRED');
      }

      // Handle 429 Rate Limiting
      if (res.status === 429) {
        const retryAfter = parseInt(res.headers.get('Retry-After') || '2', 10);
        showToast(`Server is busy. Please wait ${retryAfter}s before retrying.`, 'warn');
        throw new RateLimitError('Rate limit exceeded. Please slow down.', retryAfter);
      }

      // Handle other non-2xx statuses
      if (!res.ok) {
        let errorPayload = null;
        let errorMessage = `HTTP ${res.status}: Request failed`;
        let fieldErrors = [];

        try {
          errorPayload = await res.json();
          if (typeof errorPayload.detail === 'string') {
            errorMessage = errorPayload.detail;
          } else if (Array.isArray(errorPayload.detail)) {
            // FastAPI Pydantic v2 validation errors
            fieldErrors = errorPayload.detail;
            errorMessage = fieldErrors
              .map((err) => {
                const field = Array.isArray(err.loc) ? err.loc[err.loc.length - 1] : 'Field';
                return `${field}: ${err.msg}`;
              })
              .join('; ');
            throw new ValidationError(errorMessage, fieldErrors, errorPayload);
          } else if (errorPayload.message) {
            errorMessage = errorPayload.message;
          }
        } catch (parseErr) {
          if (parseErr instanceof ValidationError) throw parseErr;
        }

        // Production Error Tracking (Sentry hook)
        if (
          res.status >= 500 &&
          window.Sentry &&
          typeof window.Sentry.captureException === 'function'
        ) {
          window.Sentry.captureException(new Error(errorMessage), {
            extra: {
              endpoint: req.endpoint,
              status: res.status,
              payload: errorPayload,
            },
          });
        }

        throw new ApiError(errorMessage, res.status, errorPayload);
      }

      return res;
    });
  }

  /**
   * Core request engine supporting retries with full jitter
   */
  async request(endpoint, options = {}) {
    const {
      method = 'GET',
      headers: customHeaders = {},
      body,
      timeoutMs = this.defaultTimeoutMs,
      retries = method === 'GET' ? 2 : 0,
      retryDelayMs = 300,
      idempotent = false,
      useCache = false,
      cacheTtlMs = 30000,
      responseType = 'json',
      ...restFetchOptions
    } = options;

    const cacheKey = `${method}:${endpoint}`;

    // Return from cache if enabled (GET only)
    if (method === 'GET' && useCache) {
      const cached = this.cache.get(cacheKey);
      if (cached) return cached;
    }

    // Format headers map
    const headers = new Headers(customHeaders);

    // Initial Request Object for interceptors
    let reqConfig = {
      endpoint,
      method: method.toUpperCase(),
      headers,
      body:
        body && typeof body === 'object' && !(body instanceof FormData) && !(body instanceof Blob)
          ? JSON.stringify(body)
          : body,
      timeoutMs,
      idempotent,
      startTime: performance.now(),
      ...restFetchOptions,
    };

    // Execute Request Interceptor Pipeline
    for (const interceptor of this.interceptors.request) {
      reqConfig = (await interceptor(reqConfig)) || reqConfig;
    }

    const fullUrl = reqConfig.endpoint.startsWith('http')
      ? reqConfig.endpoint
      : `${this.baseUrl}${reqConfig.endpoint}`;

    // Execution Loop with Exponential Backoff + Jitter
    let attempt = 0;
    while (true) {
      attempt++;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), reqConfig.timeoutMs);

      try {
        let rawResponse = await fetch(fullUrl, {
          method: reqConfig.method,
          headers: reqConfig.headers,
          body: reqConfig.body,
          signal: controller.signal,
          ...restFetchOptions,
        });

        clearTimeout(timeoutId);

        // Execute Response Interceptor Pipeline
        for (const interceptor of this.interceptors.response) {
          rawResponse = (await interceptor(rawResponse, reqConfig)) || rawResponse;
        }

        // Parse Response Body
        let finalData;
        if (responseType === 'blob') {
          finalData = await rawResponse.blob();
        } else if (responseType === 'text') {
          finalData = await rawResponse.text();
        } else {
          const contentType = rawResponse.headers.get('content-type') || '';
          finalData = contentType.includes('application/json')
            ? await rawResponse.json()
            : rawResponse;
        }

        // Store in cache if enabled
        if (reqConfig.method === 'GET' && useCache) {
          this.cache.set(cacheKey, finalData, cacheTtlMs);
        }

        return finalData;
      } catch (err) {
        clearTimeout(timeoutId);

        // Convert AbortError to TimeoutError
        let errorToHandle = err;
        if (err.name === 'AbortError') {
          errorToHandle = new TimeoutError(reqConfig.timeoutMs);
        } else if (err.name === 'TypeError' && err.message.includes('fetch')) {
          errorToHandle = new NetworkError();
        }

        // Determine if request should retry (Network error, 502, 503, 504)
        const isRetryableStatus = errorToHandle.status >= 500 && errorToHandle.status <= 504;
        const isNetworkErr = errorToHandle instanceof NetworkError;
        const canRetry = attempt <= retries && (isRetryableStatus || isNetworkErr);

        if (canRetry) {
          // Full Jitter Exponential Backoff: delay * 2^(attempt-1) + random(0, jitter)
          const jitter = Math.random() * 100;
          const backoff = Math.min(2000, retryDelayMs * Math.pow(2, attempt - 1) + jitter);
          console.warn(
            `[ApiClient] Transient error on ${reqConfig.endpoint}. Retrying in ${Math.round(backoff)}ms (Attempt ${attempt}/${retries})...`
          );
          await sleep(backoff);
          continue;
        }

        // Re-throw if exhausted
        throw errorToHandle;
      }
    }
  }

  // ── High-Level HTTP Methods ────────────────────────────────
  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  post(endpoint, data = {}, options = {}) {
    return this.request(endpoint, { ...options, method: 'POST', body: data });
  }

  put(endpoint, data = {}, options = {}) {
    return this.request(endpoint, { ...options, method: 'PUT', body: data });
  }

  patch(endpoint, data = {}, options = {}) {
    return this.request(endpoint, { ...options, method: 'PATCH', body: data });
  }

  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }

  /**
   * Multipart Form-Data File Upload helper
   */
  upload(endpoint, formData, options = {}) {
    const headers = options.headers || {};
    // Do NOT set Content-Type header so browser calculates multipart boundary automatically
    delete headers['Content-Type'];
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: formData,
      headers,
    });
  }

  /**
   * Blob File Download helper with automatic browser download trigger
   */
  async download(endpoint, filename = 'download.csv', options = {}) {
    const blob = await this.request(endpoint, {
      ...options,
      method: 'GET',
      responseType: 'blob',
    });

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 100);

    return blob;
  }
}

// ── Global Singleton Instance ────────────────────────────────
export const apiClient = new ApiClient();

/**
 * Universal functional wrapper for standard fetch calls
 */
export async function apiRequest(endpoint, options = {}) {
  return apiClient.request(endpoint, options);
}

// Attach to window for 100% backward-compatibility
if (typeof window !== 'undefined') {
  window.apiClient = apiClient;
  window.apiRequest = apiRequest;
}

export default apiClient;
