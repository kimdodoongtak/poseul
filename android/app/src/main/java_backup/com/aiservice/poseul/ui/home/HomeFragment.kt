package com.aiservice.poseul.ui.home

import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.aiservice.poseul.databinding.FragmentHomeBinding
import com.aiservice.poseul.service.ModelService
import com.aiservice.poseul.service.PredictionResult
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.random.Random

class HomeFragment : Fragment() {

    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding ?: throw IllegalStateException("Binding should only be accessed when view is available")
    private val modelService = ModelService()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        Log.d("HomeFragment", "onCreateView 시작")
        // 레이아웃 inflate만 수행 - 다른 초기화는 모두 지연
        try {
            _binding = FragmentHomeBinding.inflate(inflater, container, false)
        } catch (e: Exception) {
            Log.e("HomeFragment", "레이아웃 inflate 오류", e)
            throw e
        }
        Log.d("HomeFragment", "onCreateView 완료")
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        
        Log.d("HomeFragment", "onViewCreated 시작")
        // UI 설정도 post로 지연하여 메인 스레드 여유 확보
        binding.root.post {
            setupUI()
            Log.d("HomeFragment", "onViewCreated 완료 (post)")
        }
        Log.d("HomeFragment", "onViewCreated 완료 (즉시)")
    }
    
    override fun onResume() {
        super.onResume()
        // Fragment가 완전히 화면에 표시된 후에 차트 초기화 (더 긴 지연)
        binding.root.postDelayed({
            if (isAdded && isResumed && isVisible) {
                setupHeartRateChart()
            }
        }, 2000) // 2초 지연으로 메인 스레드 완전히 여유 확보
    }

    private fun setupUI() {
        // 기본 온도 표시 (35.0도로 설정)
        binding.temperatureValue.text = "35.0°C"
        binding.temperatureStatus.text = "쾌적함"
        binding.temperatureStatus.setTextColor(0xFF4CAF50.toInt())
        
        // 모델 테스트 버튼
        binding.testModelButton.setOnClickListener {
            Log.d("ModelTest", "🧪 모델 테스트 시작...")
            performModelPrediction()
        }
    }

    private var heartRateChart: com.github.mikephil.charting.charts.LineChart? = null
    
    private fun setupHeartRateChart() {
        val currentBinding = _binding ?: return
        
        // Fragment 상태 확인
        if (!isAdded || !isResumed || !isVisible) {
            Log.w("HomeFragment", "Fragment가 준비되지 않아 차트 초기화 스킵")
            return
        }
        
        // 심박수 차트 설정을 완전히 비동기로 처리
        lifecycleScope.launch(Dispatchers.Main) {
            try {
                // 추가 대기로 메인 스레드 완전히 여유 확보
                kotlinx.coroutines.delay(500)
                
                // 다시 Fragment 상태 확인
                val binding = _binding ?: return@launch
                if (!isAdded || !isResumed || !isVisible) {
                    Log.w("HomeFragment", "Fragment 상태 변경으로 차트 초기화 취소")
                    return@launch
                }
                
                // 차트를 프로그래밍 방식으로 생성 (레이아웃 inflate 시점이 아님)
                if (heartRateChart == null) {
                    val chartHeight = (200 * resources.displayMetrics.density).toInt() // 200dp를 픽셀로 변환
                    heartRateChart = com.github.mikephil.charting.charts.LineChart(requireContext()).apply {
                        layoutParams = ViewGroup.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            chartHeight
                        )
                    }
                    
                    // 컨테이너에 차트 추가
                    binding.heartRateChartContainer.addView(heartRateChart)
                }
                
                // 차트 기본 설정
                heartRateChart?.apply {
                    description.isEnabled = false
                    setTouchEnabled(true)
                    isDragEnabled = true
                    setScaleEnabled(true)
                    setPinchZoom(true)
                }
                
                // 데이터는 별도로 지연하여 업데이트
                kotlinx.coroutines.delay(500)
                
                // 최종 확인 후 차트 업데이트
                if (isAdded && isResumed && isVisible && heartRateChart != null) {
                    updateHeartRateChart()
                }
            } catch (e: Exception) {
                Log.e("HomeFragment", "차트 초기화 오류", e)
            }
        }
    }

    private suspend fun updateHeartRateChart() = kotlinx.coroutines.withContext(Dispatchers.Default) {
        // 임의의 심박수 데이터 생성 (60-100 bpm)
        val heartRateData = generateHeartRateData()
        
        val entries = heartRateData.mapIndexed { index, value ->
            Entry(index.toFloat(), value.toFloat())
        }
        
        val dataSet = LineDataSet(entries, "심박수").apply {
            color = 0xFFF44336.toInt()
            setCircleColor(0xFFF44336.toInt())
            lineWidth = 2f
            circleRadius = 4f
            setDrawFilled(true)
            fillColor = 0x1AF44336.toInt()
            valueTextSize = 10f
            setDrawValues(false)
        }
        
        val lineData = LineData(dataSet)
        
        // UI 업데이트는 메인 스레드에서 (Fragment가 유효할 때만)
        kotlinx.coroutines.withContext(Dispatchers.Main) {
            heartRateChart?.let { chart ->
                chart.data = lineData
                chart.invalidate()
                Log.d("HeartRateChart", "심박수 차트 업데이트 완료: ${heartRateData.size}개 데이터")
            } ?: Log.w("HeartRateChart", "차트가 null이므로 업데이트 스킵")
        }
    }

    private fun generateHeartRateData(): List<Int> {
        // 20개의 임의 심박수 데이터 생성 (60-100 bpm 범위)
        return (1..20).map { 
            Random.nextInt(60, 101)
        }
    }

    private fun performModelPrediction() {
        val currentBinding = _binding ?: return
        
        Log.i("HomeFragment", "🎯 [MODEL TEST] 모델 테스트 버튼 클릭됨")
        
        // 로딩 상태 표시
        currentBinding.testModelButton.text = "🔄 예측 중..."
        currentBinding.testModelButton.isEnabled = false
        
        // 에러 메시지 숨기기
        currentBinding.errorText.visibility = View.GONE
        
        Log.i("HomeFragment", "🔄 [MODEL TEST] UI 상태 변경: 로딩 중...")
        
        lifecycleScope.launch {
            try {
                Log.i("HomeFragment", "🚀 [MODEL TEST] 예측 프로세스 시작")
                
                // 임의의 사용자 데이터 생성 (실제 앱에서는 센서나 사용자 입력에서 가져옴)
                val heartRate = Random.nextInt(60, 101)
                val hrvSdnn = Random.nextDouble(20.0, 50.0)
                val bmi = Random.nextDouble(18.5, 30.0)
                val meanSa02 = Random.nextDouble(95.0, 100.0)
                val gender = if (Random.nextBoolean()) "male" else "female"
                val age = Random.nextInt(20, 60)
                
                Log.i("HomeFragment", "📊 [MODEL TEST] 생성된 사용자 데이터:")
                Log.i("HomeFragment", "   💓 심박수: $heartRate bpm")
                Log.i("HomeFragment", "   📈 HRV SDNN: ${String.format("%.2f", hrvSdnn)}")
                Log.i("HomeFragment", "   ⚖️ BMI: ${String.format("%.2f", bmi)}")
                Log.i("HomeFragment", "   🫁 산소포화도: ${String.format("%.2f", meanSa02)}%")
                Log.i("HomeFragment", "   👤 성별: $gender")
                Log.i("HomeFragment", "   🎂 나이: ${age}세")
                
                Log.i("HomeFragment", "🌐 [MODEL TEST] ModelService.predictTemperature() 호출")
                
                // 모델 예측 수행
                val result = modelService.predictTemperature(
                    heartRate = heartRate,
                    hrvSdnn = hrvSdnn,
                    bmi = bmi,
                    meanSa02 = meanSa02,
                    userGender = gender,
                    age = age
                )
                
                Log.i("HomeFragment", "📥 [MODEL TEST] ModelService 응답 수신")
                
                when (result) {
                    is PredictionResult.Success -> {
                        Log.i("HomeFragment", "🎉 [MODEL TEST] 예측 성공!")
                        Log.i("HomeFragment", "🌡️ [MODEL TEST] 예측된 온도: ${result.temperature}°C")
                        Log.i("HomeFragment", "🏷️ [MODEL TEST] 온도 카테고리: ${result.category}")
                        
                        // UI 업데이트 (Fragment가 유효할 때만)
                        _binding?.let { binding ->
                            binding.temperatureValue.text = "${String.format("%.1f", result.temperature)}°C"
                            
                            // 앱의 기준(34.6~35.6도)으로 온도값을 직접 판단
                            // 서버 카테고리는 무시하고 온도값만 사용
                            Log.i("HomeFragment", "🌡️ [UI UPDATE] 온도값으로 상태 판단 시작: ${result.temperature}°C")
                            Log.i("HomeFragment", "📊 [UI UPDATE] 서버 카테고리(무시됨): ${result.category}")
                            updateTemperatureStatus(result.temperature)
                            Log.i("HomeFragment", "✅ [UI UPDATE] 온도 상태 업데이트 완료")
                            
                            Log.i("HomeFragment", "🎨 [MODEL TEST] UI 업데이트 완료")
                            
                            // 심박수 차트 업데이트 (비동기)
                            lifecycleScope.launch {
                                updateHeartRateChart()
                                Log.i("HomeFragment", "📊 [MODEL TEST] 심박수 차트 업데이트 완료")
                            }
                            
                            binding.errorText.visibility = View.GONE
                            Log.i("HomeFragment", "✅ [MODEL TEST] 모든 업데이트 완료")
                        } ?: Log.w("HomeFragment", "⚠️ [MODEL TEST] Binding이 null이므로 UI 업데이트 스킵")
                    }
                    is PredictionResult.Error -> {
                        Log.e("HomeFragment", "❌ [MODEL TEST] 예측 실패")
                        Log.e("HomeFragment", "❌ [MODEL TEST] 에러 메시지: ${result.message}")
                        
                        _binding?.let { binding ->
                            binding.errorText.text = "예측 실패: ${result.message}"
                            binding.errorText.visibility = View.VISIBLE
                            Log.e("HomeFragment", "⚠️ [MODEL TEST] 에러 메시지 UI에 표시됨")
                        } ?: Log.w("HomeFragment", "⚠️ [MODEL TEST] Binding이 null이므로 에러 표시 스킵")
                    }
                }
                
            } catch (e: Exception) {
                Log.e("HomeFragment", "💥 [MODEL TEST] 예측 중 예외 발생", e)
                Log.e("HomeFragment", "💥 [MODEL TEST] 예외 타입: ${e.javaClass.simpleName}")
                Log.e("HomeFragment", "💥 [MODEL TEST] 예외 메시지: ${e.message}")
                
                _binding?.let { binding ->
                    binding.errorText.text = "오류 발생: ${e.message ?: "알 수 없는 오류"}"
                    binding.errorText.visibility = View.VISIBLE
                    Log.e("HomeFragment", "⚠️ [MODEL TEST] 예외 에러 메시지 UI에 표시됨")
                } ?: Log.w("HomeFragment", "⚠️ [MODEL TEST] Binding이 null이므로 에러 표시 스킵")
            } finally {
                // 버튼 상태 복원 (Fragment가 유효할 때만)
                _binding?.let { binding ->
                    binding.testModelButton.text = "🧪 모델 테스트 실행"
                    binding.testModelButton.isEnabled = true
                    Log.i("HomeFragment", "🔄 [MODEL TEST] UI 상태 복원: 버튼 활성화")
                } ?: Log.w("HomeFragment", "⚠️ [MODEL TEST] Binding이 null이므로 버튼 상태 복원 스킵")
                
                Log.i("HomeFragment", "🏁 [MODEL TEST] 모델 테스트 프로세스 완료")
            }
        }
    }

    private fun updateTemperatureStatus(temperature: Float) {
        val currentBinding = _binding ?: run {
            Log.w("HomeFragment", "⚠️ Binding이 null이므로 온도 상태 업데이트 스킵")
            return
        }
        
        Log.d("HomeFragment", "🌡️ [TEMP STATUS] 온도값: ${String.format("%.2f", temperature)}°C")
        Log.d("HomeFragment", "📏 [TEMP STATUS] 기준 범위: 34.5°C ~ 35.6°C (양쪽 경계 포함)")
        
        when {
            temperature < 34.5f -> {
                Log.d("HomeFragment", "❄️ [TEMP STATUS] 추움으로 설정 (< 34.5°C)")
                currentBinding.temperatureStatus.text = "추움"
                currentBinding.temperatureStatus.setTextColor(0xFF2196F3.toInt())
            }
            temperature > 35.6f -> {
                Log.d("HomeFragment", "🔥 [TEMP STATUS] 더움으로 설정 (> 35.6°C)")
                currentBinding.temperatureStatus.text = "더움"
                currentBinding.temperatureStatus.setTextColor(0xFFFF5722.toInt())
            }
            else -> {
                // 34.5°C 이상 35.6°C 이하 = 쾌적함 (경계값 포함)
                Log.d("HomeFragment", "✅ [TEMP STATUS] 쾌적함으로 설정 (34.5°C ≤ 온도 ≤ 35.6°C)")
                currentBinding.temperatureStatus.text = "쾌적함"
                currentBinding.temperatureStatus.setTextColor(0xFF4CAF50.toInt())
            }
        }
        
        Log.d("HomeFragment", "🎨 [TEMP STATUS] 최종 상태: '${currentBinding.temperatureStatus.text}'")
    }

    private fun updateTemperatureStatusFromServer(category: String) {
        val currentBinding = _binding ?: return
        
        Log.d("HomeFragment", "🔍 [UI UPDATE] 서버에서 받은 카테고리: '$category'")
        Log.d("HomeFragment", "🔍 [UI UPDATE] 카테고리 길이: ${category.length}")
        Log.d("HomeFragment", "🔍 [UI UPDATE] 카테고리 바이트: ${category.toByteArray().contentToString()}")
        
        when (category.trim()) {
            "추움", "cold", "냉기" -> {
                Log.d("HomeFragment", "❄️ [UI UPDATE] 추움으로 설정")
                currentBinding.temperatureStatus.text = "추움"
                currentBinding.temperatureStatus.setTextColor(0xFF2196F3.toInt())
            }
            "더움", "hot", "더위" -> {
                Log.d("HomeFragment", "🔥 [UI UPDATE] 더움으로 설정")
                currentBinding.temperatureStatus.text = "더움"
                currentBinding.temperatureStatus.setTextColor(0xFFFF5722.toInt())
            }
            "적정", "normal", "쾌적함" -> {
                Log.d("HomeFragment", "✅ [UI UPDATE] 적정으로 설정")
                currentBinding.temperatureStatus.text = "적정"
                currentBinding.temperatureStatus.setTextColor(0xFF4CAF50.toInt())
            }
            else -> {
                Log.w("HomeFragment", "⚠️ [UI UPDATE] 알 수 없는 카테고리: '$category' - 기본값(적정)으로 설정")
                // 알 수 없는 카테고리인 경우 기본값으로 설정
                currentBinding.temperatureStatus.text = "적정"
                currentBinding.temperatureStatus.setTextColor(0xFF4CAF50.toInt())
            }
        }
        
        Log.d("HomeFragment", "🎨 [UI UPDATE] 최종 UI 텍스트: '${currentBinding.temperatureStatus.text}'")
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
