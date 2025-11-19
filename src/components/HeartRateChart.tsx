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
  const chartData = data.map((point) => ({
    time: `${point.hour}:${point.minute.toString().padStart(2, '0')}`,
    hour: point.hour,
    heartRate: point.heartRate,
  }));

  // 커스텀 툴팁
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            padding: '10px',
            border: '1px solid #ccc',
            borderRadius: '5px',
          }}
        >
          <p style={{ margin: 0, fontWeight: 'bold' }}>{`시간: ${data.time}`}</p>
          <p style={{ margin: '5px 0', color: '#ff6b6b' }}>
            심박수: {data.heartRate?.toFixed(0)} bpm
          </p>
        </div>
      );
    }
    return null;
  };

  if (chartData.length === 0) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>
        데이터가 없습니다. 1시간마다 자동으로 데이터가 수집됩니다.
      </div>
    );
  }

  // 최근 12시간 데이터만 표시
  const recentData = chartData.slice(-12);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={recentData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 12 }}
          interval="preserveStartEnd"
        />
        <YAxis
          label={{ value: '심박수 (bpm)', angle: -90, position: 'insideLeft' }}
          domain={['dataMin - 10', 'dataMax + 10']}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Line
          type="monotone"
          dataKey="heartRate"
          name="심박수"
          stroke="#ff6b6b"
          strokeWidth={2}
          dot={{ r: 4 }}
          activeDot={{ r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default HeartRateChart;

