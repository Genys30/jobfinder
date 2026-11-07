// Cloudflare Pages Function: GET /api/realtime -> { activeUsers } from GA4 Realtime.
// Port of api/realtime.js (Vercel edge) for jobfinderdata.com; same-origin, so no
// CORS needed there, but the header stays while the github.io site still calls it.
// Env vars (Pages project -> Settings -> Variables): GA_SERVICE_ACCOUNT, GA_PROPERTY_ID.
// Until those are set, relay the Vercel endpoint (same GA property, same answer)
// instead of failing on JSON.parse(undefined) and showing "0 online".
const VERCEL_REALTIME = 'https://jobfinder-eta-seven.vercel.app/api/realtime';

export async function onRequest({ env }) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  if (!env.GA_SERVICE_ACCOUNT || !env.GA_PROPERTY_ID) {
    try {
      const res = await fetch(VERCEL_REALTIME);
      const { activeUsers } = await res.json();
      return new Response(JSON.stringify({ activeUsers: parseInt(activeUsers) || 0, source: 'vercel-relay' }), { headers });
    } catch (e) {
      return new Response(JSON.stringify({ activeUsers: 0, error: e.message }), { headers });
    }
  }

  try {
    const sa = JSON.parse(env.GA_SERVICE_ACCOUNT);
    const propertyId = env.GA_PROPERTY_ID;

    // Build JWT
    const now = Math.floor(Date.now() / 1000);
    const payload = {
      iss: sa.client_email,
      scope: 'https://www.googleapis.com/auth/analytics.readonly',
      aud: 'https://oauth2.googleapis.com/token',
      iat: now,
      exp: now + 3600,
    };

    const header = { alg: 'RS256', typ: 'JWT' };
    const encode = (obj) =>
      btoa(JSON.stringify(obj)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');

    const unsigned = `${encode(header)}.${encode(payload)}`;

    // Sign with private key
    const keyData = sa.private_key
      .replace(/-----BEGIN PRIVATE KEY-----/, '')
      .replace(/-----END PRIVATE KEY-----/, '')
      .replace(/\n/g, '');

    const binaryKey = Uint8Array.from(atob(keyData), (c) => c.charCodeAt(0));
    const cryptoKey = await crypto.subtle.importKey(
      'pkcs8', binaryKey.buffer,
      { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
      false, ['sign']
    );

    const signature = await crypto.subtle.sign(
      'RSASSA-PKCS1-v1_5',
      cryptoKey,
      new TextEncoder().encode(unsigned)
    );

    const b64sig = btoa(String.fromCharCode(...new Uint8Array(signature)))
      .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');

    const jwt = `${unsigned}.${b64sig}`;

    // Get access token
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=${jwt}`,
    });
    const { access_token } = await tokenRes.json();

    // Call GA4 Realtime API
    const gaRes = await fetch(
      `https://analyticsdata.googleapis.com/v1beta/properties/${propertyId}:runRealtimeReport`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ metrics: [{ name: 'activeUsers' }] }),
      }
    );

    const data = await gaRes.json();
    if (data.error) throw new Error(data.error.message || 'GA error');
    const count = data.rows?.[0]?.metricValues?.[0]?.value ?? '0';

    return new Response(JSON.stringify({ activeUsers: parseInt(count), source: 'ga' }), { headers });
  } catch (e) {
    return new Response(JSON.stringify({ activeUsers: 0, error: e.message }), { headers });
  }
}
