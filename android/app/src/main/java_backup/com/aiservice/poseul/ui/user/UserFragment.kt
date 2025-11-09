package com.aiservice.poseul.ui.user

import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import com.aiservice.poseul.databinding.FragmentUserBinding

class UserFragment : Fragment() {

    private var _binding: FragmentUserBinding? = null
    private val binding get() = _binding ?: throw IllegalStateException("Binding should only be accessed when view is available")

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        Log.d("UserFragment", "onCreateView 시작")
        _binding = FragmentUserBinding.inflate(inflater, container, false)
        Log.d("UserFragment", "onCreateView 완료")
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        
        Log.d("UserFragment", "onViewCreated 시작")
        setupUI()
        Log.d("UserFragment", "onViewCreated 완료")
    }

    private fun setupUI() {
        // 기본 사용자 정보 표시
        binding.userIdText.text = "user123"
        binding.userNameText.text = "홍길동"
        binding.userEmailText.text = "user@example.com"
        
        // 버튼 설정
        binding.loginButton.setOnClickListener {
            Log.d("UserFragment", "로그인 버튼 클릭")
            binding.retrainStatus.text = "로그인 기능은 추후 구현됩니다"
            binding.retrainStatus.visibility = View.VISIBLE
        }
        
        binding.retrainButton.setOnClickListener {
            Log.d("UserFragment", "재학습 버튼 클릭")
            binding.retrainStatus.text = "모델 재학습 기능은 추후 구현됩니다"
            binding.retrainStatus.visibility = View.VISIBLE
        }
        
        // 상태 메시지 초기화
        binding.retrainStatus.visibility = View.GONE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
