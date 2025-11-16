import { HttpRequestPlugin } from './definitions';

export class HttpRequestWeb implements HttpRequestPlugin {
  async request(options: {
    url: string;
    method: 'GET' | 'POST' | 'PUT' | 'DELETE';
    headers?: { [key: string]: string };
    body?: string;
  }): Promise<{
    status: number;
    data: string;
    headers?: { [key: string]: string };
  }> {
    // 웹에서는 fetch 사용
    const response = await fetch(options.url, {
      method: options.method,
      headers: options.headers || {},
      body: options.body,
    });

    const data = await response.text();
    const headers: { [key: string]: string } = {};
    response.headers.forEach((value, key) => {
      headers[key] = value;
    });

    return {
      status: response.status,
      data,
      headers,
    };
  }
}

