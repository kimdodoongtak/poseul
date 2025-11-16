export interface HttpRequestPlugin {
  request(options: {
    url: string;
    method: 'GET' | 'POST' | 'PUT' | 'DELETE';
    headers?: { [key: string]: string };
    body?: string;
  }): Promise<{
    status: number;
    data: string;
    headers?: { [key: string]: string };
  }>;
}

