package io.ionic.starter;

import android.util.Log;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

@CapacitorPlugin(name = "HttpRequest")
public class HttpRequestPlugin extends Plugin {
    
    private static final String TAG = "HttpRequestPlugin";
    
    @PluginMethod
    public void request(PluginCall call) {
        try {
            String urlString = call.getString("url");
            String method = call.getString("method", "GET");
            JSObject headers = call.getObject("headers", new JSObject());
            String body = call.getString("body", null);
            
            if (urlString == null) {
                call.reject("URL is required");
                return;
            }
            
            Log.d(TAG, "HTTP Request: " + method + " " + urlString);
            
            // 네이티브 HTTP 요청 실행
            new Thread(() -> {
                try {
                    URL url = new URL(urlString);
                    HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                    
                    // 요청 메서드 설정
                    connection.setRequestMethod(method);
                    connection.setConnectTimeout(10000);
                    connection.setReadTimeout(10000);
                    
                    // 헤더 설정
                    Iterator<String> keys = headers.keys();
                    while (keys.hasNext()) {
                        String key = keys.next();
                        String value = headers.getString(key);
                        if (value != null) {
                            connection.setRequestProperty(key, value);
                        }
                    }
                    
                    // POST/PUT 요청인 경우 body 전송
                    if ((method.equals("POST") || method.equals("PUT")) && body != null) {
                        connection.setDoOutput(true);
                        connection.setRequestProperty("Content-Type", "application/json");
                        
                        try (OutputStream os = connection.getOutputStream()) {
                            byte[] input = body.getBytes("utf-8");
                            os.write(input, 0, input.length);
                        }
                    }
                    
                    // 응답 읽기
                    int responseCode = connection.getResponseCode();
                    Log.d(TAG, "Response Code: " + responseCode);
                    
                    BufferedReader reader;
                    if (responseCode >= 200 && responseCode < 300) {
                        reader = new BufferedReader(new InputStreamReader(connection.getInputStream()));
                    } else {
                        reader = new BufferedReader(new InputStreamReader(connection.getErrorStream()));
                    }
                    
                    StringBuilder response = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        response.append(line);
                    }
                    reader.close();
                    
                    // 응답 헤더 읽기
                    Map<String, String> responseHeaders = new HashMap<>();
                    for (String key : connection.getHeaderFields().keySet()) {
                        if (key != null) {
                            responseHeaders.put(key, connection.getHeaderField(key));
                        }
                    }
                    
                    JSObject result = new JSObject();
                    result.put("status", responseCode);
                    result.put("data", response.toString());
                    
                    JSObject headersObj = new JSObject();
                    for (Map.Entry<String, String> entry : responseHeaders.entrySet()) {
                        headersObj.put(entry.getKey(), entry.getValue());
                    }
                    result.put("headers", headersObj);
                    
                    Log.d(TAG, "Request successful: " + responseCode);
                    call.resolve(result);
                    
                } catch (Exception e) {
                    Log.e(TAG, "Request failed", e);
                    call.reject("Request failed: " + e.getMessage());
                }
            }).start();
            
        } catch (Exception e) {
            Log.e(TAG, "Plugin error", e);
            call.reject("Plugin error: " + e.getMessage());
        }
    }
}

