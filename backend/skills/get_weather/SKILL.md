---
name: get_weather
description: 获取指定城市的实时及趋势天气信息（包括过去几小时）
---

# get_weather - 天气查询技能

## 描述
获取指定城市的实时天气信息，并能提取过去或未来的天气趋势。

## 使用方法

### 步骤 1: 使用 fetch_url 获取天气数据
使用 `fetch_url` 工具访问 wttr.in 免费天气 API：

```python
fetch_url("https://wttr.in/{城市名}?format=j1")
```

### 步骤 2: 解析并展示
使用 `python_repl` 解析返回的 JSON 数据：
- **实时数据**：从 `current_condition[0]` 提取。
- **历史/趋势数据**：从 `weather[0]['hourly']` 提取。该字段包含每 3 小时（0, 300, 600...）的数据点。通过对比当前时间，可以展示过去 6 小时及未来的天气变化。

### 示例代码 (Python)
```python
import json
data = json.loads(response_text)
# 获取当前观测时间
obs_time = data['current_condition'][0]['localObsDateTime']
# 遍历 hourly 数据，根据 time 字段筛选出最近 6 小时的数据
```

### 备注
- wttr.in 的数据更新频率较高，`hourly` 列表中的过去时间点可视为历史数据。
- 城市名推荐使用拼音或英文。
