package io.ionic.starter;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private static final String TAG = "MainActivity";
    
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.d(TAG, "onCreate called");
    }

    @Override
    public void onStart() {
        super.onStart();
        Log.d(TAG, "onStart called");
        configureWebView();
    }

    private void configureWebView() {
        try {
            WebView webView = getBridge().getWebView();
            if (webView != null) {
                Log.d(TAG, "WebView found, configuring...");
                
                // WebView를 명시적으로 보이게 설정
                webView.setVisibility(View.VISIBLE);
                webView.bringToFront();
                Log.d(TAG, "WebView visibility set to VISIBLE");
                
                WebSettings webSettings = webView.getSettings();
                
                // JavaScript 활성화 (필수!)
                webSettings.setJavaScriptEnabled(true);
                Log.d(TAG, "JavaScript enabled: " + webSettings.getJavaScriptEnabled());
                
                // DOM Storage 활성화
                webSettings.setDomStorageEnabled(true);
                
                // Mixed Content 허용 (개발 환경용)
                webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
                
                // 기타 WebView 설정
                webSettings.setAllowFileAccess(true);
                webSettings.setAllowContentAccess(true);
                webSettings.setDatabaseEnabled(true);
                webSettings.setGeolocationEnabled(true);
                
                Log.d(TAG, "WebView configuration completed. Visibility: " + (webView.getVisibility() == View.VISIBLE ? "VISIBLE" : "HIDDEN"));
            } else {
                Log.w(TAG, "WebView is null");
            }
        } catch (Exception e) {
            Log.e(TAG, "Error configuring WebView", e);
        }
    }

    @Override
    public void onResume() {
        super.onResume();
        Log.d(TAG, "onResume called");
        configureWebView();
    }
}
