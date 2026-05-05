function joinUrl(baseUrl, path) {
  if (!baseUrl) return path;
  return `${baseUrl.replace(/\/+$/, "")}${path}`;
}

async function parseResponse(response) {
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
        ? payload.message || payload.detail || `请求失败，状态码 ${response.status}`
        : payload || `请求失败，状态码 ${response.status}`;
    throw new Error(message);
  }

  if (payload && typeof payload === "object" && "code" in payload) {
    if (payload.code !== 0) {
      throw new Error(payload.message || "请求失败");
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
    try {
      const response = await fetch(url, {
        ...options,
        headers: buildHeaders({
          json: options.json !== false,
          extraHeaders: options.headers || {},
        }),
      });
      return parseResponse(response);
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error(`网络连接失败，请确认 FastAPI 服务已启动并且接口地址正确。当前请求：${url}`);
      }
      throw error;
    }
  }

  async function upload(path, formData) {
    const url = joinUrl(getBaseUrl(), path);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: buildHeaders({ json: false }),
        body: formData,
      });
      return parseResponse(response);
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error(`网络连接失败，请确认 FastAPI 服务已启动并且接口地址正确。当前请求：${url}`);
      }
      throw error;
    }
  }

  async function stream(path, payload, { onStatus, onChunk, onDone }) {
    const url = joinUrl(getBaseUrl(), path);
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify(payload),
      });
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error(`网络连接失败，请确认 FastAPI 服务已启动并且接口地址正确。当前请求：${url}`);
      }
      throw error;
    }

    if (!response.ok || !response.body) {
      const message = await response.text();
      throw new Error(message || `流式请求失败，状态码 ${response.status}`);
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
              // The stream may already be closed after the final event.
            }
            return;
          }
          if (event.type === "error") throw new Error(event.detail || "流式请求失败");
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
