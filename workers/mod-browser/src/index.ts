export interface Env {
  BROWSER: any;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const targetUrl = url.searchParams.get('url') || 'https://example.com/';
    const width = parseInt(url.searchParams.get('width') || '1780', 10);
    const height = parseInt(url.searchParams.get('height') || '960', 10);

    if (url.pathname === '/health') {
      return new Response(JSON.stringify({ status: 'ok', worker: 'mod-browser' }), {
        headers: { 'Content-Type': 'application/json' },
      });
    }

    try {
      const resp = await env.BROWSER.quickAction('screenshot', {
        url: targetUrl,
        viewport: { width, height },
        gotoOptions: { waitUntil: 'load' },
        waitForTimeout: 4000,
      });

      return resp;
    } catch (err: any) {
      return new Response(JSON.stringify({ error: err.message || String(err) }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  },
};
