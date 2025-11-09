package com.aiservice.poseul.ui.iot

import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import com.aiservice.poseul.databinding.FragmentIotBinding
import com.aiservice.poseul.service.AirConditionerState
import com.aiservice.poseul.service.AirQuality

class IotFragment : Fragment() {

    private var _binding: FragmentIotBinding? = null
    private val binding get() = _binding ?: throw IllegalStateException("Binding should only be accessed when view is available")
    
    private val viewModel: IotViewModel by viewModels()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        Log.d("IotFragment", "onCreateView 시작")
        _binding = FragmentIotBinding.inflate(inflater, container, false)
        Log.d("IotFragment", "onCreateView 완료")
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        
        Log.d("IotFragment", "onViewCreated 시작")
        setupUI()
        setupObservers()
        // 에어컨 상태 조회
        viewModel.refreshDevices()
        Log.d("IotFragment", "onViewCreated 완료")
    }
    
    private fun setupObservers() {
        // 에어컨 상태 관찰
        viewModel.airConditionerState.observe(viewLifecycleOwner) { state: AirConditionerState? ->
            state?.let { airConditionerState ->
                updateAirConditionerUI(airConditionerState)
            }
        }
        
        // 에러 메시지 관찰
        viewModel.errorMessage.observe(viewLifecycleOwner) { error: String? ->
            error?.let {
                Log.e("IotFragment", "에러: $it")
                // 필요시 에러 메시지 표시
            }
        }
        
        // 로딩 상태 관찰
        viewModel.isLoading.observe(viewLifecycleOwner) { isLoading: Boolean ->
            // 로딩 상태에 따른 UI 업데이트
            if (isLoading) {
                Log.d("IotFragment", "로딩 중...")
            }
        }
    }

    private fun setupUI() {
        // 카드 표시
        binding.airConditionerCard.visibility = View.VISIBLE
        
        // 새로고침 버튼
        binding.refreshButton.setOnClickListener {
            viewModel.refreshDevices()
        }
        
        // 전원 버튼
        binding.powerButton.setOnClickListener {
            viewModel.toggleAirConditionerPower()
        }
        
        // 온도 조절 버튼
        binding.temperatureUpButton.setOnClickListener {
            val currentTemp = viewModel.airConditionerState.value?.targetTemperature ?: 24.0
            val newTemp = currentTemp + 1.0
            viewModel.setAirConditionerTemperature(newTemp)
        }
        
        binding.temperatureDownButton.setOnClickListener {
            val currentTemp = viewModel.airConditionerState.value?.targetTemperature ?: 24.0
            val newTemp = currentTemp - 1.0
            viewModel.setAirConditionerTemperature(newTemp)
        }
        
        // 작동 모드 버튼
        binding.modeCoolButton.setOnClickListener {
            viewModel.setAirConditionerMode("COOL")
        }
        
        binding.modeDryButton.setOnClickListener {
            viewModel.setAirConditionerMode("AIR_DRY")
        }
        
        binding.modeCleanButton.setOnClickListener {
            viewModel.setAirConditionerMode("AIR_CLEAN")
        }
        
        binding.modeAutoButton.setOnClickListener {
            viewModel.setAirConditionerMode("AUTO")
        }
        
        // 풍량 버튼
        binding.windHighButton.setOnClickListener {
            viewModel.setAirConditionerWindStrength("HIGH")
        }
        
        binding.windMidButton.setOnClickListener {
            viewModel.setAirConditionerWindStrength("MID")
        }
        
        binding.windLowButton.setOnClickListener {
            viewModel.setAirConditionerWindStrength("LOW")
        }
        
        binding.windAutoButton.setOnClickListener {
            viewModel.setAirConditionerWindStrength("AUTO")
        }
    }
    
    private fun updateAirConditionerUI(state: AirConditionerState) {
        // 전원 상태
        val isOnline = state.powerOn == true
        binding.airConditionerStatus.text = if (isOnline) "온라인" else "오프라인"
        binding.airConditionerStatus.setTextColor(
            if (isOnline) 0xFF4CAF50.toInt() else 0xFFF44336.toInt()
        )
        
        // 전원 버튼 텍스트 업데이트
        binding.powerButton.text = if (isOnline) "끄기" else "켜기"
        
        // 온도 정보
        state.currentTemperature?.let { temp: Double ->
            val unit = state.temperatureUnit ?: "C"
            binding.airConditionerCurrentTemp.text = "${temp.toInt()}°$unit"
        }
        
        state.targetTemperature?.let { temp: Double ->
            val unit = state.temperatureUnit ?: "C"
            binding.airConditionerTargetTemp.text = "${temp.toInt()}°$unit"
        }
        
        // 작동 모드 표시 및 버튼 상태 업데이트
        state.jobMode?.let { mode: String ->
            Log.d("IotFragment", "작동 모드: $mode")
            // 현재 모드에 따라 버튼 강조 (선택적으로 구현 가능)
            updateModeButtonState(mode)
        }
        
        // 풍량 표시 및 버튼 상태 업데이트
        state.windStrength?.let { strength: String ->
            Log.d("IotFragment", "풍량: $strength")
            // 현재 풍량에 따라 버튼 강조 (선택적으로 구현 가능)
            updateWindButtonState(strength)
        }
        
        // 공기질 정보 (있다면)
        state.airQuality?.let { airQuality: AirQuality ->
            Log.d("IotFragment", "PM2.5: ${airQuality.pm2}, 습도: ${airQuality.humidity}%")
        }
    }
    
    private fun updateModeButtonState(selectedMode: String) {
        // 모든 모드 버튼 리셋
        val buttons = listOf(
            binding.modeCoolButton,
            binding.modeDryButton,
            binding.modeCleanButton,
            binding.modeAutoButton
        )
        
        buttons.forEach { button ->
            button.isSelected = false
        }
        
        // 선택된 모드 버튼 강조
        when (selectedMode) {
            "COOL" -> binding.modeCoolButton.isSelected = true
            "AIR_DRY" -> binding.modeDryButton.isSelected = true
            "AIR_CLEAN" -> binding.modeCleanButton.isSelected = true
            "AUTO" -> binding.modeAutoButton.isSelected = true
        }
    }
    
    private fun updateWindButtonState(selectedStrength: String) {
        // 모든 풍량 버튼 리셋
        val buttons = listOf(
            binding.windHighButton,
            binding.windMidButton,
            binding.windLowButton,
            binding.windAutoButton
        )
        
        buttons.forEach { button ->
            button.isSelected = false
        }
        
        // 선택된 풍량 버튼 강조
        when (selectedStrength) {
            "HIGH" -> binding.windHighButton.isSelected = true
            "MID" -> binding.windMidButton.isSelected = true
            "LOW" -> binding.windLowButton.isSelected = true
            "AUTO" -> binding.windAutoButton.isSelected = true
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
