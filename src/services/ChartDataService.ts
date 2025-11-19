/**
 * ChartDataService
 * 하룻밤 차트 데이터를 JSON 파일로 저장하고 관리하는 서비스
 */

export interface TemperatureDataPoint {
  timestamp: string; // ISO 8601 형식 (분 단위)
  hour: number; // 0-23
  minute: number; // 0-59
  predictedTemperature: number;
  temperatureCategory: '더움' | '추움' | '적정';
  currentTemperature: number | null;
  targetTemperature: number | null;
}

export interface HeartRateDataPoint {
  timestamp: string; // ISO 8601 형식
  hour: number; // 0-23
  minute: number; // 0-59
  heartRate: number;
}

export interface NightChartData {
  date: string; // YYYY-MM-DD
  temperatureData: TemperatureDataPoint[];
  heartRateData: HeartRateDataPoint[];
  lastUpdated: string;
}

class ChartDataService {
  private readonly STORAGE_KEY = 'night_chart_data';
  private readonly MAX_DATA_POINTS = 12; // 최대 12시간 (1시간 단위)

  /**
   * 오늘 날짜의 데이터 가져오기
   */
  getTodayData(): NightChartData | null {
    try {
      const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
      const stored = localStorage.getItem(this.STORAGE_KEY);
      
      if (!stored) {
        return this.createEmptyData(today);
      }

      const data: NightChartData = JSON.parse(stored);
      
      // 오늘 날짜가 아니면 새로 생성
      if (data.date !== today) {
        return this.createEmptyData(today);
      }

      return data;
    } catch (error) {
      console.error('차트 데이터 로드 실패:', error);
      const today = new Date().toISOString().split('T')[0];
      return this.createEmptyData(today);
    }
  }

  /**
   * 빈 데이터 구조 생성
   */
  private createEmptyData(date: string): NightChartData {
    return {
      date,
      temperatureData: [],
      heartRateData: [],
      lastUpdated: new Date().toISOString(),
    };
  }

  /**
   * 온도 데이터 포인트 추가 (1시간마다)
   */
  addTemperatureDataPoint(
    predictedTemperature: number,
    temperatureCategory: '더움' | '추움' | '적정',
    currentTemperature: number | null = null,
    targetTemperature: number | null = null
  ): void {
    try {
      const now = new Date();
      const hour = now.getHours();
      const minute = now.getMinutes();
      const timestamp = now.toISOString();

      const dataPoint: TemperatureDataPoint = {
        timestamp,
        hour,
        minute,
        predictedTemperature,
        temperatureCategory,
        currentTemperature,
        targetTemperature,
      };

      const data = this.getTodayData();
      if (!data) return;

      // 같은 시간대의 데이터가 있으면 업데이트, 없으면 추가
      const existingIndex = data.temperatureData.findIndex(
        (d) => d.hour === hour
      );

      if (existingIndex >= 0) {
        data.temperatureData[existingIndex] = dataPoint;
      } else {
        data.temperatureData.push(dataPoint);
      }

      // 시간순으로 정렬
      data.temperatureData.sort((a, b) => a.hour - b.hour);

      // 최대 데이터 포인트 수 제한
      if (data.temperatureData.length > this.MAX_DATA_POINTS) {
        data.temperatureData = data.temperatureData.slice(-this.MAX_DATA_POINTS);
      }

      data.lastUpdated = timestamp;
      this.saveData(data);
    } catch (error) {
      console.error('온도 데이터 저장 실패:', error);
    }
  }

  /**
   * 심박수 데이터 포인트 추가 (1시간마다)
   */
  addHeartRateDataPoint(heartRate: number): void {
    try {
      const now = new Date();
      const hour = now.getHours();
      const minute = now.getMinutes();
      const timestamp = now.toISOString();

      const dataPoint: HeartRateDataPoint = {
        timestamp,
        hour,
        minute,
        heartRate,
      };

      const data = this.getTodayData();
      if (!data) return;

      // 같은 시간대의 데이터가 있으면 업데이트, 없으면 추가
      const existingIndex = data.heartRateData.findIndex(
        (d) => d.hour === hour
      );

      if (existingIndex >= 0) {
        data.heartRateData[existingIndex] = dataPoint;
      } else {
        data.heartRateData.push(dataPoint);
      }

      // 시간순으로 정렬
      data.heartRateData.sort((a, b) => a.hour - b.hour);

      // 최대 데이터 포인트 수 제한
      if (data.heartRateData.length > this.MAX_DATA_POINTS) {
        data.heartRateData = data.heartRateData.slice(-this.MAX_DATA_POINTS);
      }

      data.lastUpdated = timestamp;
      this.saveData(data);
    } catch (error) {
      console.error('심박수 데이터 저장 실패:', error);
    }
  }

  /**
   * 데이터 저장
   */
  private saveData(data: NightChartData): void {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(data));
    } catch (error) {
      console.error('차트 데이터 저장 실패:', error);
    }
  }

  /**
   * 데이터 초기화
   */
  clearData(): void {
    try {
      localStorage.removeItem(this.STORAGE_KEY);
    } catch (error) {
      console.error('차트 데이터 삭제 실패:', error);
    }
  }

  /**
   * JSON 데이터 내보내기 (다운로드용)
   */
  exportData(): string {
    const data = this.getTodayData();
    return JSON.stringify(data, null, 2);
  }
}

export default new ChartDataService();

