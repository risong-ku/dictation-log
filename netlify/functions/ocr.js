/**
 * Netlify Function - OCR
 * iPhone Shortcuts から画像を受け取り、Gemini で文字起こし後
 * テキストのみを GitHub API に送信する
 */

const GEMINI_MODEL = 'gemini-2.5-pro';

async function ocrWithGemini(imageBase64, apiKey) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{
        parts: [
          { text: 'この画像に書かれている手書き文字をそのまま文字起こしてください。文字起こしの結果のみを返してください。余計な説明は不要です。' },
          { inline_data: { mime_type: 'image/jpeg', data: imageBase64 } }
        ]
      }]
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Gemini API error: ${response.status} ${err}`);
  }

  const result = await response.json();
  return result.candidates[0].content.parts[0].text.trim();
}

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

    const geminiApiKey = process.env.GEMINI_API_KEY;
    if (!geminiApiKey) {
      return { statusCode: 500, body: JSON.stringify({ error: 'GEMINI_API_KEY not set' }) };
    }

    // Gemini で OCR
    const text = await ocrWithGemini(image_base64, geminiApiKey);

    // テキストのみ GitHub に送信
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
      return { statusCode: 200, body: JSON.stringify({ status: 'success', text }) };
    } else {
      const errorText = await response.text();
      return { statusCode: 500, body: JSON.stringify({ error: errorText }) };
    }
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
