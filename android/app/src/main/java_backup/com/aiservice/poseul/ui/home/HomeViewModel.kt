package com.aiservice.poseul.ui.home

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class HomeViewModel : ViewModel() {
    
    private val _predictedTemperature = MutableLiveData<Float>()
    val predictedTemperature: LiveData<Float> = _predictedTemperature

    private val _heartRateData = MutableLiveData<List<Int>>()
    val heartRateData: LiveData<List<Int>> = _heartRateData

    private val _isLoading = MutableLiveData<Boolean>()
    val isLoading: LiveData<Boolean> = _isLoading

    private val _errorMessage = MutableLiveData<String>()
    val errorMessage: LiveData<String> = _errorMessage

    // 앱 시작 시 메인 스레드 부하를 줄이기 위해 자동 로딩 제거
    // 필요할 때 refreshData()를 호출하여 로드

    private fun loadData() {
        viewModelScope.launch {
            _isLoading.value = true
            try {
                // 실제 구현에서는 API 호출이나 모델 예측을 수행
                simulateDataLoading()
            } catch (e: Exception) {
                _errorMessage.value = "데이터를 불러오는 중 오류가 발생했습니다: ${e.message}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    private suspend fun simulateDataLoading() = withContext(Dispatchers.Default) {
        kotlinx.coroutines.delay(2000) // 2초 대기 (실제 로딩 시뮬레이션)
        
        // 온도 예측 결과 시뮬레이션 (20-30도 사이)
        val temperature = (20 + Math.random() * 10).toFloat()
        _predictedTemperature.postValue(temperature)

        // 심박수 데이터 시뮬레이션 (60-100 BPM)
        val heartRates = (1..24).map { 
            (60 + Math.random() * 40).toInt() 
        }
        _heartRateData.postValue(heartRates)
    }

    fun refreshData() {
        loadData()
    }
}
