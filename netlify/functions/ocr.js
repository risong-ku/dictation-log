/**
 * Netlify Function - OCR Relay
 * iPhone Shortcuts からの画像データを受け取り
 * GitHub API の repository_dispatch に変換して転送する
 */

exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  try {
    const rawBody = event.isBase64Encoded
      ? Buffer.from(event.body, 'base64').toString('utf-8')
      : event.body;

    const body = JSON.parse(rawBody || '{}');
    const image_base64 = body.image_base64 || '';
    const timestamp = body.timestamp || '';
    const source = body.source || 'iPhone OCR';

    if (!image_base64) {
      return { statusCode: 400, body: JSON.stringify({ error: 'image_base64 is required' }) };
    }

    const githubToken = process.env.GITHUB_PAT;
    const response = await fetch(
      'https://api.github.com/repos/risong-ku/dictation-log/dispatches',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          event_type: 'ocr',
          client_payload: { image_base64, timestamp, source },
        }),
      }
    );

    if (response.status === 204) {
      return { statusCode: 200, body: JSON.stringify({ status: 'success' }) };
    } else {
      const errorText = await response.text();
      return { statusCode: 500, body: JSON.stringify({ error: errorText }) };
    }
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
