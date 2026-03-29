/**
 * Netlify Function - Dictation Relay
 * iPhone Shortcuts からのシンプルなPOSTを受け取り
 * GitHub API の repository_dispatch に変換して転送する
 */

exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  try {
    // フォームデータまたはJSONを両方受け付ける
    let text, timestamp, source;

    const contentType = event.headers['content-type'] || '';

    // Netlify は base64 エンコードする場合がある
    const rawBody = event.isBase64Encoded
      ? Buffer.from(event.body, 'base64').toString('utf-8')
      : event.body;

    if (contentType.includes('application/x-www-form-urlencoded')) {
      const params = new URLSearchParams(rawBody);
      text = params.get('text') || '';
      timestamp = params.get('timestamp') || '';
      source = params.get('source') || 'iPhone Siri';
    } else {
      const body = JSON.parse(rawBody || '{}');
      text = body.text || '';
      timestamp = body.timestamp || '';
      source = body.source || 'iPhone Siri';
    }

    if (!text) {
      return { statusCode: 400, body: JSON.stringify({ error: 'text is required' }) };
    }

    if (!timestamp) {
      timestamp = new Date().toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' });
    }

    // GitHub API を呼び出す
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
          event_type: 'dictation',
          client_payload: { text, timestamp, source },
        }),
      }
    );

    if (response.status === 204) {
      return {
        statusCode: 200,
        body: JSON.stringify({ status: 'success' }),
      };
    } else {
      const errorText = await response.text();
      return {
        statusCode: 500,
        body: JSON.stringify({ error: errorText }),
      };
    }
  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: err.message }),
    };
  }
};
