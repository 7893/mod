export interface Env {
  BROWSER: {
    quickAction: (action: string, options: Record<string, unknown>) => Promise<Response>;
  };
  MOD_BROWSER_TOKEN?: string;
  ALLOWED_HOSTS?: string;
}

const DEFAULT_WIDTH = 1780;
const DEFAULT_HEIGHT = 960;
const MIN_WIDTH = 320;
const MAX_WIDTH = 3840;
const MIN_HEIGHT = 240;
const MAX_HEIGHT = 2160;

function jsonResponse(payload: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function timingSafeEqual(a: string, b: string): Promise<boolean> {
  const encoder = new TextEncoder();
  const [hashA, hashB] = await Promise.all([
    crypto.subtle.digest('SHA-256', encoder.encode(a)),
    crypto.subtle.digest('SHA-256', encoder.encode(b)),
  ]);
  const bytesA = new Uint8Array(hashA);
  const bytesB = new Uint8Array(hashB);
  const subtle = crypto.subtle as SubtleCrypto & {
    timingSafeEqual?: (x: BufferSource, y: BufferSource) => boolean;
  };
  if (typeof subtle.timingSafeEqual === 'function') {
    return subtle.timingSafeEqual(bytesA, bytesB);
  }
  let diff = 0;
  for (let i = 0; i < bytesA.length; i += 1) {
    diff |= bytesA[i]! ^ bytesB[i]!;
  }
  return diff === 0;
}

function parseAllowedHosts(raw?: string): Set<string> {
  return new Set(
    (raw || '')
      .split(',')
      .map((host) => host.trim().toLowerCase())
      .filter(Boolean),
  );
}

function parseClampedDimension(
  raw: string | null,
  fallback: number,
  min: number,
  max: number,
): number | null {
  if (raw === null || raw.trim() === '') {
    return fallback;
  }
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.min(max, Math.max(min, Math.round(parsed)));
}

function validateTargetUrl(rawUrl: string | null, allowedHosts: Set<string>): string | null {
  if (!rawUrl || allowedHosts.size === 0) {
    return null;
  }
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return null;
  }
  if (parsed.protocol !== 'https:') {
    return null;
  }
  if (parsed.username || parsed.password) {
    return null;
  }
  if (!allowedHosts.has(parsed.hostname.toLowerCase())) {
    return null;
  }
  return parsed.toString();
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/health') {
      return jsonResponse({ status: 'ok', worker: 'mod-browser' });
    }

    const expectedToken = env.MOD_BROWSER_TOKEN?.trim() || '';
    const authHeader = request.headers.get('Authorization') || '';
    const bearerMatch = /^Bearer\s+(.+)$/i.exec(authHeader);
    const providedToken = bearerMatch?.[1]?.trim() || '';
    if (!expectedToken || !providedToken || !(await timingSafeEqual(providedToken, expectedToken))) {
      return jsonResponse({ error: 'Unauthorized' }, 401);
    }

    const allowedHosts = parseAllowedHosts(env.ALLOWED_HOSTS);
    const targetUrl = validateTargetUrl(url.searchParams.get('url'), allowedHosts);
    if (!targetUrl) {
      return jsonResponse({ error: 'Invalid or disallowed target url' }, 400);
    }

    const width = parseClampedDimension(url.searchParams.get('width'), DEFAULT_WIDTH, MIN_WIDTH, MAX_WIDTH);
    const height = parseClampedDimension(url.searchParams.get('height'), DEFAULT_HEIGHT, MIN_HEIGHT, MAX_HEIGHT);
    if (width === null || height === null) {
      return jsonResponse({ error: 'Invalid viewport dimensions' }, 400);
    }

    try {
      const resp = await env.BROWSER.quickAction('screenshot', {
        url: targetUrl,
        viewport: { width, height },
        gotoOptions: { waitUntil: 'load' },
        waitForTimeout: 4000,
      });

      return resp;
    } catch {
      return jsonResponse({ error: 'Screenshot capture failed' }, 500);
    }
  },
};
