#!/usr/bin/env node

/**
 * cap sync 후 HealthData 플러그인이 capacitor.config.json에서 사라지는 문제를 해결하는 스크립트
 */

const fs = require('fs');
const path = require('path');

const configPath = path.join(__dirname, '../ios/App/App/capacitor.config.json');

try {
  // capacitor.config.json 읽기
  const configContent = fs.readFileSync(configPath, 'utf8');
  const config = JSON.parse(configContent);

  // HealthData가 이미 있는지 확인
  const iosHasHealthData = config.ios?.packageClassList?.includes('HealthData');
  const rootHasHealthData = config.packageClassList?.includes('HealthData');

  let modified = false;

  // ios.packageClassList에 HealthData 추가
  if (!iosHasHealthData) {
    if (!config.ios) {
      config.ios = {};
    }
    if (!config.ios.packageClassList) {
      config.ios.packageClassList = [];
    }
    config.ios.packageClassList.push('HealthData');
    modified = true;
  }

  // 루트 packageClassList에 HealthData 추가
  if (!rootHasHealthData) {
    if (!config.packageClassList) {
      config.packageClassList = [];
    }
    config.packageClassList.push('HealthData');
    modified = true;
  }

  // 변경사항이 있으면 파일 저장
  if (modified) {
    fs.writeFileSync(configPath, JSON.stringify(config, null, '\t') + '\n', 'utf8');
    console.log('✅ HealthData 플러그인이 capacitor.config.json에 추가되었습니다.');
  } else {
    console.log('✅ HealthData 플러그인이 이미 capacitor.config.json에 포함되어 있습니다.');
  }
} catch (error) {
  console.error('❌ capacitor.config.json 수정 실패:', error.message);
  process.exit(1);
}

