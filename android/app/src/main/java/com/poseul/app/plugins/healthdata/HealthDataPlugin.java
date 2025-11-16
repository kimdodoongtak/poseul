package com.poseul.app.plugins.healthdata;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "HealthData")
public class HealthDataPlugin extends Plugin {

    @PluginMethod
    public void requestAuthorization(PluginCall call) {
        // Android 구현 - 껍데기만
        JSObject ret = new JSObject();
        ret.put("success", false);
        call.reject("HealthData is not yet implemented on Android. Please use iOS for now.");
    }

    @PluginMethod
    public void getLatestHeartRate(PluginCall call) {
        // Android 구현 - 껍데기만
        call.reject("HealthData is not yet implemented on Android. Please use iOS for now.");
    }

    @PluginMethod
    public void getLatestHeartRateVariability(PluginCall call) {
        // Android 구현 - 껍데기만
        call.reject("HealthData is not yet implemented on Android. Please use iOS for now.");
    }

    @PluginMethod
    public void getLatestOxygenSaturation(PluginCall call) {
        // Android 구현 - 껍데기만
        call.reject("HealthData is not yet implemented on Android. Please use iOS for now.");
    }

    @PluginMethod
    public void startBackgroundMonitoring(PluginCall call) {
        // Android 구현 - 껍데기만
        JSObject ret = new JSObject();
        ret.put("success", false);
        call.reject("HealthData is not yet implemented on Android. Please use iOS for now.");
    }
}

