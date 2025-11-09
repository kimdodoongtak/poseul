package com.aiservice.poseul.service

import com.aiservice.poseul.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.delay
import java.net.HttpURLConnection
import java.net.URL
import java.io.OutputStreamWriter
import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import android.util.Log

// 데이터 클래스를 IotService 밖으로 이동하여 외부에서 접근 가능하도록 함
data class AirConditionerStateResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("device_id") val deviceId: String?,
    @SerializedName("state") val state: AirConditionerState?,
    @SerializedName("error") val error: String?
)

data class AirConditionerState(
    @SerializedName("power_on") val powerOn: Boolean?,
    @SerializedName("current_temperature") val currentTemperature: Double?,
    @SerializedName("target_temperature") val targetTemperature: Double?,
    @SerializedName("temperature_unit") val temperatureUnit: String?,
    @SerializedName("job_mode") val jobMode: String?,
    @SerializedName("wind_strength") val windStrength: String?,
    @SerializedName("air_quality") val airQuality: AirQuality?,
    @SerializedName("filter_percent") val filterPercent: Int?
)

data class AirQuality(
    @SerializedName("pm1") val pm1: Int?,
    @SerializedName("pm2") val pm2: Int?,
    @SerializedName("pm10") val pm10: Int?,
    @SerializedName("humidity") val humidity: Int?
)

data class AirConditionerControlRequest(
    @SerializedName("action") val action: String,
    @SerializedName("target_temperature") val targetTemperature: Double? = null,
    @SerializedName("unit") val unit: String? = null,
    @SerializedName("mode") val mode: String? = null,
    @SerializedName("strength") val strength: String? = null,
    @SerializedName("power_on") val powerOn: Boolean? = null
)

data class AirConditionerControlResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("action") val action: String?,
    @SerializedName("error") val error: String?
)

class IotService {
    
    companion object {
        // 서버 URL 설정
        // 에뮬레이터: 10.0.2.2 (Android 에뮬레이터에서 호스트 PC를 가리킴)
        // 실제 기기: 컴퓨터의 IP 주소를 사용 (예: 192.168.0.143)
        // IP 주소 변경 방법:
        // 1. build.gradle의 defaultConfig에서 SERVER_URL 수정
        // 2. 또는 여기서 직접 수정 (예: "http://192.168.0.143:5000")
        private const val SERVER_URL = BuildConfig.SERVER_URL
        private const val AIR_CONDITIONER_STATE_ENDPOINT = "/air_conditioner/state"
        private const val AIR_CONDITIONER_CONTROL_ENDPOINT = "/air_conditioner/control"
    }
    
    private val gson = Gson()
    
