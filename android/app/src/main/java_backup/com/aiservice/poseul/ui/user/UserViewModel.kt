package com.aiservice.poseul.ui.user

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class UserInfo(
    val userId: String,
    val name: String,
    val email: String
)

class UserViewModel : ViewModel() {
    
    private val _userInfo = MutableLiveData<UserInfo?>()
    val userInfo: LiveData<UserInfo?> = _userInfo

    private val _isRetraining = MutableLiveData<Boolean>()
    val isRetraining: LiveData<Boolean> = _isRetraining

    private val _retrainMessage = MutableLiveData<String>()
    val retrainMessage: LiveData<String> = _retrainMessage

    init {
        // 앱 시작 시 메인 스레드 부하를 줄이기 위해 지연 로딩
        viewModelScope.launch(Dispatchers.Main) {
            kotlinx.coroutines.delay(200) // UI 렌더링 후 로드
            loadUserInfo()
        }
    }

    private fun loadUserInfo() {
        // 시뮬레이션용 사용자 정보
        val user = UserInfo(
            userId = "user123",
            name = "홍길동",
            email = "user@example.com"
        )
        _userInfo.value = user
    }

    fun logout() {
        _userInfo.value = null
    }

    fun startRetraining() {
        viewModelScope.launch {
            _isRetraining.value = true
            _retrainMessage.value = "모델 재학습을 시작합니다..."
            
            try {
                // 실제 재학습 로직 시뮬레이션
                simulateRetraining()
            } catch (e: Exception) {
                _retrainMessage.value = "재학습 중 오류가 발생했습니다: ${e.message}"
            } finally {
                _isRetraining.value = false
            }
        }
    }

    private suspend fun simulateRetraining() = withContext(Dispatchers.Default) {
        val steps = listOf(
            "데이터 수집 중...",
            "데이터 전처리 중...",
            "모델 학습 중...",
            "모델 검증 중...",
            "모델 저장 중..."
        )

        steps.forEachIndexed { index, step ->
            _retrainMessage.postValue(step)
            kotlinx.coroutines.delay(2000) // 각 단계마다 2초 대기
        }

        _retrainMessage.postValue("모델 재학습이 완료되었습니다!")
        
        // 3초 후 메시지 숨기기
        kotlinx.coroutines.delay(3000)
        _retrainMessage.postValue("")
    }
}
