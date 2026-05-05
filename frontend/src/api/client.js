import { Capacitor, CapacitorHttp } from "@capacitor/core";

function joinUrl(baseUrl, path) {
  if (!baseUrl) return path;
  return `${baseUrl.replace(/\/+$/, "")}${path}`;
}

function debug(message) {
  window.__agentDebug?.(message);
}

function describeError(error) {
  const parts = [
    `name=${error?.name || typeof error}`,
    `message=${error?.message || String(error)}`,
  ];

  if (error?.cause) {
    parts.push(`cause=${error.cause?.message || String(error.cause)}`);
  }

  if (typeof navigator !== "undefined") {
    parts.push(`online=${navigator.onLine}`);
  }

  if (typeof location !== "undefined") {
    parts.push(`origin=${location.origin}`);
    parts.push(`protocol=${location.protocol}`);
  }

  if (error?.stack) {
    parts.push(`stack=${String(error.stack).split("\n").slice(0, 3).join(" | ")}`);
  }

  return parts.join("; ");
}

const isNative = Capacitor.isNativePlatform();

function handleNativeResponse(result, url) {
  debug(`API response: ${result.status} url=${url}`);

  if (result.status < 200 || result.status >= 300) {
    const payload = result.data;
    const message =
      payload && typeof payload === "object"
        ? payload.message || payload.detail || `Request failed with status ${result.status}`
        : payload || `Request failed with status ${result.status}`;
    throw new Error(message);
  }

  const payload = result.data;
  if (payload && typeof payload === "object" && "code" in payload) {
    if (payload.code !== 0) {
      throw new Error(payload.message || "Request failed");
    }
    return payload.data;
  }

  return payload;
}

async function webParseResponse(response) {
  const text = await response.text();
  let payload = null;

  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }

  if (!response.ok) {
    const message =
      payload && typeof payload === "object"
        ? payload.message || payload.detail || `Request failed with status ${response.status}`
        : payload || `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  if (payload && typeof payload === "object" && "code" in payload) {
    if (payload.code !== 0) {
      throw new Error(payload.message || "Request failed");
    }
    return payload.data;
  }

  return payload;
}

export function createApiClient(getBaseUrl, getToken) {
  function buildHeaders({ json = true, extraHeaders = {} } = {}) {
    const headers = { ...extraHeaders };
    if (json) headers["Content-Type"] = "application/json";
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  async function request(path, options = {}) {
    const url = joinUrl(getBaseUrl(), path);
    const headers = buildHeaders({
      json: options.json !== false,
      extraHeaders: options.headers || {},
    });
    debug(`API request: ${options.method || "GET"} ${url}`);

    // Use CapacitorHttp on native to bypass WebView CORS restrictions
    if (isNative) {
      const nativeOptions = {
        method: options.method || "GET",
        url,
        headers,
        responseType: "json",
        connectTimeout: 10000,
        readTimeout: 30000,
      };
      if (options.body) {
        nativeOptions.data = JSON.parse(options.body);
      }
      const result = await CapacitorHttp.request(nativeOptions);
      return handleNativeResponse(result, url);
    }

    try {
      const response = await fetch(url, { ...options, headers });
      return webParseResponse(response);
    } catch (error) {
      debug(`API error: ${describeError(error)}`);
      if (error instanceof TypeError) {
        throw new Error(`Network request failed. url=${url}; ${describeError(error)}`);
      }
      throw error;
    }
  }

  async function upload(path, formData) {
    const url = joinUrl(getBaseUrl(), path);
    debug(`API upload: POST ${url}`);

    if (isNative) {
      const result = await CapacitorHttp.request({
        method: "POST",
        url,
        headers: {},
        data: formData,
        responseType: "json",
        connectTimeout: 10000,
        readTimeout: 60000,
      });
      return handleNativeResponse(result, url);
    }

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: buildHeaders({ json: false }),
        body: formData,
      });
      return webParseResponse(response);
    } catch (error) {
      debug(`API upload error: ${describeError(error)}`);
      if (error instanceof TypeError) {
        throw new Error(`Network upload failed. url=${url}; ${describeError(error)}`);
      }
      throw error;
    }
  }

  async function stream(path, payload, { onStatus, onChunk, onDone }) {
    const url = joinUrl(getBaseUrl(), path);
    debug(`API stream: POST ${url}`);

    if (isNative) {
      // CapacitorHttp doesn't support ReadableStream, so we fetch the full
      // response and then replay the SSE events.
      const result = await CapacitorHttp.request({
        method: "POST",
        url,
        headers: buildHeaders(),
        data: payload,
        responseType: "text",
        connectTimeout: 10000,
        readTimeout: 300000,
      });

      if (result.status < 200 || result.status >= 300) {
        throw new Error(result.data || `Stream request failed with status ${result.status}`);
      }

      const text = typeof result.data === "string" ? result.data : "";
      const lines = text.split("\n");
      let doneEventReceived = false;

      for (const raw of lines) {
        const line = raw.trim();
        if (!line) continue;

        let event;
        try {
          event = JSON.parse(line);
        } catch {
          continue;
        }

        if (event.type === "status" && onStatus) onStatus(event.message || "");
        if (event.type === "chunk" && onChunk) onChunk(event.content || "");
        if (event.type === "done") {
          doneEventReceived = true;
          if (onDone) await onDone(event.payload?.data || event.payload);
          return;
        }
        if (event.type === "error") throw new Error(event.detail || "Stream request failed");
      }

      if (!doneEventReceived && onDone) {
        await onDone({});
      }
      return;
    }

    // Web path: use fetch + ReadableStream
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify(payload),
      });
    } catch (error) {
      debug(`API stream error: ${describeError(error)}`);
      if (error instanceof TypeError) {
        throw new Error(`Network stream failed. url=${url}; ${describeError(error)}`);
      }
      throw error;
    }

    if (!response.ok || !response.body) {
      const message = await response.text();
      throw new Error(message || `Stream request failed with status ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let doneEventReceived = false;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        while (buffer.includes("\n")) {
          const index = buffer.indexOf("\n");
          const line = buffer.slice(0, index).trim();
          buffer = buffer.slice(index + 1);
          if (!line) continue;

          const event = JSON.parse(line);
          if (event.type === "status" && onStatus) onStatus(event.message || "");
          if (event.type === "chunk" && onChunk) onChunk(event.content || "");
          if (event.type === "done") {
            doneEventReceived = true;
            if (onDone) await onDone(event.payload?.data || event.payload);
            try {
              await reader.cancel();
            } catch {
              // stream may already be closed
            }
            return;
          }
          if (event.type === "error") throw new Error(event.detail || "Stream request failed");
        }
      }
    } finally {
      if (!doneEventReceived && onDone) {
        await onDone({});
      }
    }
  }

  return { request, upload, stream };
}
