async function readRawBody(req) {
  return await new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

function buildTargetUrl(req, backendBase) {
  const routePath = typeof req.query.path === 'string' ? req.query.path : '';
  const normalizedBase = backendBase.endsWith('/') ? backendBase : backendBase + '/';
  const target = new URL(`api/${routePath}`, normalizedBase);

  const incoming = new URL(req.url, 'http://localhost');
  incoming.searchParams.delete('path');
  target.search = incoming.searchParams.toString();
  return target.toString();
}

module.exports = async function handler(req, res) {
  const backendBase = process.env.BACKEND_URL;
  if (!backendBase) {
    res.status(500).json({
      detail: 'Missing BACKEND_URL env var in Vercel project settings.',
      hint: 'Set BACKEND_URL to your FastAPI base URL, e.g. https://your-app.up.railway.app'
    });
    return;
  }

  try {
    const targetUrl = buildTargetUrl(req, backendBase);

    const headers = { ...req.headers };
    delete headers.host;
    delete headers.connection;
    delete headers['content-length'];

    const hasBody = !['GET', 'HEAD'].includes((req.method || 'GET').toUpperCase());
    const body = hasBody ? await readRawBody(req) : undefined;

    const upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body: hasBody ? body : undefined,
      redirect: 'follow'
    });

    res.status(upstream.status);
    upstream.headers.forEach((value, key) => {
      if (key.toLowerCase() === 'transfer-encoding') return;
      res.setHeader(key, value);
    });

    const buffer = Buffer.from(await upstream.arrayBuffer());
    res.send(buffer);
  } catch (error) {
    res.status(502).json({
      detail: 'Proxy request failed',
      error: error instanceof Error ? error.message : String(error)
    });
  }
};
