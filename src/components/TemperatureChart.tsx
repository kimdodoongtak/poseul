import React, { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { TemperatureDataPoint } from '../services/ChartDataService';

interface TemperatureChartProps {
  data: TemperatureDataPoint[];
}

const TemperatureChart: React.FC<TemperatureChartProps> = ({ data }) => {
  const [viewMode, setViewMode] = useState<'category' | 'temperature'>('category');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [showTargetDetails, setShowTargetDetails] = useState(false);
  // 분류별 색상
  function getCategoryColor(category: string): string {
    switch (category) {
      case '더움':
        return '#ff4444';
      case '추움':
        return '#4444ff';
      case '적정':
        return '#44ff44';
      default:
        return '#888888';
    }
  }

  // 차트 데이터 포맷팅
  const chartData = data.map((point) => ({
    time: `${point.hour}:${point.minute.toString().padStart(2, '0')}`,
    hour: point.hour,
    predicted: point.predictedTemperature,
    current: point.currentTemperature,
    target: point.targetTemperature,
    category: point.temperatureCategory,
    categoryColor: getCategoryColor(point.temperatureCategory),
  }));


  // 현재온도 커스텀 도트
  const CustomCurrentDot = (props: any) => {
    const { cx, cy } = props;
    return (
      <circle
        cx={cx}
        cy={cy}
        r={5}
        fill="#82ca9d"
        stroke="#fff"
        strokeWidth={2}
      />
    );
  };

  // 목표온도 커스텀 도트
  const CustomTargetDot = (props: any) => {
    const { cx, cy } = props;
    return (
      <circle
        cx={cx}
        cy={cy}
        r={5}
        fill="#ffc658"
        stroke="#fff"
        strokeWidth={2}
      />
    );
  };

  // 분류 모드 툴팁 (마우스 오버 시 현재/목표 온도 표시)
  const CategoryTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            padding: '12px',
            border: `2px solid ${data.categoryColor}`,
            borderRadius: '8px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
        >
          <p style={{ margin: 0, fontWeight: 'bold', fontSize: '14px' }}>
            {`시간: ${data.time}`}
          </p>
          <div
            style={{
              marginTop: '8px',
              padding: '6px',
              backgroundColor: `${data.categoryColor}20`,
              borderRadius: '4px',
            }}
          >
            <p
              style={{
                margin: '4px 0',
                color: data.categoryColor,
                fontWeight: 'bold',
                fontSize: '13px',
              }}
            >
              상태: {data.category}
            </p>
          </div>
          <div style={{ marginTop: '8px' }}>
            {data.current !== null && (
              <p style={{ margin: '4px 0', color: '#82ca9d', fontSize: '12px' }}>
                현재 온도: <strong>{data.current?.toFixed(1)}°C</strong>
              </p>
            )}
            {data.target !== null && (
              <p style={{ margin: '4px 0', color: '#ffc658', fontSize: '12px' }}>
                목표 온도: <strong>{data.target?.toFixed(1)}°C</strong>
              </p>
            )}
          </div>
        </div>
      );
    }
    return null;
  };

  // 온도 모드 툴팁
  const TemperatureTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            padding: '12px',
            border: '2px solid #888',
            borderRadius: '8px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
        >
          <p style={{ margin: 0, fontWeight: 'bold', fontSize: '14px' }}>
            {`시간: ${data.time}`}
          </p>
          <div style={{ marginTop: '8px' }}>
            {data.current !== null && (
              <p style={{ margin: '4px 0', color: '#82ca9d', fontSize: '12px' }}>
                현재 온도: <strong>{data.current?.toFixed(1)}°C</strong>
              </p>
            )}
            {data.target !== null && (
              <p style={{ margin: '4px 0', color: '#ffc658', fontSize: '12px' }}>
                목표 온도: <strong>{data.target?.toFixed(1)}°C</strong>
              </p>
            )}
          </div>
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

  // Y축 범위 계산 (모든 온도 데이터를 포함하되 더 가깝게 보이도록)
  const allTemps = [
    ...recentData.map(d => d.predicted).filter((v): v is number => typeof v === 'number' && !isNaN(v) && isFinite(v)),
    ...recentData.filter(d => d.current !== null && typeof d.current === 'number' && !isNaN(d.current) && isFinite(d.current)).map(d => d.current!),
    ...recentData.filter(d => d.target !== null && typeof d.target === 'number' && !isNaN(d.target) && isFinite(d.target)).map(d => d.target!),
  ];
  
  // 유효한 데이터가 있는지 확인하고 기본값 설정
  let minTemp = 20; // 기본 최소값 (실내 온도 범위)
  let maxTemp = 40; // 기본 최대값
  let padding = 2; // 기본 패딩
  
  if (allTemps.length > 0) {
    minTemp = Math.min(...allTemps);
    maxTemp = Math.max(...allTemps);
    const tempRange = maxTemp - minTemp;
    padding = Math.max(tempRange * 0.1, 1); // 10% 패딩 또는 최소 1도
  }

  return (
    <div style={{ position: 'relative' }}>
      {viewMode === 'temperature' && (
        <button
          onClick={() => {
            setViewMode('category');
            setShowTargetDetails(false);
          }}
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            zIndex: 10,
            padding: '8px 16px',
            backgroundColor: '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: 'bold',
            boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
          }}
        >
          ← 분류 보기
        </button>
      )}
      <ResponsiveContainer width="100%" height={350}>
        <LineChart 
          data={recentData} 
          margin={{ top: 30, right: 30, left: 20, bottom: 5 }}
          onClick={() => {
            if (viewMode === 'category') {
              setViewMode('temperature');
            }
          }}
          style={{ cursor: viewMode === 'category' ? 'pointer' : 'default' }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
          />
          <YAxis
            label={{ value: '온도 (°C)', angle: -90, position: 'insideLeft' }}
            domain={[minTemp - padding, maxTemp + padding]}
            tick={false}
            allowDecimals={true}
          />
          <Tooltip 
            content={viewMode === 'category' ? <CategoryTooltip /> : <TemperatureTooltip />} 
          />
          <Legend 
            wrapperStyle={{ paddingTop: '10px' }}
            iconType="line"
          />
          
          {/* 분류 모드: 분류 라인만 표시 */}
          {viewMode === 'category' && (
            <Line
              type="monotone"
              dataKey="predicted"
              name="분류"
              stroke="#888888"
              strokeWidth={3}
              dot={(props: any) => {
                const { cx, cy, payload, index } = props;
                if (!payload || !payload.category) return null;
                const isHovered = hoveredIndex === index;
                return (
                  <g
                    onMouseEnter={() => setHoveredIndex(index)}
                    onMouseLeave={() => setHoveredIndex(null)}
                  >
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isHovered ? 8 : 6}
                      fill={payload.categoryColor}
                      stroke="#fff"
                      strokeWidth={2}
                    />
                    <text
                      x={cx}
                      y={cy - 15}
                      textAnchor="middle"
                      fontSize="11"
                      fill={payload.categoryColor}
                      fontWeight="bold"
                    >
                      {payload.category}
                    </text>
                    {/* 마우스 오버 시 현재/목표 온도 표시 */}
                    {isHovered && (
                      <>
                        {payload.current !== null && (
                          <circle
                            cx={cx}
                            cy={cy}
                            r={12}
                            fill="transparent"
                            stroke="#82ca9d"
                            strokeWidth={2}
                            strokeDasharray="3 3"
                          />
                        )}
                        {payload.target !== null && (
                          <circle
                            cx={cx}
                            cy={cy}
                            r={16}
                            fill="transparent"
                            stroke="#ffc658"
                            strokeWidth={2}
                            strokeDasharray="3 3"
                          />
                        )}
                      </>
                    )}
                  </g>
                );
              }}
              activeDot={{ r: 8 }}
            />
          )}

          {/* 온도 모드: 현재/목표 온도 라인 표시 */}
          {viewMode === 'temperature' && (
            <>
              {chartData.some((d) => d.current !== null) && (
                <Line
                  type="monotone"
                  dataKey="current"
                  name="현재 온도"
                  stroke="#82ca9d"
                  strokeWidth={2.5}
                  dot={<CustomCurrentDot />}
                  activeDot={{ r: 7 }}
                  strokeDasharray="5 5"
                />
              )}
              {chartData.some((d) => d.target !== null) && (
                <Line
                  type="monotone"
                  dataKey="target"
                  name="목표 온도"
                  stroke="#ffc658"
                  strokeWidth={2.5}
                  dot={(props: any) => {
                    const { cx, cy, payload } = props;
                    const isHovered = showTargetDetails;
                    return (
                      <g
                        onMouseEnter={() => setShowTargetDetails(true)}
                        onMouseLeave={() => setShowTargetDetails(false)}
                      >
                        <circle
                          cx={cx}
                          cy={cy}
                          r={isHovered ? 7 : 5}
                          fill="#ffc658"
                          stroke="#fff"
                          strokeWidth={2}
                        />
                        {isHovered && (
                          <text
                            x={cx}
                            y={cy - 20}
                            textAnchor="middle"
                            fontSize="10"
                            fill="#ffc658"
                            fontWeight="bold"
                          >
                            {payload.target?.toFixed(1)}°C
                          </text>
                        )}
                      </g>
                    );
                  }}
                  activeDot={{ r: 7 }}
                  strokeDasharray="3 3"
                />
              )}
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TemperatureChart;

