package com.aiservice.poseul.ui.iot

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import com.aiservice.poseul.service.IotService
import com.aiservice.poseul.service.AirConditionerState
import android.util.Log

data class IotDevice(
    val id: String,
    val name: String,
    val type: String,
    val isOnline: Boolean,
    val currentTemperature: Int? = null,
    val targetTemperature: Int? = null,
    val powerOn: Boolean = false
)

class IotViewModel : ViewModel() {
    
    private val iotService = IotService()
    
    private val _iotDevices = MutableLiveData<List<IotDevice>>()
    val iotDevices: LiveData<List<IotDevice>> = _iotDevices

    private val _isLoading = MutableLiveData<Boolean>()
    val isLoading: LiveData<Boolean> = _isLoading

    private val _errorMessage = MutableLiveData<String>()
    val errorMessage: LiveData<String> = _errorMessage
    
    // 에어컨 상태
    private val _airConditionerState = MutableLiveData<AirConditionerState?>()
    val airConditionerState: LiveData<AirConditionerState?> = _airConditionerState

    // 앱 시작 시 메인 스레드 부하를 줄이기 위해 자동 로딩 제거
    // 필요할 때 refreshDevices()를 호출하여 로드

    private fun loadIotDevices() {
        viewModelScope.launch {
            _isLoading.value = true
            try {
                // 실제 API 호출을 통해 에어컨 정보를 가져옵니다
                loadAirConditionerState()
            } catch (e: Exception) {
                Log.e("IotViewModel", "IOT 기기 정보 로드 실패", e)
                _errorMessage.value = "IOT 기기 정보를 불러오는 중 오류가 발생했습니다: ${e.message}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    private suspend fun loadAirConditionerState() = withContext(Dispatchers.IO) {
        try {
            Log.d("IotViewModel", "에어컨 상태 조회 시작")
            val stateResponse = iotService.getAirConditionerState()
            
            if (stateResponse?.success == true && stateResponse.state != null) {
                val state = stateResponse.state
                
                // 에어컨 상태 저장
                _airConditionerState.postValue(state)
                
                // IotDevice 리스트로 변환
                val devices = listOf(
                    IotDevice(
                        id = stateResponse.deviceId ?: "ac_001",
                        name = "에어컨",
                        type = "air_conditioner",
                        isOnline = state.powerOn == true,
                        currentTemperature = state.currentTemperature?.toInt(),
                        targetTemperature = state.targetTemperature?.toInt(),
                        powerOn = state.powerOn ?: false
                    )
                )
                
                _iotDevices.postValue(devices)
                Log.d("IotViewModel", "에어컨 상태 로드 성공")
            } else {
                Log.e("IotViewModel", "에어컨 상태 조회 실패: ${stateResponse?.error}")
                _errorMessage.postValue("에어컨 상태를 불러올 수 없습니다: ${stateResponse?.error}")
                _iotDevices.postValue(emptyList())
            }
        } catch (e: Exception) {
            Log.e("IotViewModel", "에어컨 상태 조회 중 오류 발생", e)
            _errorMessage.postValue("에어컨 상태 조회 실패: ${e.message}")
            _iotDevices.postValue(emptyList())
        }
    }

    fun refreshDevices() {
        loadIotDevices()
    }
    
    /**
     * 에어컨 온도 설정
     */
    fun setAirConditionerTemperature(targetTemperature: Double, unit: String = "C") {
        viewModelScope.launch {
            try {
                val success = iotService.setAirConditionerTemperature(targetTemperature, unit)
                if (success) {
                    // 상태 다시 조회
                    loadAirConditionerState()
                } else {
                    _errorMessage.value = "온도 설정 실패"
                }
            } catch (e: Exception) {
                Log.e("IotViewModel", "온도 설정 실패", e)
                _errorMessage.value = "온도 설정 실패: ${e.message}"
            }
        }
    }
    
    /**
     * 에어컨 전원 토글
     */
    fun toggleAirConditionerPower() {
        viewModelScope.launch {
            try {
                val currentState = _airConditionerState.value
                val currentPower = currentState?.powerOn ?: false
                val success = iotService.setAirConditionerPower(!currentPower)
                if (success) {
                    // 상태 다시 조회
                    loadAirConditionerState()
                } else {
                    _errorMessage.value = "전원 제어 실패"
                }
            } catch (e: Exception) {
                Log.e("IotViewModel", "전원 제어 실패", e)
                _errorMessage.value = "전원 제어 실패: ${e.message}"
            }
        }
    }
    
    /**
     * 에어컨 작동 모드 설정
     */
    fun setAirConditionerMode(mode: String) {
        viewModelScope.launch {
            try {
                val success = iotService.setAirConditionerMode(mode)
                if (success) {
                    // 상태 다시 조회
                    loadAirConditionerState()
                } else {
                    _errorMessage.value = "작동 모드 설정 실패"
                }
            } catch (e: Exception) {
                Log.e("IotViewModel", "작동 모드 설정 실패", e)
                _errorMessage.value = "작동 모드 설정 실패: ${e.message}"
            }
        }
    }
    
    /**
     * 에어컨 풍량 설정
     */
    fun setAirConditionerWindStrength(strength: String) {
        viewModelScope.launch {
            try {
                val success = iotService.setAirConditionerWindStrength(strength)
                if (success) {
                    // 상태 다시 조회
                    loadAirConditionerState()
                } else {
                    _errorMessage.value = "풍량 설정 실패"
                }
            } catch (e: Exception) {
                Log.e("IotViewModel", "풍량 설정 실패", e)
                _errorMessage.value = "풍량 설정 실패: ${e.message}"
            }
        }
    }
}