    /**
     * 에어컨 상태 조회
     */
    suspend fun getAirConditionerState(): AirConditionerStateResponse? = withContext(Dispatchers.IO) {
        var connection: HttpURLConnection? = null
        try {
            val fullUrl = "$SERVER_URL$AIR_CONDITIONER_STATE_ENDPOINT"
            Log.i("IotService", "🔍 [AIR CONDITIONER] 상태 조회 시작")
            Log.d("IotService", "🌐 [AIR CONDITIONER] 요청 URL: $fullUrl")
            
            val url = URL(fullUrl)
            connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 10000
            connection.readTimeout = 10000
            connection.setRequestProperty("Connection", "close")
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "Android-App")
            connection.useCaches = false
            
            Log.d("IotService", "🔗 [AIR CONDITIONER] HTTP 연결 설정 완료")
            Log.d("IotService", "⏱️ [AIR CONDITIONER] 연결 시도 중...")
            
            val responseCode = connection.responseCode
            Log.i("IotService", "📡 [AIR CONDITIONER] HTTP 응답 코드: $responseCode")
            
            val responseText = if (responseCode == HttpURLConnection.HTTP_OK) {
                connection.inputStream?.bufferedReader()?.use { it.readText() } ?: "{}"
            } else {
                connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "{\"success\":false,\"error\":\"HTTP $responseCode\"}"
            }
            
            Log.d("IotService", "📥 [AIR CONDITIONER] 응답 내용: $responseText")
            
            try {
                val response = gson.fromJson(responseText, AirConditionerStateResponse::class.java)
                if (response.success) {
                    Log.i("IotService", "✅ [AIR CONDITIONER] 상태 조회 성공")
                } else {
                    Log.e("IotService", "❌ [AIR CONDITIONER] 상태 조회 실패: ${response.error}")
                }
                return@withContext response
            } catch (e: Exception) {
                Log.e("IotService", "❌ [AIR CONDITIONER] JSON 파싱 실패: ${e.message}")
                return@withContext AirConditionerStateResponse(
                    success = false,
                    deviceId = null,
                    state = null,
                    error = "JSON 파싱 실패: ${e.message}"
                )
            }
            
        } catch (e: Exception) {
            Log.e("IotService", "💥 [AIR CONDITIONER] 상태 조회 오류 발생", e)
            Log.e("IotService", "💥 [AIR CONDITIONER] 오류 메시지: ${e.message}")
            return@withContext AirConditionerStateResponse(
                success = false,
                deviceId = null,
                state = null,
                error = "연결 실패: ${e.message}"
            )
        } finally {
            connection?.disconnect()
        }
    }
    
    /**
     * 에어컨 온도 설정
     */
    suspend fun setAirConditionerTemperature(targetTemperature: Double, unit: String = "C"): Boolean = withContext(Dispatchers.IO) {
        val request = AirConditionerControlRequest(
            action = "set_temperature",
            targetTemperature = targetTemperature,
            unit = unit
        )
        return@withContext sendControlCommand(request)
    }
    
    /**
     * 에어컨 작동 모드 설정
     */
    suspend fun setAirConditionerMode(mode: String): Boolean = withContext(Dispatchers.IO) {
        val request = AirConditionerControlRequest(
            action = "set_mode",
            mode = mode
        )
        return@withContext sendControlCommand(request)
    }
    
    /**
     * 에어컨 풍량 설정
     */
    suspend fun setAirConditionerWindStrength(strength: String): Boolean = withContext(Dispatchers.IO) {
        val request = AirConditionerControlRequest(
            action = "set_wind_strength",
            strength = strength
        )
        return@withContext sendControlCommand(request)
    }
    
    /**
     * 에어컨 전원 설정
     */
    suspend fun setAirConditionerPower(powerOn: Boolean): Boolean = withContext(Dispatchers.IO) {
        val request = AirConditionerControlRequest(
            action = "set_power",
            powerOn = powerOn
        )
        return@withContext sendControlCommand(request)
    }
    
    /**
     * 에어컨 제어 명령 전송
     */
    private suspend fun sendControlCommand(request: AirConditionerControlRequest): Boolean = withContext(Dispatchers.IO) {
        var connection: HttpURLConnection? = null
        var writer: OutputStreamWriter? = null
        try {
            val fullUrl = "$SERVER_URL$AIR_CONDITIONER_CONTROL_ENDPOINT"
            Log.i("IotService", "🚀 [AIR CONDITIONER] 제어 요청 시작: ${request.action}")
            Log.d("IotService", "🌐 [AIR CONDITIONER] 요청 URL: $fullUrl")
            
            val url = URL(fullUrl)
            connection = url.openConnection() as HttpURLConnection
            
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Connection", "close")
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "Android-App")
            connection.doOutput = true
            connection.connectTimeout = 10000
            connection.readTimeout = 10000
            connection.useCaches = false
            
            Log.d("IotService", "🔗 [AIR CONDITIONER] HTTP POST 연결 설정 완료")
            
            // 요청 데이터 전송
            val requestJson = gson.toJson(request)
            Log.d("IotService", "📤 [AIR CONDITIONER] JSON 데이터 전송: $requestJson")
            
            writer = OutputStreamWriter(connection.outputStream, "UTF-8")
            writer.write(requestJson)
            writer.flush()
            
            Log.d("IotService", "✅ [AIR CONDITIONER] 요청 데이터 전송 완료")
            
            // 응답 읽기
            val responseCode = connection.responseCode
            Log.i("IotService", "📡 [AIR CONDITIONER] HTTP 응답 코드: $responseCode")
            
            val responseText = if (responseCode == HttpURLConnection.HTTP_OK) {
                connection.inputStream?.bufferedReader()?.use { it.readText() } ?: "{}"
            } else {
                connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "{\"success\":false,\"error\":\"HTTP $responseCode\"}"
            }
            
            Log.d("IotService", "📥 [AIR CONDITIONER] 응답 내용: $responseText")
            
            try {
                val response = gson.fromJson(responseText, AirConditionerControlResponse::class.java)
                if (response.success) {
                    Log.i("IotService", "✅ [AIR CONDITIONER] 제어 성공: ${response.action}")
                    return@withContext true
                } else {
                    Log.e("IotService", "❌ [AIR CONDITIONER] 제어 실패: ${response.error}")
                    return@withContext false
                }
            } catch (e: Exception) {
                Log.e("IotService", "❌ [AIR CONDITIONER] JSON 파싱 실패: ${e.message}")
                return@withContext false
            }
            
        } catch (e: Exception) {
            Log.e("IotService", "💥 [AIR CONDITIONER] 제어 오류 발생", e)
            Log.e("IotService", "💥 [AIR CONDITIONER] 오류 메시지: ${e.message}")
            return@withContext false
        } finally {
            writer?.close()
            connection?.disconnect()
        }
    }
    
    // 기존 호환성을 위한 함수들
    suspend fun getIotDevices(): List<IotDeviceInfo> = withContext(Dispatchers.IO) {
        // 에어컨 상태 조회
        val stateResponse = getAirConditionerState()
        
        if (stateResponse?.success == true && stateResponse.state != null) {
            val state = stateResponse.state
            listOf(
                IotDeviceInfo(
                    id = stateResponse.deviceId ?: "ac_001",
                    name = "에어컨",
                    type = "air_conditioner",
                    isOnline = state.powerOn == true,
                    currentTemperature = state.currentTemperature?.toInt(),
                    targetTemperature = state.targetTemperature?.toInt(),
                    powerOn = state.powerOn ?: false
                )
            )
        } else {
            // 에러 발생 시 빈 리스트 반환
            emptyList()
        }
    }
    
    suspend fun updateDeviceTemperature(deviceId: String, targetTemperature: Int): Boolean = withContext(Dispatchers.IO) {
        setAirConditionerTemperature(targetTemperature.toDouble())
    }
    
    suspend fun toggleDevicePower(deviceId: String): Boolean = withContext(Dispatchers.IO) {
        // 현재 상태 조회
        val stateResponse = getAirConditionerState()
        val currentPower = stateResponse?.state?.powerOn ?: false
        // 전원 토글
        setAirConditionerPower(!currentPower)
    }
}

data class IotDeviceInfo(
    val id: String,
    val name: String,
    val type: String,
    val isOnline: Boolean,
    val currentTemperature: Int?,
    val targetTemperature: Int?,
    val powerOn: Boolean
)
