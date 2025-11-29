import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { HeartRateDataPoint } from '../services/ChartDataService';

interface HeartRateChartProps {
  data: HeartRateDataPoint[];
}

const HeartRateChart: React.FC<HeartRateChartProps> = ({ data }) => {
  // 차트 데이터 포맷팅
  // 마지막 데이터 시간 기준으로 12시간 그래프를 표시하므로 모든 데이터를 사용
  const chartData = data
    .filter((point) => point != null) // null/undefined 제거
    .map((point) => ({
      time: `${point.hour.toString().padStart(2, '0')}:${point.minute.toString().padStart(2, '0')}`,
      hour: point.hour,
      minute: point.minute,
      // 0인 경우 null로 처리하여 선이 끊기지 않도록 함 (데이터가 없는 경우)
      heartRate: point.heartRate && point.heartRate > 0 ? point.heartRate : null,
    }));

  // 커스텀 툴팁
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            padding: '12px',
            border: '2px solid #ff6b6b',
            borderRadius: '12px',
            boxShadow: '0 4px 12px rgba(255, 107, 107, 0.3), 0 2px 6px rgba(0, 0, 0, 0.1)',
          }}
        >
          <p style={{ margin: 0, fontWeight: 'bold', fontSize: '14px', color: '#333' }}>
            {`시간: ${data.time}`}
          </p>
          <p style={{ margin: '8px 0 0 0', color: '#ff6b6b', fontWeight: '600', fontSize: '15px' }}>
            심박수: <strong>{data.heartRate ? `${data.heartRate.toFixed(0)} bpm` : '데이터 없음'}</strong>
          </p>
        </div>
      );
    }
    return null;
  };

  // 최근 12시간 데이터만 표시 (서버에서 이미 12시간 데이터를 반환하지만 안전을 위해)
  const recentData = chartData.slice(-12);

  // 데이터가 없거나 유효한 데이터가 없는 경우
  if (chartData.length === 0 || recentData.length === 0) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>
        데이터가 없습니다. 10분마다 자동으로 데이터가 수집됩니다.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={recentData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E0E0E0" opacity={0.5} />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 11, fill: '#666' }}
          interval={1} // 2시간 단위로 표시 (0, 2, 4, 6, 8, 10, 12번째 인덱스)
          tickMargin={8}
        />
        <YAxis
          domain={['dataMin - 10', 'dataMax + 10']}
          width={32}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend align="center" wrapperStyle={{ paddingLeft: '5%' }} />
        <Line
          type="monotone"
          dataKey="heartRate"
          name="심박수"
          stroke="#ff6b6b"
          strokeWidth={2.5}
          dot={{ 
            r: 4, 
            fill: '#ff6b6b',
            stroke: '#fff',
            strokeWidth: 2
          }}
          activeDot={{ 
            r: 7, 
            fill: '#ff6b6b',
            stroke: '#fff',
            strokeWidth: 2.5,
            style: { filter: 'drop-shadow(0 2px 4px rgba(255, 107, 107, 0.4))' }
          }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default HeartRateChart;

