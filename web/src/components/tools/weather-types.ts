/**
 * 天气工具类型定义
 *
 * 对应后端 _extract_weather() 提取器的输出结构。
 * 所有字段均为可选，因为工具调用可能因缺少数据而缺失部分字段。
 */

/** 预警信息 */
export interface WeatherAlert {
  title: string
  type: string
  level: string
  text: string
  publish_time: string
  publisher: string
  guidance: string
}

/** 逐日预报 */
export interface WeatherForecastItem {
  day: string
  high: string
  low: string
  condition: string
  sunrise?: string
  sunset?: string
  pop?: string
  humidity?: string
}

/** 逐小时预报（UI 暂未渲染） */
export interface WeatherHourlyItem {
  time: string
  temperature: string
  weather: string
  wind_direction: string
  wind_speed: string
  humidity: string
  pop: string
}

/** 天气工具提取器输出 */
export interface WeatherData {
  // 始终存在
  city: string
  temp: string
  condition: string
  humidity: string
  wind: string

  // 更新时间（report_time → update_time）
  update_time?: string

  // extended=true
  temp_feel?: string
  visibility?: string
  pressure?: string
  alerts?: WeatherAlert[]
  aqi?: number
  aqi_level?: string
  aqi_category?: string
  aqi_primary?: string
  uv?: number
  cloud?: string

  // forecast=true
  forecast?: WeatherForecastItem[]

  // 已提取但 UI 暂未渲染（阶段 F）
  hourly_forecast?: WeatherHourlyItem[]
  minutely_precip?: unknown
  minutely_forecast?: unknown
  life_indices?: Record<string, unknown>
}
